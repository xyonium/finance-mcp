# unified-finance-mcp 设计文档

日期：2026-09-09
状态：已获用户批准（brainstorming 阶段完成）

## 1. 背景与目标

用户当前通过 mcpo 聚合多个金融 MCP：futu-opend（自建 VIP OpenD 网关）、yfinance、tradingview，另以 streamable HTTP 连接 FMP（Financial Modeling Prep）和 Alpha Vantage。痛点：

- mcpo 链路脆弱（yahoo-finance-mcp 因 wrapper 要求 Python>=3.14.6 而无法加载；底层 `yfinance` 库本身支持 3.10+）
- 工具面割裂，LLM 需要理解 5 个 server 的边界
- FMP / Alpha Vantage 的免费 key 额度小（FMP ~250 次/日，AV ~25 次/日），单 key 容易打满

**目标**：一个统一的金融与商业 MCP server `unified-finance-mcp`（GitHub 仓库名 `finance-mcp`，xyonium 账户，公开，MIT），整合五个数据源，提供：

1. **域统一工具面**——按金融领域组织的跨源工具，`source` 参数可显式指定或 auto 路由
2. **市场感知路由**——按标的市场只调用能覆盖该市场的源，不做无谓的超时等待
3. **key 管理服务化**——本项目保持单纯：单 key + `*_BASE_URL` 环境变量覆盖；多 key 轮询由既有 `api-key-rotator`（Go 服务）统一实现
4. **二级工具披露**——量化回测等次要功能收进容器工具，保持 LLM 可见的工具列表精简明确

非目标：不做交易下单（futu 侧也只挂载只读行情研究工具）；不重新实现 key 轮询代理；不维护 mcpo 兼容。

## 2. 总体架构

FastMCP（官方 `mcp` SDK）+ reach-mcp 式工厂组装 + futu-opend-mcp 式分类工具模块。

```
src/unified_finance_mcp/
  __init__.py
  __main__.py / server.py   # CLI: --transport {stdio,http} --host --port；build_mcp(settings) / build_app(settings)
  config.py                 # frozen dataclass Settings；env 解析用 default_factory（reach-mcp 式）
  http.py                   # PoliteClient：httpx.AsyncClient 包装，每 host 限速 + 429/503 Retry-After + 指数退避
  errors.py                 # {"error", "hint"} 永不死路错误字典；结构化错误信封
  symbols.py                # 符号归一化：futu/yahoo/tv 三种写法 -> (market, per-provider 格式)
  providers/
    base.py                 # Provider 协议 + 注册表 + required_env 可用性 + covers(market) 覆盖声明
    yahoo.py                # yfinance（同步库，anyio.to_thread 包装）
    tradingview.py          # tradingview-ta + tradingview-screener
    fmp.py                  # FMP stable REST（query-param apikey）+ 交易所列表运行时探测
    alphavantage.py         # AV REST；识别 200-body Note/Information 限流标记
    marketaux.py            # marketaux 新闻（并入 get_news）
    futu_bridge.py          # 挂载 futu_opend_mcp 工具；供统一工具内部调用 futu 数据
  tools/
    quote.py / history.py / fundamentals.py / news.py / technicals.py
    screener.py / ownership.py / calendar.py / macro.py / search.py
    containers.py           # tv_scan / tv_analyze / egx_market 容器
    backtest.py             # quant_backtest L2 容器
    diagnostics.py          # get_service_status
tests/                      # 单测全部 mock；integration marker 需真 key/OpenD，CI 排除
docs/superpowers/specs/     # 本设计文档
.github/workflows/ci.yml    # ruff + pytest
.github/workflows/publish.yml  # v* tag -> OIDC trusted publishing -> PyPI
```

**futu 挂载机制**：`import futu_opend_mcp.tools` 会把其 56 个工具注册到它自己的 FastMCP 单例上（注册即导入副作用，无网络连接——OpenD 连接是懒加载的）。`build_mcp` 内遍历 `futu_opend_mcp.tools._base.mcp._tool_manager.list_tools()`，用公开 API `mcp.add_tool(t.fn, name=t.name, description=t.description, annotations=t.annotations)` 转注册到本 server。启动时校验重名：与统一工具冲突的名字跳过并 warn（测试中以不变量保证无重名）。`_tool_manager` 是下划线属性但在 mcp>=1.0 全系稳定存在，用测试钉住。

**传输**：默认 stdio；`--transport http` 时 `mcp.streamable_http_app()` + uvicorn，挂 `/health` 自定义路由返回 `{"status": "ok"}`（reach-mcp 模式）。

## 3. Provider 层

### 3.1 Provider 协议（providers/base.py）

```python
class Provider(Protocol):
    name: str                      # "yahoo" | "tradingview" | "fmp" | "alphavantage" | "marketaux" | "futu"
    required_env: tuple[str, ...]  # 空 tuple = 无需 key
    def available(self) -> bool: ...       # required_env 是否齐全
    def covers(self, market: str) -> bool: ...  # 是否覆盖该市场（见 §4）
```

注册表 `PROVIDERS: dict[str, Provider]`，`get_provider(name)` / `iter_available()`。每个 provider 同时暴露能力标志（`has_history`、`has_fundamentals`、`has_news`、`has_technicals`、`has_screener`…），统一工具据此建路由链。

### 3.2 五个数据源

| Provider | 实现 | 配置 | 市场覆盖（保守静态值） |
|---|---|---|---|
| yahoo | `yfinance` 库（直接依赖，绕开 yahoo-finance-mcp wrapper 的 Python>=3.14.6 限制） | 无 | 全球广泛（含埃及 `.CA` 后缀，免费源 EGX 数据可能滞后） |
| tradingview | `tradingview-ta` + `tradingview-screener` | 无 | 全球股票市场（NASDAQ/NYSE/HKEX/SSE/SZSE/TWSE/BIST/BURSA/EGX…）+ 加密交易所 + 期货（CME/COMEX/NYMEX/CBOT） |
| fmp | FMP stable REST `https://financialmodelingprep.com/stable/...` | `FMP_API_KEY` + `FMP_BASE_URL` | 美国为主 + 部分国际；首次使用调交易所列表端点探测并缓存（TTL 24h）修正 |
| alphavantage | AV REST `https://www.alphavantage.co/query?function=...` | `ALPHAVANTAGE_API_KEY` + `ALPHAVANTAGE_BASE_URL` | 美国股票 + 全球外汇/加密；股票基本面仅美国 |
| marketaux | marketaux REST `https://api.marketaux.com/v1/...` | `MARKETAUX_API_TOKEN` + `MARKETAUX_BASE_URL` | 新闻（按 entity/country 过滤） |
| futu | `futu-opend-mcp` 挂载 + `futu-api` SDK 内部调用 | 沿用 `FUTU_OPEND_HOST/PORT/ENCRYPT/RSA_KEY` | HK/US/SH/SZ/SG/MY/JP |
| kimi | Kimi Datasource REST（自描述 meta 源，见 §3.4） | `KIMI_PROXY_URL`（默认，proxy 容器）或 `KIMI_AUTH_FILE`（cliproxy 凭证）或 `KIMI_ACCESS_TOKEN`（直注）+ `KIMI_BASE_URL` | 天眼查企业数据、wind/iFinD A股深度、世行/IMF/OECD/FRED 宏观、SEC EDGAR、S&P Capital IQ、财新/新华财经新闻、gildata 选股 |

**Alpha Vantage 限流怪癖**：限流时返回 HTTP 200 但 body 含 `{"Note": ...}` 或 `{"Information": ...}`。客户端必须识别该标记并映射为 rate-limited 错误（带 hint："日额度耗尽；明天重置，或配置多 key 走 api-key-rotator"）。

**同步库纪律**（来自 tradingview-mcp issue #91 的教训）：`tradingview_screener` 的 `Query()` 首次调用会懒导入 pandas，在 anyio worker 线程里可能死锁。server 入口必须在主线程 eager import pandas 与 tradingview_screener；所有同步库调用经 `anyio.to_thread.run_sync`。

### 3.3 key 与 rotator 接线

本项目不做多 key 池。三个需要 key 的服务各自只需：

- `FMP_API_KEY` / `FMP_BASE_URL`（默认 `https://financialmodelingprep.com`）
- `ALPHAVANTAGE_API_KEY` / `ALPHAVANTAGE_BASE_URL`（默认 `https://www.alphavantage.co`）
- `MARKETAUX_API_TOKEN` / `MARKETAUX_BASE_URL`（默认 `https://api.marketaux.com`）

指向 rotator 时（如 `FMP_BASE_URL=http://api-key-rotator:8788/fmp`），rotator 按既有语义剥离并替换上游 auth，本项目照常发送单 key（或占位值）即可。

**rotator 侧后续工作**（api-key-rotator 仓库，不属于本 repo）：新增 FMP profile（`AuthQueryParam=apikey`，401/429/402 触发轮换）与 AV profile（`AuthQueryParam=apikey`，429 + 200-body Note/Information 标记触发轮换；AV 无余额端点，套用 exa 模式：每 key 预置日预算、本地递减、UTC 午夜重置）。

**无 key 优雅降级**：provider `available()=False` 时 auto 路由跳过该源；若用户显式 `source="fmp"` 但未配 key，返回 `{"error", "hint": "set FMP_API_KEY or point FMP_BASE_URL at api-key-rotator"}`。

### 3.4 Kimi Datasource（meta 源，自描述接入）

Kimi Datasource 是 Kimi Code 官方数据插件的后端 API（计入用户 199 会员套餐额度，按次计费，只读）。一个端点挂 12+ 个数据源，后端持续扩充（OECD/FRED/财新/新华财经/iFinD/中国标准等陆续上线），因此**客户端必须自描述，不硬编码各源 API**。

**协议**（参考 AGPL 插件 `piexian/astrbot_plugin_kimi_datasource_api` 与官方文档，本项目自写实现，MIT 不受污染）：

```
POST {KIMI_BASE_URL}            # 默认 https://api.kimi.com/coding/v1/tools
Authorization: Bearer {KIMI_ACCESS_TOKEN}
X-Msh-Device-Id / X-Msh-Platform / X-Msh-Version / User-Agent: kimi-datasource/<v>
{"method": <method>, "params": {...}}
```

- `method="get_data_source_desc"`, params `{"name": <source>}` → 返回该源当前 API 文档（Markdown）
- `method="call_data_source_tool"`, params `{"data_source_name", "api_name", "params"}` → 调具体 API；多数 API 要求 `file_path`（结果 CSV + data_preview 文本）
- `method="get_stock_realtime_price"`, params `{"ticker"(≤3), "type", "file_path"}` → 快捷行情
- 已知源：`stock_finance_data yahoo_finance world_bank_open_data tianyancha arxiv scholar yuandian_law wind imf gildata sec_edgar sp_data`（运行时以 describe 实际返回为准；iFinD/财新/新华财经等新源同名接入）

**认证（2026-09-10 用户拍板：独立 proxy 容器为默认；凭证文件/直注为回退）**。官方 changelog 确认 datasource 走 OAuth 凭证（网页 API key 仅覆盖 chat 模型，不能调数据源）。CLIProxyAPI 的 plugin 体系是 translator/provider hooks，不能加任意 HTTP 路由，透传端点方案否决。token 来源按优先级：

- **`KIMI_PROXY_URL`（默认拓扑，用户选定）**：cliproxy stack 新增独立 `kimi-datasource-proxy` 容器（另一项目，不在本 repo），只读挂载 cliproxy auths、复刻 `api.kimi.com/coding/v1/tools` 协议、自己持有并经 cliproxy keeper 刷新凭证。unified-finance-mcp 设 `KIMI_PROXY_URL=http://kimi-datasource-proxy:8788/coding/v1/tools` 指向它，base_url 用该值、**不附 Authorization**（proxy 注入凭证），仍附 X-Msh-* 头。wire 协议与自描述接入与直连完全一致——proxy 仅改 token/base 来源。
- `KIMI_AUTH_FILE`（回退）：直读 cliproxy 的 kimi 凭证 JSON（如 `/mnt/docker/cliproxy/auths/kimi-*.json`，glob 取第一个 `disabled!=true`）。文件含 `access_token/refresh_token/device_id/expired`；每次调用读文件（mtime 缓存 ~1s），用 `access_token` + `device_id`（与 cliproxy 同设备身份）。
- 兜底自刷新（仅凭证文件路径）：`expired` 临近或上游 401 时，先重读文件一次（cliproxy 可能刚刷新）；仍失效则用公开 client_id（`17e5f671-d194-4dfb-9706-5516cb48c098`，Kimi Code CLI 公开 client）调 `POST https://auth.kimi.com/api/oauth/token`（grant_type=refresh_token）自刷新，flock + tmp+rename 原子写回整个 JSON（保留其他字段）。proxy 拓扑下刷新由 proxy/cliproxy 负责，本客户端不做。
- 独立用户（无 cliproxy/proxy）：`KIMI_ACCESS_TOKEN` 直接注入（从本人 `~/.kimi-code/credentials/kimi-code.json` 取，README 说明），无刷新逻辑。
- 本项目**不做** device-code 登录流程（登录在 cliproxy 已完成）。

**两个上游坑**（插件 SKILL.md 明示）：天眼查查询必须企业**全称**（先调其搜索 API 补全）；多数 API 缺省必须传 `file_path`（本项目自动生成 `/tmp/unified_finance_mcp/<场景>_<uuid>.csv`，并把响应 `files` 落盘到同目录）。

**关键响应形态**：`{"is_success", "result": {"user": [{"type":"text","text"}...], "assistant": [...]}, "files": [...]}`——`user` 通道是干净 data_preview，`assistant` 兜底；`is_success=false` 映射为上游错误。

## 4. 符号归一化与市场感知路由

### 4.1 symbols.py

接受三种写法，归一为 `(market, {provider_name: formatted_symbol})`：

| 输入形式 | 例子 | 解析 |
|---|---|---|
| futu 前缀 | `HK.00700` `US.AAPL` `SH.600519` | 前缀映射 market；转 yahoo 格式 `0700.HK`、`AAPL`、`600519.SS` |
| yahoo 后缀 | `0700.HK` `COMI.CA` `600519.SS` | 后缀映射 market（注意 `.CA`=开罗非加拿大；加拿大是 `.TO`/`.V`）；转 futu 格式等 |
| tv 交易所前缀 | `EGX:COMI` `NASDAQ:AAPL` | 交易所映射 market |
| 裸码 | `AAPL` | 默认美国 |

market 用 ISO-ish 短码：`US HK CN SG MY JP TW TR EG ...`，外加资产类 `CRYPTO FX FUTURES`。

### 4.2 路由算法（统一工具的 auto 模式）

```
market = detect(symbol)
candidates = [p for p in PRIORITY_CHAIN[tool_kind]
              if p.available() and p.covers(market) and capability(p, tool_kind)]
if not candidates:
    return {"error": f"no configured source covers market {market}",
            "hint": f"market {market} 可被 {covering_sources(market)} 覆盖；"
                    f"未配置的配置对应 env 即可启用",
            "market": market}
for p in candidates:
    try: return await call(p, ...)          # 每源独立超时（默认 20s）
    except Exception as e: source_errors[p.name] = classify(e)
return {"error": "all candidate sources failed", "source_errors": ..., "hint": ...}
```

要点：**不覆盖该市场的源不发起任何调用**（零超时浪费）；候选为空立即返回并给出可操作的启用提示；全部失败时逐源报告原因（reach-mcp SourceReport / paper-search errors 模式）。

### 4.3 各统一工具的默认优先级链

| 工具 | 链（auto） |
|---|---|
| get_quote | futu（futu 式代码且 OpenD 可达）→ yahoo → fmp → av |
| get_history | futu → yahoo → fmp → av |
| get_company_info | yahoo → fmp → av |
| get_financial_report | fmp → yahoo → av |
| get_news | fmp → av(news_sentiment) → marketaux → yahoo |
| get_technical_indicators | tradingview（评级） / av（50+ 指标库，按 indicator 参数选源） |
| run_screener | tradingview（全市场） → fmp（美股为主） |
| get_ownership | yahoo → fmp(13F/insider) → futu（futu 式代码）；CN 非上市实体回退 kimi(天眼查) |
| get_events_calendar | fmp → av |
| get_economic_data | kimi（世行/IMF/OECD/FRED，自描述发现具体 api_name） → av |
| search_symbols | fmp → av → yahoo |
| quant_backtest | yahoo（数据源） |

## 5. 工具面

### 5.1 统一工具（14 个，全部 `source="auto"` 起步）

| 工具 | 说明 |
|---|---|
| `get_quote(codes: list[str], source="auto")` | 实时快照 |
| `get_history(code, interval="1d", start/end 或 period, source="auto")` | K线/OHLCV |
| `get_company_info(symbol, source="auto")` | 公司档案 |
| `get_financial_report(symbol, statement=income\|balance\|cashflow, period=annual\|quarterly, source="auto")` | 三大报表 |
| `get_news(symbol=None, limit=10, source="auto")` | 新闻+情绪（marketaux 并入） |
| `get_technical_indicators(symbol, indicators="summary", interval="1d", source="auto")` | TA 评级与指标 |
| `run_screener(market, filters=None, limit=25, source="auto")` | 选股筛选 |
| `get_ownership(symbol, kind=major\|institutional\|insider, source="auto")` | 股东/机构/内部人 |
| `get_events_calendar(type=earnings\|dividends\|economic\|ipo, ...)` | 日历类 |
| `get_economic_data(indicator, ...)` | 宏观指标序列（GDP/CPI/利率等） |
| `search_symbols(query, ...)` | 代码检索 |
| `get_company_risk_cn(company, aspects=None, source="auto")` | 中国企业风险/穿透：工商档案、股东、董监高、司法风险、经营风险、股权穿透、关联图谱；aspects 子集可选，默认全量；内部自动「搜索补全全称 → 逐项调天眼查 → 聚合」 |
| `quant_backtest(action, ...)` | 见 §5.3 |
| `get_service_status()` | 各源配置/可用性/覆盖探测诊断 |

### 5.2 容器工具（归不进统一类的 tv 系功能，action 参数切换，docstring 每 action 一句话）

- `tv_scan(action=top_gainers|top_losers|bollinger_squeeze|rating|consecutive_candles|volume_breakout|smart_volume, exchange, timeframe, limit)`
- `tv_analyze(action=summary|coin|candle_pattern|multi_timeframe|volume_confirmation, symbol, exchange, timeframe)`
- `egx_market(action=overview|sector_scan|sector_scanner|index|screener|trade_plan|fibonacci, ...)` —— 后端只走 tradingview；移植成分股/板块静态表（变化慢），**丢弃硬编码市值快照元数据**，改为 `tradingview-screener` 实时计算

### 5.3 二级披露容器 `quant_backtest` 与 `kimi_datasource`

主工具列表里各占一个位置，描述保持精简（"action='help' 获取完整参数文档" / "action='list' 列出全部数据源"）。

`quant_backtest`：

- `action="help"` → 返回全量子功能文档（每个 action 的完整参数表、策略列表、示例）
- `action="run"` → 单策略回测（MA 交叉/RSI/布林等，pandas 实现，数据走 yahoo）
- `action="compare"` → 多策略赛跑
- `action="walk_forward"` → 滚动前推验证

`kimi_datasource`（Kimi meta 源直通，自描述，后端扩源零改动）：

- `action="list"` → 返回已知数据源清单（静态种子 + describe 探测缓存）
- `action="describe", source=<name>` → 返回该源当前 API 文档（含每个 api_name 的参数表），结果缓存 24h
- `action="call", source=<name>, api=<api_name>, params={...}` → 调用具体 API；`file_path` 缺省自动生成，响应 files 落盘并返回路径
- 金融/商业类问题优先经统一工具路由；本容器用于统一工具未覆盖的深度（wind 分钟线、SEC 文件、S&P 一致预期、财新新闻、iFinD、gildata 自然语言选股、法律/学术/标准等非金融域）

### 5.4 futu 挂载（56 个工具原样转注册，不加前缀）

futu-opend-mcp 的工具名与统一工具无冲突（它用 `get_snapshot/get_kline/get_stock_info/get_financial_statements/...`，统一工具用 `get_quote/get_history/get_company_info/get_financial_report/...`）。测试以"工具列表无重名"为不变量钉住；运行时冲突跳过并 warn。

Server `instructions` 引导 LLM：跨市场通用查询优先统一工具；futu 深度数据（窝轮/牛熊/盘口/券商席位/期权链细节）用 futu 专属工具。

## 6. 错误处理约定

- 工具永不抛异常：统一返回 dict；失败为 `{"error": str, "hint": str, ...}`（paper-search 模式）
- auto 路由多源失败：附 `source_errors: {source: reason}`
- HTTP 层（PoliteClient）：429/503 遵守 Retry-After（上限封顶），其余 5xx 与网络错误指数退避，其他 4xx 快速失败并把状态码编进错误消息（供上层做凭证降级判断）
- AV 200-body 限流标记映射为 rate-limited 类错误
- 不在错误消息里回显任何 API key（key 全走 header/query 参数注入点，错误路径统一 scrub）

## 7. 配置汇总

| env | 用途 | 默认 |
|---|---|---|
| `FINANCE_MCP_TRANSPORT` / CLI `--transport` | stdio \| http | stdio |
| `FINANCE_MCP_HOST` / `FINANCE_MCP_PORT` | http 监听 | 127.0.0.1 / 8000 |
| `FINANCE_MCP_REQUEST_TIMEOUT` | 单源超时秒 | 20 |
| `FINANCE_MCP_MAX_RETRIES` | HTTP 重试 | 3 |
| `FMP_API_KEY` / `FMP_BASE_URL` | FMP | 空 / 官方域名 |
| `ALPHAVANTAGE_API_KEY` / `ALPHAVANTAGE_BASE_URL` | AV | 空 / 官方域名 |
| `MARKETAUX_API_TOKEN` / `MARKETAUX_BASE_URL` | marketaux | 空 / 官方域名 |
| `KIMI_AUTH_FILE` / `KIMI_ACCESS_TOKEN` / `KIMI_BASE_URL` | Kimi Datasource | 空（推荐指 cliproxy `auths/kimi-*.json`）/ 空 / `https://api.kimi.com/coding/v1/tools` |
| `FUTU_OPEND_HOST/PORT/ENCRYPT/RSA_KEY` | futu（沿用 futu-opend-mcp 约定） | 127.0.0.1:11111 |

约定（reach-mcp）：server 自身旋钮用 `FINANCE_MCP_*` 前缀，第三方凭证沿用厂商惯例名。

## 8. 打包与 CI/CD

- `pyproject.toml`：hatchling + src-layout；`requires-python=">=3.10"`；dependencies：`mcp[cli]>=1.27`、`httpx>=0.27`、`yfinance>=0.2`、`tradingview-ta>=3.3`、`tradingview-screener>=3.0`、`futu-opend-mcp>=0.1.2`、`uvicorn[standard]>=0.30`、`starlette>=0.37`、`pandas>=2`；extra `dev = [pytest, pytest-asyncio, ruff, respx]`
- `[project.scripts] unified-finance-mcp = "unified_finance_mcp.server:main"`
- `ci.yml`：push/PR → `pip install -e ".[dev]"` → `ruff check .` → `pytest -q -m "not integration"`
- `publish.yml`：`v*` tag → `python -m build` → `pypa/gh-action-pypi-publish@release/v1`（OIDC trusted publishing，`permissions: id-token: write`，无 token）；用户在 PyPI 为 `unified-finance-mcp` 配 pending publisher
- GitHub：`gh repo create xyonium/finance-mcp --public`，MIT LICENSE，初始提交推送 main

## 9. 测试策略

- 全部单测 mock：HTTP 层用 respx/monkeypatch + 罐头 JSON fixtures（AV/FMP/marketaux 各端点取样响应）；yahoo/tv 在库边界 mock；futu 挂载用 stub `_tool_manager` 验证转注册与重名跳过
- 不变量测试：工具列表无重名；每个工具 docstring 非空；`quant_backtest(action="help")` 返回含全部子 action 的文档；`covers()` 矩阵与符号归一化样例（`HK.00700`/`0700.HK`/`COMI.CA`/`EGX:COMI`/`AAPL`）
- `integration` marker：需真 key / 真 OpenD，CI 排除
- `asyncio_mode = "auto"`（pytest-asyncio）

## 10. 明确不做

- 交易/下单功能
- 进程内多 key 池（rotator 的职责）
- FMP/AV 之外的付费数据源（EDGAR/Finnhub/EODHD 等留作未来候选）
- mcpo 兼容层

## 11. 后续工作（本 repo 之外）

- api-key-rotator 新增 FMP / Alpha Vantage profile（§3.3）
- （可选，非必需）CLIProxyAPI 增加 kimi datasource 透传路由；当前方案（直读其凭证文件）已够用
- 用户在 PyPI 配置 `unified-finance-mcp` pending publisher，随后打 `v0.1.0` tag 触发首发
- 用户 docker 的 mcp config 从 5 个 server 换成 1 个 `unified-finance-mcp`（附 README 迁移示例）
- （可选）企查查官方 `agent.qcc.com` MCP 作为独立 provider 接入（用户另购额度后；天眼查已覆盖同类数据）
