# ifind（同花顺 iFinD）裁决 — 摘

- **评估对象**: `docs/research/kimi-sources/ifind.md`（2026-09-13 describe dump，9 个 `ifind_get_*` API，13,398 B）
- **裁决**: **摘** — ifind 的 9 个 API 与 stock_finance_data（R1 已裁摘，免费等质 ≈93%）**逐 API 同构**，是同一上游插件换皮；对 wind 是严格能力子集，且与 wind 值得付费的 18-API gap 白名单**交集为 0**。无任何独有数据。

## 0. 关键事实（决定性发现）

1. **与 stock_finance_data 是换皮同源**。硬证据（本任务唯一验证动作，零额外 kimi 调用）：
   `sed 's/stock_finance_data/ifind/g' stock_finance_data.md` 后与 `ifind.md` 做 diff，9 个 API 段落全部逐一对应、正文**逐字相同**——相同的描述文案、相同的参数、相同的限制（max 3 tickers、价格 3 年上限）、甚至相同笔误（API 名 `get_financial_statements`、`financial_parameter` 示例 `'2021231'`）。残余差异仅为：段落顺序不同、`stock_info` 里 `request_time` 参数行位置互换、`business_segmentation` 的 ticker 示例串写法（`'600223.SH' or 'AAPL.O,0001.HK'` vs `'AAPL.O,0001.HK,600223.SH'`）。三处全是模板噪声，无语义差异。
2. **"同花顺 iFinD" 名义存疑**。两源描述行同是模板话术 "`<NAME> is a financial data platform provided by <NAME> Inc.`"（ifind 侧为 "provided by ifind Inc."）——真 iFinD 厂商是同花顺（Hithink RoyalFlush），描述却把厂商写成 "ifind Inc."。即上游大概率是同一 datasource 模板挂了不同源名，不宜当作真正的 iFinD 终端深度来计价。
3. **R1 免费实测证据直接继承**。R1（`stock_finance_data.verdict.md`，同日 2026-09-13）对本 9 个 API 逐一做过免费端点实打：新浪 `hq.sinajs.cn`（A/HK/US 三市场实时全 keyless 200）、EM `push2`/`push2his`（实时+K线 654 行）、EM datacenter（三表 54 页）、EM F10（股东/主营构成 200 条/公司资料 40+ 字段/盈利预测）、巨潮 cninfo（公告 18 条含 PDF 链接）。API 面逐字相同 → 该证据对 ifind 全额成立。
4. **不在 KNOWN_SOURCES 种子表**。`providers/kimi.py` 的 12 源种子表没有 ifind；它只能经 R14 probe-on-first-sight 路径被撞见。摘除成本 = 加一行 DISCOURAGED。

## 1. API ↔ 免费替代映射（9/9 继承 R1 实测）

| # | ifind API | 覆盖内容 | 免费替代 | R1 实测等质度 |
|---|---|---|---|---|
| 1 | `get_stock_realtime_price` | A/HK/US 实时价 + A 股分钟级技术指标集（MA/EXPMA/SAR/BOLL/BBI/RSI/KDJ/MACD/DMI/BIAS/WR/CCI/ROC/LB/ATR，仅非 ETF/非科创） | 新浪 hq 三市场 + EM push2；技术指标免费 kline 本地推导，repo `technicals.py`（TV）覆盖常用集 | ≈95% |
| 2 | `get_price` | 股/指数/商品历史价，D/W/M/Q/Y，前/后复权，≤3 年 | EM `push2his` kline（`klt`/`fqt` 全档，**长于 3 年**）；US/HK 走 repo `yahoo.py history` | ≈100% |
| 3 | `get_financial_statements` | A/HK/US 三表任意报告期 | EM datacenter（A 股）+ repo `yahoo.py financial_report`（US/HK 三表齐） | ≈100% |
| 4 | `get_stock_announcement` | A 股公告（日期/标题/PDF URL） | 巨潮 cninfo 官方（法定披露一手源） | 100% |
| 5 | `get_holder_info` | 股东名/持股/比例/股东户数/机构持仓 | EM F10 ShareholderResearch + repo `yahoo.py ownership` | ≈100% |
| 6 | `get_stock_info` | 公司资料/控股股东/实控人/主营/员工/可比公司 | EM F10 CompanySurvey（40+ 字段）+ repo `yahoo.py company_info`；可比公司无现成免费字段 | ≈90% |
| 7 | `get_stock_business_segmentation` | 主营构成（产品/行业/地区 收入/成本/毛利率） | EM F10 BusinessAnalysis `zygcfx`（实测 200 条分期构成） | 100% |
| 8 | `get_forecast` | A 股业绩预测（净利/营收及 YoY） | EM F10 ProfitForecast（机构 EPS/共识）+ datacenter `RPT_WEB_RESPREDICT` | ≈85% |
| 9 | `get_stock_financial_index` | 六大类财务指标打包（资本结构/流动性/效率/盈利/成长/现金覆盖） | 三表衍生比率免费输入 + 本地计算；akshare `stock_financial_analysis_indicator` 覆盖常用项 | ≈75%（缺"成品打包"非缺数据） |

描述里宣称的 "intelligent stock screening" 无对应 API（同 R1）；repo TV screener（`screener.py`，CN=china）反而更强。

## 2. 与 wind、yahoo 的对照（任务书第二判据）

- **对 wind 是严格子集，且不碰 gap 白名单**。wind 36 API 横跨 股/基/指/债/宏观 EDB/公告/analytics；ifind 9 个全部落在"股票"一个域，每一类 wind 都有同名能力（`stock_info`/`stock_financial_index`/`get_price`/`company_announcements`/`stock_equity_holders`/…）。而 `SOURCE_ALLOWED_API_PREFIXES["wind"]` 保留的 18 个付费 API（债券估值久期凸性、EDB 长尾宏观、风险指标、基金/指数全档、PE/PB 全史）**ifind 一个都没有**——wind 值得花 quota 的地方 ifind 全部缺席，wind 免费可替的部分 ifind 全部重复。
- **HK/US 深度不及 repo 既有 yahoo.py**。ifind 美股仅 `realtime_price` 5 字段（价/涨跌/量/额）+ 3 年**不复权**历史；`providers/yahoo.py` 已有 quote/history（无年限限制）/三表/company_info/ownership（机构+内部人+基金）/news/option_chain/short_interest/dividend_split/earnings/analyst_estimates——全面占优。HK 侧 ifind 明言"收盘后不留数据"；yahoo/futu_bridge 无此限制。
- **无 quant 因子库、无研报**。API 面里没有因子、没有 research reports；真 iFinD 的这些卖点在本 kimi 源中不存在（ Gildata 源才是研报/SQL 选股所在，已另裁 留）。
- tushare 免费档（注册 token+积分制）在 R1 已定性为非"无 key"路径，不改变结论；本裁决不依赖它。

## 3. 定量结论

- 9/9 API 均有免费落点，加权免费等质 ≈ **93%**（继承 R1：7/9 实测等质或近等质，2/9 数据免费但需聚合计算）。无一项"免费拿不到的数据"。
- 摘档成立（dedup 规则"免费覆盖 ≥90% + 公开无需 key API"）：EM/sina/cninfo 端点 R1 同日实打全 200。
- 相对 wind 的 17% 独有面（债券估值/EDB/analytics 兜底），ifind 占有率 **0%**——不构成任何"保留-仅gap"理由。

## 4. 落地建议

1. `DISCOURAGED_SOURCES`（`providers/kimi.py`）加一行：`"ifind": "R15 摘 — stock_finance_data 换皮同源（9 API 逐字同构），EM/sina/cninfo 免费等质 ≈93%，且不触 wind gap 白名单"`。无需 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap 可留）。
2. 与 stock_finance_data 同批摘除，共享 R13 既有前置：先落 `providers/eastmoney.py`（R1 已验证 quote/history/holders/segmentation/forecast 五面端点）+ cninfo 公告面；US/HK 继续走 yahoo。
3. `realtime_tech` 与 `financial_index` 不追平指标集广度：免费 kline/三表 + 本地计算 + TV `technicals.py` 常用集已够（同 R1 结论）。
4. 若上游未来给 ifind 换上真 iFinD 终端能力（研报/因子/宏观），须重跑 describe 重新评估——本裁决只对当前 9-API 面有效。
