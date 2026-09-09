"""T13 misc tools: get_ownership / get_events_calendar / get_economic_data /
search_symbols. Fully stubbed, hermetic.

Hermeticity (T10-C1 lesson): every routing test stubs the COMPLETE reachable
candidate set for its input at the provider-instance level and forces
availability at instance level (_set_available) so results are identical
keyless or keyed. futu is not in any of these chains.
"""
from unittest.mock import AsyncMock

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import calendar as calendar_mod
from unified_finance_mcp.tools import macro as macro_mod
from unified_finance_mcp.tools import ownership as ownership_mod
from unified_finance_mcp.tools import search as search_mod


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


# ---------------------------------------------------------------- ownership

async def test_ownership_major_yahoo_first(monkeypatch):
    providers = build_providers(get_settings())
    rows = [{"Holder": "Apple", "pctHeld": 0.1}]
    providers["yahoo"].ownership = AsyncMock(return_value=rows)
    providers["fmp"].ownership = AsyncMock(
        side_effect=AssertionError("fmp must not be called (yahoo first)"))
    _set_available(providers, ("fmp",))
    results = {}
    ownership_mod.register(_capture(results), providers, get_settings())
    out = await results["get_ownership"]("AAPL", "major")
    assert out == {"data": rows}
    providers["fmp"].ownership.assert_not_called()
    assert providers["yahoo"].ownership.await_args.args[1] == "major"


async def test_ownership_kind_not_supported_by_fmp_falls_back_to_yahoo(monkeypatch):
    # kind="mutualfund": fmp only knows institutional/insider, so the closure
    # raises NotFound for fmp and yahoo wins without fmp ever being called.
    providers = build_providers(get_settings())
    rows = [{"Holder": "Vanguard", "pctHeld": 0.05}]
    providers["yahoo"].ownership = AsyncMock(return_value=rows)
    providers["fmp"].ownership = AsyncMock(
        side_effect=AssertionError("fmp must not be called for mutualfund"))
    _set_available(providers, ("fmp",))
    results = {}
    ownership_mod.register(_capture(results), providers, get_settings())
    out = await results["get_ownership"]("AAPL", "mutualfund")
    assert out == {"data": rows}
    providers["fmp"].ownership.assert_not_called()


async def test_ownership_insider_transactions_mapped_to_fmp_insider(monkeypatch):
    # The tool's "insider_transactions" == fmp's "insider": mapped in the closure.
    providers = build_providers(get_settings())
    providers["yahoo"].ownership = AsyncMock(side_effect=NotFound("yahoo: none"))
    rows = [{"transactionType": "Purchase"}]
    providers["fmp"].ownership = AsyncMock(return_value=rows)
    _set_available(providers, ("fmp",))
    results = {}
    ownership_mod.register(_capture(results), providers, get_settings())
    out = await results["get_ownership"]("AAPL", "insider_transactions")
    assert out == {"data": rows}
    assert providers["fmp"].ownership.await_args.args[1] == "insider"


async def test_ownership_invalid_kind_hint(monkeypatch):
    providers = build_providers(get_settings())
    providers["yahoo"].ownership = AsyncMock(
        side_effect=AssertionError("must not be called"))
    results = {}
    ownership_mod.register(_capture(results), providers, get_settings())
    out = await results["get_ownership"]("AAPL", "bogus")
    assert "error" in out
    for kind in ("major", "institutional", "mutualfund", "insider_transactions",
                 "insider_roster"):
        assert kind in out["hint"]


async def test_ownership_bad_symbol_never_raises(monkeypatch):
    providers = build_providers(get_settings())
    providers["yahoo"].ownership = AsyncMock(side_effect=NotFound("yahoo: none"))
    providers["fmp"].ownership = AsyncMock(side_effect=NotFound("fmp: none"))
    _set_available(providers, ("fmp",))
    results = {}
    ownership_mod.register(_capture(results), providers, get_settings())
    out = await results["get_ownership"]("???bad", "institutional")
    assert "error" in out and "data" not in out
    assert set(out["source_errors"]) == {"yahoo", "fmp"}


# ---------------------------------------------------------------- calendar

async def test_events_calendar_fmp_first(monkeypatch):
    providers = build_providers(get_settings())
    rows = [{"symbol": "AAPL", "date": "2026-07-29"}]
    providers["fmp"].events_calendar = AsyncMock(return_value=rows)
    providers["alphavantage"].events_calendar = AsyncMock(
        side_effect=AssertionError("alphavantage must not be called (fmp first)"))
    _set_available(providers, ("fmp", "alphavantage"))
    monkeypatch.setattr(calendar_mod, "_default_window",
                        lambda: ("2026-01-01", "2026-01-31"))
    results = {}
    calendar_mod.register(_capture(results), providers, get_settings())
    out = await results["get_events_calendar"]("earnings")
    assert out == {"data": rows}
    providers["alphavantage"].events_calendar.assert_not_called()
    kind, start, end = providers["fmp"].events_calendar.await_args.args
    assert (kind, start, end) == ("earnings", "2026-01-01", "2026-01-31")


async def test_events_calendar_av_csv_parsed(monkeypatch):
    # The CSV text -> list[dict] parsing is provider-tested (respx); here the
    # tool layer routes the already-parsed rows through when fmp fails.
    providers = build_providers(get_settings())
    providers["fmp"].events_calendar = AsyncMock(side_effect=NotFound("fmp: none"))
    rows = [{"symbol": "AAPL", "reportDate": "2026-01-29"}]
    providers["alphavantage"].events_calendar = AsyncMock(return_value=rows)
    _set_available(providers, ("fmp", "alphavantage"))
    results = {}
    calendar_mod.register(_capture(results), providers, get_settings())
    out = await results["get_events_calendar"]("earnings", "2026-01-01", "2026-01-31")
    assert out == {"data": rows}
    assert providers["alphavantage"].events_calendar.await_args.args[0] == "earnings"


async def test_events_calendar_invalid_type_hint(monkeypatch):
    providers = build_providers(get_settings())
    providers["fmp"].events_calendar = AsyncMock(
        side_effect=AssertionError("must not be called"))
    results = {}
    calendar_mod.register(_capture(results), providers, get_settings())
    out = await results["get_events_calendar"]("splits")
    assert "error" in out and "earnings|dividends|ipo" in out["hint"]


async def test_events_calendar_bad_dates_never_raises(monkeypatch):
    providers = build_providers(get_settings())
    providers["fmp"].events_calendar = AsyncMock(side_effect=NotFound("fmp: none"))
    providers["alphavantage"].events_calendar = AsyncMock(side_effect=NotFound("av: none"))
    _set_available(providers, ("fmp", "alphavantage"))
    results = {}
    calendar_mod.register(_capture(results), providers, get_settings())
    out = await results["get_events_calendar"]("earnings", "not-a-date", "also-not")
    assert "error" in out and "data" not in out


# ---------------------------------------------------------------- macro

async def test_economic_data_returns_rows(monkeypatch):
    providers = build_providers(get_settings())
    rows = [{"date": "2026-01-01", "value": 23000.0}]
    providers["alphavantage"].economic = AsyncMock(return_value=rows)
    _set_available(providers, ("alphavantage",))
    results = {}
    macro_mod.register(_capture(results), providers, get_settings())
    out = await results["get_economic_data"]("gdp")  # case-insensitive
    assert out == {"data": rows}
    assert providers["alphavantage"].economic.await_args.args[0] == "GDP"


async def test_economic_data_unknown_indicator_hint(monkeypatch):
    providers = build_providers(get_settings())
    providers["alphavantage"].economic = AsyncMock(
        side_effect=AssertionError("must not be called"))
    results = {}
    macro_mod.register(_capture(results), providers, get_settings())
    out = await results["get_economic_data"]("M2")
    assert "error" in out
    for key in ("GDP", "CPI", "INFLATION", "UNEMPLOYMENT", "FEDERAL_FUNDS_RATE",
                "TREASURY_YIELD_10Y", "RETAIL_SALES", "NONFARM_PAYROLL"):
        assert key in out["hint"]


async def test_economic_data_av_fails_returns_error(monkeypatch):
    providers = build_providers(get_settings())
    providers["alphavantage"].economic = AsyncMock(side_effect=NotFound("av: none"))
    _set_available(providers, ("alphavantage",))
    results = {}
    macro_mod.register(_capture(results), providers, get_settings())
    out = await results["get_economic_data"]("GDP")
    assert "error" in out and "data" not in out


# ---------------------------------------------------------------- search

async def test_search_symbols_chain(monkeypatch):
    providers = build_providers(get_settings())
    rows = [{"symbol": "AAPL", "name": "Apple Inc."}]
    providers["fmp"].search = AsyncMock(return_value=rows)
    providers["alphavantage"].search = AsyncMock(
        side_effect=AssertionError("alphavantage must not be called"))
    providers["yahoo"].search = AsyncMock(
        side_effect=AssertionError("yahoo must not be called"))
    _set_available(providers, ("fmp", "alphavantage"))
    results = {}
    search_mod.register(_capture(results), providers, get_settings())
    out = await results["search_symbols"]("apple", limit=5)
    assert out == {"data": rows}
    query, limit = providers["fmp"].search.await_args.args
    assert query == "apple" and limit == 5


async def test_search_symbols_fallback_to_av(monkeypatch):
    providers = build_providers(get_settings())
    providers["fmp"].search = AsyncMock(side_effect=NotFound("fmp: none"))
    rows = [{"symbol": "AAPL", "name": "Apple Inc", "match_score": 0.93}]
    providers["alphavantage"].search = AsyncMock(return_value=rows)
    providers["yahoo"].search = AsyncMock(
        side_effect=AssertionError("yahoo must not be called"))
    _set_available(providers, ("fmp", "alphavantage"))
    results = {}
    search_mod.register(_capture(results), providers, get_settings())
    out = await results["search_symbols"]("apple")
    assert out == {"data": rows}


async def test_search_symbols_empty_query_hint(monkeypatch):
    providers = build_providers(get_settings())
    providers["fmp"].search = AsyncMock(side_effect=AssertionError("must not be called"))
    results = {}
    search_mod.register(_capture(results), providers, get_settings())
    out = await results["search_symbols"]("   ")
    assert "error" in out and "hint" in out
