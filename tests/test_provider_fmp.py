"""FMP provider tests: stable REST endpoints via respx; no live calls.

Endpoint paths are pinned to https://financialmodelingprep.com/developer/docs
(stable). The `import httpx` from the plan's verbatim block was dropped: ruff
F401 flags it as unused (deviation noted in the task report).
"""
from datetime import date

import pytest
import respx

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.providers.fmp import EXCHANGE_TO_MARKET, FmpProvider
from unified_finance_mcp.symbols import parse_symbol


def make_provider(monkeypatch, base="https://financialmodelingprep.com"):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setenv("FMP_BASE_URL", base)
    return FmpProvider(get_settings())


@respx.mock
async def test_quote(monkeypatch):
    respx.get("https://financialmodelingprep.com/stable/quote").respond(
        200, json=[{"symbol": "AAPL", "price": 189.5, "marketCap": 2.9e12}])
    p = make_provider(monkeypatch)
    q = await p.quote(parse_symbol("AAPL"))
    assert q["price"] == 189.5 and q["source"] == "fmp"
    assert respx.calls[0].request.url.params["apikey"] == "test-key"


@respx.mock
async def test_quote_non_us_symbol_untouched(monkeypatch):
    route = respx.get("https://financialmodelingprep.com/stable/quote").respond(
        200, json=[{"symbol": "0700.HK", "price": 380.0}])
    p = make_provider(monkeypatch)
    q = await p.quote(parse_symbol("HK.00700"))
    assert route.called and q["price"] == 380.0


@respx.mock
async def test_covers_after_exchange_probe(monkeypatch):
    respx.get("https://financialmodelingprep.com/stable/available-exchanges").respond(
        200, json=[{"exchange": "NASDAQ"}, {"exchange": "HKEX"}, {"exchange": "EGX"}])
    p = make_provider(monkeypatch)
    assert p.covers("US")          # static seed, no network
    await p.probe_exchanges()      # fills cache
    assert p.covers("HK") and p.covers("EG")


@respx.mock
async def test_402_maps_to_rate_limited(monkeypatch):
    from unified_finance_mcp.errors import RateLimited
    respx.get("https://financialmodelingprep.com/stable/quote").respond(402, json={})
    p = make_provider(monkeypatch)
    with pytest.raises(RateLimited):
        await p.quote(parse_symbol("AAPL"))


@respx.mock
async def test_history_eod_light_path_and_dates(monkeypatch):
    respx.get("https://financialmodelingprep.com/stable/historical-price-eod/light").respond(
        200, json=[{"date": "2026-01-02", "open": 188.5, "close": 189.5,
                    "volume": 50_000_000}])
    p = make_provider(monkeypatch)
    rows = await p.history(parse_symbol("AAPL"), start="2026-01-01", end="2026-01-31")
    assert rows[0]["close"] == 189.5
    params = respx.calls[0].request.url.params
    assert params["symbol"] == "AAPL"
    assert params["from"] == "2026-01-01" and params["to"] == "2026-01-31"
    assert params["apikey"] == "test-key"


async def test_history_intraday_unsupported(monkeypatch):
    from unified_finance_mcp.errors import ProviderError
    p = make_provider(monkeypatch)
    with pytest.raises(ProviderError):
        await p.history(parse_symbol("AAPL"), interval="1h")


@respx.mock
async def test_company_info_profile(monkeypatch):
    respx.get("https://financialmodelingprep.com/stable/profile").respond(
        200, json=[{"symbol": "AAPL", "companyName": "Apple Inc.", "sector": "Technology"}])
    p = make_provider(monkeypatch)
    info = await p.company_info(parse_symbol("AAPL"))
    assert info["companyName"] == "Apple Inc." and info["sector"] == "Technology"
    assert respx.calls[0].request.url.params["symbol"] == "AAPL"


@respx.mock
async def test_financial_report_statement_paths(monkeypatch):
    income = respx.get("https://financialmodelingprep.com/stable/income-statement").respond(
        200, json=[{"date": "2025-09-30", "revenue": 100}])
    p = make_provider(monkeypatch)
    rows = await p.financial_report(parse_symbol("AAPL"), "income", "quarterly")
    assert rows[0]["revenue"] == 100 and income.called
    params = respx.calls[0].request.url.params
    assert params["period"] == "quarter" and params["symbol"] == "AAPL"


@respx.mock
async def test_financial_report_cashflow_path_and_annual_period(monkeypatch):
    route = respx.get("https://financialmodelingprep.com/stable/cash-flow-statement").respond(
        200, json=[{"date": "2025-09-30", "netIncome": 20}])
    p = make_provider(monkeypatch)
    rows = await p.financial_report(parse_symbol("AAPL"), "cashflow", "annual")
    assert rows[0]["netIncome"] == 20 and route.called
    assert respx.calls[0].request.url.params["period"] == "annual"


async def test_financial_report_unknown_statement(monkeypatch):
    from unified_finance_mcp.errors import ProviderError
    p = make_provider(monkeypatch)
    with pytest.raises(ProviderError):
        await p.financial_report(parse_symbol("AAPL"), "bogus", "annual")


@respx.mock
async def test_news_short_circuits_free_tier_paywall(monkeypatch):
    """FMP free-key tier paywalls every news endpoint (HTTP 402 Restricted
    Endpoint, live-verified 2026-09-11), so news() must raise NotFound without
    issuing any HTTP call — letting route_and_call fall through to the next
    source."""
    from unified_finance_mcp.errors import NotFound
    route = respx.get("https://financialmodelingprep.com/stable/news/stock").respond(
        200, json=[{"title": "should never be fetched"}])
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound, match="paywalled|402"):
        await p.news(parse_symbol("AAPL"), limit=5)
    assert not route.called, "news() must not hit the network on free-tier keys"


@respx.mock
async def test_ownership_institutional_positions_summary(monkeypatch):
    respx.get("https://financialmodelingprep.com/stable/"
              "institutional-ownership/symbol-positions-summary").respond(
        200, json=[{"symbol": "AAPL", "investorsHolding": 4300}])
    p = make_provider(monkeypatch)
    rows = await p.ownership(parse_symbol("AAPL"), "institutional")
    assert rows[0]["investorsHolding"] == 4300
    params = respx.calls[0].request.url.params
    today = date.today()  # noqa: DTZ011 - mirrors the provider's local-date convention
    assert params["year"] == str(today.year)
    assert params["quarter"] == str((today.month - 1) // 3 + 1)


@respx.mock
async def test_ownership_insider_search(monkeypatch):
    respx.get("https://financialmodelingprep.com/stable/insider-trading/search").respond(
        200, json=[{"symbol": "AAPL", "transactionType": "Purchase"}])
    p = make_provider(monkeypatch)
    rows = await p.ownership(parse_symbol("AAPL"), "insider")
    assert rows[0]["transactionType"] == "Purchase"
    assert respx.calls[0].request.url.params["symbol"] == "AAPL"


async def test_ownership_unknown_kind(monkeypatch):
    from unified_finance_mcp.errors import ProviderError
    p = make_provider(monkeypatch)
    with pytest.raises(ProviderError):
        await p.ownership(parse_symbol("AAPL"), "major")


@respx.mock
async def test_events_calendar_paths(monkeypatch):
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    earnings = respx.get(
        "https://financialmodelingprep.com/stable/earnings-calendar").respond(
        200, json=[{"symbol": "AAPL", "date": "2026-07-29"}])
    dividends = respx.get(
        "https://financialmodelingprep.com/stable/dividends-calendar").respond(
        200, json=[{"symbol": "AAPL", "paymentDate": "2026-08-10"}])
    ipos = respx.get(
        "https://financialmodelingprep.com/stable/ipos-calendar").respond(
        200, json=[{"symbol": "NEWCO", "ipoDate": "2026-09-01"}])
    p = make_provider(monkeypatch)
    out = await p.events_calendar("earnings", start="2026-07-01", end="2026-08-01")
    assert out[0]["symbol"] == "AAPL" and earnings.called
    params = respx.calls[0].request.url.params
    assert params["from"] == "2026-07-01" and params["to"] == "2026-08-01"
    assert (await p.events_calendar("dividends"))[0]["paymentDate"] == "2026-08-10"
    assert dividends.called
    assert (await p.events_calendar("ipo"))[0]["ipoDate"] == "2026-09-01"
    assert ipos.called


async def test_events_calendar_unknown_kind(monkeypatch):
    from unified_finance_mcp.errors import ProviderError
    p = make_provider(monkeypatch)
    with pytest.raises(ProviderError):
        await p.events_calendar("splits")


@respx.mock
async def test_search_name_path(monkeypatch):
    respx.get("https://financialmodelingprep.com/stable/search-name").respond(
        200, json=[{"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"}])
    p = make_provider(monkeypatch)
    rows = await p.search("apple", limit=5)
    assert rows[0]["name"] == "Apple Inc."
    params = respx.calls[0].request.url.params
    assert params["query"] == "apple" and params["limit"] == "5"


@respx.mock
async def test_empty_result_maps_to_not_found(monkeypatch):
    from unified_finance_mcp.errors import NotFound
    respx.get("https://financialmodelingprep.com/stable/quote").respond(200, json=[])
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.quote(parse_symbol("AAPL"))


@respx.mock
async def test_non_json_200_maps_to_upstream_error(monkeypatch):
    """A 200 with an HTML body (rotator/gateway error page) must become an
    UpstreamError with kind=unavailable, never a raw JSONDecodeError."""
    from unified_finance_mcp.errors import UpstreamError
    respx.get("https://financialmodelingprep.com/stable/quote").respond(
        200, text="<html>bad gateway</html>")
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamError) as ei:
        await p.quote(parse_symbol("AAPL"))
    assert ei.value.kind == "unavailable"
    assert "non-JSON" in str(ei.value)
    assert "test-key" not in str(ei.value)  # no key leak, no raw decode error


@respx.mock
async def test_error_messages_never_leak_the_key(monkeypatch):
    from unified_finance_mcp.errors import NotFound
    respx.get("https://financialmodelingprep.com/stable/quote").respond(200, json=[])
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound) as ei:
        await p.quote(parse_symbol("AAPL"))
    assert "test-key" not in str(ei.value)


@respx.mock
async def test_placeholder_apikey_when_unset(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.setenv("FMP_BASE_URL", "http://api-key-rotator:8788/fmp")
    respx.get("http://api-key-rotator:8788/fmp/stable/quote").respond(
        200, json=[{"symbol": "AAPL", "price": 189.5}])
    p = FmpProvider(get_settings())
    q = await p.quote(parse_symbol("AAPL"))
    assert q["source"] == "fmp"
    assert respx.calls[0].request.url.params["apikey"] == "rotated-by-upstream"


@respx.mock
async def test_probe_sends_apikey(monkeypatch):
    respx.get("https://financialmodelingprep.com/stable/available-exchanges").respond(
        200, json=[{"exchange": "NASDAQ"}])
    p = make_provider(monkeypatch)
    await p.probe_exchanges()
    assert respx.calls[0].request.url.params["apikey"] == "test-key"


@respx.mock
async def test_probe_ignores_unknown_exchanges(monkeypatch):
    respx.get("https://financialmodelingprep.com/stable/available-exchanges").respond(
        200, json=[{"exchange": "NASDAQ"}, {"exchange": "CRYPTO"},
                   {"exchange": "BURSA"}])
    p = make_provider(monkeypatch)
    await p.probe_exchanges()
    assert p.covers("US") and p.covers("MY") and not p.covers("XX")


@respx.mock
async def test_probe_failure_keeps_old_cache(monkeypatch):
    import time
    respx.get("https://financialmodelingprep.com/stable/available-exchanges").respond(
        500, json={})
    p = make_provider(monkeypatch)
    p._exchanges_cache = (time.monotonic(), {"EG"})
    await p.probe_exchanges()  # upstream fails; previous cache must survive
    assert p.covers("EG")


async def test_covers_uses_cache_until_ttl_expires(monkeypatch):
    import time
    p = make_provider(monkeypatch)
    p._exchanges_cache = (time.monotonic() - 3600.0, {"HK"})  # probed 1h ago
    assert p.covers("HK")
    p._exchanges_cache = (time.monotonic() - 90_000.0, {"HK"})  # stale: 25h
    assert not p.covers("HK")


async def test_covers_false_without_cache(monkeypatch):
    p = make_provider(monkeypatch)
    assert p.covers("US") and not p.covers("HK")


def test_exchange_map_covers_major_exchanges():
    assert EXCHANGE_TO_MARKET["NASDAQ"] == "US"
    assert EXCHANGE_TO_MARKET["HKEX"] == "HK"
    assert EXCHANGE_TO_MARKET["EGX"] == "EG"
    assert set(EXCHANGE_TO_MARKET) >= {
        "NASDAQ", "NYSE", "AMEX", "HKEX", "SSE", "SZSE", "EGX", "TSX",
        "LSE", "TSE", "XETR", "EURONEXT", "ASX", "SGX", "BURSA"}


@respx.mock
async def test_screener_native_param_mapping(monkeypatch):
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    route = respx.get("https://financialmodelingprep.com/stable/company-screener").respond(
        200, json=[{"symbol": "AAPL", "price": 189.5, "marketCap": 2.9e12}])
    p = make_provider(monkeypatch)
    rows = await p.screener(market="US", filters={"market_cap": {"min": 1e9, "max": 5e12},
                                                  "price": {"min": 10},
                                                  "volume": {"max": 1e7},
                                                  "dividend_yield": {"min": 0.5}},
                            limit=7)
    assert rows[0]["symbol"] == "AAPL" and route.called
    params = respx.calls[0].request.url.params
    assert params["marketCapMoreThan"] == "1000000000.0"
    assert params["marketCapLowerThan"] == "5000000000000.0"
    assert params["priceMoreThan"] == "10" and "priceLowerThan" not in params
    assert params["volumeLowerThan"] == "10000000.0" and "volumeMoreThan" not in params
    assert params["dividendMoreThan"] == "0.5"
    assert params["limit"] == "7" and params["apikey"] == "test-key"


async def test_screener_tv_only_filter_is_not_found(monkeypatch):
    from unified_finance_mcp.errors import NotFound
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound) as ei:
        await p.screener(market="US", filters={"rsi": {"min": 30}})
    assert "tv-only" in str(ei.value)


async def test_screener_non_us_market_is_provider_error(monkeypatch):
    from unified_finance_mcp.errors import ProviderError
    p = make_provider(monkeypatch)
    with pytest.raises(ProviderError):
        await p.screener(market="HK")


@respx.mock
async def test_screener_no_filters(monkeypatch):
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    route = respx.get("https://financialmodelingprep.com/stable/company-screener").respond(
        200, json=[{"symbol": "AAPL"}])
    p = make_provider(monkeypatch)
    assert (await p.screener())[0]["symbol"] == "AAPL" and route.called
    assert respx.calls[0].request.url.params["limit"] == "25"
