# wind（万得）裁决 — 保留-仅gap

- **评估对象**: `docs/research/kimi-sources/wind.md`（2026-09-13 describe dump，36 个 `wind_get_* / wind_search_* / wind_query_*` API）
- **裁决**: **保留-仅gap** — 核心行情/财务/公告/常用宏观免费等质覆盖 ~58%（且多数已在本仓 provider 链内），但债券个券估值分析（久期/凸性/利差/中债估值）与 EDB 长尾宏观指标目录检索免费确实没有等质替代 → 保留 wind 但把调用面缩小到这 2-3 个 gap。

## 0. 关键事实（影响裁决的前置发现）

1. **实际 API 面不含期货/期权/外汇**。describe 文档 36 个 API 全部落在 股票/基金/指数/债券/宏观 EDB/公告新闻/analytics 七类，没有任何 futures、options、FX API。任务假设中"期货主力连、期权 greeks/链"这些免费弱项域在此源中**不存在**，因此可替比例比预期更高。
2. **wind 在本仓没有自动 dispatch**。`tools/kimi.py` 只暴露通用 `kimi_datasource call source=wind api=...`（唯一专用 fan-out 是 tianyancha 的 `get_company_risk_cn`）。保留成本 = 0 改动；摘除收益 = 省下用户/LLM 显式调用的 quota。
3. **实测验证**（本任务唯一 httpx check）: 东方财富基金净值端点 `api.fund.eastmoney.com/f10/lsjz?fundCode=110022`（akshare `fund_open_fund_info_em` 的后端）返回 200，含 2026-09-11 单位净值/累计净值/日涨幅/申赎状态 —— 基金域免费等质成立。

## 1. 领域表

| 领域 | API 数 | 代表 API | 免费等质方案 | 等质度 | 域裁决 |
|---|---|---|---|---|---|
| 股票-行情/K线 | 4 | `stock_quote`, `stock_price`, `stock_price_indicators`, `get_price` | akshare `stock_zh_a_spot_em`/`stock_zh_a_hist`/`stock_zh_a_minute`（东财）；本仓 yahoo(.SS/.SZ)+futu_bridge(港/A) 已在路由链 | **等质**（实时快照含 PE/PB/市值） | 摘 |
| 股票-财务指标 | 1 | `stock_financial_index` (PE/PB/PS/ROE/毛利) | akshare `stock_financial_analysis_indicator`(sina) + 东财 F10 | **等质** | 摘 |
| 股票-技术面 | 1 | `stock_technicals` (MACD/RSI/KDJ/BOLL) | 本仓 `technicals.py`（tradingview TA_Handler，covers()=True） | **等质** | 摘 |
| 股票-风险指标 | 1 | `risk_metrics` (beta/Sharpe/VaR) | 免费价史自算；本仓 `_backtest_indicators.py` 已有 | **等质** | 摘 |
| 股票-参考/筛选 | 3 | `stock_info`, `search_stocks`, `search_fields` | `stock_individual_info_em`（有行业但非申万分级）；本仓 `screener.py`(TV china)；`search_fields` 是 wind 自家字段目录，随源存亡 | 近似（申万分级 tushare 需积分） | 摘 |
| 股票-股东/事件 | 2 | `stock_equity_holders`, `stock_events` | akshare 十大股东/股本股东 partial；实控人 → tianyancha（kimi 另一源更对口）；分红 cninfo | 近似 | 摘（重叠域） |
| 基金-行情/净值 | 2 | `fund_quote`, `fund_price` | akshare `fund_etf_spot_em`/`fund_open_fund_info_em`（**端点实测 200**）/`fund_etf_hist_em` | **等质** | 摘 |
| 基金-资料/业绩/持仓 | 5 | `fund_info`, `fund_performance`, `fund_holdings`, `fund_company_info`, `search_funds` | 东财 F10 + akshare `fund_open_fund_rank_em`/`fund_portfolio_hold_em` | **等质** | 摘 |
| 基金-结构/财务 | 3 | `fund_price_indicators`(IOPV/折溢价), `fund_holders`(申赎/规模), `fund_financials`(利润/费用) | NAV/累计NAV/规模 free；IOPV 与申赎时序 free 仅 partial，基金利润表需翻年报 | 近似 | 摘（可接受） |
| 指数 | 6 | `index_quote`, `index_price`, `index_fundamentals`(PE/PB 分位), `index_technicals` | akshare `stock_zh_index_spot_em`/`index_zh_a_hist`；中证官网披露 PE + akshare `index_value_hist_funddb`(乐咕分位)；TA 同股票自算 | **等质-偏**（快照涨跌家数 partial） | 摘 |
| 债券-要素 | 1 | `bond_basicinfo`（发行日/规模/票面/期限） | 可转债 akshare 全；信用债要素 chinamoney/上清所原始页 partial | 近似 | 摘（糙但可得） |
| 债券-发行人 | 2 | `bond_issuer_info`, `bond_financial_data` | 上市公司发行人 → 东财 F10 等质；非上市发行人 → tianyancha 源更对口（纯 free 的 aiqicha 额度极紧） | 近似 | 摘（重叠域） |
| **债券-估值分析** | 1 | `bond_market_data`（估值/利差/**久期/凸性**） | 中债登官网需注册且无 tidy API；akshare `bond_china_yield` 仅收益率曲线，无个券估值 | **不可替** | **留** |
| 宏观-常用序列 | 1 | `query_economic_indicator_data`（GDP/CPI/PMI/LPR/社融） | 国家统计局 data.stats.gov.cn（官方免 key）+ akshare `macro_china_*` 数百序列 | **等质**（常用口径） | 摘 |
| **宏观-EDB 目录+长尾** | 1 | `search_economic_indicator`（NL 检索指标元数据目录） | free 无目录级检索——akshare 散在几百个函数里，长尾行业高频指标（EDB 数百万条）检索+取数免费做不到 | **不可替**（长尾） | **留** |
| 公告 | 1 | `company_announcements`（年报/季报/招股书/监管披露） | 巨潮 cninfo（官方、全量、免费、有 API） | **等质且更权威** | 摘 |
| 新闻 | 1 | `financial_news` | akshare `stock_news_em` 仅个股关联；全市场新闻检索 free 弱——但 wind 的新闻也只是聚合商，无独占内容 | 双弱 | 摘 |
| **analytics 兜底** | 1 | `financial_data`（NL → wind 库任意结构化查询） | 定义上的独有：本类是"其他工具不覆盖时"的逃生门 | **不可替**（兜底价值） | **留**（last-resort） |

## 2. 定量结论

36 个 API 分类账：

| 档位 | 数量 | 占比 | 明细 |
|---|---|---|---|
| 免费等质 | **21** | **58%** | 股票行情/K线/财务/技术/风险 7、基金行情净值+资料业绩持仓 7、指数 6（含分位）、公告 1（cninfo 更权威） |
| 免费近似 | 9 | 25% | 申万分级、IOPV/申赎时序、基金财务表、信用债要素、非上市发行人、新闻等——糙但可得或归 tianyancha 源 |
| 不可替（真 gap） | **6** | **17%** | `bond_market_data`（个券久期/凸性/估值）、EDB `search_economic_indicator` + 长尾时序、`financial_data` 兜底、`search_fields`（随源存亡，不算数据能力） |

**摘档不成立**：等质 58% < 90% 门槛。**留档不成立**：股票/基金/指数三大块（21/36）免费等质且核心已在 repo 路由链（yahoo/tradingview/futu）或一个 akshare provider 即可补齐。
**保留-仅gap成立**：25% 近似 + 58% 等质 = 83% 可替，17% 独有（债券估值分析 + EDB 长尾 + analytics 兜底）——正是"大部分 FREE 可替、1-2 细分免费没有"的教科书形态。

## 3. dispatch 缩小建议（wind 仅在以下场景显式调用）

1. **债券个券估值分析** — 需要久期/凸性/利差/中债估值时（akshare 只有收益率曲线）。
2. **EDB 长尾宏观** — 常用宏观先走 国家统计局/akshare；查"某行业高频指标"时先 `wind_search_economic_indicator` 拿 code 再 `wind_query_economic_indicator_data`。
3. **`wind_get_financial_data` 兜底** — 仅当所有结构化工具失败后的 last resort。

其余一律走免费：A 股/港美股行情与历史（本仓 quote/history/technicals + akshare）、财务指标（akshare/东财 F10）、公告（cninfo）、基金（akshare，端点已实测）、常用宏观（统计局/akshare）。

预估 quota 效果：按调用面比例，wind 调用量可压掉 ~83%；实际中 wind 的高频用途（行情/K线/财务）恰是免费全覆盖的部分，接近全额转移。

## 4. 后续（非本任务范围）

- 落一个 akshare provider 后，wind 的"近似档"9 个 API 大半升为等质，届时可复审是否只剩 `bond_market_data` + EDB 两个 API 值得留。
- `bond_issuer_info` 与 tianyancha 源的域重叠，以 tianyancha 侧裁决为准。
