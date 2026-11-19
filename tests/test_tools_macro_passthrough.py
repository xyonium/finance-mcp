"""get_economic_data passthrough paths: World Bank codes + Treasury aliases.

One tool, three vocabularies (2026-11-18 merge ruling). These tests pin the
dispatch boundaries: which vocabulary wins, which provider method is called
with what, and that a pinned wrong `source` fails before any provider call.
"""
from unittest.mock import AsyncMock

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import macro as macro_mod


def _capture(results):
    class FakeMCP:
        def tool(self):
            def deco(fn):
                results[fn.__name__] = fn
                return fn
            return deco
    return FakeMCP()


def _register(providers):
    results = {}
    macro_mod.register(_capture(results), providers, get_settings())
    return results["get_economic_data"]


def _stub(providers):
    """Every provider method used by the three vocabularies is stubbed, so a
    wrong dispatch fails loudly instead of hitting the network."""
    providers["macro"].world_bank_series = AsyncMock(
        return_value=[{"date": "2024", "value": 18729668435848,
                       "country": "CHN", "indicator": "NY.GDP.MKTP.CD"}])
    providers["macro"].economic = AsyncMock(return_value=[{"date": "2026", "value": 1}])
    providers["alphavantage"].economic = AsyncMock(
        side_effect=AssertionError("alphavantage must not be called"))
    providers["treasury"].yield_curve = AsyncMock(
        return_value={"period": "2026-11", "data": [{"date": "2026-11-17", "10Y": 5.1}]})
    providers["macro"].bls_series = AsyncMock(
        return_value=[{"date": "2026-09", "value": 7523.0}])
    providers["treasury"].mts_outlays = AsyncMock(
        return_value={"period": "2026-10", "record_date": "2026-10-31",
                      "limit": 50, "total": 491, "count": 1,
                      "truncated": True,
                      "data": [{"classification_desc": "Total Outlays"}]})
    providers["treasury"].fiscal = AsyncMock(
        return_value={"kind": "debt_to_penny", "total": 10, "count": 1,
                      "data": [{"record_date": "2026-11-16"}]})
    return providers


# ── World Bank passthrough ──────────────────────────────────────────────────

async def test_world_bank_code_dispatches_with_country_and_years():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("ny.gdp.mktp.cd", country="chn", start=2000, end=2024)
    assert out["indicator"] == "NY.GDP.MKTP.CD"
    assert out["country"] == "CHN" and out["start"] == 2000 and out["end"] == 2024
    assert out["data"][0]["value"] == 18729668435848
    call = providers["macro"].world_bank_series.await_args
    assert call.args == ("NY.GDP.MKTP.CD", "CHN", 2000, 2024)
    providers["treasury"].yield_curve.assert_not_called()


async def test_world_bank_bad_country_is_tool_error_before_call():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("NY.GDP.MKTP.CD", country="China!")
    assert "error" in out and "country" in out["error"]
    providers["macro"].world_bank_series.assert_not_called()


async def test_world_bank_bad_year_window_is_tool_error():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("NY.GDP.MKTP.CD", start=2030, end=2000)
    assert "error" in out and "年份" in out["error"]
    out = await tool("NY.GDP.MKTP.CD", start="year")
    assert "error" in out


async def test_world_bank_rejects_non_macro_source():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("NY.GDP.MKTP.CD", source="alphavantage")
    assert "error" in out and "alphavantage" in out["error"]
    providers["macro"].world_bank_series.assert_not_called()


# ── Treasury aliases ────────────────────────────────────────────────────────

async def test_treasury_yield_curve_passes_period_and_tags_indicator():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("treasury_yield_curve", period="2026-11")
    assert out["indicator"] == "TREASURY_YIELD_CURVE"
    assert out["period"] == "2026-11"
    assert out["data"][0]["10Y"] == 5.1
    providers["treasury"].yield_curve.assert_awaited_once_with("2026-11")
    providers["treasury"].fiscal.assert_not_called()


async def test_treasury_debt_dispatches_to_fiscal_dataset():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("TREASURY_DEBT")
    assert out["indicator"] == "TREASURY_DEBT"
    assert out["kind"] == "debt_to_penny"
    providers["treasury"].fiscal.assert_awaited_once_with("debt_to_penny")


async def test_treasury_rejects_non_treasury_source():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("TREASURY_DEBT", source="macro")
    assert "error" in out and "treasury" in out["hint"]
    providers["treasury"].fiscal.assert_not_called()


async def test_treasury_provider_failure_is_error_dict():
    providers = _stub(build_providers(get_settings()))
    providers["treasury"].yield_curve = AsyncMock(
        side_effect=NotFound("treasury: no yield-curve rows for 2026-12"))
    tool = _register(providers)
    out = await tool("TREASURY_YIELD_CURVE", period="2026-12")
    assert "error" in out and "data" not in out


# ── canonical path stays intact ─────────────────────────────────────────────

async def test_canonical_indicator_still_routes_to_macro_first():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("gdp")
    assert out == {"data": [{"date": "2026", "value": 1}]}
    providers["macro"].economic.assert_awaited_once_with("GDP")
    providers["macro"].world_bank_series.assert_not_called()


async def test_unknown_indicator_hint_names_all_three_vocabularies():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("M2")
    assert "error" in out
    assert "TREASURY_YIELD_CURVE" in out["hint"]
    assert "World Bank" in out["hint"]
    assert "GDP" in out["hint"]


async def test_treasury_avg_interest_rate_dispatches_to_its_dataset():
    providers = _stub(build_providers(get_settings()))
    providers["macro"].bls_series = AsyncMock(
        return_value=[{"date": "2026-09", "value": 7523.0}])
    providers["treasury"].fiscal = AsyncMock(
        return_value={"kind": "avg_interest_rates", "total": 1, "count": 1,
                      "data": [{"record_date": "2026-09-30",
                                "avg_interest_rate_amt": "3.4"}]})
    tool = _register(providers)
    out = await tool("TREASURY_AVG_INTEREST_RATE")
    assert out["indicator"] == "TREASURY_AVG_INTEREST_RATE"
    assert out["kind"] == "avg_interest_rates"
    providers["treasury"].fiscal.assert_awaited_once_with("avg_interest_rates")


# ── BLS:<seriesId> passthrough (plan review follow-ups) ─────────────────────

async def test_bls_prefix_is_case_insensitive_and_output_is_upper():
    providers = _stub(build_providers(get_settings()))
    providers["macro"].bls_series = AsyncMock(
        return_value=[{"date": "2026-09", "value": 7523.0}])
    tool = _register(providers)
    out = await tool("bls:jts000000000000000jol")
    assert out["indicator"] == "BLS:JTS000000000000000JOL"
    assert out["series_id"] == "JTS000000000000000JOL"
    assert out["data"] == [{"date": "2026-09", "value": 7523.0}]
    providers["macro"].bls_series.assert_awaited_once_with("JTS000000000000000JOL")


async def test_bls_invalid_id_is_rejected_before_provider_call():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("BLS:no spaces!")
    assert "error" in out and "invalid BLS series id" in out["error"]
    providers["macro"].bls_series.assert_not_called()


async def test_bls_rejects_non_macro_source_before_provider_call():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("BLS:LNS14000000", source="treasury")
    assert "error" in out and "BLS" in out["error"]
    assert "auto, macro" in out["hint"]
    providers["macro"].bls_series.assert_not_called()


async def test_bls_rate_limited_propagates_as_error_dict():
    from unified_finance_mcp.errors import RateLimited
    providers = _stub(build_providers(get_settings()))
    providers["macro"].bls_series = AsyncMock(
        side_effect=RateLimited("macro/bls: daily threshold"))
    tool = _register(providers)
    out = await tool("BLS:LNS14000000")
    assert "error" in out
    assert out["source_errors"]["macro"].startswith("rate_limited:")


async def test_bls_drift_escalates_to_contact_admin():
    from unified_finance_mcp.errors import UpstreamDrift
    providers = _stub(build_providers(get_settings()))
    providers["macro"].bls_series = AsyncMock(
        side_effect=UpstreamDrift("macro/bls: unexpected period 2026-M99"))
    tool = _register(providers)
    out = await tool("BLS:LNS14000000")
    assert out["action"] == "contact_admin"
    assert out["drifted_sources"] == ["macro"]


async def test_unknown_indicator_hint_lists_bls_vocabulary():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("M2")
    assert "BLS:" in out["hint"]


async def test_treasury_mts_outlays_dispatches_with_period():
    providers = _stub(build_providers(get_settings()))
    tool = _register(providers)
    out = await tool("TREASURY_MTS_OUTLAYS", period="2026-10")
    assert out["indicator"] == "TREASURY_MTS_OUTLAYS"
    assert out["period"] == "2026-10" and out["truncated"] is True
    assert out["data"][0]["classification_desc"] == "Total Outlays"
    providers["treasury"].mts_outlays.assert_awaited_once_with("2026-10")


async def test_treasury_mts_outlays_drift_escalates():
    from unified_finance_mcp.errors import UpstreamDrift
    providers = _stub(build_providers(get_settings()))
    providers["treasury"].mts_outlays = AsyncMock(
        side_effect=UpstreamDrift("treasury/mts: malformed report row"))
    tool = _register(providers)
    out = await tool("TREASURY_MTS_OUTLAYS")
    assert out["action"] == "contact_admin"
    assert out["drifted_sources"] == ["treasury"]
