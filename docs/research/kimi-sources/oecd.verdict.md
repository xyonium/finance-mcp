# oecd — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/oecd.md`（describe dump，2 个 API，2,031 B）vs 官方 OECD SDMX 3.0 REST API（https://sdmx.oecd.org/public/rest/）实测（httpx 直连，零 key）

## 结论

**摘。** kimi oecd 是 OECD Data Explorer 官方 SDMX 3.0 REST API（sdmx.oecd.org/public/rest）的纯薄包装——describe 文档自述 "through the official SDMX 3.0 REST API"。2 个 API 逐一映射到一次免费官方 HTTP 调用，无鉴权、无聚合、无数据增值；kimi 侧仅有的"工作量"是把官方 dataflow+key+period 查询参数收拢成一个扁平函数签名、无 key 时从 DSD 自动拼全 wildcard key、落盘 CSV——均为标准客户端卫生，不是数据能力。且其 `oecd_search` 自述只是 "small bundled catalogue of verified dataflows"——**比官方 1,546 个 dataflow 的完整目录还窄多个数量级**，转发不是增值而是降级。

## 1. kimi oecd 的 2 个 API 与官方端点逐一对应

| kimi API | 官方 OECD SDMX API 等价（实测全部 HTTP 200，零鉴权头） |
|---|---|
| `oecd_search(keyword?)` | `GET sdmx.oecd.org/public/rest/dataflow/all/all/latest`（完整 1,546 flow 目录） |
| `oecd_query(filepath, dataset?, keyword?, key?, start?, end?, last_n_observations?, top?)` | `GET sdmx.oecd.org/public/rest/data/{agency,dataflow,version}/{key}?startPeriod=&endPeriod=` 或 `?lastNObservations=`（官方原生参数） |

参数体系 1:1：`dataset`→URL path 的 `agency,flow,version`（SDMX 3.0 身份语法），`key`→URL path 点分维度段（`*` wildcard，官方原生语法；kimi 的"no key → DSD 全 wildcard"即官方 key 省略行为），`start`/`end`→`startPeriod`/`endPeriod`，`last_n_observations`→`lastNObservations`（仅拼写改写）。CSV 输出即 `Accept: application/vnd.sdmx.data+csv;version=2.0.0`。

## 2. 官方 API 实测证据（2026-09-13，无任何鉴权头）

- dataflow 目录：`GET /public/rest/dataflow/all/all/latest` + `Accept: application/vnd.sdmx.structure+json;version=2.0` → **200**，**1,546 个 dataflow**（JSON 解析实测）：EO 119（Economic Outlook）、QNA（季度国民账户）、SDG、FUA 气候/人口族等全在——kimi 的 bundled catalogue 是其严格子集。
- DSD 维度序：`GET /public/rest/dataflow/OECD.ECO.MAD/DSD_EO@DF_EO/latest?references=all` → **200**，DSD 解析出维度序 REF_AREA.MEASURE.FREQ——kimi 描述的 "official DSD dimension order" 即此官方端点。
- 数据查询（EOF119，wildcard key）：`GET /public/rest/data/OECD.ECO.MAD,DSD_EO@DF_EO,1.0/USA...?lastNObservations=3` + `Accept: application/vnd.sdmx.data+csv;version=2.0.0` → **200**，121,918 B CSV：USA GDPV_USD 2015 价、季度——2025-Q2=22,401,566,746,612.4 … 2025-Q4=22,619,702,518,016.9 USD，含 UNIT_MEASURE/BASE_PER/PRICE_BASE 全属性列。
- 任务原文给的验证例 `OECD.EDA.QNA.DSD_EO,Q_NADC1.PC.TOT.` 404（NoRecordsFound）——系旧版 agency/dataset 写法失效（EDA 已拆为 ECO.MAD 等新 agency），非 API 问题：正确 agency+flow+DSD 维度序实测即通。SDMX 3.0 的 dataflow 身份现形为 `DSD_EO@DF_EO`（DSD@flow 双段语法）。

## 3. 对比与裁决理由

| 维度 | kimi oecd | 官方 sdmx.oecd.org/public/rest |
|---|---|---|
| 数据本体 | 同一 OECD Data Explorer 库（kimi 描述自述上游） | 原始出处 |
| 鉴权/成本 | 走 cliproxy，每次 call 消耗 kimi 额度 + LLM 工具调用跳数 | 免 key、零成本、直连 |
| 目录/检索 | `oecd_search` 仅 bundled 小目录 | 完整 1,546 flow 目录（严格超集） |
| 取数 | 单 dataflow+key 一次 call，`top` 截断 + CSV 落盘 | 同一查询参数，CSV/JSON/XML 全量返回 |
| B2 隐患 | describe 必填参数为 `filepath`，而本仓库 `call()` 注入的是 `file_path`（下划线，providers/kimi.py:513）——与 R15 fred 同款签名错位，若上游同样严格拒绝则两个 API 经 `call()` 全死 | 不适用 |

- **零独有数据**：2/2 API 均为一对一官方端点转发；无跨库聚合、无付费内容、无缓存增值。
- **检索面反而更窄**：bundled catalogue ≪ 官方 1,546 flow；kimi 的 DSD wildcard 兜底就是官方省略 key 的行为，key 里 `*` 通配是 SDMX 3.0 原生语法。
- **零领域路由**：不在 `KNOWN_SOURCES` 种子表，`tools/kimi.py` 无任何 oecd 引用（R13 已删光宏观候选，macro 走 alphavantage 直连）——只能经 `kimi_datasource call` 显式触发，每次触发即烧 kimi 额度。
- 按 kimi-dedup 判据"免费官方 API 存在且包装零数据增值 → 摘"，与 R15 pubchem/chembl、R17 uniprot/pdb、R17 ecb（同为官方免费 SDMX/REST 转发）先例完全一致。

## 4. 摘除涉及面（供后续 PR）

- `src/unified_finance_mcp/providers/kimi.py`：`DISCOURAGED_SOURCES` 中 `"oecd"` 条目已预置（"R17 摘 …（subagent 验证中）"）——验证已落地，去掉"（subagent 验证中）"限定词即可；无需其它改动（不在 `KNOWN_SOURCES`，probe-on-first-sight 路径摘除成本 = 一行 DISCOURAGED，同 pubchem R15 先例）。
- 无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap 可留）。
