# eurostat 裁决：摘

**裁决：摘**（从 kimi DISCOURAGED_SOURCES 维持摘除定级；Eurostat 官方 dissemination REST API 完全免费、免 key、无鉴权，kimi 侧 2 个 API 只是同一官方端点的薄包装，在本仓库零路由、零测试引用，保留只增加 cliproxy 额度消耗与工具调用延迟）。

## 1. kimi 侧现状（2 个 API + 路由事实）

kimi eurostat 源只暴露 2 个 API（见同目录 `eurostat.md` describe dump，len=1294）：

| API | 功能 | 关键参数 |
|---|---|---|
| `eurostat_search` | 检索/列出一个**小型内置目录**（common datasets），也接受自定义 dataset code | `keyword`（可选，大小写不敏感） |
| `eurostat_query` | 按 keyword 或精确 dataset code 查询观测值，返回 CSV 文件 + 预览 | `filepath`（必填）、`dataset`/`keyword` 二选一、`filters`（维度过滤）、`top`（默认 50） |

describe 文档自述："Eurostat public statistics through the official Statistics REST API in JSON-stat 2.0 format" —— **kimi 自己也承认是官方 REST API 的转发**。

### 路由与引用：零

- `KNOWN_SOURCES`（12 源种子表）：**无 eurostat**（`src/unified_finance_mcp/providers/kimi.py:71-75`）。
- `KIMI_MACRO_CANDIDATES`：R13 已整体移除（`src/unified_finance_mcp/tools/kimi.py:52-56` 注释），macro 链现在走 alphavantage 直连，eurostat 从未有路由。
- 测试：`grep -rn eurostat tests/` 零命中。
- 唯一触点：`DISCOURAGED_SOURCES["eurostat"]` 登记项本身。

即：**今天没有任何数据流经 kimi eurostat 出数，摘除零功能损失。**

### 与 fred 同款的 B2 参数名风险（未实调验证）

`eurostat_query` 的必填参数是 `filepath`（无下划线），而本仓 `KimiProvider.call()` 注入的是 `file_path`（带下划线，`providers/kimi.py:513-515`）。fred 裁决（R15）已实证该错位 + 上游严格拒绝 = 双 API 死代码。eurostat 是同一模式（`eurostat_query` 是唯一必填 `filepath` 的 API），按本任务纪律（describe 之外不做 kimi 调用）未花额度实调验证，但风险结构同款——即使想保留也大概率打不通。

## 2. 官方免费路径实测（免 key，2026-09-13 live）

Eurostat dissemination API（`https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/<dataset>`）**完全无鉴权**：不发送任何 auth 头、无 key、无注册，纯匿名 GET。全部请求走容器内 `httpx.get` 裸调（即本仓未来 provider 的实现成本）。

### 2.1 数据查询（对应 `eurostat_query`）

```
GET https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10_gdp?format=JSON&geo=DE&time=2023&lang=EN
HTTP 200 (JSON-stat 2.0, class=dataset)
label: Gross domestic product (GDP) and main components - annual data
values: 774 个观测（如 2,649,487.5 / 2,913,878.1 —— 德国 2023 各科目 GDP，MIO EUR）

GET .../data/prc_hicp_manr?format=JSON&geo=DE&coicop=CP00&sinceTimePeriod=2025-01
HTTP 200  label: HICP - monthly data (annual rate of change)
values: 2025 年 12 个月全序列 2.8/2.6/2.3/2.2/2.1/2.0/1.8/2.1/2.4/2.3/2.6/2.0

GET .../data/demo_pjan?format=JSON&geo=DE&sex=F&age=TOTAL&time=2023
HTTP 200  label: Population on 1 January by age and sex
values: 42,198,796（德国 2023 年 1 月 1 日总人口——describe 文档示例用的正是这个数据集）
```

维度过滤（geo/sex/age/coicop/time/sinceTimePeriod）全部生效，输出即标准 JSON-stat 2.0（含 label、dimension、value）。

### 2.2 数据集发现（对应 `eurostat_search`）

kimi 的 search 只是搜一个"小型内置目录"；官方侧有全量清单：

```
GET https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT/all/latest
HTTP 200 (application/vnd.sdmx.structure+xml;version=2.1, 37MB)
dataflow 总数: 8156（agencyID=ESTAT）
NAMA_10_GDP / PRC_HICP_MANR / DEMO_PJAN 均在列
```

8156 个 dataflow 对 kimi 内置小目录是数量级压制；keyword 检索客户端对 id/名称做子串过滤即可（JSON-stat 数据响应自带 label 与维度元数据）。注：`catalogue/toc/*` 类 JSON TOC 端点探测均 404（该路径未开放或已迁移），SDMX dataflow 列表是当前可用的官方全量目录通道。

## 3. 字段级对比

| 维度 | kimi eurostat | 官方免费路径 |
|---|---|---|
| 数据本体 | 同一 Eurostat dissemination API（自述转发） | 原始出处 |
| 鉴权/成本 | 走 cliproxy，每次 call 耗 kimi 额度 | 免 key、无鉴权、零成本 |
| 数据集覆盖 | 内置小目录 + 自定义 code | 8156 个 dataflow 全量可查 |
| 单次返回量 | `top` 默认 **50** 条观测上限 | 无上限（nama_10_gdp 单请求 774 值全量返回） |
| 维度过滤 | `filters` 对象 | URL 查询参数（geo/sex/age/coicop/time…，实测生效） |
| 输出 | CSV 落盘 + 预览（经 `_parse_macro_preview` 松解析） | JSON-stat 2.0 干净结构化（version/class/label/value/dimension） |
| 本仓库路由 | 零（无 KNOWN_SOURCES、无 macro 候选、无测试） | 可作未来一等 provider 直连 |

kimi 侧没有任何官方路径缺的能力；反向倒有两处硬伤（top=50 截断、file_path/filepath 参数名错位风险）。

## 4. 裁决理由

按 kimi-dedup 判据"免费覆盖 ≥ 90% 且公开免 key API 存在 → 摘"：

1. **免 key 官方 API 存在且实测稳定**：三个数据集（nama_10_gdp / prc_hicp_manr / demo_pjan）+ 全量 dataflow 目录（8156 个）全部裸 GET 200，零鉴权零注册。
2. **覆盖 = 100%**：kimi 仅有的 2 个 API（search + query）分别被官方 dataflow 列表与 data 端点 1:1 且超额覆盖（8156 vs 小目录；774 值 vs top=50）。
3. **本仓库零路由零测试**：摘除无任何功能损失，只是把 DISCOURAGED 登记从"待验证"转为"已验证"。
4. **B2 风险同款 fred**：`filepath`（上游必填）vs `file_path`（本仓注入）错位，`eurostat_query` 经 `call()` 大概率打不通——保留成本为正、收益趋零。

## 5. 摘除涉及面（供后续 PR）

- 无需任何代码改动：eurostat 本就不在 `KNOWN_SOURCES`、不在 `SOURCE_ALLOWED_API_PREFIXES`、无路由、无测试。
- `src/unified_finance_mcp/providers/kimi.py`：`DISCOURAGED_SOURCES["eurostat"]` 的值去掉"（subagent 验证中）"标记，指向本裁决文件（本次已同步完成）。
- 未来若需欧洲宏观直连，正确做法是新增 eurostat 一等 provider（裸 httpx 即可，无需 key），而非经 kimi 付费代理。
