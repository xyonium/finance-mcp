"""SEC EDGAR provider tests: respx-mocked, zero egress.

SEC answers 403 to the shared http.UA (it contains github.com) — measured
2026-11-18 — so the UA assertions here are regression guards, not cosmetics:
a future "simplify by reusing http.UA" patch must fail this file.
"""
import pytest
import respx

from unified_finance_mcp.config import (
    DEFAULT_EDGAR_BASE_URL,
    DEFAULT_SEC_TICKERS_URL,
    get_settings,
)
from unified_finance_mcp.errors import AuthError, NotFound, UpstreamDrift
from unified_finance_mcp.providers.edgar import EdgarProvider, normalize_cik

SUB_URL = f"{DEFAULT_EDGAR_BASE_URL}/submissions/CIK0000320193.json"
CONCEPT_URL = (f"{DEFAULT_EDGAR_BASE_URL}/api/xbrl/companyconcept/"
               "CIK0000320193/us-gaap/NetIncomeLoss.json")


def make_provider(monkeypatch, ua=None):
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    for key in ("SEC_EDGAR_BASE_URL", "SEC_EDGAR_TICKERS_URL"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("SEC_EDGAR_USER_AGENT", raising=False)
    if ua is not None:
        monkeypatch.setenv("SEC_EDGAR_USER_AGENT", ua)
    return EdgarProvider(get_settings())


SUB_BODY = {
    "cik": "0000320193", "name": "Apple Inc.", "tickers": ["AAPL"],
    "exchanges": ["Nasdaq"], "sicDescription": "Electronic Computers",
    "filings": {"recent": {
        "form": ["10-K", "4", "10-K/A", "8-K"],
        "filingDate": ["2026-10-30", "2026-11-12", "2026-11-01", "2026-10-31"],
        "reportDate": ["2026-09-26", "", "2025-09-27", "2026-10-28"],
        "accessionNumber": ["0000320193-26-000100", "0001140361-26-043484",
                            "0000320193-26-000101", "0000320193-26-000102"],
        "primaryDocument": ["aapl-20260926.htm", "xslF345X06/form4.xml",
                            "aapl-20250927.htm", "aapl-8k.htm"],
        "primaryDocDescription": ["10-K", "FORM 4", "10-K/A", "8-K"],
        "items": ["", "", "", "2.02"],
        "isXBRL": [1, 0, 1, 1],
    }}}

CONCEPT_BODY = {
    "cik": 320193, "taxonomy": "us-gaap", "tag": "NetIncomeLoss",
    "label": "Net Income (Loss)", "entityName": "Apple Inc.",
    "units": {"USD": [
        {"start": "2024-09-29", "end": "2025-09-27", "val": 93736000000,
         "accn": "0000320193-25-000100", "fy": 2025, "fp": "FY",
         "form": "10-K", "filed": "2025-10-31", "frame": "CY2025"},
        {"start": "2025-09-28", "end": "2026-09-26", "val": 101000000000,
         "accn": "0000320193-26-000100", "fy": 2026, "fp": "FY",
         "form": "10-K", "filed": "2026-10-30", "frame": "CY2026"},
    ]}}


# ── user agent policy ───────────────────────────────────────────────────────

def test_default_ua_is_declared_and_has_no_github_domain(monkeypatch):
    """The default UA must never contain github.com: SEC 403s it."""
    p = make_provider(monkeypatch)
    ua = p._ua()
    assert ua and "github.com" not in ua
    assert "unified-finance-mcp" in ua


def test_configured_ua_wins(monkeypatch):
    p = make_provider(monkeypatch, ua="acme-finance eli@example.com")
    assert p._ua() == "acme-finance eli@example.com"


@respx.mock
async def test_request_carries_configured_ua(monkeypatch):
    respx.get(SUB_URL).respond(200, json=SUB_BODY)
    p = make_provider(monkeypatch, ua="acme-finance eli@example.com")
    await p.submissions("320193", limit=5)
    assert respx.calls[0].request.headers["user-agent"] == "acme-finance eli@example.com"


@respx.mock
async def test_403_maps_to_auth_error_with_ua_instruction(monkeypatch):
    respx.get(SUB_URL).respond(403, text="Undeclared Automated Tool")
    p = make_provider(monkeypatch)
    with pytest.raises(AuthError) as ei:
        await p.submissions("320193")
    assert "SEC_EDGAR_USER_AGENT" in str(ei.value)
    assert "403" in str(ei.value)


# ── CIK resolution ──────────────────────────────────────────────────────────

def test_normalize_cik_pads_and_strips_prefix():
    assert normalize_cik("320193") == "0000320193"
    assert normalize_cik("CIK0000320193") == "0000320193"
    assert normalize_cik("0000320193") == "0000320193"


def test_normalize_cik_rejects_ticker():
    with pytest.raises(NotFound):
        normalize_cik("AAPL")


@respx.mock
async def test_ticker_resolves_through_sec_map_and_caches(monkeypatch):
    route = respx.get(DEFAULT_SEC_TICKERS_URL).respond(200, json={
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
        "1": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
    })
    p = make_provider(monkeypatch)
    assert await p.resolve_cik("aapl") == "0000320193"
    assert await p.resolve_cik("NVDA") == "0001045810"
    assert route.call_count == 1  # 24h in-process cache


@respx.mock
async def test_unknown_ticker_not_found(monkeypatch):
    respx.get(DEFAULT_SEC_TICKERS_URL).respond(200, json={
        "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="ZZZZ"):
        await p.resolve_cik("ZZZZ")


# ── submissions ─────────────────────────────────────────────────────────────

@respx.mock
async def test_submissions_trim_filter_and_limit(monkeypatch):
    respx.get(SUB_URL).respond(200, json=SUB_BODY)
    p = make_provider(monkeypatch)
    out = await p.submissions("320193", form_type="10-K", limit=5)
    assert out["cik"] == "0000320193" and out["name"] == "Apple Inc."
    # "10-K" also matches its amendment "10-K/A"; Form 4/8-K filtered out.
    assert [f["form"] for f in out["filings"]] == ["10-K", "10-K/A"]
    assert out["filings"][0]["accession_number"] == "0000320193-26-000100"
    assert out["filings"][0]["is_xbrl"] == 1
    assert out["count"] == 2


@respx.mock
async def test_submissions_limit_caps_rows(monkeypatch):
    respx.get(SUB_URL).respond(200, json=SUB_BODY)
    p = make_provider(monkeypatch)
    out = await p.submissions("320193", limit=1)
    assert out["count"] == 1 and out["filings"][0]["form"] == "10-K"


@respx.mock
async def test_submissions_no_match_is_not_found(monkeypatch):
    respx.get(SUB_URL).respond(200, json=SUB_BODY)
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="13F"):
        await p.submissions("320193", form_type="13F")


@respx.mock
async def test_submissions_404_not_found(monkeypatch):
    respx.get(SUB_URL).respond(404, text="not found")
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.submissions("320193")


# ── XBRL concepts ───────────────────────────────────────────────────────────

@respx.mock
async def test_company_concept_keeps_provenance_and_caps_rows(monkeypatch):
    respx.get(CONCEPT_URL).respond(200, json=CONCEPT_BODY)
    p = make_provider(monkeypatch)
    out = await p.company_concept("320193", "NetIncomeLoss", limit=1)
    assert out["tag"] == "NetIncomeLoss" and out["label"] == "Net Income (Loss)"
    rows = out["units"]["USD"]
    assert len(rows) == 1  # newest kept
    assert rows[0]["val"] == 101000000000
    assert rows[0]["accn"] == "0000320193-26-000100"
    assert rows[0]["filed"] == "2026-10-30"
    assert "cik" not in rows[0]  # trimmed to the provenance fields only


@respx.mock
async def test_company_concept_404_is_tag_specific_not_found(monkeypatch):
    respx.get(CONCEPT_URL).respond(404, text="not found")
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="NetIncomeLoss"):
        await p.company_concept("320193", "NetIncomeLoss")


async def test_company_concept_rejects_path_like_tag(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="invalid XBRL tag"):
        await p.company_concept("320193", "NetIncomeLoss/../../x")


@respx.mock
async def test_facts_collects_missing_tags_instead_of_failing(monkeypatch):
    respx.get(CONCEPT_URL).respond(200, json=CONCEPT_BODY)
    respx.get(f"{DEFAULT_EDGAR_BASE_URL}/api/xbrl/companyconcept/"
              "CIK0000320193/us-gaap/Revenues.json").respond(404, text="no")
    p = make_provider(monkeypatch)
    out = await p.facts("320193", ["NetIncomeLoss", "Revenues"], limit=2)
    assert list(out["facts"]) == ["NetIncomeLoss"]
    assert out["missing_tags"] == ["Revenues"]
    assert out["entity_name"] == "Apple Inc."


@respx.mock
async def test_facts_all_missing_is_not_found(monkeypatch):
    respx.get(f"{DEFAULT_EDGAR_BASE_URL}/api/xbrl/companyconcept/"
              "CIK0000320193/us-gaap/Revenues.json").respond(404, text="no")
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="none of"):
        await p.facts("320193", ["Revenues"])


@respx.mock
async def test_non_json_body_is_upstream_error(monkeypatch):
    respx.get(SUB_URL).respond(200, text="<html>maintenance</html>")
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamDrift, match="non-JSON"):
        await p.submissions("320193")
