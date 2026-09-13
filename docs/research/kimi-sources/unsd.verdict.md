# unsd — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/unsd.md`（describe dump，2 API）vs UNdata 官方 SDMX REST 实测（零 key）

## 结论

**摘。** kimi unsd 自陈走 UNdata 的 "experimental ExplorerHandler and DownloadHandler endpoints"——即 data.un.org 的内部 WebForms 端点。但 UNdata 官方对外承诺的通道是 SDMX REST（`https://data.un.org/WS/rest/...`，SDMX-RI/NSI v8.15.1，免 key），本次实测**结构目录与观测数据双双 200**。kimi 的 ZIP/CSV 过滤是对官方 bulk CSV 的客户端处理，数据本体与官方 SDMX/bulk 同源；ExplorerHandler 是非承诺性内部端点，稳定性与契约还不如官方 SDMX。

## 1. kimi API → 官方免费端点对照

| kimi API | 官方免费端点（2026-09-13 实测） |
|---|---|
| `unsd_search(mart/keyword)` | `GET https://data.un.org/WS/rest/dataflow` → **200** SDMX-ML，15 个官方 dataflow（DF_UNDATA_COUNTRYDATA、DF_UNDATA_ENERGY、DF_SDG_GLH、DF_UNDATA_WDI、DF_UNDATA_MDG、NA_MAIN 等）；DataMart 目录另有 `data.un.org/Host.aspx?Content=API` 官方 API 手册（REST/SOAP，免 key） |
| `unsd_query(mart+filter/table/country/year)` | `GET https://data.un.org/WS/rest/data/DF_UNDATA_COUNTRYDATA/all` → **200**，6.8MB SDMX-ML GenericData 观测集；key 层（`POP/tableCode/240` 形式）按 dataflow key 结构取，`?format=sdmx-json` 部分查询 500（NSI 旧版兼容问题，XML 主通道稳定） |

kimi 的 `mart`（POP/ENV…）≈ 官方 `DF_*` dataflow 家族；`filter tableCode:240` ≈ SDMX key 维度；`country/year` ≈ 官方 REF_AREA/TIME_PERIOD 维度过滤。

## 2. 实测证据（2026-09-13，无任何鉴权头）

- `GET data.un.org/WS/rest/dataflow` → **200**，`NSI Web Service v8.15.1.0`，枚举出 15 个 dataflow id。
- `GET data.un.org/WS/rest/data/DF_UNDATA_COUNTRYDATA/all` → **200 / 6,821,621 B** SDMX-ML 观测。
- `GET data.un.org/WS/rest/data/POP/tableCode/240*` 变体 → 500（该 NSI 版本对部分 key-family 路径不稳定），官方稳定形态为 dataflow-id 路径。
- 官方文档：unstats.un.org/unsd/api/（UNSD API Catalogue，自述 powered by Eurostat SDMX-RI）+ SDMX_SDG_API_MANUAL（endpoint `data.un.org/WS`）。

## 3. 对比与裁决理由

| 维度 | kimi unsd | 官方 data.un.org WS |
|---|---|---|
| 数据本体 | 同一 UNdata 库（ExplorerHandler/DownloadHandler） | 同一库的官方 SDMX 通道 |
| 端点契约 | 自陈 "experimental"（内部端点） | 官方承诺 API + 手册 |
| 鉴权/成本 | 每次 call 消耗 kimi 额度 + 下载整个 zip 过滤 | 免 key，SDMX 结构化过滤省带宽 |
| 增值 | bounded CSV 扫描 + 校验 | 30-50 行 httpx + sd Retrofit 客户端 |

- 本 repo 无 UN 统计 tool 面；摘除零影响。
- 结论上 ExplorerHandler 反而是减分项：依赖一个官方标记 experimental 的内部端点，不如直连官方 SDMX 稳。

## 4. 摘除涉及面

- `DISCOURAGED_SOURCES` 加一行（R18）；无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap）。
