# pubmed — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/pubmed.md`（kimi 实 dump）vs NCBI E-utilities（live 实测）+ `~/paper-search/`（README + tool.py，pubmed/pmc/europepmc 均直连源）。

## 结论

**摘。** PubMed 的官方本体就是 NCBI 自己，kimi 只能是它的镜像，不可能给出上游没有的数据。3 个 API 逐项验证：检索+摘要走 E-utilities 免 key 直接复现（2026-09-13 live 实测 esearch+efetch 200，完整摘要文本返回）；元数据解析 PMID/PMCID/DOI 免费工具链齐全；OA 全文下载走 EuropePMC fullTextXML（live 实测 200、144KB JATS）+ 用户 paper-search 更强的下载兜底链（OA repos → Unpaywall → 直入 RAG Knowledge）。且用户 paper-search 的 `pubmed`/`pmc`/`europepmc` 本来就是默认并发源。

## kimi pubmed 的 3 个 API

| kimi API | 功能 |
|---|---|
| `pubmed_search` | 检索：自由 query / title / author / journal 过滤、日期或年份区间、翻页（page_size 1-100）、排序（relevance/pub_date/first_author/journal）、可选摘要 |
| `pubmed_get_article_metadata` | PMID/PMCID/DOI 解析 → 归一化元数据 + 摘要 + 标识符 + PubMed/PMC/DOI 链接；可选 OA 资源链接（S3 pdf/xml/txt）与本地下载记录 |
| `pubmed_download_article` | 异步下载 OA 资源（默认 pdf），轮询状态，返回 file:// oss:// 或签名 HTTPS URI |

## API ↔ 免费等价映射（逐项实测/对照）

| kimi 能力 | 免费等价 | 证据 |
|---|---|---|
| `pubmed_search` 自由检索 | **NCBI E-utilities** `esearch.fcgi?db=pubmed` → `efetch.fcgi?rettype=abstract` | live 实测 2026-09-13：einfo 200 XML；esearch 200 取 idlist → efetch 200 返回完整 Abstract（202/557/370 字符三例） |
| 摘要内容 | efetch `rettype=abstract`（XML PubmedArticleSet） | live 实测同上 |
| `title=` / `author=` / `journal=` 过滤 | PubMed 字段标签查询语法：`ti:`、`au:`、`ta:`，或 esearch `sort=Author/JournalName` | NCBI 文档（E-utilities 手册查询字段表） |
| 日期区间（YYYY/MM/DD 或年份） | esearch `datetype=mindate/maxdate` 或 term 里 `AND ("2024/01/01"[PDAT] : "2024/12/31"[PDAT])` | NCBI 文档 |
| 排序 relevance/pub_date/first_author/journal | esearch `sort=relevance / pub_date / Author / JournalName` 四档一一对应 | NCBI 文档 |
| `pmc_only` | db=pmc 或 term 加 `AND free full text[sb]` | NCBI 文档 |
| `pubmed_get_article_metadata` PMID/PMCID/DOI 解析 | efetch by PMID/PMCID；DOI → NCBI ID Converter（`/pmc/utils/idconv/v1/`）或 Crossref/OpenAlex（paper-search 已有 crossref/openalex 直连） | 免费公开端点 |
| 元数据+标识符+链接 | efetch 返回 title/authors/journal/DOI/PMID/PMCID/Abstract | live 实测 |
| OA 全文（pdf/xml/txt S3 链接） | **EuropePMC** `/{PMCID}/fullTextXML` + PMC efetch JATS 全文 | live 实测：fullTextXML 200、144,357 字符 |
| `pubmed_download_article` 异步下载 | paper-search `download_paper_to_knowledge`：native → OpenAIRE/CORE/EuropePMC/PMC → Unpaywall →（可选 Sci-Hub）→ 自动上传 OpenWebUI Knowledge RAG | README 架构图 v2.9.7+ |
| 本地下载记录/轮询 | paper-search 下载即入 Knowledge，无需轮询模型 | README |

**注（上游变动）：** NCBI 旧版 PMC OA 服务 `oa.fcgi`（kimi OA 资源链接的直系上游）2026-09-13 live 实测对文档示例 ID（PMC3356758/PMC2808877/PMC2824962 等）一律 404，疑似下线/迁移；免费 OA 全文路径已由 EuropePMC fullTextXML 与 PMC efetch 覆盖（均实测可用），paper-search 的下载链根本不依赖 oa.fcgi。

## 用户 paper-search 已有覆盖（重叠度 100%）

- `default_sources` 首位起即含 **pubmed、pmc、europepmc**（tool.py:255），另有 semantic/openalex/crossref/core 等 18+ 源并发。
- pubmed/pmc 为**直连 NCBI E-utilities**（`_pubmed_search` esearch+efetch，tool.py:1241；`_parse_pubmed_xml`，tool.py:1123）——2026-08 因旧后端 pubmed.py 无 timeout 挂起 bug 专门改的直连，工程上比 kimi 镜像链路（LLM 工具调用 → cliproxy → kimi → PubMed）更可控。
- `NCBI_API_KEY` valve（tool.py:222）：配了 10 req/s、不配 3 req/s——免费 key 一申请即得，速率宽裕。
- 语义源智能改写：PubMed 属语义源拿完整自然语言 query（README Query Adaptation 表），检索质量不低于 kimi。
- 下载侧是 kimi 没有的加分项：标题门控兜底链 + RAG Knowledge 自动入库。

## 额度与延迟账

- 每次走 kimi `call_data_source_tool` 真实消耗额度；生物医学检索高频场景摘除后归零。
- kimi 路径 = LLM → cliproxy → kimi 服务 → 镜像 PubMed；NCBI 直连实测 <1s、无 key 可用（3 req/s），配免费 api_key 到 10 req/s。

## 裁决

**摘。** PubMed 数据源头的所有者就是 NCBI，kimi 作为镜像零独有数据；3 个 API 的功能（检索+摘要、ID 解析+元数据、OA 全文下载）全部有 live 实测的免 key 等价物（E-utilities esearch+efetch、EuropePMC fullTextXML），且用户 paper-search 默认源里 pubmed/pmc/europepmc 本就直连在跑、下载链还多出 Unpaywall 兜底与 RAG 入库；保留只剩额度成本与一跳镜像延迟。
