# dongcai（东方财富妙想/Choice）裁决 — 摘

- **评估对象**: `docs/research/kimi-sources/dongcai.md`（2026-09-13 describe dump，**13** 个 `dongcai_*` API，6,544 B）
- **裁决**: **摘** — 13 个 API 分两类：数据查询类（5 个）+ 报告生成类（7 个）+ 资讯检索（1 个）。数据类全部落在 EM（东方财富）公开数据面，与 stock_finance_data（R1 已裁摘，免费等质 ≈93%）同域同构，akshare/EM 裸端点免费直出；报告生成类不是数据能力（输入数据全免费、产物是 AI 生成文本，与本项目"可验证数据"纪律相悖）；无 wind 保留的债券估值/EDB gap，无 caixin 保留的 8 类独有域，无 gildata 保留的聚源研报片段/基金经理筛选。零独有数据。
- 本裁决做了 3 个免费端点 live 验证（研报列表/涨停池/板块行情，均 200 keyless，见 §4）+ 复用 R1 的 EM 端点实测结论。

## 0. 关键事实（影响裁决的前置发现）

1. **dongcai = 东方财富妙想（Choice 系）**。数据后端就是 EM 公开面（行情/财务/估值/股本股东/事件/宏观），这正是 akshare 覆盖最深的地带——R1（stock_finance_data）已逐端点实测 EM push2/push2his/emweb F10/datacenter 全部免 key、无登录（本机 2026-09-13，含 cninfo 公告 18 条实测）。数据查询类 API 的底料免费等质在 R1 已坐实。
2. **13 个 API 里 7 个是"报告生成"而非数据**（跟踪/深度/行业/专题/业绩点评/股票诊断/基金诊断）：输入是 EM 免费数据，输出是 AI 生成的 PDF/DOCX/Markdown。这是**内容合成能力**，不是数据源——且与本项目近期反幻觉纪律（commit 2d4892f 给 quote/technicals/tv_analyze 加 anti-hallucination guidance）方向相反：把"生成文本"当数据转发恰是本项目要避免的。调用 LLM（Claude 自己）拿免费数据写报告即可，无需花 kimi 配额买一份不可验证的生成物。且 doc 自述"生成耗时较长"。
3. **不覆盖任何已留源的 gap**：无债券个券估值（久期/凸性/中债估值，wind 保留项）、无 EDB 指标目录检索（wind 保留项）、无保险/人物/环保/专利/舆情指数/债券发行人财务/银行监管指标/产业图谱（caixin 保留 8 类）、无研报正文片段级检索与基金经理筛选（gildata 保留项）。mx_finance_data 的 NL 查询面（A/港/美/基金/债券/指数行情财务估值股本股东事件）与 gildata_fin_query 不同源——后者贵在聚源专有库，前者查的就是 EM 免费面。
4. **保留成本与摘除成本均为 0 改动**：`tools/kimi.py` 只暴露通用 `kimi_datasource call source=dongcai`，dongcai 无任何专用 dispatch（aspect fan-out 仅 tianyancha 有）。摘除即从 describe 列表消失，不耗 quota。

## 1. API ↔ 免费替代映射表（13/13）

| # | kimi API | 类型 | 免费替代 | 实测证据 | 等质度 |
|---|----------|------|---------|---------|--------|
| 1 | `dongcai_mx_finance_data` | 数据：A/港/美/基金/债券/指数 行情+财务估值+股本股东+事件，NL 查询 | **= stock_finance_data R1 全套**：EM push2/push2his（行情/K线/复权）、emweb F10（三表/股东/主营/预测）、datacenter（估值/事件）；港美走本仓 yahoo；基金走东财 F10（wind 裁决实测 fund NAV 端点 200） | R1 实测：600223 前复权日线 654 行、601126 十大流通股东/F10 全键、RPT_VALUEANALYSIS_DET 2111 期 | **≈95%** |
| 2 | `dongcai_mx_stocks_screener` | 数据：A/港/美/基金/ETF/可转债/板块 NL 筛选 | 本仓 TV screener（CN=china 在 `MARKET_TO_TV_SCREENER`）+ EM clist 全市场快照（A 股 spot_em 单次全市场 ~5855 行，本地过滤）；港美 yahoo/TV | 今日实测板块端点同族 clist 200（见 #5 行证据） | **≈90%**（NL 包装便利性不算数据） |
| 3 | `dongcai_mx_macro_data` | 数据：GDP/CPI/PPI/PMI/M2/社融/利率/汇率 + 产业链量价（如猪肉价格） | 国家统计局 data.stats.gov.cn（官方免 key）+ akshare `macro_china_*` 数百序列（含猪价等高频产业链项） | R1/wind 裁决核验同款口径 | **≈90%**（常用口径等质；产业链长尾与 wind EDB gap 无关——doc 未提供指标目录检索） |
| 4 | `dongcai_stock_market_hotspot_discovery` | 数据：市场主线/板块强弱/情绪周期 | EM push2ex 涨停池（连板数/封单）+ push2 clist 板块排行（涨幅/主力净流入/涨跌家数）+ 涨停/炸板/跌停池全家（akshare `stock_zt_pool_em` 系同端点）；"情绪周期/主线"是对这批免费数据的解读性打包 | **今日实测**：ZT 池 200、40 只含连板数（闽东电力 3 连板）；板块列表 200、496 板块含主力净流入 26.7 亿/涨跌家数 | **≈85%**（原始数据全免费可得；"周期判定"是解读不是数据） |
| 5 | `dongcai_comparable_company_analysis` | 数据：单一 A 股同业对比（经营+估值横向） | 同业集合 = TV screener 行业筛选 / EM F10 行业归属；对比数据 = 三表+估值（#1 全免费）→ 本地拼表 | R1 实测三表与估值端点 200 | **≈85%**（缺"成品对比表"，数据全免费） |
| 6 | `dongcai_mx_finance_search` | 检索：个股/行业/宏观 新闻+券商研报+评级+目标价 | EM `reportapi.eastmoney.com/report/list`（券商研报列表：标题/机构/评级/EPS 预测/目标价）+ akshare `stock_news_em`（个股关联新闻） | **今日实测**：reportapi 200、2484 条（近一月），含"开源证券/增持/EPS2026 0.24"级字段 | **≈90%**（研报元数据+评级+盈利预测实测可得；正文片段级检索是 gildata 保留项，与本源无关） |
| 7 | `dongcai_industry_stock_tracker` | **报告生成**：行业/个股跟踪（日/周/月报）PDF | 输入数据全免费（#1+#4）；报告撰写是调用方 LLM 的本职 | — | 非数据能力 |
| 8 | `dongcai_initiation_of_coverage_or_deep_dive` | **报告生成**：首次覆盖/深度研究 PDF | 同上 | — | 非数据能力 |
| 9 | `dongcai_industry_research_report` | **报告生成**：行业深度研究 PDF | 同上 | — | 非数据能力 |
| 10 | `dongcai_topic_research_report` | **报告生成**：主题/政策专题研究 PDF | 同上 | — | 非数据能力 |
| 11 | `dongcai_stock_earnings_review` | **报告生成**：财报业绩点评 PDF | 财报数据免费（#1 三表），点评=LLM 合成 | — | 非数据能力 |
| 12 | `dongcai_stock_diagnosis` | **报告生成**：A 股综合诊断（基本面+资金面+风险面） | 基本面（#1）+ 资金面（EM moneyflow/主力净流入，今日板块端点同族实测 200）+ 风险（免费价史自算，wind 裁决同款判断） | — | 非数据能力 |
| 13 | `dongcai_fund_diagnosis` | **报告生成**：基金诊断（收益+风险+持仓） | 东财基金 F10 全免（净值/持仓/经理，wind 裁决实测端点 200） | — | 非数据能力 |

## 2. 定量结论

13 个 API 分类账：

| 档位 | 数量 | 占比 | 明细 |
|---|---|---|---|
| 数据查询/检索类 | 6 | 46% | #1-#6：免费等质 ≈85-95%，全部有免费落点，**零独有数据** |
| 报告生成类 | 7 | 54% | #7-#13：非数据能力，输入 100% 免费，产物为不可验证生成文本（与本项目反幻觉纪律相悖） |

- **摘档成立**：数据类 6/6 免费等质 ≥85%（R1 同域实测背书 + 本任务 3 端点今日实测），报告类 7/7 无独有底层数据。加权免费覆盖 **≈100%**（以"数据可获得性"计），远超 90% 门槛。
- **保留-仅gap 不成立**：逐项对照已留源，dongcai 对 wind 的 gap（债券估值/EDB）、caixin 的 8 类独有、gildata 的研报片段/基金经理/聚源专有库**全部零交集**——没有可缩的"gap 白名单"可言。
- **留 不成立**：唯一可辩护的"独有"是报告生成能力，但那是内容合成而非数据（§0.2），且 7 个 API 全部"生成耗时较长"，quota 收益为负。

## 3. 使用纪律（过渡期，若摘除动作尚未生效）

在正式摘除前，若 `kimi_datasource call source=dongcai` 仍可达：行情/财务/筛选/宏观问题一律走免费侧（本仓 yahoo/TV + 计划中的 EM provider），dongcai 不作任何场景的首选——包括报告生成场景（调用方 LLM 直接基于免费数据撰写，勿转发第三方生成文本）。

## 4. 证据

- dongcai.md（本目录）：describe dump，13 API 清单。
- **本任务 live 实测（2026-09-13，httpx 直打，全部免 key 无登录）**：
  1. `reportapi.eastmoney.com/report/list`（券商研报列表，akshare `stock_research_report_em` 后端）→ 200、hits=2484（近一月全市场），字段含 org（开源证券/太平洋）、emRatingName（增持）、predictThisYearEps（0.24/0.59）——#6 研报/评级/目标价面免费成立。
  2. `push2ex.eastmoney.com/getTopicZTPool`（涨停池，akshare `stock_zt_pool_em` 后端）→ 200、tc=40，含连板数（闽东电力 3 连板/瑞尔特 4 连板）——#4 情绪/热点原始面免费成立。
  3. `push2.eastmoney.com/api/qt/clist/get`（板块排行）→ 200、total=496 板块，含涨幅%（通信线缆 5.84）、主力净流入（26.7 亿）、涨/跌家数——#4 板块强弱面免费成立。
- **R1 复用证据**（stock_finance_data.verdict.md，2026-09-13 本机实测）：EM push2/push2his/emweb F10/datacenter 四族端点免 key 直出（K线 654 行、十大股东、主营构成 200 条、估值 2111 期）；cninfo 公告 18 条——#1 数据面免费等质背书。
- **wind.verdict.md**（R8）：EM 基金净值端点实测 200；债券估值/EDB 为 wind 保留 gap——dongcai 无此二项 API，交集 0。
- **caixin.verdict.md**：保险/人物/环保/专利/舆情指数/债券发行人财务/银行监管/产业图谱 8 类独有——dongcai 13 API 无一涉及。
- **gildata.verdict.md**（#10）：聚源研报片段检索/基金经理筛选/fin_query 专有库为保留项——dongcai_mx_finance_data 查的是 EM 免费面、finance_search 只有研报元数据级（实测见上），不构成重叠保留理由。
- **repo 侧**：`src/unified_finance_mcp/providers/` 清单（无 CN provider、无报告生成工具）；`tools/kimi.py` 无 dongcai 专用 dispatch（摘除=0 改动）。
