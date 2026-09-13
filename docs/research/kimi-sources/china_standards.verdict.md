# china_standards — 裁决：摘（从 kimi 摘除）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/china_standards.md`（describe dump，3 API）vs 四大官方标准平台实测（curl 直连，零 key）

## 结论

**摘。** kimi china_standards 的 4 个 platform（gb/hb/db/tt）一一对应四个官方免费平台：GB→std.samr.gov.cn/openstd.samr.gov.cn、HB→hbba.sacinfo.org.cn、DB→dbba.sacinfo.org.cn、TT→ttbz.org.cn。检索+元数据全部免 key 可直连（本次逐一实测）；全文 PDF 官方仅对在线阅读开放且有登录/验证码护栏，kimi 的 `china_standards_fetch` 自陈"Returns verified access metadata, not clauses"——即 kimi 自己也不给全文内容，与免费侧能力相同。

## 1. kimi API → 官方免费端点对照

| kimi API | 官方免费端点（2026-09-13 实测） |
|---|---|
| `china_standards_search(gb)` | `POST https://std.samr.gov.cn/gb/search/gbQueryPage`（JSON body）→ **200**，`total 79311`，行含 `C_STD_CODE`/`C_C_NAME`/`STATE`（现行/即将实施）/`ISSUE_DATE`/`ACT_DATE`/`id`（即 provider_id）。openstd.samr.gov.cn 同套 `std_list` 页面可按编号/名称检索 |
| `china_standards_search(hb)` | `POST https://hbba.sacinfo.org.cn/stdQueryList`（form）→ **200**（测试 key=铝合金 返回 136 页记录：YS/T 1869-2026 等，含 status/chargeDept/issueDate） |
| `china_standards_search(db)` | `POST https://dbba.sacinfo.org.cn/stdQueryList`（form）→ **200**（1285 页记录：DB61/T 2165-2026 等） |
| `china_standards_search(tt)` | `https://www.ttbz.org.cn/Home/Standard?searchType=2&key=…` → 200（页面有反爬混淆，需渲染或协议级复刻；kimi 亦受"100-record search cap"限制） |
| `china_standards_detail` | 上述各平台详情页/接口同源（std.samr `gbDetailed?id=`、openstd `newGbInfo?hcno=`、sacinfo 详情） |
| `china_standards_fetch` | openstd 全文在线阅读 `/bzgk/gb/review?hcno=` → 200，但 PDF 实体走登录 UAC（uac.sacinfo.org.cn）+ vcode.do 验证码；kimi fetch 仅返回"verified access metadata"——**无全文内容，与免费侧同水位** |

## 2. 实测证据（2026-09-13，无鉴权）

- GB：`gbQueryPage searchText=质量管理体系` → **200**，79,311 条总库，字段含状态与起止日期；`std_list p.p2=GB 4806` → 200 列表页。
- HB：`hbba stdQueryList` → **200** JSON（铝合金 136 页）。
- DB：`dbba stdQueryList` → **200** JSON（绿色 1285 页）。
- TT：search 页 200 但反爬混淆（kimi describe 自陈 TT 有 100 条检索上限，免费侧无此收益）。
- 全文：openstd `review?hcno=` 200，但 `filePath` 为空字符串 + 登录/验证码护栏；推荐性 GB/T 明确不挂全文（版权），强制性 GB 在线阅读也需 UAC 会话。kimi `china_standards_fetch` 不解决此问题（返回的是 access metadata）。

## 3. 对比与裁决理由

| 维度 | kimi china_standards | 免费直连四大平台 |
|---|---|---|
| 检索/元数据 | 同源转发 + 状态归一化 | 同数据（4 个平台全开放） |
| 全文 | metadata only（自陈） | metadata only（同水位） |
| 成本 | 每次 call 消耗 kimi 额度 | 免 key 零成本 |
| 增值 | 4 平台统一 schema、状态归一 | ~80 行 httpx 封装可复刻 |

- 本 repo 是金融数据 MCP：标准检索与现有 tool 面无路由需求；摘除零影响。
- 唯一理论 gap 是"四平台统一检索"，属于薄集成而非数据能力，且本 repo 无该需求场景。

## 4. 摘除涉及面

- `DISCOURAGED_SOURCES` 加一行（R18）；无 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘，无 gap）。
