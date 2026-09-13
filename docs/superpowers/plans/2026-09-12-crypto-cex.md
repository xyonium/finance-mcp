# crypto-cex USDT 永续行情接入 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 CEX(中心化加密交易所)商品/加密 USDT 永续行情接进 finance-mcp,通过一个 `cex_market` 容器提供 quote/kline/summary/funding/open_interest 等查询。

**Architecture:** 双通道 `CexProvider`(新增 `providers/cex.py`)+ 一个 `cex_market` 容器(新增 `tools/cex.py`)。TradingView `tradingview_ta.TA_Handler`(screener 固定 `crypto`)当 quote/summary 主通道;裸 REST(Bitget→Gate→MEXC failover)补 TA 给不了的历史 K 线、资金费率、持仓量。符号独立于股票 `parse_symbol`,只在本容器内归一。

**Tech Stack:** Python ≥3.10, `tradingview-ta`(已装), `httpx` + 项目自带 `http.PoliteClient`(已装), `anyio`, pytest + respx(mocked,不 live 调交易所)。

**Spec:** `docs/superpowers/specs/2026-09-12-crypto-cex-design.md`

## Global Constraints

- **零新增三方依赖**(TradingView-ta / httpx 已在 dependencies)。
- **零 secret**(公开行情端点,无 API key;`.env`/config.json 不加字段)。
- **crypto 符号不碰 `symbols.py` 的 `parse_symbol`**(`_TV` 无 OKX/BITGET/BINANCE,误入会落到 `market=US` → 必炸)。归一逻辑只在 cex 容器/provider 内部。
- **不动现有股票路径**:`providers/tradingview.py` 的 `EXCHANGE_TO_TV_SCREENER`、`MARKET_TO_TV_SCREENER` 一律不改(那是股票国家 slug)。crypto-screener 映射只放新 provider 里。
- `screener` 恒为 `"crypto"`(`cfd`/`america` 已实测对 CLUSDT.P 返回 "Exchange or symbol not found")。
- 容器 layer **never raise**:一切失败 → `tool_error(..., source="cex")`。
- 测试全 mocked(respx 拦裸 httpx + monkeypatch TA_Handler),CI 不 live 调交易所/TV。
- 错误分类沿用 `errors.py`:429/503→`rate_limited`,451/5xx/network→`unavailable`,404→`not_found`。
- 资产语义警示必须在 docstring:美国商品永续(CLUSDT.P,USDT 计价,带资金费率)≠ 交割期货(CL=F / NYMEX:CL1!)。

---

### Task 1: Settings 追加 crypto-cex 配置键

**Files:**
- Modify: `src/unified_finance_mcp/config.py`(在 `kimi_files_dir` 行后追加)
- Test: `tests/test_config.py`(追加用例)

**Interfaces:**
- Produces: `Settings` 新增 4 个只读字段,后续 Task 2/3 依赖:
  - `cex_enabled: bool`(`FINANCE_MCP_CEX`, 默认 `True`)
  - `cex_exchanges: tuple[str, ...]`(`FINANCE_MCP_CEX_EXCHANGES`, 默认 `("bitget","gate","mexc")`,逗号分隔,小写归一,顺序保留)
  - `cex_product: str`(`FINANCE_MCP_CEX_PRODUCT`, 默认 `"USDT-FUTURES"`)
  - `cex_tv_screener: str`(`FINANCE_MCP_CEX_TV_SCREENER`, 默认 `"crypto"`)

- [ ] **Step 1: 写测试(先失败)**

在 `tests/test_config.py` 尾部追加:

```python
def test_cex_defaults(monkeypatch):
    for k in ("FINANCE_MCP_CEX", "FINANCE_MCP_CEX_EXCHANGES",
              "FINANCE_MCP_CEX_PRODUCT", "FINANCE_MCP_CEX_TV_SCREENER"):
        monkeypatch.delenv(k, raising=False)
    s = get_settings()
    assert s.cex_enabled is True
    assert s.cex_exchanges == ("bitget", "gate", "mexc")
    assert s.cex_product == "USDT-FUTURES"
    assert s.cex_tv_screener == "crypto"


def test_cex_exchanges_parsing_and_disable(monkeypatch):
    monkeypatch.setenv("FINANCE_MCP_CEX_EXCHANGES", "Bitget, BINANCE ,mexc")
    monkeypatch.setenv("FINANCE_MCP_CEX", "0")
    s = get_settings()
    assert s.cex_exchanges == ("bitget", "binance", "mexc")  # lowercased, order kept
    assert s.cex_enabled is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_config.py -k cex -q`
Expected: FAIL (`AttributeError: 'Settings' object has no attribute 'cex_enabled'`)

- [ ] **Step 3: 实现**

在 `Settings` dataclass 末尾(`kimi_files_dir` 之后)追加(复用现成 `_env/_env_bool`):

```python
    cex_enabled: bool = field(default_factory=lambda: _env_bool("FINANCE_MCP_CEX", True))
    cex_exchanges: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            e.strip().lower()
            for e in _env("FINANCE_MCP_CEX_EXCHANGES", "bitget,gate,mexc").split(",")
            if e.strip()))
    cex_product: str = field(
        default_factory=lambda: _env("FINANCE_MCP_CEX_PRODUCT", "USDT-FUTURES"))
    cex_tv_screener: str = field(
        default_factory=lambda: _env("FINANCE_MCP_CEX_TV_SCREENER", "crypto"))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_config.py -q`
Expected: PASS(全部,含既有用例)

- [ ] **Step 5: lint + commit**

```bash
ruff check src/unified_finance_mcp/config.py tests/test_config.py
git add src/unified_finance_mcp/config.py tests/test_config.py
git commit -m "feat(cex): add FINANCE_MCP_CEX* settings keys"
```

---

### Task 2: `providers/cex.py` 双通道 provider

**Files:**
- Create: `src/unified_finance_mcp/providers/cex.py`
- Modify: `src/unified_finance_mcp/providers/__init__.py`(`build_providers` 列表)
- Test: `tests/test_provider_cex.py`

**Interfaces:**
- Consumes: Task 1 的 `Settings.cex_*`;`http.PoliteClient`;`errors.{NotFound,RateLimited,UpstreamError,ProviderError}`;`tradingview_ta.TA_Handler/Interval`
- Produces(后续 Task 3 容器调用):
  - `CexProvider.name == "cex"`;`.markets == frozenset({"CRYPTO"})`
  - `async def quote(exchange: str, logical: str) -> dict` →
    `{"symbol","exchange","price","mark","open","high","low","volume","change","source"}`。TV close 为 price,裸 ticker 提供 mark(Bitget markPrice;拿不到 → `None`)。
  - `async def kline(exchange: str, logical: str, interval: str = "1d", limit: int = 200) -> list[dict]` →
    `[{"date","open","high","low","close","volume"}, ...]`(裸 candles,failover)。
  - `async def funding(exchange: str, logical: str) -> dict` → `{"symbol","funding_rate","source"}`(裸)。
  - `async def open_interest(exchange: str, logical: str) -> dict` → `{"symbol","open_interest","source"}`(裸)。
  - `async def summary(exchange: str, logical: str, interval: str = "1d") -> dict` →
    `{"symbol","exchange","interval","summary","oscillators","moving_averages","indicators","source"}`(与 `TradingViewProvider.technicals` 同构)。
- 符号适配: `normalize_symbol(raw) -> str`(逻辑名) + `_NATIVE[exchange][logical] -> 原生symbol`。

实现骨架(TDD;先写测试,再实现):

- [ ] **Step 1: 写测试(先失败)** 新建 `tests/test_provider_cex.py`:

```python
"""CexProvider: TV-first (monkeypatch TA_Handler) + bare REST failover (respx)."""
import pytest
import respx

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound
from unified_finance_mcp.providers.cex import CexProvider, normalize_symbol


def make_provider(monkeypatch, exchanges=("bitget", "gate", "mexc")):
    monkeypatch.setenv("FINANCE_MCP_CEX_EXCHANGES", ",".join(exchanges))
    return CexProvider(get_settings())


def test_normalize_symbol_variants():
    assert normalize_symbol("CL") == "CL"
    assert normalize_symbol("CLUSDT") == "CL"
    assert normalize_symbol("CL_USDT") == "CL"
    assert normalize_symbol("OIL_USDT") == "CL"      # mexc 别名进同一逻辑名
    assert normalize_symbol("CL/USDT:USDT") == "CL"
    with pytest.raises(NotFound):
        normalize_symbol("USOIL")  # 已知幻觉 → not_found(hint 在容器层)


@respx.mock
async def test_kline_bitget_ok(monkeypatch):
    respx.get("https://api.bitget.com/api/v2/mix/market/candles").respond(
        200, json={"code": "00000", "msg": "success", "data": [
            ["1789142400000", "97.011", "97.571", "95.221", "95.556", "201097.83", "19390959.25"]]})
    p = make_provider(monkeypatch)
    rows = await p.kline("bitget", "CL", interval="1d", limit=1)
    assert rows[0]["close"] == "95.556" and rows[0]["open"] == "97.011"


@respx.mock
async def test_kline_failover_bitget_404_then_gate(monkeypatch):
    respx.get("https://api.bitget.com/api/v2/mix/market/candles").respond(404, json={})
    respx.get("https://api.gateio.ws/api/v4/futures/usdt/candlesticks").respond(
        200, json=[{"t": 1789142400, "o": "97.0", "h": "97.5", "l": "95.2",
                    "c": "95.5", "v": "201097"}])
    p = make_provider(monkeypatch)
    rows = await p.kline("gate", "CL", interval="1d", limit=1)
    assert rows[0]["close"] == "95.5"


async def test_exchange_whitelist(monkeypatch):
    p = make_provider(monkeypatch, exchanges=("bitget",))
    with pytest.raises(NotFound):
        await p.kline("binance", "CL")  # 未启用 → not_found


async def test_quote_tv(monkeypatch):
    fake = type("A", (), {"summary": {"RECOMMENDATION": "BUY"},
                          "oscillators": {}, "moving_averages": {},
                          "indicators": {"close": 95.6, "open": 96.5, "high": 96.6,
                                         "low": 95.2, "volume": 81440.0,
                                         "change": -1.0}})()
    monkeypatch.setattr(
        "unified_finance_mcp.providers.cex._get_analysis",
        lambda exchange, symbol, interval: fake)
    p = make_provider(monkeypatch)
    q = await p.quote("bitget", "CL")
    assert q["price"] == 95.6 and q["source"] == "cex"
```

> 说明: provider 内部 TV 调用收敛到模块级 `_get_analysis(exchange, symbol, interval)`(sync),容 `anyio.to_thread` 包;quote 再并发/顺序拉一次裸 ticker 补 `mark`(失败容忍 `None`,不让裸调用拖垮 quote)。

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_provider_cex.py -q`
Expected: FAIL (`ModuleNotFoundError: unified_finance_mcp.providers.cex`)

- [ ] **Step 3: 实现** 建 `providers/cex.py`,要点:
  - 顶部 `_TV_SCREENER = "crypto"`(读 `settings.cex_tv_screener`);`_INTERVAL` 同 tradingview.py 词表。
  - `_NATIVE = {"bitget": {"CL": "CLUSDT", ...}, "gate": {"CL": "CL_USDT", ...}, "mexc": {"CL": "OIL_USDT", ...}}`;`normalize_symbol` 亦在此。
  - `_get_analysis(exchange, symbol, interval)`:`TA_Handler(symbol=f"{logical}USDT.P", exchange=exchange.upper(), screener="crypto", interval=...)`(商品永续标准后缀 `.P`;币对同理 `BTCUSDT.P`)。
  - `quote`: TV close/open/high/low/volume/change + 裸 ticker 补 mark(可空)。
  - `kline/funding/open_interest`: 按 `settings.cex_exchanges` 顺序 failover;每家 `base_url`+路径 + `PoliteClient.get_json`;解析各家 JSON 形状(spec §1b 钉死)。
  - 错误:404→`NotFound`;429→`RateLimited`;5xx/451→`UpstreamError`;TA 异常→`ProviderError(f"tradingview TA cex: {e}")`。

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_provider_cex.py -q`
Expected: PASS

- [ ] **Step 5: 接入 `build_providers` + 跑全量 provider 测试**

`providers/__init__.py`:`from . import ... cex` + `instances.append(cex.CexProvider(settings))`(仅当 `settings.cex_enabled`)。

```bash
ruff check src/unified_finance_mcp/providers/cex.py src/unified_finance_mcp/providers/__init__.py tests/test_provider_cex.py
pytest -q -m "not integration"
```
Expected: 全 PASS

- [ ] **Step 6: commit**

```bash
git add src/unified_finance_mcp/providers/cex.py src/unified_finance_mcp/providers/__init__.py tests/test_provider_cex.py
git commit -m "feat(cex): CexProvider - TV-first quote/summary + bare REST kline/funding/OI"
```

---

### Task 3: `tools/cex.py` 容器 + 注册

**Files:**
- Create: `src/unified_finance_mcp/tools/cex.py`
- Modify: `src/unified_finance_mcp/tools/__init__.py`(`ALL_MODULES`)
- Test: `tests/test_tools_cex.py`

**Interfaces:**
- Consumes: `providers["cex"]`(Task 2)、`errors.tool_error`、容器 `_clamp_*` 套路(可复刻 containers.py)
- Produces: `@mcp.tool(name="cex_market")` 异步函数
  `cex_market(action, symbol, exchange="bitget", interval="1d", limit=200) -> dict`
  - actions: `quote|kline|summary|funding|open_interest|exchanges|symbols`
  - 未知 action → `tool_error(f"unknown action {action!r}", hint=f"可用 action: {sorted(ACTIONS)}")`
  - 非法 exchange / symbol → `tool_error(not_found, ...)` + hint 用 `symbols`

- [ ] **Step 1: 写测试(先失败)** `tests/test_tools_cex.py`(monkeypatch provider 方法):

```python
import pytest
from unified_finance_mcp.tools import cex as cex_tool


class FakeCex:
    async def quote(self, exchange, logical):
        return {"symbol": logical, "exchange": exchange, "price": 95.6, "source": "cex"}
    async def kline(self, exchange, logical, interval="1d", limit=200):
        return [{"date": "2026-09-11", "open": "97", "high": "97.5",
                 "low": "95.2", "close": "95.5", "volume": "201097"}]
    async def summary(self, exchange, logical, interval="1d"):
        return {"summary": {"RECOMMENDATION": "BUY"}, "source": "cex"}
    async def funding(self, exchange, logical):
        return {"symbol": logical, "funding_rate": "-0.0004", "source": "cex"}
    async def open_interest(self, exchange, logical):
        return {"symbol": logical, "open_interest": "525629", "source": "cex"}


@pytest.fixture
def providers():
    return {"cex": FakeCex()}


async def test_quote_action(providers):
    out = await cex_tool.cex_market("quote", "CL", "bitget", providers=providers)
    assert out["data"]["price"] == 95.6


async def test_unknown_action_lists(providers):
    out = await cex_tool.cex_market("nope", "CL", "bitget", providers=providers)
    assert "error" in out and "quote" in out["hint"]


async def test_bad_exchange(providers):
    out = await cex_tool.cex_market("quote", "CL", "kraken", providers=providers)
    assert "error" in out  # kraken 不在白名单


async def test_bad_symbol_hint(providers):
    out = await cex_tool.cex_market("quote", "USOIL", "bitget", providers=providers)
    assert "error" in out and "symbols" in out["hint"]


async def test_never_raises(providers):
    class Boom:
        async def quote(self, *a): raise RuntimeError("x")
    out = await cex_tool.cex_market("quote", "CL", "bitget",
                                    providers={"cex": Boom()})
    assert "error" in out and out["source"] == "cex"
```

> 注: 让 `cex_market` 接受 `providers` 关键字(默认 `None` → 走模块内 `_PROVIDERS` 注入点)以便测试注入 fake;`register()` 里闭包封装真 providers。

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_tools_cex.py -q`  Expected: FAIL(ModuleNotFound.)

- [ ] **Step 3: 实现** `tools/cex.py`:action 路由表 + `normalize_symbol`/exchange 白名单校验 + `PROVIDERS` 注入点 + `@mcp.tool(name="cex_market")` 裹一层。docstring 用 Task 4 文案(可先占位,Task 4 补全)。注册进 `ALL_MODULES`(append `"cex"`,放 `containers` 之后)。

- [ ] **Step 4: 跑测试确认通过** + lint

```bash
pytest tests/test_tools_cex.py -q
ruff check src/unified_finance_mcp/tools/cex.py tests/test_tools_cex.py
pytest -q -m "not integration"
```
Expected: 全 PASS

- [ ] **Step 5: commit**

```bash
git add src/unified_finance_mcp/tools/cex.py src/unified_finance_mcp/tools/__init__.py tests/test_tools_cex.py
git commit -m "feat(cex): cex_market container (quote/kline/summary/funding/oi)"
```

---

### Task 4: 文档 + 反幻觉措辞 + server instructions

**Files:**
- Modify: `src/unified_finance_mcp/tools/cex.py`(docstring 完整版)
- Modify: `src/unified_finance_mcp/server.py`(`INSTRUCTIONS` 提及 `cex_market`)
- Modify: `README.md`(Tool quick reference + 配置表加 `FINANCE_MCP_CEX*`)

**Interfaces:**
- Consumes: Task 3 容器

**反幻觉 docstring(`cex_market` 完整版,替换 Task 3 占位):**

```
CEX (crypto exchange) USDT-settled perpetual market data: quote / kline /
technical summary / funding / open interest.

action: quote|kline|summary|funding|open_interest|exchanges|symbols.
symbol: a logical name like CL (WTI crude) or OIL, an exchange-native form
(CLUSDT / CL_USDT / OIL_USDT), or ccxt-style "CL/USDT:USDT". exchange:
bitget (default) | okx | binance | gate | mexc (whitelist enforced).

IMPORTANT — do not confuse with deliverable futures:
- CL here is a USDT-settled PERPETUAL (24/7, carries a funding rate), NOT the
  USD deliverable future CL=F (yahoo) or NYMEX:CL1! (TradingView). Pick by need.
- Unsure of the exact symbol? action="symbols" first, then quote.
- funding/open_interest come from the exchange REST (TA has no such fields);
  quote/summary come from TradingView (screener=crypto).
```

- [ ] **Step 1**: 替换 Task 3 占位 docstring 为上面完整版;`server.py` 的 `INSTRUCTIONS` 在 "tv_scan/tv_analyze/egx_market" 句后追加 `cex_market` 简介一行;`README.md` Tool quick reference 表加一行 + 配置表加 4 键。
- [ ] **Step 2**: `pytest -q -m "not integration"` 仍全 PASS(doc-only);`ruff check`。
- [ ] **Step 3**: commit `docs(cex): anti-hallucination docstring + README + instructions`

---

### Task 5: 全量 lint + 测试套件 + 发布

- [ ] **Step 1**: `ruff check .` 与 `pytest -q -m "not integration"` 全绿(≥544 旧 + 新增)。
- [ ] **Step 2**(推前授权): `git push origin HEAD`;`git tag v0.1.6 && git push origin v0.1.6`(触发 PyPI;hatch-vcs tag=version)。
- [ ] **Step 3**:`gh run watch` publish;`gh api /pypi/unified-finance-mcp/json .info.version` 验证 0.1.6。
