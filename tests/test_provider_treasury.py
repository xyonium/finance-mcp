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


# ── MTS outlays by agency/function (table 5) ────────────────────────────────

MTS_URL = f"{DEFAULT_TREASURY_FISCAL_BASE_URL}/v1/accounting/mts/mts_table_5"
MTS_LATEST = {"data": [{"record_date": "2026-10-31"}],
              "meta": {"total-count": 1}}
MTS_ROWS = {
    "data": [
        {"record_date": "2026-10-31", "classification_id": "1",
         "parent_id": "0", "line_code_nbr": "1",
         "classification_desc": "Total Outlays",
         "current_month_gross_outly_amt": "835147029099.80",
         "current_fytd_gross_outly_amt": "835147029099.80"},
        {"record_date": "2026-10-31", "classification_id": "2",
         "parent_id": "1", "line_code_nbr": "2",
         "classification_desc": "Zero Line",
         "current_month_gross_outly_amt": "0.00"},
        {"record_date": "2026-10-31", "classification_id": "3",
         "parent_id": "1", "line_code_nbr": "3",
         "classification_desc": "Negative Line",
         "current_month_gross_outly_amt": "-5.00"},
        {"record_date": "2026-10-31", "classification_id": "4",
         "parent_id": "1", "line_code_nbr": "4",
         "classification_desc": "Blank Line",
         "current_month_gross_outly_amt": None},
    ],
    "meta": {"total-count": 4},
}


def _mts_routes(monkeypatch, rows=MTS_ROWS, latest=MTS_LATEST):
    respx.get(MTS_URL, params={"sort": "-record_date",
                               "page[size]": "1"}).respond(200, json=latest)
    respx.get(MTS_URL, params={"filter": "record_date:eq:2026-10-31",
                               "page[size]": "1000"}).respond(200, json=rows)
    return make_provider(monkeypatch)


@respx.mock
async def test_mts_outlays_latest_month_keeps_amounts_as_strings(monkeypatch):
    p = _mts_routes(monkeypatch)
    out = await p.mts_outlays()
    assert out["period"] == "2026-10" and out["record_date"] == "2026-10-31"
    assert out["total"] == 4 and out["count"] == 4 and out["truncated"] is False
    # descending by amount; blank sorts last; strings are NOT converted
    assert [r["classification_desc"] for r in out["data"]] == [
        "Total Outlays", "Zero Line", "Negative Line", "Blank Line"]
    assert out["data"][0]["current_month_gross_outly_amt"] == "835147029099.80"
    assert out["data"][1]["current_month_gross_outly_amt"] == "0.00"
    assert out["data"][2]["current_month_gross_outly_amt"] == "-5.00"
    assert out["data"][3]["current_month_gross_outly_amt"] is None
    assert out["data"][0]["classification_id"] == "1"  # hierarchy retained
    assert out["data"][0]["parent_id"] == "0"


@respx.mock
async def test_mts_outlays_limit_is_visible_and_truncated(monkeypatch):
    p = _mts_routes(monkeypatch)
    out = await p.mts_outlays(limit=2)
    assert out["limit"] == 2 and out["count"] == 2
    assert out["total"] == 4 and out["truncated"] is True


@respx.mock
async def test_mts_outlays_period_uses_real_month_end(monkeypatch):
    respx.get(MTS_URL, params={"filter": "record_date:eq:2026-02-28",
                               "page[size]": "1000"}).respond(200, json=MTS_ROWS)
    p = make_provider(monkeypatch)
    out = await p.mts_outlays(period="2026-02")
    assert out["record_date"] == "2026-02-28"
    assert respx.calls[0].request.url.params["filter"] == \
        "record_date:eq:2026-02-28"  # no latest-month lookup


async def test_mts_outlays_bad_period_is_not_found(monkeypatch):
    p = make_provider(monkeypatch)
    for period in ("2026-13", "2026-1", "10-2026"):
        with pytest.raises(NotFound, match="YYYY-MM"):
            await p.mts_outlays(period=period)


@respx.mock
async def test_mts_outlays_malformed_latest_date_is_drift(monkeypatch):
    respx.get(MTS_URL, params={"sort": "-record_date",
                               "page[size]": "1"}).respond(
        200, json={"data": [{"record_date": "October 2026"}],
                   "meta": {"total-count": 1}})
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamDrift, match="latest"):
        await p.mts_outlays()


@respx.mock
async def test_mts_outlays_missing_total_count_is_drift(monkeypatch):
    bad = dict(MTS_ROWS, meta={"count": 4})
    p = _mts_routes(monkeypatch, rows=bad)
    with pytest.raises(UpstreamDrift, match="total-count"):
        await p.mts_outlays()


@respx.mock
async def test_mts_outlays_malformed_row_is_drift(monkeypatch):
    bad = {"data": [{"record_date": "2026-10-31"}], "meta": {"total-count": 1}}
    p = _mts_routes(monkeypatch, rows=bad)
    with pytest.raises(UpstreamDrift, match="malformed"):
        await p.mts_outlays()


@respx.mock
async def test_mts_outlays_empty_rows_is_not_found(monkeypatch):
    p = _mts_routes(monkeypatch, rows={"data": [], "meta": {"total-count": 0}})
    with pytest.raises(NotFound, match="no outlay rows"):
        await p.mts_outlays()


@respx.mock
async def test_mts_outlays_non_json_is_upstream_error(monkeypatch):
    respx.get(MTS_URL, params={"sort": "-record_date",
                               "page[size]": "1"}).respond(
        200, text="<html>maintenance</html>")
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamError, match="non-JSON"):
        await p.mts_outlays()
