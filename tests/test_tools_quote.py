from unittest.mock import AsyncMock

import respx

from unified_finance_mcp.config import (
    DEFAULT_EASTMONEY_HISTORY_BASE_URL,
    DEFAULT_EASTMONEY_QUOTE_BASE_URL,
    get_settings,
)
from unified_finance_mcp.errors import NotFound
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import history as history_mod
from unified_finance_mcp.tools import quote as quote_mod


def _capture(results):
    class FakeMCP:
        def tool(self):
            def deco(fn):
                results[fn.__name__] = fn
                return fn
            return deco
    return FakeMCP()


async def test_get_quote_routes_yahoo_for_egx(monkeypatch):
    providers = build_providers(get_settings())
    providers["yahoo"].quote = AsyncMock(return_value={"price": 80.0, "source": "yahoo"})
    providers["futu"].quote = AsyncMock(side_effect=AssertionError("must not be called"))
    results = {}

    class FakeMCP:
        def tool(self):
            def deco(fn): results[fn.__name__] = fn; return fn
            return deco

    quote_mod.register(FakeMCP(), providers, get_settings())
    out = await results["get_quote"](["COMI.CA"])
    assert out["data"]["COMI.CA"] == {"price": 80.0, "source": "yahoo"}
    providers["futu"].quote.assert_not_called()


async def test_get_quote_bad_symbol_never_raises(monkeypatch):
    # "???bad" does NOT hit the parse-error branch: parse_symbol defaults any
    # unrecognized bare token to market US, so routing runs and every covering
    # candidate is tried. All env-dependent candidates are stubbed to fail, so
    # this pins the routing outcome (all candidates failed -> error dict, never
    # raises) instead of a live upstream 404. futu needs no stub: available()
    # requires a live OpenD TCP probe (loopback-only, none in test env).
    providers = build_providers(get_settings())
    for name in ("yahoo", "fmp", "alphavantage"):
        providers[name].quote = AsyncMock(side_effect=NotFound(f"{name}: no such symbol"))
    results = {}
    quote_mod.register(_capture(results), providers, get_settings())
    out = await results["get_quote"](["???bad"])
    assert "error" in out["data"]["???bad"]


async def test_get_quote_empty_symbol_parse_error(monkeypatch):
    # The other branch: parse_symbol raises, so the error carries the hint and
    # no provider is ever called ("" -> ValueError("empty symbol")).
    providers = build_providers(get_settings())
    providers["yahoo"].quote = AsyncMock(side_effect=AssertionError("must not be called"))
    results = {}
    quote_mod.register(_capture(results), providers, get_settings())
    out = await results["get_quote"]([""])
    assert "error" in out["data"][""] and out["data"][""]["hint"]
    providers["yahoo"].quote.assert_not_called()


async def test_get_history_returns_bars():
    providers = build_providers(get_settings())
    bars = [{"date": "2026-01-02", "close": 1.5}]
    providers["yahoo"].history = AsyncMock(return_value=bars)
    results = {}
    history_mod.register(_capture(results), providers, get_settings())
    out = await results["get_history"]("COMI.CA", "1d", "2026-01-01", "2026-01-31")
    assert out == {"data": bars}


async def test_get_history_bad_symbol_never_raises():
    # Same non-parsing input as get_quote: routing runs, every env-dependent
    # candidate is stubbed to fail, and the error must surface at the TOP level
    # (not nested under "data") — the T11-T13 error convention. futu needs no
    # stub (available() needs a live OpenD probe).
    providers = build_providers(get_settings())
    for name in ("yahoo", "fmp", "alphavantage"):
        providers[name].history = AsyncMock(side_effect=NotFound(f"{name}: no such symbol"))
    results = {}
    history_mod.register(_capture(results), providers, get_settings())
    out = await results["get_history"]("???bad")
    assert "error" in out and "data" not in out


# ── CN market: eastmoney heads the sub-chain (R19) ──────────────────────────

@respx.mock
async def test_get_quote_cn_routes_eastmoney_first(monkeypatch):
    """A bare 6-digit code parses to market CN; eastmoney (keyless, CN-only)
    answers from push2 and yahoo/futu are never called."""
    respx.get(f"{DEFAULT_EASTMONEY_QUOTE_BASE_URL}/api/qt/stock/get").respond(
        200, json={"rc": 0, "data": {"f43": 127516, "f44": 128615, "f45": 126301,
                                     "f46": 128515, "f47": 34801, "f57": "600519",
                                     "f58": "贵州茅台", "f60": 128513, "f168": 28,
                                     "f169": -997, "f170": -78, "f171": 180}})
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    providers = build_providers(get_settings())
    providers["yahoo"].quote = AsyncMock(side_effect=AssertionError("must not be called"))
    providers["futu"].quote = AsyncMock(side_effect=AssertionError("must not be called"))
    results = {}
    quote_mod.register(_capture(results), providers, get_settings())
    out = await results["get_quote"](["600519"])
    q = out["data"]["600519"]
    assert q["price"] == 1275.16 and q["source"] == "eastmoney"
    providers["yahoo"].quote.assert_not_called()
    providers["futu"].quote.assert_not_called()


@respx.mock
async def test_get_quote_cn_eastmoney_miss_falls_back_to_yahoo(monkeypatch):
    """rc!=0 (bad code) -> NotFound walks the chain; yahoo (600519.SS) serves."""
    respx.get(f"{DEFAULT_EASTMONEY_QUOTE_BASE_URL}/api/qt/stock/get").respond(
        200, json={"rc": 1, "data": None})
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    providers = build_providers(get_settings())
    providers["yahoo"].quote = AsyncMock(return_value={"price": 1275.0, "source": "yahoo"})
    providers["futu"].quote = AsyncMock(side_effect=AssertionError("must not be called"))
    results = {}
    quote_mod.register(_capture(results), providers, get_settings())
    out = await results["get_quote"](["600519"])
    assert out["data"]["600519"] == {"price": 1275.0, "source": "yahoo"}
    providers["futu"].quote.assert_not_called()


@respx.mock
async def test_get_quote_cn_explicit_eastmoney_source(monkeypatch):
    respx.get(f"{DEFAULT_EASTMONEY_QUOTE_BASE_URL}/api/qt/stock/get").respond(
        200, json={"rc": 0, "data": {"f43": 1000, "f57": "000001", "f58": "平安银行"}})
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    providers = build_providers(get_settings())
    providers["yahoo"].quote = AsyncMock(side_effect=AssertionError("must not be called"))
    results = {}
    quote_mod.register(_capture(results), providers, get_settings())
    out = await results["get_quote"](["000001"], source="eastmoney")
    q = out["data"]["000001"]
    assert q["price"] == 10.0 and q["source"] == "eastmoney"


@respx.mock
async def test_get_quote_eastmoney_skipped_for_non_cn(monkeypatch):
    """US symbol: eastmoney is in the chain but covers() skips it — no request."""
    route = respx.get(f"{DEFAULT_EASTMONEY_QUOTE_BASE_URL}/api/qt/stock/get").respond(
        200, json={"rc": 0, "data": {"f43": 1}})
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    providers = build_providers(get_settings())
    providers["yahoo"].quote = AsyncMock(return_value={"price": 189.5, "source": "yahoo"})
    results = {}
    quote_mod.register(_capture(results), providers, get_settings())
    out = await results["get_quote"](["AAPL"])
    assert out["data"]["AAPL"]["source"] == "yahoo"
    assert not route.called


@respx.mock
async def test_get_history_cn_routes_eastmoney_first(monkeypatch):
    """CN daily bars come from push2his klines; yahoo/futu never called."""
    respx.get(f"{DEFAULT_EASTMONEY_HISTORY_BASE_URL}/api/qt/stock/kline/get").respond(
        200, json={"rc": 0, "data": {"klines": [
            "2026-09-10,1291.00,1285.13,1294.99,1282.00,18900,2428698784.00,1.01,-0.45,-5.75,0.15",
            "2026-09-11,1285.15,1275.16,1286.15,1263.01,34801,4430841445.00,1.80,-0.78,-9.97,0.28"]}})
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    providers = build_providers(get_settings())
    providers["yahoo"].history = AsyncMock(side_effect=AssertionError("must not be called"))
    providers["futu"].history = AsyncMock(side_effect=AssertionError("must not be called"))
    results = {}
    history_mod.register(_capture(results), providers, get_settings())
    out = await results["get_history"]("600519", "1d", "2026-09-10", "2026-09-11")
    assert out == {"data": [
        {"date": "2026-09-10", "open": 1291.0, "close": 1285.13, "high": 1294.99,
         "low": 1282.0, "volume": 18900},
        {"date": "2026-09-11", "open": 1285.15, "close": 1275.16, "high": 1286.15,
         "low": 1263.01, "volume": 34801}]}
    providers["yahoo"].history.assert_not_called()
    providers["futu"].history.assert_not_called()
    params = respx.calls[0].request.url.params
    assert params["secid"] == "1.600519" and params["klt"] == "101"
