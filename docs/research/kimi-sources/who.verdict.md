# who — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/who.md`（describe dump，2 API）vs WHO GHO Athena OData 实测（零 key）

## 结论

**摘。** kimi who 自陈 "through the official OData API"，即 WHO GHO Athena：`https://ghoapi.azureedge.net/api`。两个 API 的能力 = 该 OData 服务两个 GET：目录检索（`/Indicator?$filter=contains(...)`）与观测取数（`/{IndicatorCode}?$filter=SpatialDim eq 'CHN'...`）。免 key、免注册，OData `$filter/$top/$skip` 原生支持分页与维度过滤，比 kimi 的扁平参数更强。

## 1. kimi API → 官方免费端点对照

| kimi API | 官方 GHO OData 等价（2026-09-13 实测） |
|---|---|
| `who_search(keyword)` | `GET /api/Indicator?$top=N` + `$filter=contains(tolower(IndicatorName),'…')` → **200** 指标目录（kimi 实调 provenance 显示上游请求就是 `Indicator` + `$filter` contains，逐字段同源） |
| `who_query(code/country/year/top)` | `GET /api/{CODE}?$filter=SpatialDim eq 'CHN' and TimeDim eq 2022` → **200**（观测集按指标分 entity set，`TimeDimensionBegin` 过滤年份、`SpatialDim` 过滤国家——kimi 的 country/year 参数就是这两个维度） |

## 2. 实测证据（2026-09-13，无任何鉴权头）

- `GET https://ghoapi.azureedge.net/api/Indicator?$top=1` → **200** `{"IndicatorCode":"ABORTION_ADMISSIONS",...}`（firecrawl 直取，OData minimal metadata）。
- `GET /api/WHOSIS_000001?$filter=SpatialDim eq 'CHN' and TimeDim eq 2022` → **200**（空结果为该维度组合下无 obs——端点、协议、过滤语法均工作）。
- kimi 实调 `who_search keyword=life expectancy` → 返回 `provenance.provider: "WHO Global Health Observatory (GHO) OData API"`、`endpoint: Indicator`、`$filter` 与上述语法完全一致 → 1:1 转发实锤。
- 官方文档：who.int/data/gho/info/gho-odata-api（Athena API examples），免 key 明载。

## 3. 对比与裁决理由

| 维度 | kimi who | 官方 ghoapi.azureedge.net |
|---|---|---|
| 数据本体 | 同一 GHO 库 | 原始出处 |
| 鉴权/成本 | 每次 call 消耗 kimi 额度 | 免 key 零成本 |
| 过滤力 | keyword/code/country/year/top | OData 全语法（维度/时间/聚合维度任意组合） |
| 增值 | CSV 化 | ~30 行 httpx 封装 |

- 本 repo 无公共卫生 tool 面；摘除零影响。与 R15 pubchem/chembl、R17 uniprot/pdb 同一模式：官方免 key 开放 API 的 1:1 转发。
- 按 kimi-dedup 判据 → 摘。

## 4. 摘除涉及面

- `DISCOURAGED_SOURCES` 加一行（R18）；无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap）。
