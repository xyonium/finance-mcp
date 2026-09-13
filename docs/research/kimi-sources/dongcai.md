# dongcai

**Description:** 东方财富妙想金融数据。覆盖 A股、港股、美股、基金、债券、指数板块行情财务、
宏观经济指标、智能选股、金融资讯搜索、股票/基金综合诊断、A股市场热点发现，
以及行业/主题研究报告、个股跟踪、首次覆盖、业绩点评、可比公司分析等报告写作能力。
使用自然语言查询即可获取结构化金融数据与研究报告。


## Available APIs

### dongcai_stock_market_hotspot_discovery

**Description:** 东方财富A股市场热点发现。识别当前市场主线、板块强弱与情绪周期。

**Required Parameters:**
- `query` (string): 热点发现问句，例如 &#39;今日市场热点&#39;、&#39;当前主线板块&#39;。

**Optional Parameters:**
- `file_path` (string): 结果 CSV 文件保存路径（可选，默认自动生成）。

---

### dongcai_industry_stock_tracker

**Description:** 东方财富行业/个股跟踪报告。生成行业或个股的跟踪类报告（日报/周报/月报与跟踪解读），返回标题、总结与 PDF/DOCX 附件（base64）。生成耗时较长。

**Required Parameters:**
- `query` (string): 跟踪对象问句，含行业或个股名称，例如 &#39;贵州茅台月度跟踪&#39;。

---

### dongcai_initiation_of_coverage_or_deep_dive

**Description:** 东方财富首次覆盖/深度研究报告。为沪深京港美上市公司生成首次覆盖或深度研究报告，返回标题、正文与 PDF/DOCX 附件（base64）。生成耗时较长。

**Required Parameters:**
- `query` (string): 含公司名称或代码的问句，例如 &#39;贵州茅台深度研究报告&#39;。

---

### dongcai_comparable_company_analysis

**Description:** 东方财富可比公司分析。对单一A股上市公司进行同业对比、经营与估值横向比较，返回结构化对比数据。

**Required Parameters:**
- `query` (string): 含单一公司名称或代码的问句，例如 &#39;贵州茅台的可比公司分析&#39;。

**Optional Parameters:**
- `file_path` (string): 结果 CSV 文件保存路径（可选，默认自动生成）。

---

### dongcai_mx_finance_data

**Description:** 东方财富金融数据查询。支持自然语言查询A股、港股、美股、基金、债券、指数板块等行情、财务估值、股本股东、公司事件等结构化数据。

**Required Parameters:**
- `query` (string): 自然语言查询问句，例如 &#39;贵州茅台近一年营收&#39;、&#39;沪深300成分股市盈率&#39;。

**Optional Parameters:**
- `indicators` (string): 从 query 中提取的金融指标，多实体（&gt;5）查数时必填。例如 &#39;近一年营收&#39;、&#39;市盈率、总市值&#39;。
- `file_path` (string): 结果 CSV 文件保存路径（可选，默认自动生成）。

---

### dongcai_mx_stocks_screener

**Description:** 东方财富智能选股。按股价、市值、涨跌幅、市盈率、技术信号、行业/概念板块等条件筛选A股、港股、美股、基金、ETF、可转债、板块等。

**Required Parameters:**
- `query` (string): 自然语言筛选条件，例如 &#39;市盈率低于20的白酒股&#39;、&#39;近一月涨幅前50的ETF&#39;。

**Optional Parameters:**
- `select_type` (string): 筛选类型，例如 A股、港股、美股、基金、ETF、可转债、板块等。
- `file_path` (string): 结果 CSV 文件保存路径（可选，默认自动生成）。

---

### dongcai_mx_finance_search

**Description:** 东方财富金融资讯搜索。检索个股、行业、板块、宏观策略的最新新闻、券商研报、评级观点、目标价等文本内容。

**Required Parameters:**
- `query` (string): 自然语言搜索问句，例如 &#39;宁德时代最新研报观点&#39;、&#39;美联储降息影响&#39;。

**Optional Parameters:**
- `file_path` (string): 结果 CSV 文件保存路径（可选，默认自动生成）。

---

### dongcai_industry_research_report

**Description:** 东方财富行业深度研究报告。根据行业关键词生成完整研究报告，返回标题、正文与 PDF/DOCX 附件（base64）。生成耗时较长。

**Required Parameters:**
- `query` (string): 行业关键词，例如 &#39;半导体&#39;、&#39;新能源汽车&#39;、&#39;AI芯片&#39;。

---

### dongcai_topic_research_report

**Description:** 东方财富主题/专题深度研究报告。围绕主题、事件或政策生成专题研究，返回标题、正文与 PDF/DOCX 附件（base64）。生成耗时较长。

**Required Parameters:**
- `query` (string): 研究主题问句，例如 &#39;美联储降息对A股的影响&#39;。

---

### dongcai_stock_earnings_review

**Description:** 东方财富上市公司业绩点评。面向沪深京港美上市公司生成财报/业绩点评，返回标题、正文与 PDF/DOCX/数据表附件（base64）。生成耗时较长。

**Required Parameters:**
- `query` (string): 含公司名称或代码的问句，例如 &#39;东方财富2025年报业绩点评&#39;。

**Optional Parameters:**
- `report_date` (string): 报告期（可选，格式 YYYY-MM-DD，例如 2025-12-31）。缺省时自动取最新已发布报告期。

---

### dongcai_mx_macro_data

**Description:** 东方财富宏观经济与行业经济指标查询。支持GDP、CPI、PPI、PMI、M2、社融、利率、汇率及产业链量价数据。

**Required Parameters:**
- `query` (string): 自然语言查询问句，例如 &#39;中国最新CPI同比&#39;、&#39;猪肉价格走势&#39;。

**Optional Parameters:**
- `file_path` (string): 结果 CSV 文件保存路径（可选，默认自动生成）。

---

### dongcai_stock_diagnosis

**Description:** 东方财富股票综合诊断。对单只A股进行基本面+资金面+风险面的综合分析，返回结构化Markdown诊断报告。

**Required Parameters:**
- `query` (string): 股票名称或代码，例如 &#39;贵州茅台&#39;、&#39;600519.SH&#39;。

**Optional Parameters:**
- `file_path` (string): 结果 CSV 文件保存路径（可选，默认自动生成）。

---

### dongcai_fund_diagnosis

**Description:** 东方财富基金综合诊断。对单只公募基金进行收益表现+风险特征+持仓结构的综合分析，返回结构化Markdown诊断报告。

**Required Parameters:**
- `query` (string): 基金名称或代码，例如 &#39;华夏成长混合&#39;、&#39;000001.OF&#39;。

**Optional Parameters:**
- `file_path` (string): 结果 CSV 文件保存路径（可选，默认自动生成）。

---

