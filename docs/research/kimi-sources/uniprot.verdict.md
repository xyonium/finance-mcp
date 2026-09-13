# uniprot — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/uniprot.md`（describe dump，4 个 API，7,286 B）vs 官方 UniProt REST 实测（httpx 直连，零 key）

## 结论

**摘。** kimi uniprot 是 UniProt 官方 REST（https://rest.uniprot.org）的纯薄包装——其 describe 文档自述 "via the official REST API (https://rest.uniprot.org) ... Free, no API key"。4 个 API 逐一映射到一次免费官方 HTTP 调用，无鉴权、无跨库聚合、无数据增值；kimi 侧仅有的"工作量"是标准客户端卫生（把 Link-header 分页 cursor 合成为 `next_cursor` 字段、异步 ID Mapping job 的 submit→303→poll 轮询），全部是 UniProt 官方帮助文档明载的接入方式，不是数据能力。

## 1. kimi uniprot 的 4 个 API 与官方端点逐一对应

| kimi API | 官方 UniProt REST 等价（实测全部 HTTP 200，零鉴权头） |
|---|---|
| `uniprot_get_entry(accession)` | `GET /uniprotkb/P05067.json` |
| `uniprot_search(query, size, fields, cursor)` | `GET /uniprotkb/search?query=gene:TP53 AND organism_id:9606&size=3&fields=accession,...` |
| `uniprot_idmapping_submit(from, to, ids)` | `POST /idmapping/run`（form body，from=UniProtKB_AC-ID, to=PDB, ids=P04637,P05067） |
| `uniprot_idmapping_result(job_id, size, fields, cursor)` | `GET /idmapping/status/{jobId}`（303 →）`GET /idmapping/results/{jobId}` 轮询 |

## 2. 官方 API 实测证据（2026-09-13，无任何鉴权头）

- `GET /uniprotkb/P05067.json`（APP 蛋白，任务指定验证例）：**200**，`primaryAccession: P05067`，`sequence.length: 770`——单条目全文免费免 key。
- `GET /uniprotkb/search?query=gene:TP53 AND organism_id:9606`：**200**，首页返回 `P04637, K7PPA8, E9PFT5`；响应 `Link` header 携带下一页 cursor——kimi 的 `next_cursor` 只是把这个官方 header 搬进 body，约 5 行代码。
- `POST /idmapping/run`（P04637,P05067 → PDB）：**200**，`{"jobId": "kh397TTdCg"}`；随后 `GET /idmapping/status/kh397TTdCg` → **303** → `GET /idmapping/results/...` → **200**，返回 `P04637 → 1A1U, 1AIE, 1C26, 1DT7 ...`——异步映射全链路免费免 key 打通。
- kimi describe 自述的坑（from/to 数据库名封闭集、`Ensembl_Protein` 不是 `Ensembl_PRO`）只是把官方 ID Mapping 数据库表复述了一遍，不构成增值。

## 3. 对比与裁决理由

| 维度 | kimi uniprot | 官方 rest.uniprot.org |
|---|---|---|
| 数据本体 | 同一 UniProtKB 库（kimi 描述自述 via 官方 REST） | 原始出处 |
| 鉴权/成本 | 走 cliproxy，每次 call 消耗 kimi 额度 + LLM 工具调用跳数 | 免 key、零成本、直连 |
| 分页 | `next_cursor` 合成字段（源自官方 Link header） | Link header（标准 RFC 5988 分页） |
| ID Mapping 异步 | submit + ≤60 s 轮询（官方流程照搬） | 同一流程，httpx follow_redirects 即可 |

- **零独有数据**：4/4 API 均为一对一官方端点转发，无跨库聚合（ID Mapping 的 from/to 跨库转换本身就是 UniProt 官方服务，不是 kimi 聚合）、无付费内容、无缓存增值。
- **零领域路由**：本 repo（finance-mcp）src/ 全量 grep 无任何 uniprot/蛋白质引用，不在 `KNOWN_SOURCES` 种子表，也无任何 tool 路由到它——只能经 `kimi_datasource call` 显式触发，每次触发即烧 kimi 额度。
- kimi 唯一加分项（next_cursor 合成、job 轮询）是标准客户端卫生，按 kimi-dedup 判据"免费官方 API 存在且包装零数据增值 → 摘"，与 R15 pubchem/chembl（同为 EBI/NIH 系官方 REST 免费转发）先例完全一致。

## 4. 摘除涉及面（供后续 PR）

- `src/unified_finance_mcp/providers/kimi.py`：`DISCOURAGED_SOURCES` 加一行 `"uniprot": "R17 摘 — 官方 rest.uniprot.org 免 key（4/4 API 一对一映射），纯客户端卫生无数据增值"`（它不在 `KNOWN_SOURCES`，probe-on-first-sight 路径摘除成本 = 一行 DISCOURAGED，同 pubchem R15 先例）。
- 无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap 可留）。
