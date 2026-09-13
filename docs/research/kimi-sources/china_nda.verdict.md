# china_nda — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/china_nda.md`（describe dump，4 API）vs 国家数据局登记平台实测（curl 直连，零 key）

## 结论

**摘。** kimi china_nda 是国家数据局公共数据登记平台（sjdj.nda.gov.cn）+ 13 个省级开放数据目录的薄包装。核心 API `china_nda_registry_search` 底层就是该站一个免鉴权公开 JSON 接口，本次实测直通；`china_nda_registry_access` / `china_nda_province_search` 是目录检索与访问指引，均无数据增值。唯一"能力"是 CSV 落地与参数校验——标准客户端卫生，不构成 gap。

## 1. kimi API → 官方免费端点对照

| kimi API | 官方/免费等价（2026-09-13 实测） |
|---|---|
| `china_nda_registry_search` | `POST https://sjdj.nda.gov.cn/register/dataassets/publicityInfo/queryPublicityDataAssets`（JSON body `{"pageNum":1,"pageSize":2}`）→ **200**，`total: 324,373` 条已登记公共数据资源，含 uuid/名称/登记单位（统一社会信用代码）/公示状态/起止日期 |
| `china_nda_registry_access` | 登记条目自带 `dataRegistType`/`publicityStatus` 字段；访问方式随登记元数据公开，无独立接口必要 |
| `china_nda_province_search` | 省级平台（如北京、上海、广东开放数据平台）各自有公开 portal API；kimi 只封装了 13 省，免费侧覆盖面 ≥ kimi |
| `china_nda_provinces` | 静态 13 行常量表（kimi 实调返回硬编码省份列表） |

## 2. 实测证据（2026-09-13，无任何鉴权头）

- kimi 实调 `china_nda_provinces`：13 省（北京/安徽/福建/江西/山东/湖北/湖南/广东/海南…），type=api。
- 直连 `sjdj.nda.gov.cn`：首页 200（Vue SPA），`/static/index-*.js` bundle 内枚举出 `baseURL:"/register"` + `dataassets/publicityInfo/queryPublicityDataAssets` 等公开路径；POST 实测 **200 / success:true / total 324,373**，字段完整。
- 该接口面向社会公示（"公共数据资源登记"），无登录、无验证码、无速率提示。

## 3. 对比与裁决理由

| 维度 | kimi china_nda | 免费直连 sjdj.nda.gov.cn |
|---|---|---|
| 数据本体 | 同一登记库 | 原始出处 |
| 鉴权/成本 | 每次 call 消耗 kimi 额度 | 免 key 零成本 |
| 覆盖 | 13 省封装 + 国家库 | 国家库全量 + 各省平台自选 |
| 增值 | CSV 化、分页、参数校验 | 无需（约 30 行 httpx 封装） |

- 本 repo 是金融数据 MCP：公共数据资源登记目录与现有 tool 面无路由需求，仅能经 `kimi_datasource call` 显式触发。摘除零影响。
- 按 kimi-dedup 判据"官方免费公开接口 + 包装零数据增值 → 摘"。

## 4. 摘除涉及面

- `DISCOURAGED_SOURCES` 加一行（R18）；无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap）。
