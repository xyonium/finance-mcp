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

另外：`companyfacts`（AAPL 3.86 MB）不用；白名单 tag 改成逐个 `companyconcept`（2–50 KB/tag，随概念点数增长），一次调用永远到不了 MB 级。

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

## 2026-11-18 二次调研：未接入源的"备用价值"实测

**方法**：先测**部署机可达性**，再谈价值。被网络挡住的源没有备份价值——这一点比 API 文档更重要。

| 源 | 从 dockerno1 实测 | 结论 |
|---|---|---|
| BLS `api.bls.gov` | **403 Access Denied**（Akamai，默认 UA 与浏览器 UA 都一样） | 不可接：v2 key 再免费也没用，部署出口被拦 |
| US Census `api.census.gov` | **403 Access Denied**（同上） | 不可接 |
| BEA `apps.bea.gov` | 200；`UserID=DEMO` 取数报 `This UserId is not active` | 可达，真 key 免费（100 req/min），但只补 NIPA 细分/区域 GDP/行业 PCE |
| ECB `data-api.ecb.europa.eu` | 200；`YC/B.U2...SR_10Y` 有日频欧元区即期曲线 | 可达且是唯一"今天答不了"的增量，但受众小众（本仓库以 US/HK/CN/EG 为主） |
| Eurostat | 200（JSON-stat 2.0，34 KB/单指标） | HICP 与 FRED 欧元区序列重叠，解析成本高 |
| OECD | 200（SDMX/XML） | 与 World Bank/IMF 高度重叠 |
| Data Commons | **401 UNAUTHENTICATED** | 需 key + 自有 schema，不是 REST 直读 |
| Treasury MTS `/v1/accounting/mts/mts_table_1` | 200 | 机构/职能级收支明细；FRED 已有总额（收/支/赤字），增量小众 |

**裁决：本轮不再加源。** 理由按强度排序：

1. BLS/Census 的"免费 key 备份"在部署出口上**不可实现**（403），先排除。
2. BEA 可达但只补区域/行业细分；作为 GDP/PCE 备份的价值低于多维护一个 key-gated provider 的成本。
3. ECB 日频欧元区曲线、MTS 机构明细、Eurostat/OECD 都是"有增量但主线弱"；不做。
4. Data Commons/WHO 仍按原裁决不做。

**触发条件（满足再开任务）**：
- 换出口/加代理后 BLS 可达 → 再评估 BLS v2 作为 CPI/UNRATE/PAYEMS 的 FRED 备份（500 查询/日、50 序列/查询）；
- 明确需要 BEA 区域 GDP / 行业 PCE 或欧元区日频曲线；
- FRED 停服或 key 政策变化。

**给未来的提示**：任何"免费 key 源"的立项都先跑一遍 `curl` 可达性，再写 provider——`docs/CREDENTIALS.md` 第 2 级表格里的配额数字，只有在网络可达时才有意义。
