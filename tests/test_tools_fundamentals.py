"""get_company_info / get_financial_report: routing + validation, fully stubbed.

Hermeticity (T10-C1 lesson): every routing test stubs the COMPLETE reachable
candidate set for its input at the provider-instance level — yahoo is always
available()+covers(), and fmp/alphavantage become candidates the moment their
key env is set, so all chain members are stubbed no matter the env state.
Availability of env-dependent candidates is forced per test at instance level
(_set_available) so results are identical keyless or keyed. futu needs no
stub (loopback-only OpenD probe, none in test env) and is in no chain here.
"""
from unittest.mock import AsyncMock

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import fundamentals as fundamentals_mod


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


def _stub_info_fail(providers):
    for name in ("yahoo", "fmp", "alphavantage"):
        providers[name].company_info = AsyncMock(
            side_effect=NotFound(f"{name}: no such symbol"))


async def test_company_info_chain_order(monkeypatch):
    # yahoo succeeds -> fmp/alphavantage must not be called (chain order pinned).
    providers = build_providers(get_settings())
    info = {"longName": "Apple Inc.", "sector": "Technology"}
    providers["yahoo"].company_info = AsyncMock(return_value=info)
    providers["fmp"].company_info = AsyncMock(
        side_effect=AssertionError("fmp must not be called"))
    providers["alphavantage"].company_info = AsyncMock(
        side_effect=AssertionError("alphavantage must not be called"))
    _set_available(providers, ("fmp", "alphavantage"))  # candidates if yahoo failed
    results = {}
    fundamentals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_company_info"]("AAPL")
    assert out == {"data": info}
    providers["fmp"].company_info.assert_not_called()
    providers["alphavantage"].company_info.assert_not_called()


async def test_company_info_yahoo_fails_then_fmp(monkeypatch):
    providers = build_providers(get_settings())
    providers["yahoo"].company_info = AsyncMock(side_effect=NotFound("yahoo: 404"))
    fmp_info = {"companyName": "Apple Inc.", "sector": "Technology"}
    providers["fmp"].company_info = AsyncMock(return_value=fmp_info)
    providers["alphavantage"].company_info = AsyncMock(
        side_effect=AssertionError("alphavantage must not be called"))
    _set_available(providers, ("fmp", "alphavantage"))
    results = {}
    fundamentals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_company_info"]("AAPL")
    assert out == {"data": fmp_info}


async def test_company_info_all_fail_returns_error(monkeypatch):
    providers = build_providers(get_settings())
    _stub_info_fail(providers)
    _set_available(providers, ("fmp", "alphavantage"))
    results = {}
    fundamentals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_company_info"]("AAPL")
    assert "error" in out and "data" not in out
    assert set(out["source_errors"]) == {"yahoo", "fmp", "alphavantage"}


async def test_company_info_bad_symbol_never_raises(monkeypatch):
    # "???bad" does NOT hit the parse-error branch: parse_symbol US-defaults it,
    # so routing runs and every env-dependent candidate is stubbed to fail.
    providers = build_providers(get_settings())
    _stub_info_fail(providers)
    _set_available(providers, ("fmp", "alphavantage"))
    results = {}
    fundamentals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_company_info"]("???bad")
    assert "error" in out and "data" not in out


async def test_financial_report_returns_rows():
    providers = build_providers(get_settings())
    rows = [{"date": "2025-09-30", "revenue": 100}]
    providers["fmp"].financial_report = AsyncMock(return_value=rows)
    providers["yahoo"].financial_report = AsyncMock(
        side_effect=AssertionError("fmp is first in the chain"))
    _set_available(providers, ("fmp", "alphavantage"))
    results = {}
    fundamentals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_financial_report"]("AAPL", "income", "annual")
    assert out == {"data": rows}
    providers["fmp"].financial_report.assert_awaited_once()
    parsed, statement, period = providers["fmp"].financial_report.await_args.args
    assert parsed.local == "AAPL" and statement == "income" and period == "annual"


async def test_financial_report_validates_statement():
    providers = build_providers(get_settings())
    for name in ("fmp", "yahoo", "alphavantage"):
        providers[name].financial_report = AsyncMock(
            side_effect=AssertionError("must not be called"))
    results = {}
    fundamentals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_financial_report"]("AAPL", statement="bogus")
    assert "error" in out and "income|balance|cashflow" in out["hint"]


async def test_financial_report_validates_period():
    providers = build_providers(get_settings())
    for name in ("fmp", "yahoo", "alphavantage"):
        providers[name].financial_report = AsyncMock(
            side_effect=AssertionError("must not be called"))
    results = {}
    fundamentals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_financial_report"]("AAPL", "income", period="monthly")
    assert "error" in out and "annual|quarterly" in out["hint"]


async def test_financial_report_bad_symbol_never_raises(monkeypatch):
    providers = build_providers(get_settings())
    for name in ("fmp", "yahoo", "alphavantage"):
        providers[name].financial_report = AsyncMock(
            side_effect=NotFound(f"{name}: no such symbol"))
    _set_available(providers, ("fmp", "alphavantage"))
    results = {}
    fundamentals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_financial_report"]("???bad", "income", "annual")
    assert "error" in out and "data" not in out
