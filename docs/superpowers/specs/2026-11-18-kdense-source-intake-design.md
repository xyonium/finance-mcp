# K-Dense 缺口源接入设计 — SEC EDGAR / World Bank 透传 / US Treasury

> 2026-11-18 ｜ 输入：`docs/handoff-2026-11-18-kdense-gaps.md` ｜ 裁决记录：`docs/memory/kdense-source-intake.md`

## 一句话

只新增 **1 个** unified 工具（`get_sec_filing`，EDGAR filings + XBRL facts，`kind` 容器）；World Bank 任意指标与 US Treasury 收益率曲线/债务全部并入 **`get_economic_data`** 的第三种词表。统一工具面 22 → 23。

## 为什么是这三个

| 源 | 现状 | 新增能力 | 价值 |
|---|---|---|---|
| SEC EDGAR | 未覆盖（`providers/macro.py` 里是 tombstone；README 的 "SEC EDGAR via Kimi" 已过期） | 原始 filing 索引 + as-reported XBRL（带 `accn`/`filed`/`form` 溯源） | 高：厂商归一化报表之外的"原始披露" |
| World Bank 任意指标 | 只有 `WLD` × 3 个 code | 任意 indicator × country，年频 | 中高：边际成本低，CN/EG/IN 也能用 |
| US Treasury | 只有 10Y（FRED/AV） | 1Mo–30Y 全曲线 + 债务余额 | 中高：2s10s/倒挂此前答不了 |
| ECB EXR | 未覆盖 | 官方欧元参考价 | 低（现有 FX 已覆盖）→ 不做 |
| BEA / BLS / Census / Data Commons | 部分经 FRED 派生 | 区域/行业细分、JOLTS 等 | 需免费 key，价值未验证 → 暂缓 |

## 方案对比

- **A. 4 个新工具**（EDGAR 2 + WB 1 + Treasury 1）：语义最清晰，但工具面 22 → 26，LLM 选择成本上升。
- **B. 全并入现有工具**（EDGAR 塞进 `get_symbol_intel`，WB/Treasury 塞进 `get_economic_data`）：工具面不变，但 `get_symbol_intel` 的 symbol 解析/市场门控与 CIK 语义不吻合。
- **C（选定）. 1 个新工具 + 2 处合并**：EDGAR 独立成 `get_sec_filing`（它有自己的 ID 体系：ticker/CIK），WB/Treasury 并入 `get_economic_data`（都是宏观时间序列）。**用户 2026-11-18 补充裁决：能合并的尽量合并，少新建工具。**

## 设计

### 1. `get_sec_filing(symbol_or_cik, kind="filings"|"facts", form_type=None, tags=None, limit=20, source="auto")`

- `kind=filings` → `EdgarProvider.submissions()`：读 `filings.recent`（最近 ~1000 条），字段 form / filing_date / report_date / accession_number / primary_document / description / items / is_xbrl。`form_type` 逗号分隔，裸 form 同时匹配修订版（`10-K` ⊃ `10-K/A`）。
- `kind=facts` → `EdgarProvider.facts()`：`tags` 白名单（≤8，默认 `Revenues,NetIncomeLoss,EarningsPerShareDiluted`），**逐个 `companyconcept`**（2–50 KB/tag，随概念点数增长），不取 `companyfacts`（AAPL 3.86 MB）；未上报的 tag 进 `missing_tags`，不是错误。
- CIK 解析：`CIK0000320193` / `320193` / 10 位零填充直接过；ticker 走 `company_tickers.json`（~800 KB，进程内缓存 24h）。
- UA：`SEC_EDGAR_USER_AGENT`，默认 `unified-finance-mcp`；**不复用 `http.UA`**（含 github.com → 403）。403 映射为 `AuthError` 并附配置指引。
- markets = `{"US"}`；chain `["edgar"]`。

### 2. `get_economic_data` 扩容（无新工具）

```
get_economic_data(indicator, source="auto", country="WLD", start=1980, end=2026, period=None)
```

三种词表，靠形状区分，互不干扰：

1. canonical 8（无点号，且在 `ECONOMIC_INDICATORS` 里）→ 原 chain `["macro","alphavantage"]`。
2. World Bank code（**含点号**，如 `NY.GDP.MKTP.CD`）→ `macro.world_bank_series(code, country, start, end)`；chain `["macro"]`。
3. Treasury 伪指标 `TREASURY_YIELD_CURVE` / `TREASURY_DEBT` → `treasury.yield_curve(period)` / `treasury.fiscal("debt_to_penny")`；chain `["treasury"]`。

`source` 按词表校验（WB 只接受 auto|macro，Treasury 只接受 auto|treasury），错配直接 `tool_error`，不产生 AttributeError envelope。

### 3. `providers/treasury.py`

- 曲线：`{TREASURY_YIELD_CSV_URL}/{YYYYMM}?type=daily_treasury_yield_curve&_format=csv` → `csv.DictReader`，tenor 列名归一（`1 Mo`→`1M`、`1.5 Month`→`1.5M`、`10 Yr`→`10Y`），`Date` `%m/%d/%Y`→ISO，空单元格 → `None`；空 body（未来月份）→ `NotFound`。
- Fiscal Data：`/v2/accounting/od/{debt_to_penny|avg_interest_rates}`，`page[size]`/`sort=-record_date`/`filter=record_date:gte:…`，`meta.total-count` → `total`，行原样透传。
- 不做：`monthly_treasury_statement`（404）、日度曲线以外的期限结构推导。

### 4. 一致性同步

`providers/__init__.py`、`tools/__init__.ALL_MODULES`（19）、`tools/diagnostics.py`（`UNIFIED_MODULES` + `MODULE_TOOLS`，**顺手补上此前漏掉的 fred，修掉 20 vs 22 的 drift**）、`server.INSTRUCTIONS`、README、`tests/test_invariants.py`（23）、`tests/test_diagnostics.py`（23 / 19 / grouped 30）、`docs/CREDENTIALS.md`。

## 非目标

- 不做 13F 持仓解析、不做 EDGAR 全文检索（`efts.sec.gov` 非稳定契约）、不做 `companyfacts` 整包。
- 不做 ECB/OECD/Eurostat/SDMX/JSON-stat。
- 不引入 key 的注册引导弹窗类机制：免 key 源就是零配置；需 key 源的引导集中在 `docs/CREDENTIALS.md` 与 `AuthError.hint`。

## 验收

- `pytest -q -m "not integration"` 全绿（新增 58 条），`ruff check .` 全绿。
- live smoke：AAPL filings/facts、CHN GDP、2026-11 曲线、debt_to_penny 各返回真实数据。
- `get_service_status().tools.unified == 23`，与 `test_invariants` 一致。
