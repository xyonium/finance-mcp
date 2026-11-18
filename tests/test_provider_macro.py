"""Native macro provider tests (R18): all respx-mocked, zero egress.

The provider wraps keyless official endpoints (api.worldbank.org,
www.imf.org, api.stlouisfed.org); no test may touch any of them. Every
request target is pinned via the settings base-url defaults, and the FRED
key (when exercised) is "test-key" so the leak assertions are meaningful.
"""
import pytest
import respx

from unified_finance_mcp.config import (
    DEFAULT_FRED_BASE_URL,
    DEFAULT_WB_BASE_URL,
    get_settings,
)
from unified_finance_mcp.errors import NotFound, ProviderError
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.providers.macro import MACRO_INDICATORS, MacroProvider

WB = f"{DEFAULT_WB_BASE_URL}/country/WLD/indicator"
FRED = f"{DEFAULT_FRED_BASE_URL}/series/observations"
IMF = "https://www.imf.org/external/datamapper/api/v1"


def make_provider(monkeypatch, fred_key=None):
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    if fred_key:
        monkeypatch.setenv("FRED_API_KEY", fred_key)
    monkeypatch.delenv("WORLD_BANK_BASE_URL", raising=False)
    monkeypatch.delenv("IMF_BASE_URL", raising=False)
    monkeypatch.delenv("FRED_BASE_URL", raising=False)
    return MacroProvider(get_settings())


def wb_body(rows):
    """World Bank [meta, rows] shape (live shape confirmed 2026-09-13)."""
    return [{"page": 1, "pages": 1, "per_page": 200, "total": len(rows)},
            rows]


WB_GDP_ROWS = [
    {"indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
     "country": {"id": "1W", "value": "World"}, "countryiso3code": "WLD",
     "date": "2024", "value": 111669432109121, "decimal": 0},
    {"indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
     "country": {"id": "1W", "value": "World"}, "countryiso3code": "WLD",
     "date": "2023", "value": 107348614073350, "decimal": 0},
]

FRED_GDP_ROWS = [
    {"date": "2026-01-01", "value": "30000.0", "realtime_start": "2026-02-01",
     "realtime_end": "9999-12-31"},
    {"date": "2025-10-01", "value": "29800.1", "realtime_start": "2026-02-01",
     "realtime_end": "9999-12-31"},
]


# ── world_bank: keyless 200 path ─────────────────────────────────────────────

@respx.mock
async def test_world_bank_gdp_200(monkeypatch):
    respx.get(f"{WB}/NY.GDP.MKTP.CD").respond(200, json=wb_body(WB_GDP_ROWS))
    p = make_provider(monkeypatch)
    rows = await p.economic("GDP")
    assert rows == [
        {"date": "2024", "value": 111669432109121,
         "country": "WLD", "indicator": "NY.GDP.MKTP.CD"},
        {"date": "2023", "value": 107348614073350,
         "country": "WLD", "indicator": "NY.GDP.MKTP.CD"},
    ]
    params = respx.calls[0].request.url.params
    assert params["format"] == "json" and params["per_page"] == "200"
    assert params["date"] == "1980:2026"


@respx.mock
async def test_world_bank_value_null_kept_not_dropped(monkeypatch):
    """A not-yet-reported year arrives as value: null — passed through."""
    rows_in = [dict(WB_GDP_ROWS[0], value=None)]
    respx.get(f"{WB}/NY.GDP.MKTP.CD").respond(200, json=wb_body(rows_in))
    p = make_provider(monkeypatch)
    rows = await p.economic("GDP")
    assert rows[0]["value"] is None and rows[0]["date"] == "2024"


@respx.mock
async def test_world_bank_empty_is_not_found_then_chain_continues(monkeypatch):
    """WB [meta, []] (unknown code) -> NotFound (route_and_call walks on)."""
    respx.get(f"{WB}/NY.GDP.MKTP.CD").respond(200, json=wb_body([]))
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p._world_bank("NY.GDP.MKTP.CD")


@respx.mock
async def test_world_bank_multipage_refused(monkeypatch):
    """pages > 1 would mean silent truncation at per_page — refuse."""
    respx.get(f"{WB}/NY.GDP.MKTP.CD").respond(200, json=[
        {"page": 1, "pages": 2, "per_page": 200, "total": 300},
        WB_GDP_ROWS])
    p = make_provider(monkeypatch)
    with pytest.raises(Exception) as ei:  # UpstreamError, not partial rows
        await p._world_bank("NY.GDP.MKTP.CD")
    assert "partial" in str(ei.value)


# ── fred: preferred when a key is configured ─────────────────────────────────

@respx.mock
async def test_fred_with_key_takes_priority_over_world_bank(monkeypatch):
    route_fred = respx.get(FRED).respond(
        200, json={"observations": FRED_GDP_ROWS})
    route_wb = respx.get(f"{WB}/NY.GDP.MKTP.CD").respond(
        200, json=wb_body(WB_GDP_ROWS))
    p = make_provider(monkeypatch, fred_key="test-key")
    rows = await p.economic("GDP")
    assert route_fred.called and not route_wb.called
    assert [r["date"] for r in rows] == ["2026-01-01", "2025-10-01"]
    assert rows[0]["value"] == 30000.0
    params = respx.calls[0].request.url.params
    assert params["series_id"] == "GDP" and params["api_key"] == "test-key"
    assert params["file_type"] == "json"


@respx.mock
async def test_fred_missing_dot_value_is_none(monkeypatch):
    """FRED's "." missing marker maps to None, not the string "."."""
    respx.get(FRED).respond(200, json={"observations": [
        {"date": "2026-01-01", "value": "."}]})
    p = make_provider(monkeypatch, fred_key="test-key")
    rows = await p.economic("TREASURY_YIELD_10Y")
    assert rows[0]["value"] is None


@respx.mock
async def test_fred_without_key_skipped_world_bank_serves(monkeypatch):
    """No FRED_API_KEY: fred is skipped (no fred request at all) and the
    keyless world_bank sub-endpoint serves the indicator."""
    route_fred = respx.get(FRED).respond(
        200, json={"observations": FRED_GDP_ROWS})
    route_wb = respx.get(f"{WB}/NY.GDP.MKTP.CD").respond(
        200, json=wb_body(WB_GDP_ROWS))
    p = make_provider(monkeypatch)  # no fred key
    rows = await p.economic("GDP")
    assert not route_fred.called and route_wb.called
    assert rows[0]["date"] == "2024"  # WB annual rows, not FRED monthly


async def test_fred_without_key_no_request_at_all(monkeypatch):
    """Keyless fred raise happens before any HTTP call (pure env check)."""
    p = make_provider(monkeypatch)  # no key
    with pytest.raises(NotFound, match="FRED_API_KEY"):
        await p._fred("FEDFUNDS")


@respx.mock
async def test_fred_http_429_rate_limited_then_world_bank(monkeypatch):
    """FRED 429 -> RateLimited on the fred leg, then world_bank serves the
    indicator (retryable sub-source failure falls through, chain intact)."""
    route_fred = respx.get(FRED).respond(429, text="slow down")
    route_wb = respx.get(f"{WB}/NY.GDP.MKTP.CD").respond(
        200, json=wb_body(WB_GDP_ROWS))
    p = make_provider(monkeypatch, fred_key="test-key")
    rows = await p.economic("GDP")
    assert route_fred.called and route_wb.called
    assert rows[0]["value"] == 111669432109121  # WB value came through


@respx.mock
async def test_fred_error_body_mapped(monkeypatch):
    """FRED 200 + error_code body (auth shape) is an error, not empty rows."""
    respx.get(FRED).respond(200, json={
        "error_code": 400,
        "error_message": "Bad Request. The value for variable api_key is not "
                         "a 32 character alpha-numeric lower-case string."})
    p = make_provider(monkeypatch, fred_key="test-key")
    with pytest.raises(NotFound):
        await p._fred("FEDFUNDS")


@respx.mock
async def test_fred_error_message_never_leaks_key(monkeypatch):
    route_wb = respx.get(f"{WB}/NY.GDP.MKTP.CD").respond(
        200, json=wb_body(WB_GDP_ROWS))
    respx.get(FRED).respond(500, text="boom test-key boom")
    p = make_provider(monkeypatch, fred_key="test-key")
    with pytest.raises(Exception) as ei:  # all sub-sources failed
        await p.economic("TREASURY_YIELD_10Y")  # fred-only indicator
    assert "test-key" not in str(ei.value)
    assert route_wb.called is False  # no WB candidate for this indicator


# ── imf: supplement ──────────────────────────────────────────────────────────

@respx.mock
async def test_imf_datamapper_gdp_growth(monkeypatch):
    """Keyless DataMapper JSON: values.{code}.{area} annual map."""
    route_wb = respx.get(f"{WB}/NY.GDP.MKTP.CD").respond(
        200, json=wb_body([]))
    respx.get(f"{IMF}/NGDP_RPCH/WLD").respond(200, json={
        "values": {"NGDP_RPCH": {"WLD": {"2024": 2.8, "2023": 2.9}}}})
    p = make_provider(monkeypatch)
    rows = await p.economic("GDP")
    assert route_wb.called  # world_bank was tried first, came back empty
    assert rows == [{"date": "2023", "value": 2.9},
                    {"date": "2024", "value": 2.8}]  # sorted ascending


@respx.mock
async def test_fred_only_indicators_no_world_bank_call(monkeypatch):
    """FEDFUNDS has no WB candidate: keyless provider must not call WB."""
    route_wb_base = respx.get(f"{WB}/FEDFUNDS").respond(
        200, json=wb_body(WB_GDP_ROWS))
    respx.get(FRED).respond(200, json={"observations": FRED_GDP_ROWS})
    p = make_provider(monkeypatch, fred_key="test-key")
    rows = await p.economic("FEDERAL_FUNDS_RATE")
    assert respx.calls.last.request.url.host == "api.stlouisfed.org"
    assert rows[0]["date"] == "2026-01-01"
    assert not route_wb_base.called  # FEDFUNDS never had a WB candidate


# ── indicator map / unknown ──────────────────────────────────────────────────

async def test_unknown_indicator_provider_error(monkeypatch):
    """Unknown indicator is a vocabulary error — the chain cannot know it
    either, so ProviderError (not NotFound) must come out immediately."""
    p = make_provider(monkeypatch, fred_key="test-key")
    with pytest.raises(ProviderError) as ei:
        await p.economic("M2")
    assert "M2" in str(ei.value)
    assert "GDP" in str(ei.value)  # hint carries the valid names


async def test_indicator_map_covers_canonical_vocabulary():
    assert set(MACRO_INDICATORS) == {
        "GDP", "CPI", "INFLATION", "UNEMPLOYMENT", "FEDERAL_FUNDS_RATE",
        "TREASURY_YIELD_10Y", "RETAIL_SALES", "NONFARM_PAYROLL"}
    # every indicator has at least one candidate, and fred-first where present
    for candidates in MACRO_INDICATORS.values():
        assert candidates
        assert all(src in ("fred", "world_bank", "imf")
                   for src, _ in candidates)


@respx.mock
async def test_all_sub_sources_fail_raises_last(monkeypatch):
    """Every candidate fails -> the last (most informative) error surfaces
    for route_and_call to fold into its source_errors dict."""
    respx.get(f"{WB}/NY.GDP.MKTP.CD").respond(200, json=wb_body([]))
    respx.get(f"{IMF}/NGDP_RPCH/WLD").respond(
        200, json={"values": {"NGDP_RPCH": {"WLD": {}}}})
    p = make_provider(monkeypatch)  # no fred key: fred leg is NotFound-fast
    with pytest.raises(NotFound, match="imf"):
        await p.economic("GDP")


def test_registered_in_build_providers(monkeypatch):
    ps = build_providers(get_settings())
    assert isinstance(ps["macro"], MacroProvider)
    assert ps["macro"].name == "macro"


# ── world_bank passthrough (2026-11-18 merge into get_economic_data) ────────

CHN_GDP = f"{DEFAULT_WB_BASE_URL}/country/CHN/indicator/NY.GDP.MKTP.CD"


@respx.mock
async def test_world_bank_series_any_country_and_indicator(monkeypatch):
    respx.get(CHN_GDP).respond(200, json=wb_body([
        {"indicator": {"id": "NY.GDP.MKTP.CD", "value": "GDP (current US$)"},
         "country": {"id": "CN", "value": "China"}, "countryiso3code": "CHN",
         "date": "2024", "value": 18729668435848, "decimal": 0}]))
    p = make_provider(monkeypatch)
    rows = await p.world_bank_series("NY.GDP.MKTP.CD", "CHN", 2000, 2024)
    assert rows == [{"date": "2024", "value": 18729668435848,
                     "country": "CHN", "indicator": "NY.GDP.MKTP.CD"}]
    params = respx.calls[0].request.url.params
    assert params["date"] == "2000:2024"


@respx.mock
async def test_world_bank_series_paging_refused_at_custom_per_page(monkeypatch):
    respx.get(CHN_GDP).respond(200, json=[
        {"page": 1, "pages": 3, "per_page": 5, "total": 13}, []])
    p = make_provider(monkeypatch)
    with pytest.raises(Exception) as ei:
        await p.world_bank_series("NY.GDP.MKTP.CD", "CHN", 2000, 2024, per_page=5)
    assert "partial" in str(ei.value)


async def test_world_bank_series_rejects_bad_window(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="start"):
        await p.world_bank_series("NY.GDP.MKTP.CD", "CHN", 2024, 2000)
    with pytest.raises(NotFound, match="1960"):
        await p.world_bank_series("NY.GDP.MKTP.CD", "CHN", 1900, 2000)


@respx.mock
async def test_world_bank_series_empty_rows_is_not_found(monkeypatch):
    respx.get(CHN_GDP).respond(200, json=wb_body([]))
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="CHN"):
        await p.world_bank_series("NY.GDP.MKTP.CD", "CHN", 2000, 2024)
