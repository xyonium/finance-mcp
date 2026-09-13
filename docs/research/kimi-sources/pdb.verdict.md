# pdb — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/pdb.md`（describe dump，4 个 API，5,154 B）vs 官方 RCSB PDB Data/Search API 实测（httpx 直连，零 key）

## 结论

**摘。** kimi pdb 是 RCSB PDB 官方 API（Data API https://data.rcsb.org + Search API https://search.rcsb.org）的纯薄包装——其 describe 文档自述 "Free public API, no key required"，并直接给出两个上游 URL。4 个 API 逐一映射到一次免费官方 HTTP 调用，无鉴权、无聚合、无数据增值；kimi 侧仅有的"工作量"是把 Search API 的 POST JSON 组装收窄为一个 attribute+operator 参数对（照搬官方终端节点查询格式），属标准客户端卫生，不是数据能力。

## 1. kimi pdb 的 4 个 API 与官方端点逐一对应

| kimi API | 官方 RCSB API 等价（实测全部 HTTP 200，零鉴权头） |
|---|---|
| `pdb_get_entry(pdb_id)` | `GET data.rcsb.org/rest/v1/core/entry/4HHB` |
| `pdb_get_polymer_entity(pdb_id, entity_id)` | `GET data.rcsb.org/rest/v1/core/polymer_entity/4HHB/1` |
| `pdb_get_ligand(pdb_id, entity_id)` | `GET data.rcsb.org/rest/v1/core/nonpolymer_entity/1STP/2` |
| `pdb_search(attribute, operator, value, size)` | `POST search.rcsb.org/rcsbsearch/v2/query`（terminal/text 节点） |

## 2. 官方 API 实测证据（2026-09-13，无任何鉴权头）

- `GET /rest/v1/core/entry/4HHB`（任务指定验证例）：**200**，`struct.title: THE CRYSTAL STRUCTURE OF HUMAN DEOXYHAEMOGLOBIN AT 1.74 ANGSTROMS RESOLUTION`，`exptl.method: X-RAY DIFFRACTION`，`rcsb_entry_container_identifiers.polymer_entity_ids: ['1','2']`——kimi describe 里 rcsb_entry_container_identifiers 的取值逐字段同源。
- `GET /rest/v1/core/polymer_entity/4HHB/1`：**200**，`rcsb_polymer_entity.pdbx_description: Hemoglobin subunit alpha`。
- `GET /rest/v1/core/nonpolymer_entity/1STP/2`：**200**，`pdbx_entity_nonpoly.name: BIOTIN`（kimi describe 自述的 1STP entity 2 = biotin 例证复现）。
- `POST search.rcsb.org/rcsbsearch/v2/query`（struct.title contains_words "hemoglobin"，rows=3）：**200**，`total_count: 569`，返回 `1A3N, 1IT2, 1OUT`——文本检索免费免 key 打通。
- kimi describe 自述的坑（entity_id 是 1-based 实体号不是 chain id；PDB ID 大小写归一）是 RCSB 官方文档明载的数据模型常识，约 10 行 httpx 客户端代码即覆盖，不构成数据或能力 gap。

## 3. 对比与裁决理由

| 维度 | kimi pdb | 官方 data.rcsb.org / search.rcsb.org |
|---|---|---|
| 数据本体 | 同一 RCSB PDB 库（kimi 描述自述两个上游 URL） | 原始出处 |
| 鉴权/成本 | 走 cliproxy，每次 call 消耗 kimi 额度 + LLM 工具调用跳数 | 免 key、零成本、直连 |
| 检索 | attribute+operator 收窄到 6 运算符、5 个已验证属性 | 完整 Search API（结构化布尔组合、序列/结构motif检索等远超 kimi 暴露面） |
| 实体导航 | entry→container_identifiers→entity 两跳（官方数据模型本身） | 同一模型 |

- **零独有数据**：4/4 API 均为一对一官方端点转发；无跨库聚合（UniProt 交叉引用是 PDB Data API 自带字段，不是 kimi 聚合）、无付费内容、无缓存增值。
- **检索面反而更窄**：kimi pdb_search 只暴露单条件 terminal 查询（一个 attribute + 一个 operator），官方 Search API 支持完整布尔组合与更多检索类型——用 kimi 转发不是增值而是降级。
- **零领域路由**：本 repo（finance-mcp）src/ 全量 grep 无任何 pdb/rcsb/结构生物学引用，不在 `KNOWN_SOURCES` 种子表，也无任何 tool 路由到它——只能经 `kimi_datasource call` 显式触发，每次触发即烧 kimi 额度。
- 按kimi-dedup 判据"免费官方 API 存在且包装零数据增值 → 摘"，与 R15 pubchem/chembl、R17 uniprot（同为官方免费 REST 转发）先例完全一致。

## 4. 摘除涉及面（供后续 PR）

- `src/unified_finance_mcp/providers/kimi.py`：`DISCOURAGED_SOURCES` 加一行 `"pdb": "R17 摘 — 官方 data/search.rcsb.org 免 key（4/4 API 一对一映射），检索面反而比官方窄"`（它不在 `KNOWN_SOURCES`，probe-on-first-sight 路径摘除成本 = 一行 DISCOURAGED，同 pubchem R15 先例）。
- 无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap 可留）。
