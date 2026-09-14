"""get_fred_series / search_fred_series tool wiring (task ④): single-source
chain through route_and_call, never-raises error dicts, no network (provider
face stubbed)."""
from unittest.mock import AsyncMock

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import AuthError
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import fred as fred_mod


def _capture(results):
    class FakeMCP:
        def tool(self):
            def deco(fn):
                results[fn.__name__] = fn
                return fn
            return deco
    return FakeMCP()


def _set_available(providers, names, value=True):
    for name in names:
        providers[name].available = lambda v=value: v


def test_fred_module_registered_in_all_modules():
    from unified_finance_mcp import tools as tools_pkg
    assert "fred" in tools_pkg.ALL_MODULES
    assert len(set(tools_pkg.ALL_MODULES)) == len(tools_pkg.ALL_MODULES)


async def test_get_fred_series_returns_provider_dict(monkeypatch):
    providers = build_providers(get_settings())
    payload = {"series_id": "DGS10", "units": "lin",
               "data": [{"date": "2026-02-06", "value": 4.2}]}
    providers["fred"].series_observations = AsyncMock(return_value=payload)
    _set_available(providers, ("fred",))
    results = {}
    fred_mod.register(_capture(results), providers, get_settings())
    out = await results["get_fred_series"]("dgs10", limit=5)
    assert out == payload
    call = providers["fred"].series_observations.await_args
    assert call.args[0] == "dgs10" and call.kwargs["limit"] == 5


async def test_search_fred_series_wraps_list_in_data(monkeypatch):
    providers = build_providers(get_settings())
    rows = [{"id": "DEXJPUS", "title": "Yen/Dollar"}]
    providers["fred"].series_search = AsyncMock(return_value=rows)
    _set_available(providers, ("fred",))
    results = {}
    fred_mod.register(_capture(results), providers, get_settings())
    out = await results["search_fred_series"]("yen")
    assert out == {"data": rows}
    providers["fred"].series_search.assert_awaited_once_with("yen", limit=20)


async def test_fred_tools_no_key_routing_error_never_raises(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    providers = build_providers(get_settings())
    assert providers["fred"].available() is False
    providers["fred"].series_observations = AsyncMock(
        side_effect=AssertionError("must not be called when unavailable"))
    providers["fred"].series_search = AsyncMock(
        side_effect=AssertionError("must not be called when unavailable"))
    results = {}
    fred_mod.register(_capture(results), providers, get_settings())
    out = await results["get_fred_series"]("GDP")
    assert "error" in out
    out = await results["search_fred_series"]("gdp")
    assert "error" in out


async def test_fred_provider_error_folded_into_error_dict(monkeypatch):
    providers = build_providers(get_settings())
    providers["fred"].series_observations = AsyncMock(
        side_effect=AuthError("fred: bad key"))
    _set_available(providers, ("fred",))
    results = {}
    fred_mod.register(_capture(results), providers, get_settings())
    out = await results["get_fred_series"]("GDP")
    assert out["error"].startswith("all candidate sources failed")
    assert out["source_errors"]["fred"].startswith("auth: ")
