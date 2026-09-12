# crypto-cex 接入设计 — CEX 商品/加密 USDT 永续行情进 finance-mcp (v2, TV-first)

## 结论(spike 已验证,另一 agent 发现已证实)

**TradingView 原生通道本身就能取 CEX 商品永续**,只是现 provider 的映射表没接。`tradingview_ta.TA_Handler` 在 **`screener="crypto"`** 下对 `OKX/BITGET/BINANCE` 的 `CLUSDT.P` 直接返回行情 + 技术指标 + 评级 — 宿主实测三家全 OK(见 §1b)。**决定: CEX 侧主通道用 tradingview_ta(零新增依赖),裸 REST(Bitget/Gate/MEXC)只补 TA 给不了的"历史 K 线"和"funding/OI"。不引 ccxt。**

### 1a) Spike 可达性矩阵(裸 REST,2026-09-12)

| 交易所 | 合约 | 宿主 | 容器 | 延迟 | 裸REST评级 |
|---|---|---|---|---|---|
| **Bitget** | CLUSDT | ✅ 4/4 | ✅ | ~0.7s | 首选(K线/funding/OI) |
| **Gate** | CL_USDT | ✅ 4/4 | ✅ | ~0.3s | 次选 |
| **MEXC** | OIL_USDT | ✅ 4/4 | ✅ | 4–8s | 兜底(慢) |
| Binance | CLUSDT | ⚠️ 451(geo) | ✅ | — | 默认不入裸链 |

### 1b) tradingview_ta 实测(宿主,2026-09-12)

`TA_Handler(symbol="CLUSDT.P", exchange=X, screener="crypto")`:

```
exch=OKX     → close=95.62   rating=BUY  ✅
exch=BITGET  → close=95.597  rating=BUY  ✅   ← BITGET 有 CLUSDT.P
exch=BINANCE → close=95.64   rating=BUY  ✅
screener=cfd / america → Exchange or symbol not found  ❌(必须 crypto)
```

单调用返回 91 字段,含 `open/high/low/close/volume/change` + 全技术指标 + `summary`(BUY/SELL)。**唯二缺口: 无历史 K 线序列、无 funding/OI。**

## 架构(v2)

新增 2 个文件,改 4 处,零破坏现有工具。

### 1) `src/unified_finance_mcp/providers/cex.py`(新) — 双通道

`CexProvider(Provider)`, `name="cex"`, `markets=frozenset({"CRYPTO"})`。两条内部路径:

- **TV 通道**(quote/summary/indicators): 复用 `tradingview_ta.TA_Handler`,`anyio.to_thread` 包(sync lib)。需 **`ceX_EXCHANGE → "crypto" screener` 映射**,不复用 `EXCHANGE_TO_TV_SCREENER`(那是股票国家 slug,crypto 要固定 slug)。
- **裸 REST 通道**(kline 历史 / funding / open_interest): 适配表 → `{base_url, native_symbol, paths{candles}, parse}`。Bitget `CLUSDT+productType=USDT-FUTURES`、Gate `CL_USDT`、MEXC `OIL_USDT`。走共享 `http.PoliteClient`(httpx)。

方法(签名对齐现有 provider 形态):
- `async def quote(exchange, logical) -> dict` — TV `open/high/low/close/volume/change` + 加挂裸 ticker 的 `markPrice`。→ `{symbol, price, open, high, low, volume, change, mark, source}`
- `async def kline(exchange, logical, interval, limit) -> list[dict]` — **裸 REST candles**(Bitget→Gate→MEXC failover)。OHLCV rows。
- `async def funding(exchange, logical) / open_interest(...) -> dict` — **裸 REST** Bitget/Gate ticker(fundingRate/holdingAmount → total_size)。TV 不提供。
- `async def summary(exchange, logical, interval) -> dict` — TV `a.summary` + oscillators/moving_averages/indicators(与现 `technicals` 同构)。
- TV 通道 raise → 该 action 回退裸 ticker(仅 quote 可回退;summary 无裸替代→unavailable)。裸 REST 按 `route_and_call` 之类做 bitget→gate→mexc failover。
- availability 恒 `True`(无 key);geo-451/5xx → 单次 `unavailable`。

### 2) `src/unified_finance_mcp/tools/cex.py`(新,容器)

```
cex_market(action, symbol, exchange="bitget", interval="1d", limit=200)
  action ∈ quote | kline | summary | funding | open_interest | exchanges | symbols
```
- `quote` → TV 快照(+mark)
- `kline` → 历史 OHLCV(裸 candles)
- `summary` → TV 评级 + 指标(看技术走势走这)
- `funding` / `open_interest` → 衍生品专属(裸)
- `exchanges` → 启用所清单与健康
- `symbols` → crypto screener 检索 + 裸合约清单,确认名字存在(治幻觉: USOIL→CLUSDT.P / CL=F↔CL 区分)
- 未知 action → 可用列表;容器 never raise → `tool_error(..., source="cex")`
- 注册进 `tools/__init__.py` `ALL_MODULES`, `@mcp.tool(name="cex_market")`

### 3) 符号规范(独立,不碰 `symbols.py`)

**⚠️ 不复用 `parse_symbol`**:`_TV` 无 OKX/BITGET/BINANCE,`OKX:CLUSDT.P` 会被误判成 `market=US` 并经 `EXCHANGE_TO_TV_SCREENER` 落到错误 slug → 必炸(cfd/america 实测 not found)。
- 逻辑名 `CL`/`OIL` + ccxt 风 `CL/USDT:USDT` + 原生 `CLUSDT`/`CL_USDT`/`OIL_USDT` → 归一为 logical,适配表翻各形态。
- `exchange` 参数 ∈ `bitget|okx|binance|gate|mexc`(容器校验),TV 用前三个促、裸用后三个。
- 非法/不存在的 contract → `tool_error(not_found)` + hint 用 `symbols`。

### 4) `symbols.py` / `providers/tradingview.py` 的"零改动"边界

- 只**新增** `providers/cex.py` 内置 crypto-screener 映射,不动 `EXCHANGE_TO_TV_SCREENER` 表现有股票路径。
- 若之后想让通用 `tv_analyze` 也吃 CEX:再议(需给 `_TV` + `EXCHANGE_TO_TV_SCREENER` 加 OKX/BITGET/BINANCE→crypto),本期不做,避免游离耦合。

## 配置(Settings 追加,全 `FINANCE_MCP_*`,无 secret)

| 变量 | 默认 | 说明 |
|---|---|---|
| `FINANCE_MCP_CEX` | `true` | `0` 禁用容器 |
| `FINANCE_MCP_CEX_EXCHANGES` | `bitget,gate,mexc` | 裸 REST 链顺序;`binance` 仅在显式含时启用(geo) |
| `FINANCE_MCP_CEX_PRODUCT` | `USDT-FUTURES` | Bitget productType |
| `FINANCE_MCP_CEX_TV_SCREENER` | `crypto` | crypto 永续 slug(基本固定) |

`.env`/config.json 零新增 key。

## 错误/限流纪律(沿用)

- 裸走 `http.PoliteClient` → per-host gap、Retry-After、429/503→`rate_limited`、451/5xx→`unavailable`、404→`not_found`,与 `errors.py` 一致,落 `source_errors` 形态。
- TV 走 `ProviderError(f"tradingview TA cex: {e}")`。
- 容器层 never raise → `tool_error(f"{type(e).__name__}: ...", source="cex")`。

## 测试(mocked + 一个受控 live)

- `tests/test_provider_cex.py`(全 mocked): respx 模拟 Bitget/Gate/MEXC 裸 JSON → kline/funding/oi 解析正确;符号映射(逻辑名↔各原生)正确;裸 failover(一家 404→next,全挂→not_found);交易所白名单生效。
- `tests/test_tools_cex.py`(mocked): action 分发、未知 action 列表、`interval` 映射、非法 exchange/symbol 的 not_found+hint、never-raise。
- TV 通道(mock `TA_Handler` 或 respx 拦 scanner.tradingview.com): quote/summary 字段提取。
- **live**: 仅 `integration` 标记手动跑(已证连通)。CI 全程 mocked,不 live 调交易所/TV。

## 依赖

`tradingview-ta`(已装,TV 通道)+ `httpx`(已装,裸)。**无新增三方依赖,零 secret。**

## 工作量切分(plan 见 docs/superpowers/plans/)

1. providers/cex.py(双通道)+ Settings + 测试
2. tools/cex.py 容器 + ALL_MODULES + 测试
3. 文档(README/config)+ 反幻觉 docstring(CLUSDT.P ↔ CL=F、永续 vs 交割期货、资金费率语义)
4. lint + pytest + tag v0.1.6
