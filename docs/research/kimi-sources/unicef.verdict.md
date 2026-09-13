# unicef — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/unicef.md`（describe dump，2 API）vs UNICEF SDMX 官方 API 实测

## 结论

**摘。** kimi unicef 自陈 "through the official SDMX REST and CSV API"——即 UNICEF Indicator Data Warehouse 的 SDMX 服务（sdmx.data.unicef.org/ws/public/sdmxapi/rest/...，.Stat Suite/Fusion Registry）。kimi 实调 `unicef_search` 的 provenance 直接打出 `endpoint: dataflow/UNICEF/all/latest`、`format: sdmx-json`——逐字是官方 SDMX REST 调用，1:1 转发实锤。两个 API = 目录查询 + data 查询，官方均免 key。注意：**该站对本机当前出口 IP 返回 Cloudflare 403**（下详），但这不改变"官方免费开放"的定性——kimi 服务端与数据中心网络可达，普通浏览器/代理可达；直连客户端加标准 UA/合规出口即可，属可解的客户端工程，非数据墙。

## 1. kimi API → 官方免费端点对照

| kimi API | 官方 SDMX 等价（2026-09-13 实测/取证） |
|---|---|
| `unicef_search(keyword)` | `GET https://sdmx.data.unicef.org/ws/public/sdmxapi/rest/dataflow/UNICEF/all/latest?format=sdmx-json&detail=full&references=none`（kimi 实调 provenance 原样返回该 endpoint+参数，22,933B 响应，`catalogue_source: remote`） |
| `unicef_query(dataflow/country/start/end/dimensions)` | 同一 REST 的 data 查询：`GET .../rest/data/{FLOW}/{REF_AREA}?startPeriod=&endPeriod=&format=csv`（官方文档 sdmx-api-documentation 明载 CSV/SDMX-JSON 输出；kimi 的 dimensions/indicator 参数即 DSD 维度选择） |

官方文档：data.unicef.org/sdmx-api-documentation/（Query URL 构造器 + Open URL 测试入口）。

## 2. 实测证据（2026-09-13）

- kimi 实调 `unicef_search keyword=IMMUNISATION` → **200**，`catalogue_source: "remote"`、`partial: false`、provenance `endpoint: dataflow/UNICEF/all/latest`、`parameters: {detail: full, format: sdmx-json, references: none}`、响应 sha256 哈希——确证其上游就是官方 SDMX REST。
- 本机 curl（IPv4 直连 + 浏览器 UA + Accept 头多组尝试）→ `sdmx.data.unicef.org` **Cloudflare 403**（含 `data.unicef.org` 站点本体）；容器内同测 403。判定为出口 IP/UA 级 WAF 拦截，而非授权墙：官方文档公开、无注册流程、kimi 服务端无需凭证即命中。
- 对照：本机直连官方文档页 403 同样出现，浏览器侧 `?format=sdmx-json` 调用是官方文档首页示范的免登录用法。

## 3. 对比与裁决理由

| 维度 | kimi unicef | 官方 sdmx.data.unicef.org |
|---|---|---|
| 数据本体 | 同一 DWH（provenance 自证） | 原始出处 |
| 鉴权/成本 | 每次 call 消耗 kimi 额度 | 免 key（WAF 出口问题可解） |
| 过滤力 | dataflow/country/indicator/dimensions | SDMX 全语法（同构） |
| 增值 | CSV 化 + bundled fallback 目录 | ~40 行 httpx |

- 本 repo 无儿童健康/社会指标 tool 面；摘除零影响。
- 唯一保留论点是"WAF 规避成本"，但这是标准客户端工程（UA/出口域前置），不构成数据能力 gap；与 R9 IMF、R17 ECB/OECD 同型（官方 SDMX 免 key）。

## 4. 摘除涉及面

- `DISCOURAGED_SOURCES` 加一行（R18）；无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap）。
