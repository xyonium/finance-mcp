# gildata（恒生聚源）去重裁决

**裁决：留**（kimi-dedup #10）

- 评估输入：`docs/research/kimi-sources/gildata.md`（2026-09-13 19:50 describe dump，8-tool bundle）
- 本裁决未做 kimi live 调用；免费对手结论来自公开文档核验（见文末证据）。

## 1. API 面（来自 gildata.md，8 个 tool）

全部 tool 签名一致：`query`（自然语言财务请求）+ `file_path`（落地 CSV），返回归一化行
（vendor / tool_name / query / score / retrieved_at 证据字段）。走 agent-gw 封装，上游
GILDATA_MCP_TOKEN 不落客户端。

| # | tool | 能力 |
|---|------|------|
| 1 | `gildata_fin_query` | 结构化财务/市场/基金/债券/指数/行业/工商数据即席查询（事实上的 SQL sandbox 入口） |
| 2 | `gildata_smart_stock_selection` | 自然语言多因子条件选股，返回结构化候选行 |
| 3 | `gildata_smart_fund_selection` | 基金筛选（业绩/风险/持仓/经理/公司） |
| 4 | `gildata_smart_fund_manager_selection` | 基金经理筛选（规模/业绩/风控特质） |
| 5 | `gildata_financial_research_report` | 券商研报片段、观点、report snippets 检索 |
| 6 | `gildata_announcement_data` | A 股公告摘录与披露片段 |
| 7 | `gildata_news_data_query` | 聚源新闻/舆情语料检索 |
| 8 | `gildata_macro_industry_data` | 宏观/行业时序指标 |

注意：doc 的示例 query（"筛选净利润增速超过30%且ROE大于15%的消费股"）正是各 tool 的目标场景
——全市场跨股财务筛选。

## 2. 免费对手核验

| 免费源 | 能给什么 | 给不了什么 |
|--------|---------|-----------|
| **cninfo/巨潮**（官方免费） | www.cninfo.com.cn 公告查询 + webapi.cninfo.com.cn（深证信数据服务平台，覆盖上市公司/基金/债券/公告，支持接口访问）；公告 PDF 全文+元数据 | 仅公告；无财务、无研报、无 SQL sandbox |
| **akshare**（免 key、pip 即用） | `stock_yjbb_em(date=期)`：单次返回该报告期**全市场**业绩报表（~5855 行 ×16 列，含净资产收益率/营收净利同比/毛利率/所处行业）→ 单期简单筛选可替；`stock_financial_abstract` / `stock_financial_analysis_indicator`：**按单股**全历史指标；`stock_zcfz/lrb/xjll_em`：按期全市场三大表；个股研报接口：仅**标题/东财评级/机构/近一月研报数/盈利预测** | 跨期/多因子条件需逐期拉全表再本地 join（每次查询=一个小 pipeline）；东财改参数时 akshare 滞后约一周+；无研报正文片段/观点检索；无基金经理筛选 |
| **tushare** | 免费档（注册积分）：行情/股票列表等基础面 | `fina_indicator`（财务指标）需 **≥2000 积分**（Pro 付费档），且只能**按单只股票**、每次≤100 条 —— 免费档无全市场财务指标 |
| **大智慧/同花顺 free** | — | 无稳定公开 API（iFinD 为付费终端） |

## 3. 决定性问题检验

> 免费侧能否让 agent 免爬虫地跑即席跨股财务查询（"全市场 ROE>20% 且 3 年营收 CAGR>15%"）？

- **单期条件**（ROE>20%）：可以——akshare `stock_yjbb_em` 一次调用 + 本地 pandas 过滤 ≈ 等质。
- **完整问题**（含 3yr CAGR）：**不行**——需要逐报告期（≥12 期）拉全市场表、按股票代码对齐 join、
  再算复合增速；免费侧没有任何"谓词下推"的查询引擎，等于每个问题都要现场搭一条采集-清洗管线。
  tushare 免费档无此权限；cninfo 无财务；大智慧/同花顺无 API。
- 叠加：repo 现有 providers（alphavantage/cex/fmp/futu_bridge/kimi/marketaux/tradingview/yahoo）
  **没有任何 CN A 股基本面 provider**，akshare/tushare 也未接入——摘除 gildata 后该能力归零。

**→ 答案为 No → 留。**

## 4. 为什么不是 保留-仅gap

若"仅 SQL sandbox 独有、公告/新闻免费"则可降级为 保留-仅gap，但实际独有面更宽：

1. **研报检索独有**：`gildata_financial_research_report` 提供研报**片段/观点**级检索；akshare
   个股研报只有标题、评级、盈利预测数字，无正文片段、无观点语义检索。
2. **基金经理筛选独有**：`smart_fund_manager_selection` 无任何免费等价物。
3. **即席查询引擎独有**：`fin_query` 是免管线、一次 NL 调用拿结构化行的唯一入口，覆盖
   股/基/债/指数/行业/工商（聚源 core-data 自述全域覆盖，与 fin_query 描述吻合）。
4. repo 侧也没有可缩的 dispatch 杠杆：gildata 走 `kimi_datasource` 直呼，
   `ASPECT_APIS` aspect 路由仅 tianyancha 有——"缩小 dispatch"无处落子。
5. 唯一明显可免替的是 announcement / news / macro 三类（约 3/8 tool），留档如下条建议，
   不构成降级整个源的依据。

## 5. 映射表（kimi gildata tool → 免费对手）

| kimi tool | 免费对手 | 等质？ | 备注 |
|-----------|---------|-------|------|
| `gildata_fin_query` | akshare（逐期全表+本地 join）/ tushare（2000 积分） | **✗** | 唯一免管线的即席跨股查询引擎；决定性问题在此FAIL |
| `gildata_smart_stock_selection` | akshare `stock_yjbb_em`（单期简单条件） | △ | 单期可替；多期 CAGR/复杂多因子差 |
| `gildata_financial_research_report` | akshare 个股研报（列表/评级/盈利预测） | **✗** | 研报片段/观点检索无免费等价 |
| `gildata_smart_fund_manager_selection` | — | **✗** | 无免费等价 |
| `gildata_smart_fund_selection` | akshare fund 系列（排行/净值/持仓） | △ | 基础数据有，NL 多条件筛选无 |
| `gildata_announcement_data` | cninfo 官方 API + akshare 公告接口 | ✓ | 免费更强（PDF 全文）；agent-gw 检索式摘录是便利性而非独有数据 |
| `gildata_news_data_query` | akshare 快讯/东财 + marketaux（全球，已接入） | ✓ 大体 | |
| `gildata_macro_industry_data` | World Bank/IMF 官方 REST（免 key）+ akshare 宏观 | ✓ 大体 | 与 #3/#9 源的免费替代重叠 |

## 6. 后续建议（不改本裁决）

- 若未来接入 akshare provider，公告/新闻/宏观三类问题优先路由免费侧，gildata 只兜
  fin_query / 研报 / 基金经理三条 gap 路径（届时可复核升 保留-仅gap）。
- 高频消耗预期集中在 `fin_query` 与 `smart_stock_selection`（选股类 query 是 doc 示例场景）。

## 7. 证据

- gildata.md（本目录）：8-tool describe dump。
- tushare 财务指标权限：tushare.pro/document/2?doc_id=79 — "用户需要至少2000积分才可以调取…
  当前接口只能按单只股票获取"（2026-09-13 核验）。
- akshare `stock_yjbb_em`：输入仅 date（XXXX0331/0630/0930/1231），输出 16 列含"净资产收益率"，
  示例 ~5855 行/期（akshare_docs 镜像，2026-09-13 核验）。
- akshare 个股研报字段：报告名称/东财评级/机构/近一月研报数/盈利预测（知乎 akshare 官方更新文，
  2026-09-13 核验；无正文片段）。
- cninfo：webapi.cninfo.com.cn（深证信数据服务平台自述"支持接口方式访问…覆盖上市公司、基金、
  债券、公告"）。
- 聚源 core-data 自述全域覆盖（gildata.com/products/core-data），与 fin_query 描述互证。
- repo 无 CN 基本面 provider：`src/unified_finance_mcp/providers/` 清单（ls 核验，2026-09-13）。
