"""get_dividend_split_history / get_earnings_history routing tests.

Hermeticity discipline as in test_tools_options.py: every test stubs the
COMPLETE reachable candidate set at provider-instance level and forces
availability, yahoo and fmp both stubbed regardless of env.
"""
from unittest.mock import AsyncMock

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound, RateLimited
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import dividends as dividends_mod
from unified_finance_mcp.tools import earnings as earnings_mod


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


# ── get_dividend_split_history ──────────────────────────────────────────────

async def test_dividend_split_yahoo_wins_first():
    providers = build_providers(get_settings())
    payload = {"symbol": "AAPL",
               "dividends": [{"kind": "dividend", "date": "2026-08-10",
                              "value": 0.27, "source": "yahoo"}],
               "splits": [],
               "next_events": [{"kind": "dividend", "date": "2026-08-13",
                                "source": "yahoo"}],
               "source": "yahoo"}
    providers["yahoo"].dividend_split_history = AsyncMock(return_value=payload)
    providers["fmp"].dividend_split_history = AsyncMock(
        side_effect=AssertionError("fmp must not be called (yahoo won)"))
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    dividends_mod.register(_capture(results), providers, get_settings())
    out = await results["get_dividend_split_history"]("AAPL")
    assert out == {"data": payload}
    providers["fmp"].dividend_split_history.assert_not_called()


async def test_dividend_split_yahoo_empty_falls_to_fmp():
    providers = build_providers(get_settings())
    providers["yahoo"].dividend_split_history = AsyncMock(
        side_effect=NotFound("yahoo: none"))
    fmp_payload = {"symbol": "AAPL", "dividends": [{"date": "2026-05-09"}],
                   "splits": [], "next_events": [], "source": "fmp"}
    providers["fmp"].dividend_split_history = AsyncMock(return_value=fmp_payload)
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    dividends_mod.register(_capture(results), providers, get_settings())
    out = await results["get_dividend_split_history"]("AAPL")
    assert out == {"data": fmp_payload}


async def test_dividend_split_all_fail_returns_error_dict():
    providers = build_providers(get_settings())
    providers["yahoo"].dividend_split_history = AsyncMock(
        side_effect=NotFound("yahoo: none"))
    providers["fmp"].dividend_split_history = AsyncMock(
        side_effect=RateLimited("fmp: 402"))
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    dividends_mod.register(_capture(results), providers, get_settings())
    out = await results["get_dividend_split_history"]("AAPL")
    assert "error" in out and "data" not in out
    assert set(out["source_errors"]) == {"yahoo", "fmp"}


async def test_dividend_split_bad_symbol_no_network():
    providers = build_providers(get_settings())
    providers["yahoo"].dividend_split_history = AsyncMock(
        side_effect=AssertionError("must not reach provider on bad symbol"))
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    dividends_mod.register(_capture(results), providers, get_settings())
    out = await results["get_dividend_split_history"]("???bad")
    assert isinstance(out, dict)


# ── get_earnings_history ─────────────────────────────────────────────────────

async def test_earnings_history_yahoo_wins_first():
    providers = build_providers(get_settings())
    rows = [{"date": "2026-07-30", "eps_estimate": 1.89, "reported_eps": 2.02,
             "surprise_pct": 6.74, "source": "yahoo"}]
    providers["yahoo"].earnings_history = AsyncMock(return_value=rows)
    providers["fmp"].earnings_history = AsyncMock(
        side_effect=AssertionError("fmp must not be called"))
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    earnings_mod.register(_capture(results), providers, get_settings())
    out = await results["get_earnings_history"]("AAPL")
    assert out == {"data": rows}
    parsed, limit = providers["yahoo"].earnings_history.await_args.args
    assert parsed.local == "AAPL" and limit == 12


async def test_earnings_history_limit_passed_through():
    providers = build_providers(get_settings())
    providers["yahoo"].earnings_history = AsyncMock(return_value=[])
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    earnings_mod.register(_capture(results), providers, get_settings())
    await results["get_earnings_history"]("AAPL", limit=4)
    *_, limit = providers["yahoo"].earnings_history.await_args.args
    assert limit == 4


async def test_earnings_history_yahoo_empty_then_fmp():
    providers = build_providers(get_settings())
    providers["yahoo"].earnings_history = AsyncMock(
        side_effect=NotFound("yahoo: no earnings dates"))
    fmp_rows = [{"date": "2026-07-29", "epsActual": 2.02, "source": "fmp"}]
    providers["fmp"].earnings_history = AsyncMock(return_value=fmp_rows)
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    earnings_mod.register(_capture(results), providers, get_settings())
    out = await results["get_earnings_history"]("AAPL")
    assert out == {"data": fmp_rows}


async def test_earnings_history_all_fail_returns_error_dict():
    providers = build_providers(get_settings())
    providers["yahoo"].earnings_history = AsyncMock(
        side_effect=NotFound("yahoo: none"))
    providers["fmp"].earnings_history = AsyncMock(
        side_effect=RateLimited("fmp: 402"))
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    earnings_mod.register(_capture(results), providers, get_settings())
    out = await results["get_earnings_history"]("AAPL")
    assert "error" in out and "data" not in out
    assert set(out["source_errors"]) == {"yahoo", "fmp"}


async def test_earnings_history_bad_symbol_no_network():
    providers = build_providers(get_settings())
    providers["yahoo"].earnings_history = AsyncMock(
        side_effect=AssertionError("must not reach provider on bad symbol"))
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    earnings_mod.register(_capture(results), providers, get_settings())
    out = await results["get_earnings_history"]("???bad")
    assert isinstance(out, dict)
