"""Standalone FRED provider tests (task ④): all respx-mocked, zero egress.

The provider wraps api.stlouisfed.org; no test may touch it. Every request
target is pinned via the settings base-url default, and the FRED key is
"test-key" so the scrub assertions are meaningful.
"""
import pytest
import respx

from unified_finance_mcp.config import DEFAULT_FRED_BASE_URL, get_settings
from unified_finance_mcp.errors import AuthError, NotFound, RateLimited, UpstreamError
from unified_finance_mcp.providers.fred import FredProvider

OBS = f"{DEFAULT_FRED_BASE_URL}/series/observations"
SEARCH = f"{DEFAULT_FRED_BASE_URL}/series/search"


def make_provider(monkeypatch, fred_key="test-key"):
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    if fred_key:
        monkeypatch.setenv("FRED_API_KEY", fred_key)
    monkeypatch.delenv("FRED_BASE_URL", raising=False)
    return FredProvider(get_settings())


OBS_BODY = {
    "realtime_start": "2026-02-01", "realtime_end": "9999-12-31",
    "observation_start": "2025-10-01", "observation_end": "2026-01-01",
    "units": "lin", "output_type": 1, "file_type": "json",
    "order_by": "observation_date", "sort_order": "desc",
    "count": 3, "offset": 0, "limit": 120,
    "observations": [
        {"date": "2026-01-01", "value": "30000.0",
         "realtime_start": "2026-02-01", "realtime_end": "9999-12-31"},
        {"date": "2025-12-01", "value": ".",
         "realtime_start": "2026-02-01", "realtime_end": "9999-12-31"},
        {"date": "2025-10-01", "value": "29800.1",
         "realtime_start": "2026-02-01", "realtime_end": "9999-12-31"},
    ]}

SEARCH_BODY = {
    "realtime_start": "2026-02-01", "realtime_end": "9999-12-31",
    "order_by": "search_rank", "sort_order": "desc",
    "count": 2, "offset": 0, "limit": 20,
    "seriess": [
        {"id": "DEXJPUS", "title": "Japanese Yen to U.S. Dollar Exchange Rate",
         "frequency": "Daily", "units": "Yen to One U.S. Dollar",
         "seasonal_adjustment": "Not Seasonally Adjusted", "popularity": 87,
         "observation_start": "1971-01-04", "observation_end": "2026-02-06",
         "notes": "long notes blob not passed through"},
        {"id": "DEXCHUS", "title": "Chinese Yuan to U.S. Dollar Exchange Rate",
         "frequency": "Daily", "units": "Yuan to One U.S. Dollar",
         "seasonal_adjustment": "Not Seasonally Adjusted", "popularity": 80,
         "observation_start": "1981-01-02", "observation_end": "2026-02-06"},
    ]}


# ── availability ─────────────────────────────────────────────────────────────

def test_available_only_with_key(monkeypatch):
    assert make_provider(monkeypatch, "test-key").available() is True
    assert make_provider(monkeypatch, None).available() is False


# ── series_observations ─────────────────────────────────────────────────────

@respx.mock
async def test_observations_happy_path_dot_becomes_none(monkeypatch):
    route = respx.get(OBS).respond(200, json=OBS_BODY)
    p = make_provider(monkeypatch)
    out = await p.series_observations("cpiaucsl")
    assert route.called
    q = dict(route.calls[0].request.url.params)
    # series_id is normalized to upper-case; key travels in params.
    assert q["series_id"] == "CPIAUCSL"
    assert q["api_key"] == "test-key"
    assert q["file_type"] == "json"
    assert q["sort_order"] == "desc" and q["limit"] == "120"
    assert out["series_id"] == "CPIAUCSL"
    assert out["units"] == "lin"
    assert out["count"] == 3
    rows = out["data"]
    assert rows[0] == {"date": "2026-01-01", "value": 30000.0}
    # FRED's "." missing marker -> None, never dropped or fabricated.
    assert rows[1] == {"date": "2025-12-01", "value": None}
    assert rows[2]["value"] == 29800.1


@respx.mock
async def test_observations_window_params_passed_through(monkeypatch):
    route = respx.get(OBS).respond(200, json=OBS_BODY)
    p = make_provider(monkeypatch)
    await p.series_observations("DGS10", observation_start="2025-01-01",
                                observation_end="2025-12-31", limit=10,
                                sort_order="asc")
    q = dict(route.calls[0].request.url.params)
    assert q["observation_start"] == "2025-01-01"
    assert q["observation_end"] == "2025-12-31"
    assert q["limit"] == "10" and q["sort_order"] == "asc"


@respx.mock
async def test_observations_empty_is_notfound(monkeypatch):
    respx.get(OBS).respond(200, json={**OBS_BODY, "observations": []})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.series_observations("NOSUCHSERIES")


async def test_observations_no_key_is_notfound_no_http(monkeypatch):
    p = make_provider(monkeypatch, None)
    with pytest.raises(NotFound, match="FRED_API_KEY"):
        await p.series_observations("GDP")


async def test_observations_rejects_bad_sort_order_no_http(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="sort_order"):
        await p.series_observations("GDP", sort_order="sideways")


@respx.mock
async def test_observations_bad_key_is_auth_error_scrubbed(monkeypatch):
    """Standalone boundary ruling: no chain here, so a bad key is AuthError
    (macro maps it to NotFound so its sub-source chain can walk on)."""
    respx.get(OBS).respond(200, json={
        "error_code": 400,
        "error_message": "Bad Request. The value for variable api_key is "
                         "not a 32-character key: test-key"})
    p = make_provider(monkeypatch)
    with pytest.raises(AuthError) as ei:
        await p.series_observations("GDP")
    assert "test-key" not in str(ei.value)
    assert "fredaccount.stlouisfed.org" in str(ei.value)


@respx.mock
async def test_observations_429_body_is_rate_limited(monkeypatch):
    respx.get(OBS).respond(200, json={
        "error_code": 429,
        "error_message": "Too many requests. Limit is 120 per minute."})
    p = make_provider(monkeypatch)
    with pytest.raises(RateLimited, match="120 req/min"):
        await p.series_observations("GDP")


@respx.mock
async def test_observations_other_error_body_is_upstream(monkeypatch):
    respx.get(OBS).respond(200, json={
        "error_code": 500, "error_message": "internal melt"})
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamError, match="internal melt"):
        await p.series_observations("GDP")


@respx.mock
async def test_observations_non_dict_body_is_upstream(monkeypatch):
    respx.get(OBS).respond(200, json=["not", "a", "dict"])
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamError, match="unexpected list body"):
        await p.series_observations("GDP")


# ── series_search ────────────────────────────────────────────────────────────

@respx.mock
async def test_search_happy_path_curated_fields(monkeypatch):
    route = respx.get(SEARCH).respond(200, json=SEARCH_BODY)
    p = make_provider(monkeypatch)
    rows = await p.series_search("yen exchange rate")
    q = dict(route.calls[0].request.url.params)
    assert q["search_text"] == "yen exchange rate" and q["limit"] == "20"
    assert [r["id"] for r in rows] == ["DEXJPUS", "DEXCHUS"]
    assert rows[0]["frequency"] == "Daily" and rows[0]["popularity"] == 87
    # The long `notes` blob is deliberately not passed through.
    assert "notes" not in rows[0]


@respx.mock
async def test_search_no_hits_is_notfound(monkeypatch):
    respx.get(SEARCH).respond(200, json={**SEARCH_BODY, "seriess": []})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="no series matching"):
        await p.series_search("zzzz not a series")


async def test_search_empty_query_is_notfound_no_http(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="empty search query"):
        await p.series_search("   ")
