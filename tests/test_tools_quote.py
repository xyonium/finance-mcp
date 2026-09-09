from unittest.mock import AsyncMock

from unified_finance_mcp.config import get_settings
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
