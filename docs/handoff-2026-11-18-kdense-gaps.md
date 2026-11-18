# 交接：K-Dense 缺口源接入 finance-mcp

> 2026-11-18 ｜ 提出方：scientific-data-mcp ｜ 目标仓库：`eli@dockerno1:~/finance-mcp`（审计时 HEAD `36d4230`）
> 背景：scientific-data-mcp 把 K-Dense `database-lookup`（v1.8，80 库）做成快照 + 季度扫描。按域归属，经济/金融/监管/社科 14 个源应由 finance-mcp 或 paper-search 覆盖。本文件只包含 **finance-mcp 侧确认值得做的缺口**；paper-search 侧结论是暂不新增（见文末）。

## 一句话结论

**只新增 1 个真正缺口：SEC EDGAR（P1）。** 另有两个低成本增量（World Bank 任意指标透传、US Treasury Fiscal Data）和一个可选（ECB EXR）。Fed/BEA/BLS 已由 FRED 派生序列部分覆盖，Eurostat/WHO/Census/Data Commons 建议暂缓。

---

## 现状证据（只读审计，2026-11-18）

| 源 | 状态 | 证据 |
|---|---|---|
| FRED | 已覆盖 | `providers/fred.py:48`、`tools/fred.py:13/24/43`、`providers/macro.py:52-62` |
| Federal Reserve | 部分覆盖（利率经 FRED/FedWatch） | `providers/macro.py:58-59`、`providers/alphavantage.py:33-34`、`tools/futu_containers.py:108-110` |
| Alpha Vantage | 已覆盖 | `providers/alphavantage.py:129/275` |
| World Bank | 部分覆盖（仅 WLD + 3 个 code） | `providers/macro.py:67-69/133` |
| US Treasury | 部分覆盖（仅 10Y，经 FRED/AV） | `providers/macro.py:59`、`providers/alphavantage.py:284-286` |
| BEA | 部分覆盖（仅 FRED 派生） | 无 BEA provider；`get_fred_series` 可拉 BEA 源序列 |
| BLS | 部分覆盖（仅 FRED 派生） | `providers/macro.py:55-61` |
| SEC EDGAR | **未覆盖** | 仅 `config.py:49/105` 基址、`providers/macro.py:33` tombstone；README:44 仍写 “SEC EDGAR via Kimi”（过期） |
| ECB | 未覆盖（native） | `providers/macro.py:30` tombstone；`config.py:50/107` 未使用 |
| Eurostat | 未覆盖（native） | `providers/macro.py:32` tombstone；`config.py:52-53/111` 未使用 |
| US Census | 未覆盖 | 全仓 0 命中 |
| Data Commons | 未覆盖 | 全仓 0 命中 |
| WHO GHO | 未覆盖 | 仅 `providers/kimi.py:123` DISCOURAGED 文档标记 |

审计未实测的项：部署时 `FRED_API_KEY` 是否注入（`.env` 没有，mcpo 由 `/config/config.json` 注入，未读值）；futu OpenD 容器网络可达性；Treasury Fiscal Data 端点字段/限速（本轮未发请求）。

---

## P1 · SEC EDGAR（唯一高价值缺口）

**为什么值得做**：官方 REST、免 key、权威公司披露/XBRL，补足 yahoo/fmp 之外的“原始 filing”能力；`providers/macro.py:28-34` 已把它标成 future fundamentals provider，但一直没接。不要让这条继续走 kimi 旁路（计额度、DISCOURAGED、无 schema）。

**API 事实**（K-Dense `references/sec-edgar.md`）：

- Base：`https://data.sec.gov`
- 鉴权：无 key，但 **必须有描述性 `User-Agent`（含联系邮箱）**，否则 403；官方限速 10 req/s。
- 端点：
  - `GET /submissions/CIK##########.json`（10 位零填充 CIK；filings + fiscal 标签；Form 3/4/13F 入口）
  - `GET /api/xbrl/companyconcept/CIK##########/us-gaap/{tag}.json`（单概念时序，体积小）
  - `GET /api/xbrl/companyfacts/CIK##########.json`（约 3.8 MB，**必须做 concept 白名单/裁剪**，不要整包返回）
  - ticker→CIK：`https://www.sec.gov/files/company_tickers.json`
- 注意：`efts.sec.gov` 全全文搜索不是稳定公开契约，不要接；只接 `data.sec.gov` 文档化端点。

**改动清单**

1. `src/unified_finance_mcp/providers/edgar.py`
   - `class EdgarProvider(Provider)`，`name="edgar"`，`available()` 恒 True（无需 key）。
   - `async def submissions(cik: str) -> dict`：CIK 归一化（去前缀、`zfill(10)`），返回 `filings.recent` 的裁剪字段（form/accessionNumber/filingDate/reportDate/primaryDocument）。
   - `async def company_concept(cik, tag, taxonomy="us-gaap") -> dict`：返回 `units` 原样裁剪。
   - `async def company_facts(cik, tags: list[str]) -> dict`：只取白名单 tag，避免 3.8 MB。
   - `async def ticker_to_cik(ticker: str) -> str`：抓 `company_tickers.json`，缓存进程内。
   - UA：新增 settings 字段 `sec_edgar_user_agent`，默认 `finance-mcp (set SEC_EDGAR_USER_AGENT)`；**不要**用库的通用 UA。`config.py` 已有 `SEC_EDGAR_BASE_URL`，沿用。
2. `src/unified_finance_mcp/tools/edgar.py`
   - `get_edgar_filings(symbol_or_cik: str, form_type: str | None = None, limit: int = 20)`
   - `get_edgar_xbrl_facts(symbol_or_cik: str, tags: str = "Revenues,NetIncomeLoss", limit: int = 20)`
   - 用 `route_and_call` 的 chain `["edgar"]`，返回 `{"data": ...}`；失败走 `tool_error`，不抛异常。
3. 接线：`providers/__init__.py`、`runtime`/`server` 的 provider 构建处、`tools/__init__.py`、`tools/diagnostics.py:37-61` 的 `UNIFIED_MODULES`/`MODULE_TOOLS`。
4. 测试：`tests/test_provider_edgar.py`（UA 头、CIK 零填充、404→NotFound、companyfacts 白名单）+ `tests/test_tools_edgar.py`（无 key 可用、limit 校验、错误 envelope）。
5. 文档：README 工具表加两行；删掉 README:44 “SEC EDGAR via Kimi” 的过期表述，改成 “tombstoned until providers/edgar.py lands”。

**验收**：`pytest`/`ruff` 绿；live 调 AAPL submissions（HTTP 200，不 403）；`get_edgar_filings("AAPL")` 返回最近 10-K/10-Q；companyfacts 响应 < 1 MB。

**工作量**：M（provider ~250 行 + 2 个测试文件 + 接线）。

---

## P1/S · World Bank 任意指标/国家透传

现状只覆盖 `WLD` + 3 个 code（`macro.py:67-69/133`），而 World Bank API 本身免 key、任意国家/指标可用。

**改动**

1. `providers/macro.py`：抽出 `async def world_bank_series(indicator: str, country: str = "WLD", start: int = 1980, end: int = 2026) -> list[dict]`，复用 `_wb_row` 与现有分页拒绝逻辑；原 `_world_bank(code)` 改为调用它。
2. `tools/macro.py`：新增 `get_world_bank_series(indicator, country="WLD", start=1980, end=2026)`，chain `["macro"]`。
3. 测试：换国家（`country="CHN"`）、未知 indicator → NotFound、`per_page` 超限拒绝。
4. README 工具表加一行。

**验收**：`get_world_bank_series("NY.GDP.MKTP.CD", "CHN")` 返回中国 GDP；无 key；不动现有 8 指标行为。

**工作量**：S。

---

## P2/S · US Treasury Fiscal Data（可选）

**API 事实**（K-Dense `references/treasury.md`）：

- Base：`https://api.fiscaldata.treasury.gov/services/api/fiscal_service`
- 免 key；无正式限速，分页 `page[size]`/`page[number]`。
- 已验证数据集：
  - `/v2/accounting/od/debt_to_penny`（每日国债）
  - `/v2/accounting/od/avg_interest_rates`（存量平均利率）
  - `/v1/accounting/od/rates_of_exchange`（汇率）
  - `/v1/accounting/od/monthly_treasury_statement`（月度收支）
- **重要**：日度 par yield curve **不在 FiscalData**，在 `home.treasury.gov` 的 XML feed；不要用 `avg_interest_rates` 冒充收益率曲线。若要做曲线，单开 XML 任务。

**改动**：`providers/treasury.py` + `tools/treasury.py`，`get_treasury_data(kind: Literal["debt_to_penny","avg_interest_rates","rates_of_exchange","monthly_statement"], date_from=None, page_size=100)`；字段原样透传，`meta.total-count` 映射为 `total`。测试 respx + live 三端点。

**工作量**：S/M（不做 yield curve）。

---

## P2/S · ECB EXR（可选，只做一条）

`https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata` 免 key，CSV 解析即可，补欧元汇率主诉求。SDMX 全谱（MIR/ICP）继续留 tombstone。

**工作量**：S。

---

## 明确不做 / 暂缓

| 源 | 决定 | 理由 |
|---|---|---|
| Federal Reserve | 不做 native | FOMC/新闻稿不在数据库清单；利率已由 FRED/FedWatch 覆盖 |
| BEA | 暂缓 | 需免费 key；FRED 派生已覆盖头部序列，细分区域/行业表优先级低 |
| BLS | 暂缓 | 需免费 key；CPI/UNRATE/PAYEMS 已由 FRED 覆盖，JOLTS/OES 需求未验证 |
| Eurostat | 暂缓 | JSON-stat 2.0 解析成本；与金融主线弱相关 |
| WHO GHO | 不做 | 健康统计，放 scientific-data-mcp 的 M6 更合适 |
| US Census | 暂缓 | 需 key，匿名配额约束未评估；社科侧，非金融主线 |
| Data Commons | 暂缓 | 需 key + 自有 schema，不是 REST 直读 |
| OECD | 不做 | 不在 K-Dense 80 库内 |

---

## 通用约定（finance-mcp 现状）

- provider/tool 两层；HTTP 走 `PoliteClient`；错误走 `errors.py`；工具永不抛异常。
- 不加载 `.env`；key 只按需 `os.environ.get`，有 key 启用、无 key 静默跳过。
- 测试 respx hermetic；live smoke 单独脚本，不跑 CI。
- 发布 hatch-vcs：版本只来自 tag，不改 pyproject version。
- 新增 tool 后同步 `tools/diagnostics.py` 的模块/工具表与 README。

## 参考

- K-Dense 原文：`https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/database-lookup/references/{sec-edgar,treasury,worldbank,ecb}.md`
- 本仓快照：`scientific-data-mcp/docs/research/kdense-databases.json`
- 旧证据：`finance-mcp/docs/research/kimi-sources/sec_edgar.verdict.md`（7 工具 ↔ 官方端点实测映射）

---

## 附：paper-search 侧结论（不需要开任务）

- **USPTO 官方直连完全未覆盖**，现有专利能力 100% 依赖智慧芽 patsnap 付费 key。
- 但 USPTO ODP PFW 的现实门槛高：需 USPTO.gov 账号 + **ID.me 实名 + MFA**（中国大陆用户需视频认证）、key 绑定个人不可共享；只覆盖美国、2001 至今、不支持全文/语义检索；PatentsView PatentSearch 自 2026-03 起暂停，无 ETA。
- 结论：**暂不新增**。触发条件：patsnap key 不可用，或明确需要美国申请状态/审查文书时，再加 `lookup_patent_uspto`（S，约 200 行）。
- 顺手发现（非 K-Dense 任务）：`tool.py:111` 把 `patsnap` 放进 `DIRECT_SOURCES`，但 `search_papers` 无对应分支，传 `sources=patsnap` 会静默 0 结果；建议单独修一行或从集合移除。
