# 2026-11-18 K-Dense 缺口源裁决

## 背景

`scientific-data-mcp` 把 K-Dense `database-lookup`（v1.8，80 库）做成快照 + 季度扫描，按域归属把经济/金融/监管/社科 14 源判给 finance-mcp。立项文档：`docs/handoff-2026-11-18-kdense-gaps.md`。本文记录**实测后的最终裁决**，与 handoff 有出入的地方以本文为准。

## 已接入（2026-11-18）

| 源 | 入口 | 形态 | 为什么 |
|---|---|---|---|
| SEC EDGAR | `get_sec_filing(kind=filings\|facts)`（新工具，1 个） | data.sec.gov，免 key，声明 UA | 唯一真缺口：原始 filing + as-reported XBRL（带 accn/filed/form 溯源），补足 yahoo/fmp 厂商归一化报表之外的"原始披露" |
| World Bank 任意指标 | `get_economic_data(indicator="NY.GDP.MKTP.CD", country=…, start=…, end=…)` | 复用 macro provider | 原来只覆盖 WLD + 3 指标；API 本身免 key、任意国家/指标可用，边际成本几十行 |
| US Treasury 收益率曲线 + 债务 | `get_economic_data("TREASURY_YIELD_CURVE", period="YYYY-MM")` / `("TREASURY_DEBT")` | 新 provider，两个 host | 原来只有 10Y（FRED/AV），2s10s/倒挂答不了；CSV 导出免 key |

**表面积裁决（用户 2026-11-18）**：能并入现有工具的就不新开工具。所以 4 个候选源只新增 **1 个** unified 工具（`get_sec_filing`），22 → 23；WB/Treasury 全部挂进 `get_economic_data` 的第三种词表。

## 与 handoff 的三处修正

1. **SEC UA 是硬门槛，且共享 UA 必 403**。实测（本机 + dockerno1，同一出口）：
   - `unified-finance-mcp/0.1 (+https://github.com/xyonium/finance-mcp)` → **403** "Undeclared Automated Tool"
   - `unified-finance-mcp/0.1` → 200；`… eli@example.com` → 200；`+https://example.com` → 200
   触发词是 UA 里的 `github.com`，不是"有没有版本号"。所以 EDGAR 自带 `SEC_EDGAR_USER_AGENT`，默认 `unified-finance-mcp`，403 翻译成带配置指引的 `AuthError`。SEC 站点级 10 req/s。
2. **`/v1/accounting/od/monthly_treasury_statement` 是 404**（handoff 标"已验证"），正确入口是 `/v1/accounting/mts/mts_table_N`；本轮不做 MTS。
3. **收益率曲线不必走 XML**：`home.treasury.gov/.../daily-treasury-rates.csv/all/{YYYYMM}?type=daily_treasury_yield_curve&_format=csv` 直接返回 1Mo–30Y 全曲线（约 1 KB/月）。handoff 说的"单开 XML 任务"不成立。

另外：`companyfacts`（AAPL 3.86 MB）不用；白名单 tag 改成逐个 `companyconcept`（2-8 KB/tag），一次调用永远到不了 MB 级。

## 明确不做 / 暂缓

| 源 | 决定 | 理由 |
|---|---|---|
| ECB EXR | 不做 | Yahoo/现有 FX 已覆盖 EURUSD；官方参考价边际价值低 |
| BEA | 暂缓 | 需免费 UserID（100 req/min）；FRED 派生已覆盖头部序列，细分区域/行业表需求未验证 |
| BLS | 暂缓 | v2 需注册（500 查询/日）；CPI/UNRATE/PAYEMS 已由 FRED 覆盖 |
| US Census | 暂缓 | 2026-05 起**所有查询强制 key**；社科侧，非金融主线 |
| Data Commons | 暂缓 | v2 已强制 key + 自有 schema，不是 REST 直读 |
| Eurostat / OECD / WHO | 不做 | SDMX/JSON-stat 解析成本高，与金融主线弱相关 |
| Treasury MTS 月度表 | 不做 | 数据集入口变更 + 行数大，价值低于曲线/债务 |

**触发条件**：只有当 FRED 停产、或明确需要 BEA 区域/行业细分、BLS JOLTS/OES、人口普查微观数据时，才重新评估；届时按 FRED 形态接（无 key 静默跳过、`AuthError` 带注册 URL、`docs/CREDENTIALS.md` 补一行）。

## 验收证据

- `pytest -q -m "not integration"`：734 passed, 3 skipped；`ruff check .` 全绿
- live smoke（2026-11-18）：AAPL 10-K×3、AAPL 三 tag facts、CHN GDP 2022-2024、2026-11 曲线（1M 4.09 / 2Y 4.80 / 10Y 5.10 / 30Y 5.46）、debt_to_penny 2026-11-16 = 40,662,417,395,617.43
