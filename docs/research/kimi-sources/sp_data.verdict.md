# sp_data 裁决（S&P Capital IQ via kimi）

- 评估日期：2026-09-13（依据 `docs/research/kimi-sources/sp_data.md` describe dump，16,916 字节）
- 裁决框架：`docs/research/kimi-dedup.md`（摘 | 留 | 保留-仅gap）
- **结论：保留-仅gap** —— 13 个 API 中 5 个（transcripts、预估历史、竞对/交易关系图谱）免费无解，值得花 kimi 额度；其余 8 个免费-first。

## 1. 结论一句话

sp_data 是真·商业数据集（S&P Capital IQ：机构级预估、电话会纪要、公司关系图谱），免费世界无等质替代，整源不能摘；但它的公司画像/财报/持仓/日历类 API 与我们已有的 yahoo/fmp 免费链重叠，且 kimi 调用按 API 逐次显式发起（`kimi_datasource(action='call', source, api)`），不做自动扇出，所以正确姿势是"源保留、dispatch 只在 gap 能力上花额度"。

## 2. API 面（13 个 API，按能力分组）

| # | API | 能力 | 范围（describe 自述，password-protected scope 裁剪） |
|---|-----|------|------|
| 1 | sp_get_estimates | 共识预估 | 2 年历史 + 2 年预测；data_item_id 级科目（EPS/营收/EBITDA/...），带 effective_date/to_date 有效期窗口 |
| 2 | sp_get_transcripts | 电话会/演示 transcript | Machine Readable Transcripts，当前年−2 至当前年；组件级 speaker 归属 + keyword 全文检索 |
| 3 | sp_get_competitors | 竞对关系 | CIQ 策展的公司竞争关系（company_id ↔ competitor_company_id） |
| 4 | sp_get_transactions_relationships | 并购对手方关系 | 5 年交易史：acquirer/seller/investor/counterparty + 关系类型 |
| 5 | sp_get_transactions_advisors | 并购顾问 | 5 年交易史：advisor 公司 + 顾问角色 |
| 6 | sp_get_financials | 标准化财报 | 10 年 CIQ Latest Financials；standard/bank/insurance/ratio/key_stats/valuation 模块 |
| 7 | sp_get_company_info | 公司画像/标识解析 | ticker↔company_id↔security_id/trading_item_id、交易所、行业、简介 |
| 8 | sp_get_top_owners | 头部股东 | top-50 持有人：持股、%流通、变动、%组合、排名、持有期 |
| 9 | sp_get_ownership_sellers | 买卖家数 | 增持/减持持有人数量汇总 |
| 10 | sp_get_top_executives | 高管 | top-15：职务、任期、rank、履历 |
| 11 | sp_get_key_developments | 历史公司事件 | 2 年内重大事件（诉讼/产品/管理层变更等分类） |
| 12 | sp_get_future_events | 未来公司事件 | 2 年内财报会/路演/投资者日历 |
| 13 | sp_get_topic_tags | 主题标签 | 公司关联主题/业务标签 + 分数 |

注：sp_data **没有** constituents（指数成分）和 market data（行情/报价）类 API —— S&P 侧这两块本源就不存在，行情已由 kimi 的 yahoo_finance 源和我们自己的 `providers/yahoo.py` 覆盖。因此"成分股/行情免费替代"这一条在本源天然成立，无需裁决。

## 3. 能力 ↔ 免费替代映射表（诚实评估）

| 能力 | sp_data API | 免费最佳替代（repo 现状） | 免费质量诚实评估 | 裁决 |
|------|-------------|--------------------------|------------------|------|
| 共识预估 | sp_get_estimates | yfinance `analyst_estimates`（`providers/yahoo.py` 已有：earnings/revenue estimate、growth、price targets、recommendations、eps_trend；`get_symbol_intel(kind='analyst')` 链 ["yahoo","fmp"]） + FMP `analyst-estimates`（免费档未验证，402 概率高） | yahoo 给**当期快照**（EPS/营收共识、目标价、评级，约 4 季度前瞻），日常"市场怎么看"够用；**缺**预估历史（修正轨迹）、EBITDA/科目级 breadth、data_item 有效期窗口。Capital IQ 共识广度/历史免费无对手 | **gap**（快照走 yahoo 免费，历史+科目级才花额度） |
| 电话会 transcript | sp_get_transcripts | Alpha Vantage EARNINGS_CALL_TRANSCRIPT（~25 req/day 配额、仅近期、美股）；FMP transcript 免费档订阅锁（402，已知）；Motley Fool / Seeking Alpha 爬取（脆弱、反爬、ToS 风险） | **免费无一可靠规模替代**。AV 配额一天 25 次根本撑不起 transcript 精读工作流 | **gap（最硬的一条）** |
| 竞对关系图谱 | sp_get_competitors | 无。TradingView 同行业 screener 只能按 sector 近似 peer，不是 CIQ 策展的竞争关系；FMP stock_peers 我们未接且免费档存疑 | 无结构化等价物 | **gap** |
| 供应链/交易关系图谱 | sp_get_transactions_relationships / sp_get_transactions_advisors | 无。SEC EDGAR 只有 13F 持仓 + 8-K/SDC 公告**原文**，无结构化 acquirer/seller/advisor 关系；FactSet Revere / S&P supply chain 均为同价位商业产品 | 规模化免费替代不存在 | **gap** |
| 标准化财报 | sp_get_financials | yfinance 三表（`providers/yahoo.py financial_report`，约 4-5 年）+ FMP statements（免费档近年可用） | 日常 90% 需求够用；CIQ 独有 bank/insurance 行业科目模块、data_item 跨公司标准化、10 年深度 | 免费-first（金融/保险股深度分析可例外走 kimi） |
| 公司画像/标识 | sp_get_company_info | yfinance `company_info` / `search`（已有） | 等质（CIQ 的 company_id 体系只在链 sp_data 其余 API 时有用） | 免费-first |
| 头部股东持仓 | sp_get_top_owners | `get_ownership`（yahoo/fmp 链已有：major/institutional/mutualfund/insider）+ SEC 13F（官方免 key） | yahoo 覆盖前 10-20 机构持仓及变动；sp 多至 top-50 + % of portfolio + 持有期，边际增量小 | 免费-first |
| 买卖家数汇总 | sp_get_ownership_sellers | 无直接（13F 可自算但要自建聚合） | 结构化汇总独有但小众、低频 | 免费-first（可留作次要兜底） |
| 高管 | sp_get_top_executives | yfinance 无；FMP key-executives 免费档未验证 | 弱替代（公司 IR/Wikipedia 非结构化） | 免费-first（弱 gap，价值低不值得额度） |
| 公司事件（历史/未来） | sp_get_key_developments / sp_get_future_events | `get_events_calendar`（fmp/av：earnings/dividends/ipo）+ 新闻链（marketaux/yahoo） | 财报日历等质；诉讼/产品/管理层变更等**分类**事件只能靠新闻流近似，结构化程度差一档 | 免费-first |
| 主题标签 | sp_get_topic_tags | 无结构化替代（TradingView screener 主题勉强近似） | 独有但小众 | 免费-first |

（免费侧事实依据：FMP 免费 key 一切订阅锁端点 402（已验证，见 memory fmp-free-tier-endpoints）；AV 日配额 ~25（memory finance-mcp-env-and-quotas，禁 live 测）；`tools/intel.py` docstring 自述 fmp 的 analyst 端点不在已验证免费矩阵内。）

## 4. 额度经济账

- **使用模式是事件驱动深研，不是日常行情**：财报季 transcript 精读、并购链条梳理、预估修正历史 —— 低频、单次高价值。一次 kimi 调用换一段 CIQ 级数据（商业单席位年费数万美金级），额度花在刀刃上。
- **对照**：daily quotes / 持仓快照这类高频路径若路由到 kimi，就是纯浪费额度 —— 而这些路径我们已有免费 provider（yahoo/fmp），没有理由让 agent 优先碰 sp_data 的 #6/#7/#8。
- **结构上零成本保留**：`kimi_datasource` 的 call 是 per-API 显式 `(source, api, params)`，sp_data 没有 tianyancha 式的 `get_company_risk_cn` 自动扇出容器 —— 源挂在 KNOWN_SOURCES 里本身不消耗额度，只有 agent 主动点名某 API 才扣。所以"保留-仅gap"的落地成本几乎为零，本质是 dispatch/指引层的排序问题。

## 5. Dispatch 建议

- **gap 白名单（值得花 kimi 额度，5/13）**：
  `sp_get_transcripts`、`sp_get_estimates`（预估历史/科目级）、`sp_get_competitors`、`sp_get_transactions_relationships`、`sp_get_transactions_advisors`
- **免费-first（kimi 仅兜底，8/13）**：
  `sp_get_financials`（→ yahoo/FMP 三表；bank/insurance 深度例外）、`sp_get_company_info`（→ yahoo company_info/search）、`sp_get_top_owners`（→ get_ownership + 13F）、`sp_get_ownership_sellers`、`sp_get_top_executives`、`sp_get_key_developments` / `sp_get_future_events`（→ get_events_calendar + 新闻链）、`sp_get_topic_tags`
- **落地方式**（供 kimi-dedup 统一 PR 参考）：
  1. sp_data 行标"保留-仅gap"，不摘源；
  2. 若日后给 sp_data 建 L2 容器（类似 get_company_risk_cn 的 aspect 扇出），aspects 只暴露上述 5 个 gap API；
  3. 容器/docstring 写明"预估快照、财报、持仓、日历先走 yahoo/fmp 免费链，仅 gap 能力调 kimi"，防 agent 拿额度买免费数据。

## 6. kimi-dedup.md 表格第 12 行建议填法

```
| sp_data | S&P CIQ 预估/transcript/竞对+并购关系图谱（13 API） | yfinance 部分预估快照+AV transcript(25/day)+免费无关系图谱 | 保留-仅gap | R? 证据: docs/research/kimi-sources/sp_data.verdict.md（5 gap API: transcripts/estimates/competitors/transactions_*） |
```
