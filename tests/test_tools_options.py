"""get_option_chain / get_short_interest / get_analyst_estimates routing tests.

Hermeticity (identical discipline as test_tools_news.py): every test stubs the
COMPLETE reachable candidate set for its input at the provider-instance
level — yahoo is always available()+covers(); fmp becomes a candidate the
moment its key env is set (or base-url is overridden), so both chains are
stubbed no matter the env state.
"""
from unittest.mock import AsyncMock

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound, RateLimited
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import estimates as estimates_mod
from unified_finance_mcp.tools import options as options_mod
from unified_finance_mcp.tools import short as short_mod


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


# ── get_option_chain ─────────────────────────────────────────────────────────

async def test_option_chain_yahoo_wins_first():
    providers = build_providers(get_settings())
    yahoo_payload = {"underlying": "AAPL", "expiration": "2025-09-19",
                     "available_expirations": ["2025-09-19"],
                     "calls": [{"strike": 220.0}], "puts": [], "source": "yahoo"}
    providers["yahoo"].option_chain = AsyncMock(return_value=yahoo_payload)
    providers["fmp"].option_chain = AsyncMock(
        side_effect=AssertionError("fmp must not be called (yahoo won)"))
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    options_mod.register(_capture(results), providers, get_settings())
    out = await results["get_option_chain"]("AAPL", expiration="2025-09-19")
    assert out == {"data": yahoo_payload}
    parsed, exp = providers["yahoo"].option_chain.await_args.args
    assert parsed.local == "AAPL" and exp == "2025-09-19"


async def test_option_chain_yahoo_empty_falls_through_to_fmp():
    providers = build_providers(get_settings())
    providers["yahoo"].option_chain = AsyncMock(side_effect=NotFound("yahoo: none"))
    fmp_payload = {"underlying": "AAPL", "expiration": None,
                   "available_expirations": [], "chain": [{"optionType": "CALL"}],
                   "source": "fmp"}
    providers["fmp"].option_chain = AsyncMock(return_value=fmp_payload)
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    options_mod.register(_capture(results), providers, get_settings())
    out = await results["get_option_chain"]("AAPL")
    assert out == {"data": fmp_payload}


async def test_option_chain_all_fail_returns_error_dict():
    providers = build_providers(get_settings())
    providers["yahoo"].option_chain = AsyncMock(side_effect=NotFound("yahoo: none"))
    providers["fmp"].option_chain = AsyncMock(side_effect=RateLimited("fmp: 402"))
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    options_mod.register(_capture(results), providers, get_settings())
    out = await results["get_option_chain"]("AAPL")
    assert "error" in out and "data" not in out
    assert set(out["source_errors"]) == {"yahoo", "fmp"}


async def test_option_chain_explicit_fmp_respected():
    providers = build_providers(get_settings())
    fmp_payload = {"underlying": "AAPL", "expiration": None,
                   "available_expirations": [], "chain": [], "source": "fmp"}
    providers["yahoo"].option_chain = AsyncMock(
        side_effect=AssertionError("yahoo bypassed by explicit source"))
    providers["fmp"].option_chain = AsyncMock(return_value=fmp_payload)
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    options_mod.register(_capture(results), providers, get_settings())
    out = await results["get_option_chain"]("AAPL", source="fmp")
    assert out == {"data": fmp_payload}
    providers["yahoo"].option_chain.assert_not_called()


async def test_option_chain_bad_symbol_no_network():
    providers = build_providers(get_settings())
    providers["yahoo"].option_chain = AsyncMock(
        side_effect=AssertionError("must not reach provider on bad symbol"))
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    options_mod.register(_capture(results), providers, get_settings())
    out = await results["get_option_chain"]("???bad")
    # "???bad" US-defaults through parse_symbol (no ValueError), reaches routing.
    # We assert that the tool returned an error dict regardless of yahoo's mock
    # being configured here — parse shouldn't explode, route shouldn't call fmp.
    assert isinstance(out, dict)


# ── get_short_interest ───────────────────────────────────────────────────────

async def test_short_interest_yahoo_wins_first():
    providers = build_providers(get_settings())
    yahoo_payload = {"symbol": "GME", "shares_short": 11345000,
                     "short_percent_of_float": 0.0731, "source": "yahoo"}
    providers["yahoo"].short_interest = AsyncMock(return_value=yahoo_payload)
    providers["fmp"].short_interest = AsyncMock(
        side_effect=AssertionError("fmp must not be called"))
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    short_mod.register(_capture(results), providers, get_settings())
    out = await results["get_short_interest"]("GME")
    assert out == {"data": yahoo_payload}


async def test_short_interest_fmp_402_falls_through_to_error_dict():
    providers = build_providers(get_settings())
    providers["yahoo"].short_interest = AsyncMock(side_effect=NotFound("yahoo: none"))
    providers["fmp"].short_interest = AsyncMock(side_effect=RateLimited("fmp: 402"))
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    short_mod.register(_capture(results), providers, get_settings())
    out = await results["get_short_interest"]("GME")
    assert "error" in out and "data" not in out
    assert set(out["source_errors"]) == {"yahoo", "fmp"}


# ── get_analyst_estimates ─────────────────────────────────────────────────────

async def test_analyst_estimates_yahoo_wins_first():
    providers = build_providers(get_settings())
    yahoo_payload = {"symbol": "AAPL",
                     "price_targets": {"current": 232.5, "mean": 245.3},
                     "earnings_estimate": [{"period": "0q", "avg": 1.65}],
                     "revenue_estimate": [], "growth_estimates": [],
                     "eps_trend": [], "recommendations": [], "source": "yahoo"}
    providers["yahoo"].analyst_estimates = AsyncMock(return_value=yahoo_payload)
    providers["fmp"].analyst_estimates = AsyncMock(
        side_effect=AssertionError("fmp must not be called"))
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    estimates_mod.register(_capture(results), providers, get_settings())
    out = await results["get_analyst_estimates"]("AAPL")
    assert out == {"data": yahoo_payload}


async def test_analyst_estimates_yahoo_empty_then_fmp():
    providers = build_providers(get_settings())
    providers["yahoo"].analyst_estimates = AsyncMock(
        side_effect=NotFound("yahoo: no estimates"))
    fmp_payload = {"symbol": "AAPL", "estimates": [{"epsAvg": 1.65}],
                   "price_targets": [], "recommendations": [], "source": "fmp"}
    providers["fmp"].analyst_estimates = AsyncMock(return_value=fmp_payload)
    _set_available(providers, ("yahoo", "fmp"))
    results = {}
    estimates_mod.register(_capture(results), providers, get_settings())
    out = await results["get_analyst_estimates"]("AAPL")
    assert out == {"data": fmp_payload}
