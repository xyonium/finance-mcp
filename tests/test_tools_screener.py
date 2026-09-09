"""run_screener: filter validation, tv-first routing, sanitized output.

Hermeticity (T10-C1 lesson): tradingview is always available()+covers();
fmp becomes a candidate the moment its key env is set, so both chain members
are stubbed and availability is forced at instance level (_set_available).
"""
import json
from unittest.mock import AsyncMock

import pytest

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound, ProviderError
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.providers.tradingview import FILTER_COLUMNS
from unified_finance_mcp.tools import screener as screener_mod


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


async def test_screener_tv_first_chain_order(monkeypatch):
    providers = build_providers(get_settings())
    rows = [{"name": "Apple", "close": 189.5, "market_cap_basic": 2.9e12}]
    providers["tradingview"].screener = AsyncMock(return_value=rows)
    providers["fmp"].screener = AsyncMock(
        side_effect=AssertionError("fmp must not be called (tv first)"))
    _set_available(providers, ("fmp",))
    results = {}
    screener_mod.register(_capture(results), providers, get_settings())
    out = await results["run_screener"](market="US", sort="market_cap", order="desc")
    assert out == {"data": rows}
    providers["fmp"].screener.assert_not_called()
    kwargs = providers["tradingview"].screener.await_args.kwargs
    assert kwargs["market"] == "US" and kwargs["filters"] == {}
    assert kwargs["sort"] == "market_cap" and kwargs["order"] == "desc"
    assert kwargs["limit"] == 25


async def test_screener_tv_fails_then_fmp(monkeypatch):
    providers = build_providers(get_settings())
    providers["tradingview"].screener = AsyncMock(side_effect=NotFound("tv: no rows"))
    rows = [{"symbol": "AAPL", "marketCap": 2.9e12}]
    providers["fmp"].screener = AsyncMock(return_value=rows)
    _set_available(providers, ("fmp",))
    results = {}
    screener_mod.register(_capture(results), providers, get_settings())
    out = await results["run_screener"](market="US", filters={"price": {"min": 10}})
    assert out == {"data": rows}
    fmp_filters = providers["fmp"].screener.await_args.kwargs["filters"]
    assert fmp_filters == {"price": {"min": 10}}  # passed through unchanged


async def test_screener_rejects_unknown_filter_field():
    providers = build_providers(get_settings())
    for name in ("tradingview", "fmp"):
        providers[name].screener = AsyncMock(
            side_effect=AssertionError("must not be called"))
    results = {}
    screener_mod.register(_capture(results), providers, get_settings())
    out = await results["run_screener"](market="US", filters={"nope": {"min": 1}})
    assert "error" in out and "FILTER" in out["hint"].upper()
    for field in FILTER_COLUMNS:
        assert field in out["hint"]


async def test_screener_rejects_invalid_order():
    providers = build_providers(get_settings())
    results = {}
    screener_mod.register(_capture(results), providers, get_settings())
    out = await results["run_screener"](order="sideways")
    assert "error" in out and "order" in out["hint"]


async def test_screener_bad_market_never_raises(monkeypatch):
    providers = build_providers(get_settings())
    # tv covers() everything but its screener has no slug; fmp is US-centric.
    providers["tradingview"].screener = AsyncMock(side_effect=NotFound("tv: no slug"))
    providers["fmp"].screener = AsyncMock(side_effect=ProviderError("fmp: US-only"))
    _set_available(providers, ("fmp",))
    results = {}
    screener_mod.register(_capture(results), providers, get_settings())
    out = await results["run_screener"](market="MARS")
    assert "error" in out and "data" not in out


async def test_screener_sanitizes_tv_output(monkeypatch):
    np = pytest.importorskip("numpy")
    providers = build_providers(get_settings())
    rows = [{"name": "Apple", "close": np.float64(189.5),
             "volume": np.int64(50_000_000), "bad": np.float64(np.nan)}]
    providers["tradingview"].screener = AsyncMock(return_value=rows)
    providers["fmp"].screener = AsyncMock(
        side_effect=AssertionError("must not be called"))
    _set_available(providers, ("fmp",))
    results = {}
    screener_mod.register(_capture(results), providers, get_settings())
    out = await results["run_screener"](market="US")
    json.dumps(out)  # must not raise
    assert out["data"][0]["close"] == 189.5
    assert out["data"][0]["volume"] == 50_000_000
    assert out["data"][0]["bad"] is None
