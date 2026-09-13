# arxiv — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/arxiv.md` vs `~/paper-search/`（README + tool.py v2.9.9）

## 结论

**摘。** arXiv 是全免费、免 key 的公开 API，用户自有 paper-search 项目已等质覆盖 kimi arxiv 全部 4 个功能且远超（arXiv 之外还并发 17+ 个学术库）。kimi 侧只增加 LLM 工具调用延迟与额度消耗，覆盖增益为零。

## kimi arxiv 的 4 个 API

| kimi API | 功能 |
|---|---|
| `search_papers(query, file_path)` | 检索 arXiv，结果写 CSV（可选 max_results / date_from / date_to / categories） |
| `download_paper(paper_id)` | 下载论文并异步转 markdown，支持状态查询 |
| `read_paper(paper_id)` | 读已下载论文的 markdown 全文 |
| `list_papers(file_path)` | 列出已下载论文（标题/作者/摘要）写 CSV |

## 免费可替代性验证

**arXiv 官方 API 完全免费、无需 key：**
- 官方文档 https://arxiv.org/help/api ：`https://export.arxiv.org/api/query`（Atom）公开开放，无需注册、无需 API key；唯一约束是 3 秒礼貌间隔的速率礼仪。arXiv bulk 数据（S3 requester-pays / OAI-PMH）同样免费开放。
- 硬证据：用户 paper-search `tool.py` 里就有一个长期在用的免 key 直连客户端 —— `_ARXIV_API = "https://export.arxiv.org/api/query"`（tool.py:1303），`_arxiv_get`（:1307）纯 `requests.get` 无任何鉴权，带 429/5xx 三次退避。第三方资料（freeapihub/apify 等）也一致确认 "No API key required: The arXiv API is free and open to everyone"。

**paper-search 对 4 个功能的逐一覆盖：**

| kimi API | paper-search 等价 | 证据 |
|---|---|---|
| search_papers | `search_papers(query, sources="arxiv")` — `_arxiv_search`（tool.py:1370）直连 Atom API，单请求即含 title/authors/abstract/doi/pdf_url；还做了逐级放宽（AND 全词→砍尾词）救 0 命中，比 kimi "≤6 词禁 OR" 的硬限制更鲁棒 | tool.py:1370-1404 |
| download_paper | `download_paper_to_knowledge(...)` — arxiv 是原生下载源（pdf_url=`arxiv.org/pdf/{id}`），下载后直接入 OpenWebUI Knowledge（RAG），比 kimi 落 CSV/本地 markdown 更进一步 | tool.py:3533-3622 |
| read_paper | `read_paper(source="arxiv", paper_id)` — `read_arxiv_paper` 快车道全文 + pdf_url fallback + jina 兜底；且不要求先下载 | tool.py:3163-3266（_READ_TOOLS :309） |
| list_papers | 下载即入 Knowledge 集合（`knowledge_id`），清单由 OWUI 知识库原生列出；kimi 的 read_paper 同样要求先 download，语义对称，无净损失 | tool.py:3553-3555 |

**覆盖面对比：** kimi arxiv 只有 1 个库；paper-search 并发覆盖 arXiv + PubMed/Semantic Scholar/OpenAlex/CORE/HAL/EuropePMC/PMC/dblp/Zenodo/IACR/DOAJ/OpenAIRE/Crossref + 智慧芽/IEEE/专利等 18+ 源，含去重、OA 下载 fallback 链（OpenAIRE/CORE/EuropePMC/PMC/Unpaywall）、web 兜底（tavily→firecrawl）。

**仅有的微小差异（不构成保留理由）：**
- kimi 检索参数有 date_from/date_to/categories；paper-search 的 arxiv 直连未显式暴露日期/分类过滤，但 arXiv API 原生支持 `submittedDate`/`cat:` 字段（加两行参数即可补），且 OpenAlex/S2 源已提供日期过滤的学术检索。
- kimi 默认 `date_from=2023-01-01` 会漏掉老论文，反而是缺陷。

## 额度与延迟账

- 每次走 kimi `call_data_source_tool` 真实消耗额度；论文检索是高频操作，摘除后全部此类调用归零。
- kimi 路径 = LLM 工具调用 → cliproxy → kimi arxiv 服务 → 再返回；paper-search 直连官方 API（含退避重试），延迟与可控性都更优。

## 裁决

**摘。** 纯重复：免费官方 API + 已有更强自建覆盖，kimi 无任何独有能力，只有额度成本与延迟。
