# tianyancha 裁决（kimi-dedup R4）

> 评估对象：kimi datasource `tianyancha`（226 个动态 API + `tianyancha_api_search` 发现 + `tianyancha_company_search` 全称解析）。
> 上游文档：[tianyancha.md](tianyancha.md)（2026-09-13 19:50 dump）。

## 结论：留

中国公司注册数据（工商 + 股东 + 司法 + 股权穿透 + 集团谱系）**不存在免费 API 等价物**；
本 repo 已把 tianyancha 织入两条工具链（`get_company_risk_cn`、`get_ownership` CJK 分支），摘除即断链。
额度成本有界（describe 24h 缓存；单次风险画像 = 1 次 company_search + ≤7 次 api_call），且该场景天然低频（尽调型，非行情轮询）。

## 1. tianyancha 给了什么（226 API 的实际面）

三个入口（上游 doc，见 tianyancha.md）：

| 入口 | 用途 |
|---|---|
| `tianyancha_company_search` | 简称 → 全称/信用代码解析（返回注册号、经营状态、统一社会信用代码、成立日期、注册资本、法人、公司 id、省份等 13 列） |
| `tianyancha_api_search` | 按关键词（"企业基本信息,股东信息" 等）搜索 API 目录，返回 API 名/参数/示例 URL —— 上游改名可自愈 |
| `tianyancha_api_call` | 226 个数据 API 的统一动态调用，结果落 CSV |

`get_company_risk_cn`（`src/unified_finance_mcp/tools/kimi.py`）按 7 个 aspect 扇出，API 名经 live 验证：

| aspect | API（前缀） | 实测返回字段（live CSV 表头） |
|---|---|---|
| profile | 工商信息-企业基本信息 | 60+ 列：regStatus/businessScope/taxNumber/regCapital/actualCapital/industryAll 八级类目/staffNumRange/legalPersonName/creditCode/regInstitute/estiblishTime/companyOrgType/economicFunctionZone/percentileScore… |
| shareholders | 工商信息-企业股东 | cgid/capital（认缴 JSON：金额/币种/缴付日期/percent）/capitalActl（实缴）/ftShareholding/hcgid —— 实测含自然人（马化腾 54.2857%、3528.57 万）与法人股东（ALIBABA GROUP SERVICES LIMITED 100%） |
| executives | 工商信息-主要人员 | name/id/typeJoin（董事长;总经理、董事…）—— 实测马化腾/奚丹/卢山带职务 |
| judicial | 司法风险-法律诉讼 | docType/court/judgeTime/caseNo/caseType/caseReason/casePersons/caseMoney/lawsuitUrl —— 腾讯实测 31–35KB 诉讼文书列表 |
| operation | 经营风险-行政处罚 | departmentName/reason/decisionDate/punishName/punishNumber/pecuniary/attachment —— 实测含处罚机关、法条、罚款 |
| equity_penetration | 工商信息-股权穿透 | 股权穿透/受益所有人链（本轮 7 aspect 中唯一未回数据的 1 个，见下"已知缺口"） |
| related_graph | 工商信息-分支机构 | regStatus/estiblishTime/regCapital/legalPersonName/base —— 实测上海/北京/宝安分公司、已注销杭州办事处均在 |

## 2. 免费对手对比（2026-09 核实）

| 免费/公开渠道 | 工商 | 股东(非上市) | 司法诉讼 | 行政处罚 | 股权穿透 | 集团谱系 | API 可用性 | 结论 |
|---|---|---|---|---|---|---|---|---|
| **gsxt.gov.cn**（官方公示系统） | ✅ 公示口径 | 部分（年报） | 链接跳转 | ✅ | ❌ | ❌ | **无公开 API**（官方确认），滑块/点选验证码墙 | 权威但不可编程接入 |
| **爱企查**（百度免费 web） | ✅ | ✅ | ✅ | ✅ | ✅ | 部分 | 免费仅限 web 手查；官方 API 走付费/聚合市场（幂简等转售），且有限流 | 无免费 API |
| **天眼查/企查查 免费档** | 基础版 ~100–500 次/天，仅基础字段 | ❌ 付费 | ❌ 付费 | ❌ 付费 | ❌ 付费 | ❌ 付费 | 深度数据（司法/变更/知产）= 专业版付费 | 免费档深度远不及 |
| **开源爬虫**（qccspider / webinfo-crawler / company-crawler / businessInfo-api） | 依赖账号 cookie | 同左 | 同左 | 同左 | 同左 | 同左 | 爬虫非 API：2026 反爬为 JA4/TLS 指纹 + 极验 v6 行为验证码 + IP 频控 | 不可稳定依赖，ToS 风险 |
| **akshare**（repo 免费主力） | ❌ | 仅上市股东结构（交易所口径） | ❌ | ❌ | ❌ | ❌ | 面向行情/财报，无工商注册域 | 领域不重叠 |

（gsxt 无 API 与验证码：百度 ailegal 官方问答 + 艺赛旗验证码破解文；天眼查免费 500 次/天仅基础信息、专业版付费：百度云开发者文章；企查查/天眼查 2026 反爬：GitHub nick3keater/jj 文档。）

**判定**：CN 公司"工商+股东+司法+行政处罚+股权穿透+集团谱系"整链，免费面只有两条路 —— 官方 gsxt（无 API、验证码墙）和商业平台 web 免费档（频控+验证码，无官方免费 API）。**没有免费 API parity。**

## 3. repo 内已织入的调用链（摘除断链点）

- `src/unified_finance_mcp/tools/kimi.py` — `get_company_risk_cn`：全称解析 + 7 aspect 扇出 + api_search 自愈（`ASPECT_APIS`/`_probe_aspect`）。
- `src/unified_finance_mcp/tools/ownership.py:52-59` — `get_ownership(kind="major")` 收到 **CJK 公司名**时**优先**走 kimi→tianyancha 股东（统一 A 股链不认裸中文公司名）：摘除即失去"中文公司名→股东"能力。
- `src/unified_finance_mcp/providers/kimi.py:462` — `KimiProvider.shareholders` 直接委托 `get_company_risk_cn(aspects=["shareholders"])`。
- 测试：`tests/test_provider_kimi.py`（banner 前置 saved_files、bare-string doc、files base64 落盘）、`tests/test_tools_kimi.py`（aspect 扇出、api_search 回退、`_first_csv_name` 解析）。

## 4. live 探测证据（2026-09-13，mcpo 容器）

- 探测脚本：`/tmp/kimi_probe_tyc.py`、`/tmp/kimi_live_stage2.py`、`/tmp/kimi_live_full.py`（容器内跑 wheel，密钥已脱敏）。
- 落盘结果：容器 `/tmp/unified_finance_mcp/tianyancha_*.csv` 共 **23 个**（11:38–11:46）——
  - 10 × `company_search`（腾讯/阿里巴巴/腾讯科技，约 3697B，13 列注册信息）
  - 13 × `api_call`，覆盖 6 类 aspect：企业基本信息（2763B，60+ 列）×3、股东（578–728B，认缴/实缴 JSON）×3、主要人员（578B 带职务）×2、法律诉讼（31–35KB 文书列表）×2、行政处罚（5366B 带处罚机关与法条）×1、分支机构（980–2722B）×2。
- `company_search`、`api_call(工商信息-企业基本信息)`、`api_search` 三入口全部成功；`get_company_risk_cn` 7 aspect 中 **6 个各回 1 个 CSV**。

## 5. 已知缺口与额度纪律

- **equity_penetration 未回数**：本轮 7 aspect 中唯一失败项（`工商信息-股权穿透` 前缀 + api_search 回退都没命中可用 API 名）。非摘除理由 —— 其余 6 aspect 已证明数据深度独有；该项留待在 `ASPECT_APIS` 里换成 api_search 实测出的确切 API 名（一次 describe/api_search 的成本）。
- **额度**：describe 24h 缓存；`get_company_risk_cn` 单次 = 1 company_search + ≤7 api_call（漂移才多一次 api_search）。相对 226 API 的面，这是"按需取用"而非全量拉。保持现状即可，无需缩 dispatch。

## 6. 裁决行（供 kimi-dedup.md 汇总）

| source | 免费覆盖 | 裁决 | 证据 |
|---|---|---|---|
| tianyancha | gsxt 无 API+验证码 / 爱企查无免费 API / 天眼查企查查免费档仅基础字段 / 开源爬虫不可稳定依赖 / akshare 无此域 | **留** | R4：本文 §2 矩阵 + §4 live CSV（容器 /tmp/unified_finance_mcp/ 23 文件）+ ownership.py:52 CJK 优先路由 |
