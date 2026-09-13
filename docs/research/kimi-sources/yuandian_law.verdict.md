# yuandian_law — 裁决：留（保留）

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/yuandian_law.md` vs 免费中国法律数据源实测（firecrawl + curl，未调用 kimi）

## 结论

**留。** 案例检索（普通 + 权威案例库 + 语义）在免费生态中**没有任何实时可编程替代**；法规检索侧官方免费的 flk.npc.gov.cn 仅是「网站级」免费——已重构为 SPA、无官方文档化 API、匿名调用被 500 + 验证码拦住，不构成 API 级替代，且完全没有语义检索与案例。两个工具（`yd_law_search` / `yd_case_search`）的独有能力占大头，无免费等价物。

## kimi yuandian_law 的 API（2 个工具，10 个 mode）

| 工具 | mode | 底层端点 | 能力 |
|---|---|---|---|
| `yd_law_search` | semantic | /open/law_vector_search | 法律法规**语义检索**（自然语言问题） |
| | ft_keyword | /open/rh_ft_search | **法条级**关键词命中 |
| | fg_keyword | /open/rh_fg_search | 整部法规检索（支持仅按过滤项浏览） |
| | ft_detail | /open/rh_ft_detail | 法条详情（id 或 law_name+article_number） |
| | fg_detail | /open/rh_fg_detail | 法规详情（含附件正文） |
| `yd_case_search` | semantic | /open/case_vector_search | 案例**语义检索** |
| | keyword_pt | /open/rh_ptal_search | 普通案例库关键词检索 |
| | keyword_qw | /open/rh_qwal_search | **权威案例库**（典型案例/参考案例）检索 |
| | detail_pt | /open/rh_case_details?type=ptal | 普通案例详情（id 或案号） |
| | detail_qw | /open/rh_case_details?type=qwal | 权威案例详情 |

独有维度：效力级别/时效性/地域过滤（法规侧），案由/法院层级/行政区划/文书种类/裁判日期区间/**援引法条**（cited_articles，形如「中华人民共和国刑法第二条」）过滤（案例侧），以及法规 + 案例的向量语义检索。

## 免费替代品功能矩阵（实测）

| 能力 | yuandian (kimi) | flk.npc.gov.cn 国家法律法规数据库 | 裁判文书网 wenshu | OpenLaw | 北大法宝 pkulaw | CAIL 数据集 |
|---|---|---|---|---|---|---|
| 法规检索 | ✅ 关键词 + 语义 | ⚠️ 网站内可检索，无官方 API | ❌ | ❌（旧功能已停） | ✅（订阅付费） | ❌ |
| 法条级命中 | ✅ ft_keyword / ft_detail | ⚠️ 详情页粒度，非检索契约 | ❌ | ❌ | ✅（付费） | ❌ |
| 法规语义检索 | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| 普通案例检索（规模） | ✅ keyword_pt + 语义 | ❌（只有法规） | ⚠️ 网站可查，登录 + 验证码 + 反爬，无 API | ❌ 已停止 | ✅（付费） | ❌ 静态快照 |
| 权威/典型案例库 | ✅ keyword_qw | ❌ | ⚠️ 散落专题页，无统一检索 | ❌ | ✅（付费） | ❌ |
| 案例详情全文 | ✅ detail（id/案号） | ❌ | ⚠️ 登录后逐篇 | ❌ | ✅（付费） | 含原文但静态 |
| 程序化 API（免 key 免费） | ✅ 经 kimi 工具 | ❌ 无契约（匿名 500 + 验证码端点） | ❌ | ❌ | ❌ | ❌（下载文件） |

## 实测证据（verified / not verified）

**已验证（2026-09-13 实测）：**
- `https://flk.npc.gov.cn/` 可达（HTTP 200），但整站为 Vue SPA（`/assets/index-Y9B5oxpu.js`），内容全部 JS 渲染。
- 旧公开端点 `GET /api/?type=flfg...` 返回 SPA HTML 壳（非 JSON）；`POST /api/` 返回 **405 Not Allowed**（nginx）。
- 从 JS bundle 中提取到新端点族：`/law-search/search/list`（POST）、`/law-search/search/flfgDetails`（GET）、`/law-search/highSearch/highSearch`、以及 **`/law-search/index/captchaImage`**。
- `POST /law-search/search/list` 匿名调用（3 种 payload 变体：JSON/form、带 cookie + Referer、searchType:2+searchContent）全部返回 `{"msg":"系统异常","code":500}`；`GET /law-search/index/captchaImage` 实测返回 `{"msg":"操作成功","img":"/9j/...JPEG base64..."}` —— **验证码墙在位**。
- `https://wenshu.court.gov.cn/` 可达但首页为登录/注册壳 + 「网站系统升级维护公告」，所有统计数字（文书总量等）JS 渲染为空；搜索无结果页无法匿名访问。
- `https://openlaw.cn/` 直接跳转「用户登录」页；第三方确认其裁判文书检索已停止使用（百度知道问答）。
- pkulaw.com 官网确认商业订阅模式（「免费试用或致电 400-810-8266 成为法宝用户」；高校走 CARSI/IP 登录）。
- CAIL（thunlp/CAIL / china-ai-law-challenge/CAIL）：静态数据集（268 万刑法文书，CAIL2018-Small/Large 等），面向比赛评测，非实时检索服务。
- 公开资料一致佐证裁判文书网反爬：一级/二级验证码、JS 反爬、IP 检测（知乎 Scrapy 实战、CSDN selenium 自动登录等）。

**未能验证（诚实声明）：**
- 未调用 yuandian/kimi 上游（任务要求 no kimi live calls），10 个 mode 的实际返回质量、权威案例库覆盖面、数据新鲜度均**未实测**，仅基于文档。
- flk 未穷尽全部 payload 组合逆向（500 可能部分来自 payload 形状），但「无官方文档化 API + 验证码端点在位 + 匿名 500」已足以判定其**没有可依赖的免费 API 契约**。
- 北大法宝/威科先行/无讼等商业库的付费墙内部覆盖未实测，仅采信官网与公开信息。

## 额度与延迟账

- CN 法律检索在 finance-mcp 场景中属低频（法律尽调/合规分析/案例援引核查），kimi 额度消耗可控——与 arxiv 那类高频纯重复源不同。
- 走 kimi 的代价是延迟（LLM 工具调用 → cliproxy → 元典服务），但换到的是**别处买不到的语料**：付费库之外的唯一可编程法规+案例+语义检索入口。

## 裁决

**留。** 法规侧 flk.npc 名义免费但只是网站级访问（无 API 契约、验证码墙、无语义检索），案例侧（普通 + 权威 + 语义 + 援引法条过滤）免费生态完全空白；`yd_case_search` 全部 mode 与 `yd_law_search` 的 semantic/ft 系 mode 无任何免费替代，整体不可摘除。
