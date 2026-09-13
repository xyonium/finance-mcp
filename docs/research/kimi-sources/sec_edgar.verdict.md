# sec_edgar 评审结论(kimi source 摘留判定)

**日期:** 2026-09-13
**结论: 摘** —— SEC EDGAR 官方 REST 全部免费、免 key、无需登录,数据面 100% 覆盖 kimi sec_edgar 的全部 7 个工具。kimi 增值仅为客户端解析便利(XML/HTML→CSV、关键词→concept 映射),可在需要时以原生 provider 低成本复刻。建议直接摘除 kimi sec_edgar;后续若需要 EDGAR 能力,自建原生 edgar provider(官方 REST + 合规 User-Agent)。

---

## 1. kimi sec_edgar API 面(7 个工具)

| # | kimi 工具 | 能力 | 输出 |
|---|---|---|---|
| 1 | `sec_edgar_get_insider_trades` | Form 3/4/5 内部人交易,summary/明细 | CSV 文件 |
| 2 | `sec_edgar_get_institutional_holdings` | 13F 机构持仓,可季度环比 | CSV 文件 |
| 3 | `sec_edgar_get_company_events` | 8-K 重大事件(财报/并购/高管变动) | CSV 文件 |
| 4 | `sec_edgar_get_company_info` | 公司信息:CIK/SIC/交易所/股本/public float | CSV 文件 |
| 5 | `sec_edgar_get_financial_statements` | 完整三表结构(行项目/小计/分段),FY/Q 期间定位 | CSV 文件 |
| 6 | `sec_edgar_get_xbrl_facts` | 单指标跨年时间序列(keyword/concept/metric 三模式) | CSV 文件 |
| 7 | `sec_edgar_get_filings` | 申报列表含 fiscal 标签 | CSV 文件 |

注:kimi 侧为内部 DB(alpha-longdata)供数,**存在滞后风险**;且所有工具强制 `file_path` 落 CSV,接口形态笨重(相对于直接返回 JSON)。

---

## 2. 官方免费替代 —— 实测证据(2026-09-13,AAPL/CIK0000320193)

全部请求携带描述性 User-Agent(SEC 公平访问政策要求;限速 10 req/s,足够)。

### 2.1 companyfacts(XBRL 聚合,即 kimi xbrl_facts 的数据源)

```
GET https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json
→ 200 OK,3,789,099 bytes(约 3.8 MB)
```

- 顶层字段:`cik`, `entityName` ("Apple Inc."), `facts`
- 税目:`dei`, `us-gaap`;**us-gaap 概念数 503 个**(AAPL 全历史)
- 每个数据点字段:`accn, end, filed, form, fp, frame, fy, start, val` —— **自带 fiscal_year/fiscal_period 标签**,kimi `get_filings` 的 fiscal 标签诉求在此已内含
- 样例概念(直接命中 kimi metric 快捷项):
  - `RevenueFromContractWithCustomerExcludingAssessedTax`:117 个点,最新 end=2026-06-27,val=$109,417,000,000
  - `NetIncomeLoss`:338 个点,最新 10-K(FY2025, end=2025-09-27)val=$112,010,000,000
  - `Assets`:146 个点,最新 end=2026-06-27,val=$383,266,000,000
  - `Revenues`(旧概念):11 个点,至 2018-09-29 止 —— 证明概念切换(AAPL FY2018 后弃用)在原始数据中同样可见
- `dei` 含 `EntityCommonStockSharesOutstanding`, `EntityPublicFloat` —— 覆盖 kimi get_company_info 的股本/市值字段

### 2.2 companyconcept(单概念时间序列 = kimi xbrl_facts concept 模式)

```
GET https://data.sec.gov/api/xbrl/companyconcept/CIK0000320193/us-gaap/NetIncomeLoss.json
→ 200 OK,50,767 bytes
```

- 字段:`cik, description, entityName, label, tag, taxonomy, units`
- USD 单位 338 个点;最近两个 10-K 点:(2023-10-01→2024-09-28, $93,736M, fy=2025, fp=FY)、(2024-09-29→2025-09-27, $112,010M, fy=2025, fp=FY)
- **体积仅为 companyfacts 的 1.3%**,适合按概念精准拉取

### 2.3 submissions(公司信息 + 申报列表 + 8-K/Form4/13F 入口)

```
GET https://data.sec.gov/submissions/CIK0000320193.json
→ 200 OK,164,091 bytes
```

- 公司字段直接覆盖 kimi get_company_info:`name`="Apple Inc."、`tickers`=["AAPL"]、`exchanges`=["Nasdaq"]、`sic`=3571(Electronic Computers)、`fiscalYearEnd`="0926"、`stateOfIncorporation`="CA"、`category`="Large accelerated filer"、`addresses`、`formerNames`;另有 `insiderTransactionForIssuerExists`=true 等
- `filings.recent` 返回最近 **1000 条**申报,列含 `form, reportDate, filingDate, accessionNumber, items, primaryDocument` 等:
  - Form 4(内部人)样例:(form=4, report=2026-09-08, filed=2026-09-10, acc=0001140361-26-036226)→ 拿 accession 即可下原始 Form 4 XML
  - 8-K 样例:(form=8-K, report=2026-07-30, items="2.02,9.01")→ items 编码即事件类型(2.02=业绩发布),kimi get_company_events 的事件分类官方免费可判
  - 13F-HR 同列表可过滤
- 注意:recent 中无 `fiscalYear/fiscalPeriod` 键,fiscal 标签需由 companyfacts 各点的 fy/fp 或 reportDate+fiscalYearEnd 推得(纯客户端逻辑)

### 2.4 全文检索(efts)

```
GET https://efts.sec.gov/LATEST/search-index?q="net income"&forms=10-K
→ 200 OK, application/json
```

- ES 后端返回 `{"took":372, "hits":{"total":{"value":10000,"relation":"gte"}, "hits":[{"_id":"0000950123-11-030440:w82162exv10w2.htm", "_source":{"ciks":[...], "display_names":[...], ...}}]}}`
- 免 key、无鉴权,文档级全文检索可用

### 2.5 财务三表结构组装(FilingSummary + 渲染 R 文件)

```
GET https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/FilingSummary.xml
→ 200 OK,70 个 Report
GET .../R3.htm(CONSOLIDATED STATEMENTS OF OPERATIONS)
→ 200 OK,92,927 bytes
```

- R3.htm 为官方 XBRL 渲染的三表,文本解析后得到完整利润表结构(3 个财年并列):
  `Net sales $416,161 / $391,035 / $383,285 → Cost of sales → Gross margin $195,201 → R&D $34,550 → SG&A → Operating income $133,050 → Net income $112,010`(单位 $M,FY2025/2024/2023)
- 报表清单含 `Cover Page → R1`, `Auditor Information → R2`, `STATEMENTS OF OPERATIONS → R3`, `BALANCE SHEETS → R5`, `CASH FLOWS → R8` 等 —— **kimi get_financial_statements 的"完整报表结构"诉求,官方渲染件免费覆盖**,且最新 10-K 单份已含 3 年比较数据(kimi 文档自己也承认这一点)

---

## 3. 对照分析:kimi 到底加了什么?

| kimi 工具 | 官方免费覆盖 | kimi 增值 | 评估 |
|---|---|---|---|
| get_xbrl_facts | companyfacts / companyconcept(实测 200) | keyword→concept 静态字典(约 100 词)、year/period 过滤 | **纯静态字典,零数据增值**;自建 dict 十行代码量级 |
| get_financial_statements | FilingSummary.xml + R*.htm(实测 200) | R 文件 HTML→CSV 解析、FY/Q→accession 定位 | 解析便利;原始链路 2-3 个请求可复刻 |
| get_company_info | submissions.json(实测 200) | 无(字段一一对应) | **零增值** |
| get_filings | submissions.json recent 1000 条(实测 200) | fiscal 标签拼装(companyfacts 的 fy/fp 已有) | 近零增值 |
| get_company_events | submissions 的 8-K + items 编码(实测 200) | items→事件名映射 | 小字典工作量 |
| get_insider_trades | submissions 过滤 form=4 + 原始 XML(实测 200) | Form 4 XML→CSV 行转列 | 真正的解析工作量(XML 非表格),但一次性 |
| get_institutional_holdings | submissions 过滤 13F-HR + 原始 XML | 13F XML→持仓表、季度环比 | 同上,中等解析工作量 |

**关键判断:**
1. **数据零缺口** —— kimi sec_edgar 没有任何一条数据是官方免费拿不到的(其自身数据也源自 EDGAR)。
2. **增值全部在客户端解析层** —— Form 4/13F XML 解析、R 文件 HTML 解析、两三个静态映射字典。这类逻辑恰恰是 finance-mcp 该自己掌握的(参照 futu wrapper 教训:外部黑盒 wrapper 一旦 kwarg/行为不符只能干等)。
3. **kimi 侧反而有劣势** —— 内部 DB 供数有滞后风险(官方是实时申报流)、强制 file_path CSV 输出、消耗 kimi 配额。
4. **官方配额宽松** —— 免 key,仅要求描述性 User-Agent,限速 10 req/s。

---

## 4. 决策

**摘。**

- 官方免费 REST(companyfacts / companyconcept / submissions / efts / FilingSummary+R 文件)已 100% 覆盖 kimi sec_edgar 的数据面,且更新更及时、无配额、无鉴权。
- kimi 的"报表组装便利"不足以抵消配额成本与黑盒风险;三表组装所需的 FilingSummary→R 文件链路已实测打通,将来需要时以原生 `edgar` provider 实现(估算:概念字典 + R 文件表格解析 + Form4/13F XML 解析,均为纯客户端逻辑)。
- 不符合"保留-仅gap"标准:不存在只有 kimi 能提供的数据缺口。

## 5. 后续(不阻塞本决策)

若未来建原生 EDGAR provider,直接复用本次实测端点:
- `data.sec.gov/api/xbrl/companyfacts|companyconcept/CIK*.json` —— XBRL 指标
- `data.sec.gov/submissions/CIK*.json` —— 公司信息/申报列表/8-K items/Form4/13F 入口
- `www.sec.gov/Archives/edgar/data/{cik}/{acc-no-dash}/FilingSummary.xml` + `R{n}.htm` —— 三表结构
- `efts.sec.gov/LATEST/search-index?q=...` —— 全文检索
- 纪律:每个请求带描述性 User-Agent(`FinanceMCP/... contact`),限速 ≤10 req/s。
