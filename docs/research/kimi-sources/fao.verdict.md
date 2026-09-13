# fao — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/fao.md`（describe dump，2 API，7 个 curated 数据集）vs FAOSTAT 官方免费通道实测

## 结论

**摘。** kimi fao 自陈 "Seven explicitly curated FAOSTAT normalized bulk datasets"——即 FAOSTAT 官方 bulk 下载通道（`bulks-faostat.fao.org/production/*.zip`，Normalized CSV）的 7 个白名单子集。kimi 实调 `fao_search` 返回的 `download_url` 直接暴露官方 bulk URL（`https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_All_Data_(Normalized).zip` 等），等价于"给你官方免费 zip 的下载链接 + 客户端解压过滤"。数据本体零增值；过滤是 bounded CSV scan，任何客户端 20 行代码可复刻。

## 1. kimi API → 官方免费端点对照

| kimi API | 官方免费通道（2026-09-13 实测） |
|---|---|
| `fao_search(keyword)` | FAOSTAT bulk 目录（官方页 bulks-faostat.fao.org + FAOSTAT Bulk Download API，apis.io 有 OpenAPI）。kimi 实调返回的 7 条记录即官方 zip 清单，`required_columns` 就是 Normalized CSV 表头 |
| `fao_query(code/area/item/element/year)` | 同一官方 zip（QCL/PP/FS/MK/RF/QP/PE）解压后流式过滤；或 FAOSTAT 公开 REST（faostatservices.fao.org/api/v1，免 key；旧 fenixservices 域名 2026-09 实测已 521 下线，kimi 未提供 API 之外的任何东西） |

curated 7 集 = QCL 作物畜牧产量、PP 生产者价格、FS 食品安全、MK 贸易、RF 农药、QP 牲畜产品、PE 农药使用——全部是 FAOSTAT 免费公开域。

## 2. 实测证据（2026-09-13，无鉴权）

- kimi 实调 `fao_search` → 返回 7 数据集，每条含官方 `download_url`（bulks-faostat.fao.org）与压缩体积（QCL 32.35MB 等）——kimi 自己把免费下载链接打在返回值里。
- `fenixservices.fao.org/faostat/api/v1/...` → **521**（旧 API 已死）；新 API 域名 `faostatservices.fao.org/api/v1` 为官方现行 REST（FAOSTAT Developer Portal）。
- bulk zip 直链官方公开、免 key、无速率注册。

## 3. 对比与裁决理由

| 维度 | kimi fao | 免费侧 |
|---|---|---|
| 数据本体 | 同 7 个官方公开数据集 | 同（官方 bulk zip / REST） |
| 鉴权/成本 | 每次 call 消耗 kimi 额度 + 异步下载等待 | 免 key，一次 zip 下载本地复用 |
| 覆盖 | 7/FAOSTAT 全库（自陈非完整目录） | FAOSTAT 全库免费 |
| 增值 | bounded CSV 过滤 | 20 行 pandas/duckdb |

- 本 repo 无农业 tool 面；摘除零影响。
- 注意：7 集 bulk zip 32MB 级，客户端处理是唯一"工作量"，属标准数据工程，不构成 kimi 独有能力。

## 4. 摘除涉及面

- `DISCOURAGED_SOURCES` 加一行（R18）；无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap）。
