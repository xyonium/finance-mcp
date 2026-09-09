"""get_news: symbol-scoped and global routing, fully stubbed.

Hermeticity (T10-C1 lesson): every routing test stubs the COMPLETE reachable
candidate set for its input at the provider-instance level — yahoo is always
available()+covers(), and fmp/alphavantage/marketaux become candidates the
moment their key env is set, so all chain members are stubbed no matter the
env state. Availability of env-dependent candidates is forced per test at
instance level (_set_available) so results are identical keyless or keyed.
futu is not in any news chain.
"""
from unittest.mock import AsyncMock

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import news as news_mod


def _capture(results):
    class FakeMCP:
        def tool(self):
            def deco(fn):
                results[fn.__name__] = fn
                return fn
            return deco
    return FakeMCP()


def _set_available(providers, names, value=True):
    """Force env-dependent availability at provider-instance level."""
    for name in names:
        providers[name].available = lambda v=value: v


def _stub_news_fail(providers):
    for name in ("fmp", "alphavantage", "marketaux", "yahoo"):
        providers[name].news = AsyncMock(side_effect=NotFound(f"{name}: no news"))


async def test_news_with_symbol_chain_order(monkeypatch):
    # fmp succeeds -> alphavantage/marketaux/yahoo must not be called.
    providers = build_providers(get_settings())
    items = [{"title": "Apple ships", "source": "fmp"}]
    providers["fmp"].news = AsyncMock(return_value=items)
    for name in ("alphavantage", "marketaux", "yahoo"):
        providers[name].news = AsyncMock(
            side_effect=AssertionError(f"{name} must not be called"))
    _set_available(providers, ("fmp", "alphavantage", "marketaux"))
    results = {}
    news_mod.register(_capture(results), providers, get_settings())
    out = await results["get_news"]("AAPL", limit=5)
    assert out == {"data": items}
    parsed, limit = providers["fmp"].news.await_args.args
    assert parsed.local == "AAPL" and limit == 5


async def test_news_fmp_fails_then_alphavantage(monkeypatch):
    providers = build_providers(get_settings())
    providers["fmp"].news = AsyncMock(side_effect=NotFound("fmp: none"))
    av_items = [{"title": "Apple ships", "source": "alphavantage"}]
    providers["alphavantage"].news = AsyncMock(return_value=av_items)
    providers["marketaux"].news = AsyncMock(
        side_effect=AssertionError("marketaux must not be called"))
    _set_available(providers, ("fmp", "alphavantage", "marketaux"))
    results = {}
    news_mod.register(_capture(results), providers, get_settings())
    out = await results["get_news"]("AAPL")
    assert out == {"data": av_items}


async def test_news_without_symbol_uses_marketaux_only(monkeypatch):
    # symbol=None: only marketaux has a global feed. fmp/alphavantage/yahoo
    # accept no None symbol, so the routing fallback lands on marketaux.
    providers = build_providers(get_settings())
    global_items = [{"title": "Global markets roundup", "source": "marketaux"}]
    providers["marketaux"].news = AsyncMock(return_value=global_items)
    for name in ("fmp", "alphavantage", "yahoo"):
        providers[name].news = AsyncMock(
            side_effect=AssertionError(f"{name} must not be called (no global feed)"))
    _set_available(providers, ("fmp", "marketaux"))
    results = {}
    news_mod.register(_capture(results), providers, get_settings())
    out = await results["get_news"](None, limit=3)
    assert out == {"data": global_items}
    parsed, limit = providers["marketaux"].news.await_args.args
    assert parsed is None and limit == 3


async def test_news_without_symbol_marketaux_fails_never_calls_symbol_feeds(monkeypatch):
    # Global feed failure must not fall through to symbol-only providers: the
    # chain for parsed=None is ["marketaux", "fmp"] with market="GLOBAL", and
    # fmp.covers("GLOBAL") is False, so fmp is filtered out before the closure
    # (which would also raise NotFound for fmp with parsed=None as backstop).
    providers = build_providers(get_settings())
    providers["marketaux"].news = AsyncMock(side_effect=NotFound("marketaux: down"))
    providers["fmp"].news = AsyncMock(
        side_effect=AssertionError("fmp has no global feed and must not be called"))
    _set_available(providers, ("fmp", "marketaux"))
    results = {}
    news_mod.register(_capture(results), providers, get_settings())
    out = await results["get_news"](None)
    assert "error" in out and "data" not in out
    assert set(out["source_errors"]) == {"marketaux"}
    providers["fmp"].news.assert_not_called()


async def test_news_bad_symbol_never_raises(monkeypatch):
    # "???bad" US-defaults through parse_symbol; every env-dependent candidate
    # is stubbed to fail so the outcome is the routing error, never a raise.
    providers = build_providers(get_settings())
    _stub_news_fail(providers)
    _set_available(providers, ("fmp", "alphavantage", "marketaux"))
    results = {}
    news_mod.register(_capture(results), providers, get_settings())
    out = await results["get_news"]("???bad")
    assert "error" in out and "data" not in out
    assert set(out["source_errors"]) == {"fmp", "alphavantage", "marketaux", "yahoo"}


async def test_news_limit_bounds(monkeypatch):
    providers = build_providers(get_settings())
    providers["fmp"].news = AsyncMock(return_value=[])
    for name in ("alphavantage", "marketaux", "yahoo"):
        providers[name].news = AsyncMock(
            side_effect=AssertionError(f"{name} must not be called"))
    _set_available(providers, ("fmp", "alphavantage", "marketaux"))
    results = {}
    news_mod.register(_capture(results), providers, get_settings())
    out = await results["get_news"]("AAPL", limit=999)
    assert out == {"data": []}
    _, limit = providers["fmp"].news.await_args.args
    assert limit == 50  # bounded to the provider contract
