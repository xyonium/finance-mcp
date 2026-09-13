# pubchem — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/pubchem.md`（describe dump，4 个 API，6,804 B）vs 官方 PUG-REST 实测（httpx 直连，零 key）

## 结论

**摘。** kimi pubchem 是 NIH/NCBI 官方 PUG-REST 的纯薄包装——其 describe 文档自述 "via the official PUG-REST API ... Free, no API key"。4 个 API 逐一映射到一次免费官方 HTTP 调用，无鉴权、无聚合、无数据增值；kimi 侧唯一的"工作量"是标准客户端卫生（SMILES 用 POST form、429/503 退避、ListKey 轮询），全部是官方文档明载的接入方式，不是数据能力。

## 1. kimi pubchem 的 4 个 API 与官方端点逐一对应

| kimi API | 官方 PUG-REST 等价（实测全部 HTTP 200，零鉴权头） |
|---|---|
| `pubchem_to_cids(by, value)` | `GET /rest/pug/compound/name/aspirin/cids/JSON` |
| `pubchem_get_properties(by, value, properties)` | `GET /rest/pug/compound/cid/2244/property/MolecularFormula,MolecularWeight,IUPACName,XLogP,TPSA/JSON` |
| `pubchem_get_synonyms(by, value)` | `GET /rest/pug/compound/name/aspirin/synonyms/JSON` |
| `pubchem_similarity(smiles, threshold, max_records)` | `POST /rest/pug/compound/similarity/smiles/JSON`（form body）→ ListKey 轮询 |

## 2. 官方 API 实测证据（2026-09-13，无任何鉴权头）

- `name→cids`：**200**，`{"IdentifierList": {"CID": [2244]}}`（aspirin）。
- `cid=2244 取属性`：**200**，`MolecularFormula C9H8O4 / MolecularWeight 180.16 / IUPACName 2-acetyloxybenzoic acid / XLogP 1.2 ...`——kimi 默认属性列表逐字段同源。
- `name→synonyms`：**200**，`Synonym` 数组完整（ACETYLSALICYLIC ACID 等）。
- `similarity POST`：**202 + ListKey**（PUG-REST 标准异步模式），随后 `GET /compound/listkey/{key}/cids/JSON` → **200**，返回 `[2244, 4133, 5161, 8361, 8365]`——相似性检索全链路免费免 key 打通。
- kimi describe 自述的坑（服务器不解 URL path 里 percent-encoded 的 `/` `\`、特殊字符 `()=#[]+@/\` 必须走 POST form）在实测中成立，但这正是 **PUG-REST 官方文档明载的标准接入方式**，约 20 行 httpx 客户端代码即覆盖，不构成数据或能力 gap。

## 3. 对比与裁决理由

| 维度 | kimi pubchem | 官方 pubchem.ncbi.nlm.nih.gov/rest/pug |
|---|---|---|
| 数据本体 | 同一 PubChem 库（kimi 描述自述 via PUG-REST） | 原始出处 |
| 鉴权/成本 | 走 cliproxy，每次 call 消耗 kimi 额度 + LLM 工具调用跳数 | 免 key、零成本、直连 |
| 429/503 处理 | 自动重试（≤2 次， honoring Retry-After） | 客户端自实现同样两行；官方动态限速礼仪 |
| SMILES 传输 | POST form（官方推荐方式） | 同一方式 |

- **零独有数据**：4/4 API 均为一对一官方端点转发，无跨库聚合、无付费内容、无缓存增值。
- **零领域路由**：本 repo（finance-mcp）src/ 全量 grep 无任何 chemistry/pubchem 引用，不在 `KNOWN_SOURCES` 种子表，也无任何 tool 路由到它——只能经 `kimi_datasource call` 显式触发，每次触发即烧 kimi 额度。
- kimi 唯一加分项（POST-form SMILES、ListKey 轮询、退避重试）是标准客户端卫生，按 kimi-dedup 判据"免费官方 API 存在且包装零数据增值 → 摘"。

## 4. 摘除涉及面（供后续 PR）

- `src/unified_finance_mcp/providers/kimi.py`：`DISCOURAGED_SOURCES` 加一行 `"pubchem": "R16 摘 — 官方 PUG-REST 免 key（4/4 API 一对一映射），纯客户端卫生无数据增值"`（它不在 `KNOWN_SOURCES`，R14 probe-on-first-sight 路径摘除成本 = 一行 DISCOURAGED，同 ifind R15 先例）。
- 无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap 可留）。
