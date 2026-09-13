# scholar — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/scholar.md` vs `~/paper-search/`（README + tool.py v2.9.9）+ [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) paper-lookup skill（18 个免费学术 API）。无 kimi 实调。

## 结论

**摘。** kimi scholar 本质是 Google Scholar 镜像（默认 `hl=zh-cn`、i10-index 是 GS 独有指标），仅 2 个 API：论文检索 + 作者画像。两条全部被免费 API 覆盖且已实测验证 —— OpenAlex 免 key 返回与 scholar_author_info 完全同构的 h-index/i10-index/总引用/研究方向/机构（2026-09-13 live 实测），论文检索的作者过滤/年份区间/排序也全部免 key 可用；而"Google Scholar 自己的索引"这唯一可能独特的点，用户自有 paper-search 的 google_scholar 链（firecrawl→tavily→Apify）已经在抓。

## kimi scholar 的 2 个 API

| kimi API | 功能 |
|---|---|
| `scholar_search(query, file_path, author?, num_results?, start?, hl?, start_year?, end_year?, sort_by?)` | 论文检索：关键词 + 作者过滤 + 年份区间 + 相关性/时间排序，结果写 CSV；≤50 条/页、按 10 翻页、禁 OR/≤6 词 |
| `scholar_author_info(author_name, file_path)` | 作者画像：基本信息 + 学术指标（h-index、i10-index、总引用）+ 研究方向 + 代表作，写 CSV |

## API ↔ 免费等价映射（逐参数）

| kimi 能力 | 免费等价 | 证据 |
|---|---|---|
| `scholar_search` 关键词检索 | **OpenAlex** `/works?search=`（keyless，mailto 进 polite pool）；**S2** `/paper/search`（免费 key 100 rps）；用户 paper-search 已有直连客户端 `_openalex_search`（tool.py:1523）、`_semantic_search`（tool.py:1455），另并发 arXiv/PubMed/Crossref/CORE/EuropePMC/dblp/Zenodo/HAL 等 18+ 源 | live 实测 2026-09-13 |
| `author=` 作者过滤 | OpenAlex `filter=raw_author_name.search:vaswani` | live 实测（与年份+排序组合调用成功） |
| `start_year` / `end_year` 年份区间 | OpenAlex `filter=from_publication_date:2017-01-01,to_publication_date:2018-12-31` | live 实测同上 |
| `sort_by=relevance/date` | OpenAlex `sort=relevance_score:desc / cited_by_count:desc / publication_date:desc`（比 GS 只给"相关性/时间"两档更细） | live 实测 `sort=cited_by_count:desc` |
| `num_results≤50` / `start` 翻页 | OpenAlex `per-page` 至 200、cursor 分页（比 kimi 的 50/10 更宽） | OpenAlex 文档 |
| `scholar_author_info` h-index / i10 / 总引用 | **OpenAlex** `/authors?search=` → `summary_stats.h_index`、`summary_stats.i10_index`、`cited_by_count`、`works_count` —— **live 实测**（Bengio：h=181、i10=697、475093 引、1216 作）；**S2** `/author/search` → `hIndex/paperCount/citationCount`（免费 key） | live 实测 |
| 作者研究方向 / 机构 | 同一 OpenAlex 调用：`topics[]`（研究方向）、`affiliations[]`（机构） | live 实测返回 3 topics + 2 机构 |
| 作者代表作 | OpenAlex `/works?filter=author.id:A…&sort=cited_by_count:desc`；S2 `author/{id}/papers` | OpenAlex/S2 文档 |
| `hl=zh-cn` 界面语言 | 展示层关注点非数据能力；paper-search 本身中文注释/中文输出 | — |

**唯一 kimi 侧可能独特之处 —— Google Scholar 自有索引（含灰色文献、GS 口径引用数）：** 已被用户 paper-search 的 google_scholar 链覆盖（firecrawl stealth 抓搜索页 → tavily extract(advanced) → Apify `johnvc/google-scholar-api` actor，README "Key-gated Sources" 表）。i10-index 虽是 GS 指标，但 OpenAlex 同样计算（实测 697），无需 GS。

## scientific-agent-skills 免费学术源盘点

该仓库（v2.68，165 skills）的 **paper-lookup** skill 封装 **18 个免费学术 API**，其选路指南与 kimi scholar 逐项对得上：

- **多学科索引**：OpenAlex（250M+ works，作者/机构/引用）、Crossref（150M+ DOI）、Semantic Scholar（200M+，引用图/AI TLDR/推荐）、OpenCitations（开放引用边）、PubTator3
- **生物医学**：PubMed、PMC、Europe PMC（全文关键词检索 + 预印本）
- **预印本**：arXiv、bioRxiv、medRxiv
- **OA 全文**：CORE、Unpaywall、DOAJ
- **仓储**：Zenodo、Figshare、BioStudies、ROR
- 选路指南原文：*"Citation graph (who cites whom) → Semantic Scholar | OpenAlex, Europe PMC, OpenCitations"*；*"Author overview with citation metrics → Semantic Scholar + OpenAlex"* —— **正是 kimi scholar 两个 API 的免费官方等价物**
- keyless 范围标注：Europe PMC 完全无 key、Crossref mailto polite pool、OpenAlex 推荐 key、S2 免费 key（匿名池易 429，实测复现）
- 另有 Paperclip（~11M 全文论文 + 217K 监管文档的只读虚拟文件系统）、Exa Search（学术神经检索）、database-lookup（78 个公共数据库）—— 全部超出 kimi scholar 的能力面

**kimi scholar 无独有能力：** 无引用上下文（S2 `contexts` 字段免费有）、无全文片段（EuropePMC/CORE 免费）、无作者消歧 API（OpenAlex 内建实体消歧 + 概率匹配机构）。

## 额度与延迟账

- 每次走 kimi `call_data_source_tool` 真实消耗额度；论文检索高频，摘除后归零。
- kimi 路径 = LLM 工具调用 → cliproxy → kimi scholar 服务 → 返回；OpenAlex 免 key 直连（实测 <1s 响应）延迟与可控性更优，且无 GS 反爬风险（kimi 作为 GS 镜像本身受上游反爬约束）。

## 裁决

**摘。** 2 个 API 全部有已实测验证的免 key 等价物（OpenAlex 一家即全覆盖），Google Scholar 独有索引用户自有 google_scholar 链已抓，SAS paper-lookup 18 个免费 API 佐证生态成熟；kimi 侧零独有能力，只有额度成本、延迟与上游反爬不确定性。
