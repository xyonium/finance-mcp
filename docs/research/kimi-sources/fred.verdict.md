# fred 裁决：摘

**裁决：摘**（从 kimi 通路摘除；官方 FRED API 完全免费、key 只需 5 分钟注册即可得、120 req/min 额度宽裕，本仓库 alphavantage 宏观面已覆盖全部 8 个常用指标，且 kimi fred 在本仓库的 call 路径因 `file_path` 参数冲突实测 100% 失败——与 R3/R9 同款死代码）。

> 评估日期：2026-09-13 ｜ 对照：`docs/research/kimi-sources/fred.md`（describe dump，2 个 API，2,790 B）vs 官方 FRED REST（live 实测）+ 本仓库 `providers/alphavantage.py` ECONOMIC_INDICATORS 8 指标。

## 1. kimi 侧现状（2 个 API）

| API | 功能 | 备注 |
|---|---|---|
| `fred_search` | 按 keyword 搜官方 FRED 序列元数据；空 keyword 返回**内置 10 个热门序列目录**（GDPC1 等，`bundled-v1` 目录，非全库搜索） | live 验证 2026-09-13 |
| `fred_query` | 按 `id`（如 GDPC1）或 `keyword` 查观测值，落 CSV + 预览 | 参数面完整：frequency（d/w/m/q/a…）、units（lin/pch/log…）、aggregation_method、realtime_start/end、vintage_dates、output_type 1-4（官方全量参数透传） |

describe 文档自述："FRED_API_KEY is read only from server configuration"——即 key 由 kimi 服务器持有，用户侧免 key。这是 kimi fred 唯一的理论优势。

## 2. 关键实测：本仓库 call 路径 100% 死代码（第三个 R3/R9 同款）

`KimiProvider.call()`（`providers/kimi.py:477-484`）对**所有**源无条件注入落盘参数：

```python
merged = dict(params or {})
if not merged.get("file_path"):
    merged["file_path"] = f"{settings.kimi_files_dir}/{source}_{api}_{uuid4().hex[:8]}.csv"
```

而 fred 上游严格校验参数名，且它的形参是 **`filepath`（无下划线）**，与注入的 `file_path`（有下划线）不匹配。实测（2026-09-13，live）：

```
p.call('fred', 'fred_query',  {'id': 'FEDFUNDS', 'filepath': '/tmp/fedfunds.csv', 'limit': 10})
→ UpstreamError PARAMETER_ERROR - Unexpected parameter(s): file_path

p.call('fred', 'fred_search', {'keyword': 'unemployment', 'limit': 5})
→ UpstreamError PARAMETER_ERROR - Unexpected parameter(s): file_path
```

两个 API 全灭。绕过 `call()` 直调上游 `_invoke` 则正常出数：

```
_invoke('call_data_source_tool', {... 'params': {'id': 'FEDFUNDS', 'filepath': '/tmp/fedfunds.csv', 'limit': 10}})
→ is_success: true；FEDFUNDS 1954-07 起 866 条观测，CSV 落盘，realtime 2026-09-13
```

即：上游 wrap 本身能用（key 在服务器侧），但**本仓库工具面今天没有任何 fred 调用能成功**——与 R3（world_bank）、R9（imf）完全相同的死代码形态。即使想留，也要先修 provider 的 `file_path` 注入逻辑（按源适配参数名），收益却只省一个 5 分钟的免费注册。

## 3. 官方 FRED API 实测与获取成本

### 3.1 免 key 请求的形状（live，2026-09-13）

```
GET https://api.stlouisfed.org/fred/series/observations?series_id=GNPCA&api_key=YOUR_KEY_HERE&file_type=json
HTTP 400
{"error_code":400,"error_message":"Bad Request. The value for variable api_key is not a 32
 character alpha-numeric lower-case string. Read https://fred.stlouisfed.org/docs/api/api_key.html"}
```

确认：**免费但 signup 门禁**（32 位 key 必填，无 key 一律 400）。

### 3.2 key 获取成本（官方文档核验）

- 注册 `fredaccount.stlouisfed.org` 账号 → 申请 key，即时发放、无需审批、每应用可申多个、**永久免费**；
- 速率限制：**120 requests/minute**（超限 429），对宏观序列（最快日更）绰绰有余；
- ToS 要求（写原生 provider 时注意）：应用需展示声明 "This product uses the FRED® API but is not endorsed or certified by the Federal Reserve Bank of St. Louis."；不得以 FRED 命名 hostname、不得用官方 logo。

**结论：key 是 trivially obtainable（5 分钟、真免费、120 req/min 宽裕）——按 kimi-dedup 判据直接落入"摘"档。**

## 4. 与本仓库 alphavantage 的交集映射

`tools/macro.py get_economic_data`（R13 后 alphavantage 直连）8 个指标全部是 FRED 底层序列，kimi fred 逐一对得上：

| alphavantage indicator | AV function | FRED 等价序列 | kimi fred 可取 |
|---|---|---|---|
| GDP | REAL_GDP | GDPC1 | ✅ id=GDPC1 |
| CPI | CPI | CPIAUCSL | ✅ |
| INFLATION | INFLATION | CPIAUCSL 增速 | ✅ |
| UNEMPLOYMENT | UNEMPLOYMENT | UNRATE | ✅ |
| FEDERAL_FUNDS_RATE | FEDERAL_FUNDS_RATE | FEDFUNDS | ✅（live 验证 866 条） |
| TREASURY_YIELD_10Y | TREASURY_YIELD 10year | DGS10 | ✅ |
| RETAIL_SALES | RETAIL_SALES | RSAFS | ✅ |
| NONFARM_PAYROLL | NONFARM_PAYROLL | PAYEMS | ✅ |

**交集 = 8/8（常用宏观指标 100% 重叠）**。kimi fred 的独有增量只有：任意序列 id（FRED 全库 80 万+ 序列，如 DGS2/T10YIE/M2/SP500）、`fred_search` 元搜索、`vintage_dates`/ALFRED 实时史、`output_type` 2/4。但这一切**官方 FRED 免费 key 全部原生提供**，且无 kimi 额度消耗、无 cliproxy 依赖。

另一动机：AV 免费档日配额 ~25 次，宏观调用在吃 AV 配额。将来若需长尾 FRED 序列（超出 8 指标面），正途是写原生 `providers/fred.py`（一个 `FRED_API_KEY` 设置项 + series/observations 两个端点），把宏观流量从 AV 迁去——**不是**保留 kimi 的付费代理。

## 5. 裁决理由（kimi-dedup 判据）

1. **官方免费 API 存在**：免数据费，仅 5 分钟注册门禁，120 req/min 远超宏观场景需求。
2. **覆盖 100%**：alphavantage 8 指标面 8/8 重叠；长尾序列官方直连同样覆盖（且比 kimi 的 bundled 10 序列目录更全）。
3. **本仓库路由死代码**：`file_path` vs `filepath` 参数名冲突致 fred 两 API 在 `call()` 路径全灭（live 实测），摘除无任何功能损失——今天零调用经 kimi fred 出数。
4. **kimi 唯一卖点（服务器持 key、用户免注册）价值 ≈ 0**：换来的代价是 cliproxy 额度消耗、CSV 松解析、上游可用性依赖；而官方 key 成本仅 5 分钟一次性注册。
5. **不在 KNOWN_SOURCES 种子表**（12 源里无 fred），只能经 R14 probe-on-first-sight 被撞见——摘除成本 = 一行 DISCOURAGED（同 ifind R15 / pubchem R16 先例）。

## 6. 摘除涉及面（供后续 PR）

- `src/unified_finance_mcp/providers/kimi.py`：`DISCOURAGED_SOURCES` 加一行
  `"fred": "R17 摘 — 官方 FRED API 免费仅 5 分钟注册（120 req/min），AV 8 宏观指标 100% 重叠，且 call 路径 file_path 参数冲突全灭"`。
  无需 `SOURCE_ALLOWED_API_PREFIXES` 条目（整源摘）。
- 无路由/工具面改动：`tools/macro.py` 已是 alphavantage 直连（R13），`KIMI_MACRO_CANDIDATES` 已删；测试无 fred 断言。
- 附带记录（不修，属通用卫生）：`KimiProvider.call` 的 `file_path` 自动注入对严格校验参数名的源会全灭（fred 即首例）——若将来引入此类源需按源适配注入名。
- 远期（独立 PR，非本次）：`providers/fred.py` 原生 provider（settings 加 `FRED_API_KEY`，系列端点 series/observations + search），承接 AV 之外的 FRED 长尾序列并分流 AV 日配额。
