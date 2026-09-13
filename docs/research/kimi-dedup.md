# Kimi datasource 去重评估（kimi-dedup）

背景：kimi 12 源走 cliproxy kimi-tools，每次 `call_data_source_tool` 消耗额度。
目标：**凡是被开源/免费数据“等质覆盖”的源就从 kimi 摘除/降级**，独有或显著更优的保留。

评估维度（每个源一张小节）：
1. **数据覆盖** — 免费源能给到同样的实体/字段吗？
2. **质量差异** — 免费源的频率/深度/结构化程度是否显著差？
3. **接入成本** — 免费源需要自建采集/清洗吗？（只在我们已有 provider 覆盖时才算“等质”）
4. **额度收益** — 移除后省多少 kimi 调用？（高频工具优先）

输出规则：
- **摘** — 免费覆盖 ≥ kimi 90%，且我们已有直接 provider 或公开无需 key API。
- **留** — 免费做不到同等（独有字段、结构化深度、或批量阻力）。
- **保留-仅gap** — 大部分 FREE 可替，但某 1-2 个细分能力免费没有 → 保留 kimi 但缩小 dispatch（`_probe_aspect` 已经按 aspect 分调用）。

12 源逐档：

| # | kimi source | 主要用途（来自 docs/research/kimi-sources/*.md） | 免费对手（已有 repo 证据） | 裁决 | 证据 |
|---|-------------|------------------------------------------|----------------------|-----|-----|
| 1 | stock_finance_data | CN A 股 realtime/财务/股东/板块/公告/预测 | akshare(east money/sina) / tushare / yfinance | **摘** (≈93% 等质) | [R1](kimi-sources/stock_finance_data.verdict.md) — EM/sina/cninfo 实测 200，6/9 等质 100%、无独有数据 |
| 2 | yahoo_finance | 历史价/持仓/期权/推荐 | **已有 providers/yahoo.py（自有 provider）** | **摘** | [R2](kimi-sources/yahoo_finance.verdict.md) — 9 API 全由 yfinance 覆盖、8 已直连，仅 upgrades_downgrades 缺一行接线 |
| 3 | world_bank_open_data | GDP/CPI 等宏观 | **World Bank 官方 REST（免 key）** | **摘** | [R3](kimi-sources/world_bank_open_data.verdict.md) — 实测 200 且 lastupdated 2026-07-13；kimi 路由是死代码（describe 无那 2 个 api 名） |
| 4 | tianyancha | 工商/股东/司法/股权穿透/集团谱系（226 API） | aiqicha/qcc(免费额度极紧) / gsxt(captcha+无API) | **留** | [R4](kimi-sources/tianyancha.verdict.md) — 无免费 API 等价物（gsxt 无API+验证码、爬虫被 JA4/极验 v6 压制、akshare 无此域）；摘即断 get_ownership/get_company_risk_cn 两链 |
| 5 | arxiv | 论文搜索/下载/读 | **arXiv 官方 API + user ~/paper-search** | **摘** | [R5](kimi-sources/arxiv.verdict.md) — export.arxiv.org 免 key 直连 + paper-search 已等质覆盖 4 API 外加 17+ 库 |
| 6 | scholar | scholar_search + author_info | OpenAlex/S2（free key）/user google_scholar 链 | **摘** | [R6](kimi-sources/scholar.verdict.md) — 仅 2 API；OpenAlex 免 key 实测覆盖 h-index/i10/引用/机构，GoogleScholar 独特点被 paper-search google_scholar 链兜底，SAS 18 免费学术 API 佐证 |
| 7 | yuandian_law | 中国法律/判例 检索+详情 | 裁判文书网(captcha)/openlaw 收缩 | **留** | [R7](kimi-sources/yuandian_law.verdict.md) — flk.npc.gov.cn 实测：SPA+旧 api 死链 405+新 search 匿名 500+captchaImage 在位，法规侧退路也断 |
| 8 | wind | CN 全资产：股/债/基/宏观/期权 30+ API | akshare+tushare 部分覆盖 | **保留-仅gap** | [R8](kimi-sources/wind.verdict.md) — 36 API 中 58% 免费等质、25% 近似、17% 不可替（债券估值久期凸性/EDB 长尾宏观/analytics 兜底），压到 3 类省 ~83% quota |
| 9 | imf | 11 个 IMF 数据集 | **IMF SDMX 官方 REST（免 key）** | **摘** | [R9](kimi-sources/imf.verdict.md) — DataMapper+新 api.imf.org SDMX 2.1 双双免 key 覆盖 ≥9/10；kimi 侧 `get_imf_series` 同 R3 模式死代码，且预置旧 CompactData 端点已 DNS 死亡 |
| 10 | gildata | 聚源选股/财报 SQL/研报/公告 | cninfo(巨潮, 官方免费) / 大智慧免费 | **留** | [R10](kimi-sources/gildata.verdict.md) — 即席 SQL 跨股选股/研报片段/基金经理筛选免费零等质；akshare 需逐期拉全表本地 join、tushare 要 2000 积分 |
| 11 | sec_edgar | SEC XBRL/持仓/内幕交易 | **SEC EDGAR 官方 REST（免 key）** | **摘** | [R11](kimi-sources/sec_edgar.verdict.md) — companyfacts/companyconcept/submissions/efts/FilingSummary+R 文件全部免 key 实测 200；kimi 增值仅在客户端解析层 |
| 12 | sp_data | S&P Capital IQ 预估/transcript/关系图谱 | yfinance 部分 + Alpha Vantage 部分 + 免费中转缺 transcript/estimates | **保留-仅gap** | [R12](kimi-sources/sp_data.verdict.md) — 5/13 API 独有（transcripts/预估历史/竞对/并购交易/顾问关系图谱），8/13 已由 yahoo/fmp/13F 覆盖 |

**结果汇总**：摘×7（yahoo_finance, world_bank_open_data, arxiv, scholar, imf, sec_edgar, stock_finance_data — 其中 stock_finance_data 摘除前需先补 eastmoney provider）、留×3（tianyancha, gildata, yuandian_law）、保留-仅gap×2（wind, sp_data）。

## R15 第二发现轮（2026-09-13 晚）：6 个新源

| # | kimi source | 主要用途 | 裁决 | 证据 |
|---|-------------|---------|-----|-----|
| 13 | ifind | CN A 股行情/财务 | **摘** | [R15-ifind](kimi-sources/ifind.verdict.md) — 与 stock_finance_data 逐字同构、wind 股票域严格子集、wind gap 白名单零交集 |
| 14 | pubchem | 化学库 | **摘** | [R15-pubchem](kimi-sources/pubchem.verdict.md) — 4/4 API 1:1 PUG-REST 免费转发，全 200 实测 |
| 15 | chembl | 生物活性库 | **摘** | [R15-chembl](kimi-sources/chembl.verdict.md) — 4/4 API 1:1 EBI REST 免费转发，样例 IC50 40.0 nM 即 kimi 文档自家引值 |
| 16 | caixin | CN 财经 687 API 22 大类 | **留** | [R15-caixin](kimi-sources/caixin.verdict.md) — 8 类 ~200 API（保险/人物/环保/舆情/专利/私募/债券发行人/产业图谱）免费+wind+gildata 双重不可替；687 全走单一 caixin_api_call → per-API 前缀白名单机械不可行，软路由建议见裁决 §处置 |
| 17 | fred | 美宏观 （圣路易斯联储） | **摘** | [R15-fred](kimi-sources/fred.verdict.md) — 官方 FRED 免 key (5min 注册） + alphavantage 8 指标 8/8 重叠 + B2 `file_path`/`filepath` 参数冲突全死代码 |
| 18 | pubmed | 生物医学文献 | **摘** | [R15-pubmed](kimi-sources/pubmed.verdict.md) — NCBI E-utilities 免 key + 用户 paper-search `_pubmed_search` 直连已覆盖 |

**B 系列 bug 发现**（非硬性本期，列入后续）：
- **B1** `caixin_api_search` 响应 assistant+`is_success` 嵌套 → `_extract_call_result` 只认 user 通道返回空 envelope → **已修**（providers/kimi.py）
- **B2** fred `file_path` vs `filepath` 参数冲突 → fred 两个 API 全死（不影响，fred 已摘）
- **B3** wind `wind_get_bond_financial_data` 上游要 `question` 参数（不是 `code`）→ 该 API 现无法正确调，后续调用方适配

**18 源终局**：留×4（tianyancha, gildata, yuandian_law, caixin）、窄化×2（wind 18-API、sp_data 5-API）、摘×12（yahoo_finance, world_bank, arxiv, scholar, imf, sec_edgar, stock_finance_data, ifind, pubchem, chembl, fred, pubmed）。

## R13 实施设计（由本评估直接推出）

1. **KNOWN_SOURCES 缩到 5**：`tianyancha, gildata, yuandian_law, wind, sp_data`。
2. **per-API 白名单**（数据来自 R8+R12 双"仅 gap"）：新增 `SOURCE_ALLOWED_API_PREFIXES` 映射，仅 wind/sp_data 非空：
   - `wind`: 债券估值 / EDB 长尾 / analytics 兜底 3 类（前缀待定——R8 报告 §"摘除涉及面"）
   - `sp_data`: transcripts / 预估历史 / 竞对 / 并购交易 / 顾问关系图谱 5 类
   - `# Tianyancha Query OK` 不受影响（前缀过滤发生在 `KimiProvider.call()` 层，不源码改 `call_data_source_tool` 协议）
3. **`KIMI_MACRO_CANDIDATES` 整组删**（R3+R9 双重证实是死代码），`KIMI_MACRO_VALUES` 留作 alphavantage 直连路由的参考（不再走 kimi），`economic()` face 改为"无实现 → NotFound"或直接删 face，让 macro chain 退化为 `alphavantage` 直连。
4. **`shareholders()` face 保留**——它只调用 tianyancha（在保留源里），不受影响。
5. **删源后 describe 的 skeleton 防护**（`providers/kimi.py` describe 的 `###` 检查）需保持——dropped sources 会被 `NotFound` 提前拦掉，不会到那一步，但留着不危害。
6. **附带已识别非阻塞优化项**（独立任务，不在本 PR）：
   - `providers/yahoo.py` 接 `upgrades_downgrades` 一行
   - `ASPECT_APIS["equity_penetration"]` 用 api_search 拿确切名回填（R4 §5）
   - 新增 eastmoney provider（R1 交叉指向，~300-500 LOC）——在摘 stock_finance_data 前完成

## 决策提交格式

每个源最终行写：
```
| stock_finance_data | ... | akshare/tushare 覆盖 X%；暂无直达 provider | 摘 | R1 证据 / path/to/notes |
```
全部完成后发一个 `fix(kimi): drop 7 sources / shrink dispatch` 的 PR（同一系列任务）。

## 基线（R0 已 fact）

- kimi 侧 quota ~ 待用户确认总量，但每次 call 真实消耗；12 源 describe 最近一次 dump：`docs/research/kimi-sources/*.md`（2026-09-13 19:50）。
- finance-mcp 现有免费 provider：`yahoo.py`、`tradingview.py`、`cex.py`(bitget/gate/mexc)、`fmp.py`(free news 不可)、`alphavantage.py`(25 req/day)、`marketaux.py`、`futu_bridge.py`(券商通道)。
- 用户 ~/paper-search：arXiv、PubMed、Semantic Scholar、OpenAlex、CORE、HAL、EuropePMC、Zenodo、bioRxiv/medRxiv、dblp、IACR、SSRN/DOAJ safety net + IEEE Xplore(direct) + zhihuiya/patsnap(文书&专利, key) — 已 isE 覆盖多数“科研/文献”需求。
- scientific-agent-skills 项目（用户指定参考）：https://github.com/K-Dense-AI/scientific-agent-skills — 具体源清单由 R5/R6 子 agent 在该 repo 内核对。

## 决策提交格式
每个源最终行写：
```
| stock_finance_data | ... | akshare/tushare 覆盖 X%；暂无直达 provider | 摘 | R1 证据 / path/to/notes |
```
全部完成后发一个 `fix(kimi): drop N sources / shrink dispatch` 的 PR（同一系列任务）。
