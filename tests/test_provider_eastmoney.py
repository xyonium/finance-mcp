"""Eastmoney provider tests: all respx-mocked, zero live EM calls.

EM rate-limits by IP (the R1 verdict doc saw RemoteProtocolError after a
burst), so no test may touch push2/push2his/searchapi.eastmoney.com. Base
URLs are pinned via env to the defaults so a request target can never drift
to a live host; EM is keyless so there is no key to leak — the leak-style
assertions here pin that quote/history never leave the CN market instead.
"""
from __future__ import annotations

import pytest
import respx

from unified_finance_mcp.config import (
    DEFAULT_EASTMONEY_HISTORY_BASE_URL,
    DEFAULT_EASTMONEY_QUOTE_BASE_URL,
    DEFAULT_EASTMONEY_SEARCH_BASE_URL,
    get_settings,
)
from unified_finance_mcp.errors import NotFound, ProviderError, UpstreamError
from unified_finance_mcp.providers.eastmoney import EastmoneyProvider
from unified_finance_mcp.symbols import parse_symbol

QUOTE_URL = f"{DEFAULT_EASTMONEY_QUOTE_BASE_URL}/api/qt/stock/get"
KLINE_URL = f"{DEFAULT_EASTMONEY_HISTORY_BASE_URL}/api/qt/stock/kline/get"
SUGGEST_URL = f"{DEFAULT_EASTMONEY_SEARCH_BASE_URL}/api/suggest/get"

# Live probe 2026-09-13 (secid=1.600519 贵州茅台): the exact envelope of a
# real quote answer, values trimmed for readability.
REAL_QUOTE = {"rc": 0, "rt": 4, "svr": 180606386, "lt": 1, "full": 1,
              "data": {"f43": 127516, "f44": 128615, "f45": 126301,
                       "f46": 128515, "f47": 34801, "f57": "600519",
                       "f58": "贵州茅台", "f60": 128513, "f168": 28,
                       "f169": -997, "f170": -78, "f171": 180}}

# Live probe 2026-09-13 (600519 daily, 前复权): klines rows are
# "date,open,close,high,low,volume,amount,amplitude,pct,chg,turnover".
REAL_KLINE = {"rc": 0, "rt": 17, "lt": 1, "full": 0,
              "data": {"code": "600519", "market": 1, "name": "贵州茅台",
                       "decimal": 2, "dktotal": 6003, "preKPrice": 1299.52,
                       "klines": [
                           "2026-09-10,1291.00,1285.13,1294.99,1282.00,18900,2428698784.00,1.01,-0.45,-5.75,0.15",
                           "2026-09-11,1285.15,1275.16,1286.15,1263.01,34801,4430841445.00,1.80,-0.78,-9.97,0.28"]}}


def make_provider(monkeypatch, quote=DEFAULT_EASTMONEY_QUOTE_BASE_URL,
                  history=DEFAULT_EASTMONEY_HISTORY_BASE_URL,
                  search=DEFAULT_EASTMONEY_SEARCH_BASE_URL):
    monkeypatch.setenv("EASTMONEY_QUOTE_BASE_URL", quote)
    monkeypatch.setenv("EASTMONEY_HISTORY_BASE_URL", history)
    monkeypatch.setenv("EASTMONEY_SEARCH_BASE_URL", search)
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    return EastmoneyProvider(get_settings())


# ── available / market gating ────────────────────────────────────────────────

def test_available_always_true(monkeypatch):
    # Keyless: no env to set, no base override needed.
    assert EastmoneyProvider(get_settings()).available()


def test_markets_is_cn_only():
    assert EastmoneyProvider(get_settings()).markets == frozenset({"CN"})


# ── quote ───────────────────────────────────────────────────────────────────

@respx.mock
async def test_quote_maps_fields_and_scales_by_100(monkeypatch):
    respx.get(QUOTE_URL).respond(200, json=REAL_QUOTE)
    p = make_provider(monkeypatch)
    q = await p.quote(parse_symbol("600519"))
    assert q["price"] == 1275.16        # f43 127516 -> 1275.16
    assert q["high"] == 1286.15 and q["low"] == 1263.01
    assert q["open"] == 1285.15 and q["previous_close"] == 1285.13
    assert q["volume"] == 34801         # f47 raw int (hands)
    assert q["change"] == -9.97         # f169 -997 -> -9.97
    assert q["change_percent"] == -0.78  # f170 -78 -> -0.78
    assert q["symbol"] == "600519" and q["name"] == "贵州茅台"
    assert q["source"] == "eastmoney"


@respx.mock
async def test_quote_secid_prefixes_by_market(monkeypatch):
    """SH -> 1.{code}; SZ/BJ -> 0.{code}."""
    respx.get(QUOTE_URL).respond(200, json=REAL_QUOTE)
    p = make_provider(monkeypatch)
    await p.quote(parse_symbol("600519"))                # bare 6 -> SH
    assert respx.calls[0].request.url.params["secid"] == "1.600519"
    await p.quote(parse_symbol("SH.600519"))              # futu form
    assert respx.calls[1].request.url.params["secid"] == "1.600519"
    await p.quote(parse_symbol("000001"))                # 0xxxxx -> SZ
    assert respx.calls[2].request.url.params["secid"] == "0.000001"
    await p.quote(parse_symbol("300750"))                # 300xxx (ChiNext) -> SZ
    assert respx.calls[3].request.url.params["secid"] == "0.300750"
    await p.quote(parse_symbol("832000"))                # 83xxxx BSE -> BJ->0
    assert respx.calls[4].request.url.params["secid"] == "0.832000"
    await p.quote(parse_symbol("430047"))                # 43xxxx BSE -> 0
    assert respx.calls[5].request.url.params["secid"] == "0.430047"


@respx.mock
async def test_quote_rc_nonzero_is_not_found(monkeypatch):
    respx.get(QUOTE_URL).respond(200, json={"rc": 1, "data": None})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.quote(parse_symbol("600519"))


@respx.mock
async def test_quote_null_data_is_not_found(monkeypatch):
    respx.get(QUOTE_URL).respond(200, json={"rc": 0, "rt": 4, "data": None})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.quote(parse_symbol("600519"))


@respx.mock
async def test_quote_request_params(monkeypatch):
    route = respx.get(QUOTE_URL).respond(200, json=REAL_QUOTE)
    p = make_provider(monkeypatch)
    await p.quote(parse_symbol("600519"))
    params = route.calls[0].request.url.params
    assert params["secid"] == "1.600519" and params["invt"] == "2"
    assert "f43" in params["fields"] and "f170" in params["fields"]


async def test_quote_non_cn_market_is_not_found(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.quote(parse_symbol("AAPL"))
    with pytest.raises(NotFound):
        await p.quote(parse_symbol("HK.00700"))


# ── history ─────────────────────────────────────────────────────────────────

@respx.mock
async def test_history_parses_klines(monkeypatch):
    respx.get(KLINE_URL).respond(200, json=REAL_KLINE)
    p = make_provider(monkeypatch)
    rows = await p.history(parse_symbol("600519"), "1d",
                           start="2026-09-10", end="2026-09-11")
    assert len(rows) == 2
    r = rows[0]
    assert r == {"date": "2026-09-10", "open": 1291.0, "close": 1285.13,
                 "high": 1294.99, "low": 1282.0, "volume": 18900}
    assert rows[1]["close"] == 1275.16 and rows[1]["volume"] == 34801


@respx.mock
async def test_history_request_params(monkeypatch):
    route = respx.get(KLINE_URL).respond(200, json=REAL_KLINE)
    p = make_provider(monkeypatch)
    await p.history(parse_symbol("600519"), "1d",
                    start="2026-09-01", end="2026-09-13")
    params = route.calls[0].request.url.params
    assert params["secid"] == "1.600519" and params["klt"] == "101"
    assert params["fqt"] == "1"                       # 前复权
    assert params["beg"] == "20260901" and params["end"] == "20260913"
    assert params["fields2"] == "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"


@respx.mock
async def test_history_weekly_monthly_klt(monkeypatch):
    respx.get(KLINE_URL).respond(200, json=REAL_KLINE)
    p = make_provider(monkeypatch)
    await p.history(parse_symbol("600519"), "1wk")
    assert respx.calls[0].request.url.params["klt"] == "102"
    await p.history(parse_symbol("600519"), "1mo")
    assert respx.calls[1].request.url.params["klt"] == "103"


async def test_history_unsupported_interval_is_provider_error(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(ProviderError) as ei:
        await p.history(parse_symbol("600519"), "1h")
    assert "1d" in str(ei.value) and "1wk" in str(ei.value)


@respx.mock
async def test_history_empty_klines_is_not_found(monkeypatch):
    respx.get(KLINE_URL).respond(200, json={
        "rc": 0, "data": {"code": "600519", "market": 1, "klines": []}})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.history(parse_symbol("600519"), "1d")


@respx.mock
async def test_history_rc_nonzero_is_not_found(monkeypatch):
    respx.get(KLINE_URL).respond(200, json={"rc": 1, "data": None})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.history(parse_symbol("600519"), "1d")


# ── search ──────────────────────────────────────────────────────────────────

@respx.mock
async def test_search_maps_suggest_rows(monkeypatch):
    # Live probe 2026-09-13 (input=茅台): the exact QuotationCodeTable shape.
    respx.get(SUGGEST_URL).respond(200, json={"QuotationCodeTable": {
        "Data": [{"Code": "600519", "Name": "贵州茅台", "PinYin": "GZMT",
                  "ID": "6005191", "JYS": "2", "Classify": "AStock",
                  "MarketType": "1", "SecurityTypeName": "沪A",
                  "SecurityType": "1", "MktNum": "1", "TypeUS": "2",
                  "QuoteID": "1.600519", "UnifiedCode": "600519",
                  "InnerCode": "46077278941243"}],
        "Status": 0, "Message": "成功", "TotalCount": 1}})
    p = make_provider(monkeypatch)
    rows = await p.search("茅台", limit=5)
    assert rows[0]["symbol"] == "600519" and rows[0]["name"] == "贵州茅台"
    assert rows[0]["exchange"] == "沪A" and rows[0]["quote_id"] == "1.600519"
    assert rows[0]["source"] == "eastmoney"
    params = respx.calls[0].request.url.params
    assert params["input"] == "茅台" and params["type"] == "14"


@respx.mock
async def test_search_null_data_is_not_found(monkeypatch):
    # Live probe 2026-09-13 (input=maotai): English names do NOT match.
    respx.get(SUGGEST_URL).respond(200, json={"QuotationCodeTable": {
        "Data": None, "Status": 0, "Message": "成功", "TotalCount": 0}})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.search("maotai")


@respx.mock
async def test_search_respects_limit(monkeypatch):
    respx.get(SUGGEST_URL).respond(200, json={"QuotationCodeTable": {"Data": [
        {"Code": "600519", "Name": "贵州茅台", "Classify": "AStock"},
        {"Code": "600520", "Name": "另一家公司", "Classify": "AStock"}]}})
    p = make_provider(monkeypatch)
    rows = await p.search("600", limit=1)
    assert len(rows) == 1 and rows[0]["symbol"] == "600519"
    assert respx.calls[0].request.url.params["count"] == "1"


# ── body-shape hardening ─────────────────────────────────────────────────────

@respx.mock
async def test_non_json_200_maps_to_upstream_error(monkeypatch):
    respx.get(QUOTE_URL).respond(200, text="<html>bad gateway</html>")
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamError) as ei:
        await p.quote(parse_symbol("600519"))
    assert ei.value.kind == "unavailable"
    assert "non-JSON" in str(ei.value)


@respx.mock
async def test_non_dict_body_maps_to_upstream_error(monkeypatch):
    respx.get(QUOTE_URL).respond(200, json=[1, 2, 3])
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamError):
        await p.quote(parse_symbol("600519"))
