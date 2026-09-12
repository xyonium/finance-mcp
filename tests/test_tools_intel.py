"""get_symbol_intel routing tests: one container over the former five tools.

Hermeticity discipline: every test stubs the COMPLETE reachable candidate
set (yahoo and fmp regardless of env) and forces availability.
"""
from unittest.mock import AsyncMock

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound, RateLimited
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import intel as intel_mod


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


def _tool():
    providers = build_providers(get_settings())
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    intel_mod.register(_capture(results), providers, get_settings())
    return providers, results["get_symbol_intel"]


async def test_unknown_kind_lists_valid():
    _, tool = _tool()
    out = await tool("AAPL", kind="bogus")
    assert "error" in out and "kind" in out["hint"]


async def test_options_routes_with_expiration():
    providers, tool = _tool()
    payload = {"underlying": "AAPL", "expiration": "2026-10-16", "calls": [],
               "puts": [], "source": "yahoo"}
    providers["yahoo"].option_chain = AsyncMock(return_value=payload)
    providers["fmp"].option_chain = AsyncMock(
        side_effect=AssertionError("fmp must not be called (yahoo won)"))
    out = await tool("AAPL", kind="options", expiration="2026-10-16")
    assert out == {"data": payload}
    parsed, expiration = providers["yahoo"].option_chain.await_args.args
    assert parsed.local == "AAPL" and expiration == "2026-10-16"


async def test_short_yahoo_empty_falls_to_fmp():
    providers, tool = _tool()
    providers["yahoo"].short_interest = AsyncMock(
        side_effect=NotFound("yahoo: none"))
    fmp_payload = {"symbol": "AAPL", "shares_short": 1, "source": "fmp"}
    providers["fmp"].short_interest = AsyncMock(return_value=fmp_payload)
    out = await tool("AAPL", kind="short")
    assert out == {"data": fmp_payload}
    providers["yahoo"].short_interest.assert_awaited_once()


async def test_analyst_yahoo_wins_first():
    providers, tool = _tool()
    providers["yahoo"].analyst_estimates = AsyncMock(
        return_value={"symbol": "AAPL", "price_targets": {}, "source": "yahoo"})
    providers["fmp"].analyst_estimates = AsyncMock(
        side_effect=AssertionError("fmp must not be called"))
    out = await tool("AAPL", kind="analyst")
    assert "data" in out
    providers["fmp"].analyst_estimates.assert_not_called()


async def test_dividends_all_fail_returns_error_dict():
    providers, tool = _tool()
    providers["yahoo"].dividend_split_history = AsyncMock(
        side_effect=NotFound("yahoo: none"))
    providers["fmp"].dividend_split_history = AsyncMock(
        side_effect=RateLimited("fmp: 402"))
    out = await tool("AAPL", kind="dividends")
    assert "error" in out and "data" not in out
    assert set(out["source_errors"]) == {"yahoo", "fmp"}


async def test_earnings_limit_passed_through():
    providers, tool = _tool()
    providers["yahoo"].earnings_history = AsyncMock(return_value=[])
    providers["fmp"].earnings_history = AsyncMock(
        side_effect=NotFound("not reached"))
    await tool("AAPL", kind="earnings", limit=4)
    parsed, limit = providers["yahoo"].earnings_history.await_args.args
    assert parsed.local == "AAPL" and limit == 4


async def test_garbage_symbol_returns_error_dict():
    # parse_symbol is permissive (bare tickers default to US), so "???bad"
    # parses and reaches the providers — errors surface as the error dict.
    providers, tool = _tool()
    providers["yahoo"].short_interest = AsyncMock(
        side_effect=NotFound("yahoo: no data"))
    providers["fmp"].short_interest = AsyncMock(
        side_effect=NotFound("fmp: no data"))
    out = await tool("???bad", kind="short")
    assert isinstance(out, dict) and "error" in out
    assert set(out["source_errors"]) == {"yahoo", "fmp"}
