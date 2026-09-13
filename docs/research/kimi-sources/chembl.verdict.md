# chembl — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/chembl.md`（describe dump，4 个 API，4,728 B）vs 官方 EMBL-EBI ChEMBL REST 实测（httpx 直连，零 key）

## 结论

**摘。** kimi chembl 是 EMBL-EBI 官方 ChEMBL REST API 的纯薄包装——其 describe 文档自述 "through the official EMBL-EBI REST API (https://www.ebi.ac.uk/chembl/api/data). Free public API, no key required"。4 个 API 逐一映射到一次免费官方 GET，且 kimi 版本暴露的能力严格小于官方（molecule/target/activity/mechanism 之外官方还有 drug_indication、binding_site、cell_line、document、compound_structural_alert 等数十个资源未包装）。零数据增值。

## 1. kimi chembl 的 4 个 API 与官方端点逐一对应

| kimi API | 官方 ChEMBL REST 等价（实测全部 HTTP 200，零鉴权头） |
|---|---|
| `chembl_search(resource, q, limit, offset)` | `GET /molecule.json?search_parameters__q=imatinib&limit=3`（target/assay 同理） |
| `chembl_get(resource, chembl_id)` | `GET /molecule/CHEMBL25.json`、`/target/CHEMBL1862.json`、`/assay/CHEMBL846551.json` |
| `chembl_activities(molecule_chembl_id 或 target_chembl_id, ...)` | `GET /activity.json?molecule_chembl_id=CHEMBL941`（或 `target_chembl_id=CHEMBL1862`） |
| `chembl_mechanisms(molecule_chembl_id 或 target_chembl_id, ...)` | `GET /mechanism.json?molecule_chembl_id=...`（或 `target_chembl_id=...`） |

## 2. 官方 API 实测证据（2026-09-13，无任何鉴权头）

- `search molecule "imatinib"`：**200**，返回 `molecules` 数组 + 分页 meta，字段与 kimi 描述一致（`molecule_chembl_id` 等）。`search target "ABL1"`、`search assay "kinase"` 同 **200**。
- `get molecule CHEMBL25`：**200**，`pref_name "ASPIRIN"`、`molecule_structures.canonical_smiles CC(=O)Oc1ccccc1C(=O)O`、`max_phase 4`——kimi 描述的全部字段（synonyms/properties/max_phase）原生在官方 JSON 里。
- `get target CHEMBL1862`：**200**，`"Tyrosine-protein kinase ABL1" / SINGLE PROTEIN / Homo sapiens`。`get assay CHEMBL846551`：**200**，`"Inhibition of Abl tyrosine kinase"`。
- `activity?molecule_chembl_id=CHEMBL941`：**200**，样例记录 `target CHEMBL2111414 / IC50 40.0 nM / pchembl_value 7.40`——与 kimi describe 自己举例的数值一字不差（kimi 的 pChEMBL 解释文案即官方口径）。`activity?target_chembl_id=CHEMBL1862` 同 **200**。
- `mechanism`：**200**，全表 7,561 条；`?target_chembl_id=CHEMBL1862` 返回 3 条 ABL 抑制剂 MoA。
- 唯一"坑"：`?molecule_chembl_id=CHEMBL941`（imatinib 游离碱）返回 0 条机制——这不是端点缺陷，是 ChEMBL 数据语义：MoA 记录挂在盐形式上（`CHEMBL1642` IMATINIB MESYLATE 携带 3 条 MoA，"Tyrosine-protein kinase ABL inhibitor / INHIBITOR" 等）。kimi 走同一官方端点，同样解不了这个语义（其 describe 文档只提示"空列表是正常答案"）。

## 3. 对比与裁决理由

| 维度 | kimi chembl | 官方 www.ebi.ac.uk/chembl/api/data |
|---|---|---|
| 数据本体 | 同一 ChEMBL 库（kimi 描述自述 via 官方 REST） | 原始出处 |
| 鉴权/成本 | 走 cliproxy，每次 call 消耗 kimi 额度 + LLM 工具调用跳数 | 免 key、零成本、直连 |
| 覆盖面 | 仅 molecule/target/assay 三资源 + activity + mechanism | 数十个资源全开放（drug_indication、document、cell_line 等）——kimi 是严格子集 |
| 分页 | limit/offset 透传（kimi describe 还贴心解释 page_meta.next 用法） | 官方原生 |

- **零独有数据**：4/4 API 均为一对一官方端点转发，无跨库聚合、无付费内容；反被官方覆盖为子集。
- **零领域路由**：本 repo（finance-mcp）src/ 全量 grep 无任何 chembl/chemistry 引用，不在 `KNOWN_SOURCES` 种子表，也无任何 tool 路由到它——只能经 `kimi_datasource call` 显式触发，每次触发即烧 kimi 额度。
- 唯一注意项是官方"keep request rates moderate"的礼貌速率要求，属客户端卫生，不构成数据 gap。

## 4. 摘除涉及面（供后续 PR）

- `src/unified_finance_mcp/providers/kimi.py`：`DISCOURAGED_SOURCES` 加一行 `"chembl": "R16 摘 — 官方 EMBL-EBI REST 免 key（4/4 API 一对一映射且为严格子集），零数据增值"`（它不在 `KNOWN_SOURCES`，R14 probe-on-first-sight 路径摘除成本 = 一行 DISCOURAGED，同 ifind R15 先例）。
- 无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap 可留）。
