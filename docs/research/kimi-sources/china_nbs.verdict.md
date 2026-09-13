# china_nbs — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/china_nbs.md`（describe dump，2 API）vs 国家统计局新版发布库实测（curl 直连，零 key）

## 结论

**摘。** kimi china_nbs 是国家统计局新版"国家数据"发布库（`data.stats.gov.cn/dg/website/publicrelease/web/external/*`，2026-03-27 上线）的薄包装。该 API 家族 2026-03 后被 akshare (#7260)、cnstats 等开源库完整逆向并公开文档化：免 key、仅需浏览器 UA + Referer 两个 header。kimi 两个 API 的全部能力（关键词→指标、目录→GUID、取数）= 2-3 个免费 HTTP 调用。

## 1. kimi API → 官方免费端点对照

| kimi API | 官方免费端点（2026-09-13 实测） |
|---|---|
| `china_nbs_indicators`（keyword/scope/page 检索） | `GET /dg/website/publicrelease/web/external/query?search=<kw>&code=<1|2|3|4|5|6|8>&pagenum=1&pageSize=N` → **200**，`count` + 行（`i_name`/`indic_id`/`cid`/`treeinfo_globalid`/最新 `dt`/`value`） |
| `china_nbs_query`（indicator+region+year+frequency 取数） | `POST /dg/website/publicrelease/web/external/stream/esData`（body: cid/indicatorIds/das/dts/rootId）→ **200**，`{"data":[{"code":"2024YY","values":[{"_name":"国内生产总值","value":"1348066.2",...}]}]}`；dts 支持 `["2015YY-2024YY"]` 区间、月度 `YYYYMM`、季度 `YYYY0QSS`（akshare PR #7260 实测口径） |

wire 细节（免费侧实现要点，非 gap）：
- header 只需 `User-Agent`（浏览器 UA）+ `Referer: https://data.stats.gov.cn/dg/website/page.html`。
- `code` 1/2/3=全国月/季/年，4/5/6=分省月/季/年，8=主要城市年；`das=[{"text":"全国","value":"000000000000"}]`，分省传省代码。
- 旧版 `easyquery.htm` 已被 WAF 拉黑（`reason:UrlACL`），新版 GUID API 是唯一官方通道——kimi 和免费侧用同一通道。

## 2. 实测证据（2026-09-13，无鉴权）

- `query?search=国内生产总值&code=3` → **200**，`count 709`，行含 2025 年值 `1401879.2`（亿元）。
- `stream/esData`（GDP cid=f7fd25aa…，indicatorIds=7dc6a2ee…，dts=["2015YY-2024YY"]）→ **200**，返回 2024 年 `1348066.2`、2023 年（截断展示），字段 `i_showname`/`value`/`da_name`/`du_name`（单位）齐备。
- 省级（code=6）检索返回 `count 172`（rows 需按目录 ID 精确取，与 akshare #7260 注释一致）。
- 开源交叉证据：akshare PR #7260（fix macro_china_nbs 切新版 API）与 cnstats（PyPI `cn-stats`）均已把该 API 家族文档化并生产使用。

## 3. 对比与裁决理由

| 维度 | kimi china_nbs | 免费直连 data.stats.gov.cn 新版发布库 |
|---|---|---|
| 数据本体 | 同一发布库 | 原始出处 |
| 鉴权/成本 | 每次 call 消耗 kimi 额度 | 免 key，仅需 UA+Referer |
| 指标面 | "curated + 目录检索"，粒度同发布库 | 发布库全量（含未进 kimi curated 表的目录） |
| 地区面 | 全国/省/36 城 | 同（同一 API 家族） |
| 增值 | CSV 化 + 年段拆分（CPI/PPI 分段选择） | 客户端 ~50 行逻辑可复刻 |

- 本 repo 已有宏观链（alphavantage 直连 + R15 fred 摘除先例），且 akshare 生态提供 `macro_china_*` 同源实现。kimi 侧零独有数据。
- 按 kimi-dedup 判据 → 摘。

## 4. 摘除涉及面

- `DISCOURAGED_SOURCES` 加一行（R18）；无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap）。
