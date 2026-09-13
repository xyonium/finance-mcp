# ecb — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/ecb.md`（describe dump，2 个 API，1,665 B）vs 官方 ECB Statistical Data Warehouse SDW API（https://data-api.ecb.europa.eu/，SDMX 2.1）实测（httpx 直连，零 key）

## 结论

**摘。** kimi ecb 是 ECB 官方 SDW SDMX API（data-api.ecb.europa.eu）的纯薄包装——describe 文档自述 "through the official ECB SDMX-JSON data service"。2 个 API 逐一映射到一次免费官方 HTTP 调用，无鉴权、无聚合、无数据增值；kimi 侧仅有的"工作量"是把官方 dataflow+key+start/end 查询参数收拢成一个扁平函数签名并落盘 CSV，属标准客户端卫生，不是数据能力。且其 `ecb_search` 自述只是 "phase-one curated dataflow allowlist"——**比官方 214 个 dataflow 的完整目录还窄**，转发不是增值而是降级。

## 1. kimi ecb 的 2 个 API 与官方端点逐一对应

| kimi API | 官方 ECB SDW API 等价（实测全部 HTTP 200，零鉴权头） |
|---|---|
| `ecb_search(keyword?)` | `GET data-api.ecb.europa.eu/service/dataflow/all/all/latest`（完整 214 flow 目录，XML/JSON） |
| `ecb_query(filepath, dataflow?, key?, keyword?, start?, end?, top?)` | `GET data-api.ecb.europa.eu/service/data/{dataflow}/{key}?startPeriod=&endPeriod=&format=csvdata`（或 jsondata） |

参数体系 1:1：`dataflow`→URL path 首段，`key`→URL path 点分维度段（DSD 维度序），`start`/`end`→`startPeriod`/`endPeriod`（官方原生 SDMX 参数），CSV 输出即官方 `format=csvdata`。

## 2. 官方 API 实测证据（2026-09-13，无任何鉴权头）

- 数据查询（任务指定验证例）：`GET /service/data/EXR/D.USD.EUR.SP00.A?startPeriod=2026-01-01&endPeriod=2026-01-31` → **200**：
  - `format=csvdata`：22 行（表头 + 21 个观测日），USD/EUR 欧央行参考汇率 2026-01-02=1.1721 … 2026-01-30=1.1919，含 OBS_STATUS/UNIT/BREAKS 全属性列；
  - `format=jsondata` + `Accept: application/vnd.sdmx.data+json`：**200** `application/vnd.sdmx.data+json;version=1.0.0-wd`，`dataSets[0].series["0:0:0:0:0"].observations` 21 条，`structure.dimensions.series` 解析出 FREQ=D / CURRENCY=USD / CURRENCY_DENOM=EUR / EXR_TYPE=SP00 / EXR_SUFFIX=A——维度标签齐备，无需任何封装。
- dataflow 目录：`GET /service/dataflow/all/all/latest` → **200**，**214 个 dataflow**（XML 解析实测）：EXR（汇率）、BSI（货币金融统计）、MIR（MIR 利率）、FM（金融市场）、ICP（HICP 通胀）、SEC（证券统计）、BLS（银行放贷调查）、CPP（综合信贷）、MFI（货币金融机构名录）、EST/SPF（专业预测者调查）全在——kimi 的 curated allowlist 是其严格子集。
- 实现注记（写官方 provider 时要注意，不是保留 kimi 的理由）：dataflow 目录端点对 `Accept: application/vnd.sdmx.structure+json`（含/不含 version）一律 **406**，`?format=jsondata` 也仍回 XML——目录查询走 XML 解析或改用 data 端点 JSON；数据端点 JSON/CSV 双通道均稳定 200。

## 3. 对比与裁决理由

| 维度 | kimi ecb | 官方 data-api.ecb.europa.eu |
|---|---|---|
| 数据本体 | 同一 ECB SDW 库（kimi 描述自述上游） | 原始出处 |
| 鉴权/成本 | 走 cliproxy，每次 call 消耗 kimi 额度 + LLM 工具调用跳数 | 免 key、零成本、直连 |
| 目录/检索 | `ecb_search` 仅 curated allowlist（phase-one 子集） | 完整 214 flow 目录（严格超集） |
| 取数 | 单 dataflow+key 一次 call，`top` 截断 + CSV 落盘 | 同一查询参数，CSV/JSON/XML 全量返回 |
| B2 隐患 | describe 必填参数为 `filepath`，而本仓库 `call()` 注入的是 `file_path`（下划线，providers/kimi.py:513）——与 R15 fred 同款签名错位，若上游同样严格拒绝则两个 API 经 `call()` 全死 | 不适用 |

- **零独有数据**：2/2 API 均为一对一官方端点转发；无跨库聚合、无付费内容、无缓存增值。
- **检索面反而更窄**：curated allowlist < 官方 214 flow 完整目录；kimi 的"sample key when omitted"只是把官方 DSD 维度序拼 key 的常识预置了一份。
- **零领域路由**：不在 `KNOWN_SOURCES` 种子表，`tools/kimi.py` 无任何 ecb 引用（R13 已删光宏观候选，macro 走 alphavantage 直连）——只能经 `kimi_datasource call` 显式触发，每次触发即烧 kimi 额度。
- 按 kimi-dedup 判据"免费官方 API 存在且包装零数据增值 → 摘"，与 R15 pubchem/chembl、R17 uniprot/pdb（同为官方免费 REST 转发）先例完全一致。

## 4. 摘除涉及面（供后续 PR）

- `src/unified_finance_mcp/providers/kimi.py`：`DISCOURAGED_SOURCES` 中 `"ecb"` 条目已预置（"R17 摘 …（subagent 验证中）"）——验证已落地，去掉"（subagent 验证中）"限定词即可；无需其它改动（不在 `KNOWN_SOURCES`，probe-on-first-sight 路径摘除成本 = 一行 DISCOURAGED，同 pubchem R15 先例）。
- 无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap 可留）。
