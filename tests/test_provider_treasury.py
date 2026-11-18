"""US Treasury provider tests: respx-mocked, zero egress.

Two shapes on two hosts: the par-yield-curve CSV export and the Fiscal Data
JSON API. The CSV parse is the part with real failure modes (Treasury adds
tenor columns over time, cells can be empty), so it gets the most coverage.
"""
import pytest
import respx

from unified_finance_mcp.config import (
    DEFAULT_TREASURY_FISCAL_BASE_URL,
    DEFAULT_TREASURY_YIELD_CSV_URL,
    get_settings,
)
from unified_finance_mcp.errors import NotFound, UpstreamDrift, UpstreamError
from unified_finance_mcp.providers.treasury import (
    FISCAL_KINDS,
    TreasuryProvider,
    _tenor,
)

CURVE_URL = f"{DEFAULT_TREASURY_YIELD_CSV_URL}/202611"
DEBT_URL = f"{DEFAULT_TREASURY_FISCAL_BASE_URL}/v2/accounting/od/debt_to_penny"

CURVE_CSV = (
    'Date,"1 Mo","1.5 Month","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr",'
    '"3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"\n'
    '11/17/2026,4.09,4.24,4.26,4.33,4.32,4.41,4.60,4.80,4.84,4.90,4.99,5.10,5.50,5.46\n'
    '11/16/2026,4.10,4.19,4.27,4.34,4.33,4.42,4.62,4.83,4.87,4.93,5.01,5.12,5.51,\n'
)

DEBT_BODY = {
    "data": [
        {"record_date": "2026-11-16",
         "tot_pub_debt_out_amt": "40662417395617.43",
         "debt_held_public_amt": "32852881286592.80"},
        {"record_date": "2026-11-13",
         "tot_pub_debt_out_amt": "40610000000000.00"},
    ],
    "meta": {"count": 2, "total-count": 10, "total-pages": 5},
}


def make_provider(monkeypatch):
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    for key in ("TREASURY_FISCAL_BASE_URL", "TREASURY_YIELD_CSV_URL"):
        monkeypatch.delenv(key, raising=False)
    return TreasuryProvider(get_settings())


# ── tenor labels ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("label,expected", [
    ("1 Mo", "1M"), ("1.5 Month", "1.5M"), ("2 Mo", "2M"),
    ("1 Yr", "1Y"), ("10 Yr", "10Y"), ("30 Yr", "30Y"),
])
def test_tenor_labels_normalised(label, expected):
    assert _tenor(label) == expected


def test_unknown_tenor_column_kept_verbatim():
    """Treasury adds columns over time; an unparsed label must not be dropped."""
    assert _tenor("CMT Index") == "CMT Index"


# ── yield curve ─────────────────────────────────────────────────────────────

async def test_available_is_keyless():
    p = TreasuryProvider.__new__(TreasuryProvider)
    assert TreasuryProvider.available(p) is True


@respx.mock
async def test_yield_curve_parses_full_tenor_set(monkeypatch):
    respx.get(CURVE_URL).respond(200, text=CURVE_CSV)
    p = make_provider(monkeypatch)
    out = await p.yield_curve("2026-11")
    assert out["period"] == "2026-11"
    first = out["data"][0]
    assert first["date"] == "2026-11-17"
    assert first["1M"] == 4.09 and first["1.5M"] == 4.24
    assert first["2Y"] == 4.80 and first["10Y"] == 5.10 and first["30Y"] == 5.46
    params = respx.calls[0].request.url.params
    assert params["type"] == "daily_treasury_yield_curve"
    assert params["_format"] == "csv"


@respx.mock
async def test_yield_curve_missing_cell_is_none_not_zero(monkeypatch):
    respx.get(CURVE_URL).respond(200, text=CURVE_CSV)
    p = make_provider(monkeypatch)
    out = await p.yield_curve("2026-11")
    assert out["data"][1]["30Y"] is None  # empty trailing cell in the CSV


async def test_yield_curve_rejects_bad_period_before_network(monkeypatch):
    p = make_provider(monkeypatch)
    for period in ("2026-13", "11-2026", "20261101", ""):
        with pytest.raises(NotFound, match="YYYY-MM"):
            await p.yield_curve(period)


@respx.mock
async def test_yield_curve_empty_body_is_not_found(monkeypatch):
    """A future month returns HTTP 200 with an empty body — not empty data."""
    respx.get(CURVE_URL).respond(200, text="")
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="2026-11"):
        await p.yield_curve("2026-11")


@respx.mock
async def test_yield_curve_unexpected_header_is_upstream_error(monkeypatch):
    respx.get(CURVE_URL).respond(200, text="foo,bar\n1,2\n")
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamDrift, match="CSV header"):
        await p.yield_curve("2026-11")


def test_default_period_is_current_utc_month(monkeypatch):
    period = TreasuryProvider.default_period()
    assert len(period) == 7 and period[4] == "-"
    assert 1 <= int(period[5:]) <= 12


# ── Fiscal Data ─────────────────────────────────────────────────────────────

@respx.mock
async def test_fiscal_debt_passes_rows_through_and_maps_total(monkeypatch):
    respx.get(DEBT_URL).respond(200, json=DEBT_BODY)
    p = make_provider(monkeypatch)
    out = await p.fiscal("debt_to_penny", page_size=2)
    assert out["kind"] == "debt_to_penny"
    assert out["total"] == 10 and out["count"] == 2
    assert out["data"][0]["tot_pub_debt_out_amt"] == "40662417395617.43"  # unchanged
    params = respx.calls[0].request.url.params
    assert params["page[size]"] == "2"
    assert params["sort"] == "-record_date"
    assert "filter" not in params


@respx.mock
async def test_fiscal_date_from_becomes_record_date_filter(monkeypatch):
    respx.get(DEBT_URL).respond(200, json=DEBT_BODY)
    p = make_provider(monkeypatch)
    await p.fiscal("debt_to_penny", date_from="2026-11-01", page_size=100)
    assert respx.calls[0].request.url.params["filter"] == "record_date:gte:2026-11-01"


@respx.mock
async def test_fiscal_avg_interest_rates_hits_its_own_dataset(monkeypatch):
    url = f"{DEFAULT_TREASURY_FISCAL_BASE_URL}/v2/accounting/od/avg_interest_rates"
    respx.get(url).respond(200, json={"data": [{"avg_interest_rate_amt": "3.4"}],
                                      "meta": {"total-count": 1}})
    p = make_provider(monkeypatch)
    out = await p.fiscal("avg_interest_rates")
    assert out["data"][0]["avg_interest_rate_amt"] == "3.4"


async def test_fiscal_rejects_unknown_kind(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="unknown kind"):
        await p.fiscal("yield_curve")
    assert set(FISCAL_KINDS) == {"debt_to_penny", "avg_interest_rates"}


async def test_fiscal_rejects_bad_date_from(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="YYYY-MM-DD"):
        await p.fiscal("debt_to_penny", date_from="11/01/2026")


@respx.mock
async def test_fiscal_empty_rows_is_not_found(monkeypatch):
    respx.get(DEBT_URL).respond(200, json={"data": [], "meta": {"total-count": 0}})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="debt_to_penny"):
        await p.fiscal("debt_to_penny")


# ── review follow-ups (2026-11-18) ──────────────────────────────────────────

@respx.mock
async def test_yield_curve_skips_impossible_calendar_date(monkeypatch):
    """02/31/2026 matches the shape but is not a date; the row is skipped."""
    bad_row = ('02/31/2026,4.0,4.0,4.0,4.0,4.0,4.0,4.0,4.0,4.0,4.0,4.0,4.0,4.0,4.0\n')
    respx.get(CURVE_URL).respond(200, text=CURVE_CSV + bad_row)
    p = make_provider(monkeypatch)
    out = await p.yield_curve("2026-11")
    assert [r["date"] for r in out["data"]] == [
        "2026-11-17", "2026-11-16"]  # bad row dropped, never invented


@respx.mock
async def test_fiscal_non_json_body_is_upstream_error(monkeypatch):
    """HTTP 200 with HTML must map to the taxonomy, not leak ValueError."""
    respx.get(DEBT_URL).respond(200, text="<html>maintenance</html>")
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamError, match="non-JSON"):
        await p.fiscal("debt_to_penny")


async def test_fiscal_rejects_impossible_date_from(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="real"):
        await p.fiscal("debt_to_penny", date_from="2026-02-31")
