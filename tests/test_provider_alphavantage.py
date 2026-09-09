"""Alpha Vantage provider tests: all respx-mocked, zero live AV calls.

AV's free tier is ~25 requests/day, so no test may touch www.alphavantage.co.
The `make_provider` helper deviates from the brief's `"k"` key: it uses
"test-key" (the FMP suite's convention) so the leak assertion is meaningful,
and pins ALPHAVANTAGE_BASE_URL so the request target can never drift to a live
host. The brief's `BASE` constant and its 5 verbatim tests are unchanged.
"""
import pytest
import respx

from unified_finance_mcp.config import DEFAULT_AV_BASE_URL, get_settings
from unified_finance_mcp.errors import NotFound, ProviderError, RateLimited
from unified_finance_mcp.providers.alphavantage import (
    ECONOMIC_INDICATORS,
    AlphaVantageProvider,
)
from unified_finance_mcp.symbols import parse_symbol

BASE = "https://www.alphavantage.co/query"


def make_provider(monkeypatch, base=DEFAULT_AV_BASE_URL):
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test-key")
    monkeypatch.setenv("ALPHAVANTAGE_BASE_URL", base)
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    return AlphaVantageProvider(get_settings())


@respx.mock
async def test_quote(monkeypatch):
    respx.get(BASE).respond(200, json={"Global Quote": {"05. price": "189.50",
                                                         "08. previous close": "188.0"}})
    p = make_provider(monkeypatch)
    q = await p.quote(parse_symbol("AAPL"))
    assert q["price"] == 189.5


@respx.mock
async def test_note_body_is_rate_limited(monkeypatch):
    respx.get(BASE).respond(200, json={"Note": "Thank you for using Alpha Vantage! "
                                               "Our standard API rate limit is 25 requests per day."})
    p = make_provider(monkeypatch)
    with pytest.raises(RateLimited):
        await p.quote(parse_symbol("AAPL"))


@respx.mock
async def test_information_body_is_rate_limited(monkeypatch):
    respx.get(BASE).respond(200, json={"Information": "premium endpoint"})
    p = make_provider(monkeypatch)
    with pytest.raises(RateLimited):
        await p.economic("GDP")


@respx.mock
async def test_empty_global_quote_is_not_found(monkeypatch):
    respx.get(BASE).respond(200, json={"Global Quote": {}})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.quote(parse_symbol("AAPL"))


@respx.mock
async def test_economic_series(monkeypatch):
    respx.get(BASE).respond(200, json={"name": "Real Gross Domestic Product",
                                       "data": [{"date": "2025-01-01", "value": "23000.0"}]})
    p = make_provider(monkeypatch)
    rows = await p.economic("GDP")
    assert rows[0]["date"] == "2025-01-01" and rows[0]["value"] == 23000.0


@respx.mock
async def test_quote_params_symbol_and_apikey(monkeypatch):
    respx.get(BASE).respond(200, json={"Global Quote": {"01. symbol": "AAPL",
                                                        "05. price": "189.50",
                                                        "06. volume": "50000000",
                                                        "09. change": "1.50",
                                                        "10. change percent": "0.7978%"}})
    p = make_provider(monkeypatch)
    q = await p.quote(parse_symbol("AAPL"))
    params = respx.calls[0].request.url.params
    assert params["function"] == "GLOBAL_QUOTE" and params["symbol"] == "AAPL"
    assert params["apikey"] == "test-key"
    assert q["symbol"] == "AAPL" and q["previous_close"] is None  # key absent -> None
    assert q["volume"] == 50_000_000          # str -> int
    assert q["change"] == 1.5 and q["change_percent"] == 0.7978  # trailing % stripped
    assert q["source"] == "alphavantage"


@respx.mock
async def test_history_daily_sorted_and_numeric(monkeypatch):
    respx.get(BASE).respond(200, json={
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (Daily)": {
            "2026-01-03": {"1. open": "188.0", "2. high": "190.0", "3. low": "187.0",
                           "4. close": "189.5", "5. volume": "50000000"},
            "2026-01-02": {"1. open": "187.0", "2. high": "188.0", "3. low": "186.0",
                           "4. close": "188.0", "5. volume": "40000000"}}})
    p = make_provider(monkeypatch)
    rows = await p.history(parse_symbol("AAPL"))
    params = respx.calls[0].request.url.params
    assert params["function"] == "TIME_SERIES_DAILY" and params["outputsize"] == "compact"
    assert [r["date"] for r in rows] == ["2026-01-02", "2026-01-03"]  # ascending
    assert rows[0]["close"] == 188.0 and rows[0]["volume"] == 40_000_000
    assert rows[1]["close"] == 189.5


@respx.mock
async def test_history_intraday_interval_and_full_outputsize(monkeypatch):
    respx.get(BASE).respond(200, json={
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (5min)": {"2026-01-02 16:00:00": {"1. open": "188.0",
                                                       "4. close": "189.5",
                                                       "5. volume": "100"}}})
    p = make_provider(monkeypatch)
    rows = await p.history(parse_symbol("AAPL"), interval="5m", start="2026-01-01",
                           end="2026-01-31")
    params = respx.calls[0].request.url.params
    assert params["function"] == "TIME_SERIES_INTRADAY"
    assert params["interval"] == "5min" and params["outputsize"] == "full"
    assert rows[0]["date"] == "2026-01-02 16:00:00" and rows[0]["close"] == 189.5


@respx.mock
async def test_history_daily_widens_to_full_when_start_given(monkeypatch):
    """AV has no date params: a start date can predate the compact (100-bar) window."""
    respx.get(BASE).respond(200, json={"Time Series (Daily)": {
        "2024-01-02": {"4. close": "150.0", "5. volume": "1"}}})
    p = make_provider(monkeypatch)
    rows = await p.history(parse_symbol("AAPL"), start="2024-01-01")
    assert respx.calls[0].request.url.params["outputsize"] == "full"
    assert rows[0]["date"] == "2024-01-02"


@respx.mock
async def test_history_filters_out_of_range_dates(monkeypatch):
    respx.get(BASE).respond(200, json={
        "Time Series (Daily)": {
            "2026-01-02": {"4. close": "188.0", "5. volume": "1"},
            "2025-12-31": {"4. close": "187.0", "5. volume": "2"},
            "2026-02-28": {"4. close": "190.0", "5. volume": "3"}}})
    p = make_provider(monkeypatch)
    rows = await p.history(parse_symbol("AAPL"), start="2026-01-01", end="2026-01-31")
    assert [r["date"] for r in rows] == ["2026-01-02"]
    respx.get(BASE).respond(200, json={
        "Time Series (Daily)": {
            "2026-01-02": {"4. close": "188.0", "5. volume": "1"},
            "2025-12-31": {"4. close": "187.0", "5. volume": "2"},
            "2026-02-28": {"4. close": "190.0", "5. volume": "3"}}})
    p = make_provider(monkeypatch)
    rows = await p.history(parse_symbol("AAPL"), start="2026-01-01", end="2026-01-31")
    assert [r["date"] for r in rows] == ["2026-01-02"]


@respx.mock
async def test_history_empty_time_series_is_not_found(monkeypatch):
    respx.get(BASE).respond(200, json={"Meta Data": {}, "Time Series (Daily)": {}})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.history(parse_symbol("AAPL"))


@respx.mock
async def test_company_info_overview(monkeypatch):
    respx.get(BASE).respond(200, json={"Symbol": "AAPL", "Name": "Apple Inc",
                                       "Sector": "TECHNOLOGY", "MarketCapitalization": "2900000000000",
                                       "Beta": "1.24", "DividendPerShare": "None"})
    p = make_provider(monkeypatch)
    info = await p.company_info(parse_symbol("AAPL"))
    params = respx.calls[0].request.url.params
    assert params["function"] == "OVERVIEW" and params["symbol"] == "AAPL"
    assert info["Name"] == "Apple Inc" and info["Sector"] == "TECHNOLOGY"
    assert info["MarketCapitalization"] == 2.9e12 and info["Beta"] == 1.24
    assert info["DividendPerShare"] is None  # AV's "None" string -> None
    assert info["source"] == "alphavantage"


@respx.mock
async def test_company_info_empty_overview_is_not_found(monkeypatch):
    respx.get(BASE).respond(200, json={})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.company_info(parse_symbol("AAPL"))


@respx.mock
async def test_financial_report_annual(monkeypatch):
    respx.get(BASE).respond(200, json={
        "symbol": "AAPL",
        "annualReports": [{"fiscalDateEnding": "2025-09-30", "totalRevenue": "391035000000",
                           "netIncome": "93736000000"}]})
    p = make_provider(monkeypatch)
    rows = await p.financial_report(parse_symbol("AAPL"), "income", "annual")
    params = respx.calls[0].request.url.params
    assert params["function"] == "INCOME_STATEMENT" and params["symbol"] == "AAPL"
    assert rows[0]["fiscalDateEnding"] == "2025-09-30"   # not coerced to a number
    assert rows[0]["totalRevenue"] == 391_035_000_000.0


@respx.mock
async def test_financial_report_quarterly_cash_flow(monkeypatch):
    respx.get(BASE).respond(200, json={
        "symbol": "AAPL",
        "quarterlyReports": [{"fiscalDateEnding": "2025-06-30",
                              "operatingCashflow": "28000000000"}],
        "annualReports": [{"fiscalDateEnding": "2025-09-30", "operatingCashflow": "1"}]})
    p = make_provider(monkeypatch)
    rows = await p.financial_report(parse_symbol("AAPL"), "cashflow", "quarterly")
    assert respx.calls[0].request.url.params["function"] == "CASH_FLOW"
    assert rows[0]["fiscalDateEnding"] == "2025-06-30"    # quarterly bucket wins
    assert rows[0]["operatingCashflow"] == 28_000_000_000.0


@respx.mock
async def test_financial_report_balance_sheet(monkeypatch):
    respx.get(BASE).respond(200, json={"annualReports": [{"totalAssets": "364000000000"}]})
    p = make_provider(monkeypatch)
    rows = await p.financial_report(parse_symbol("AAPL"), "balance")
    assert respx.calls[0].request.url.params["function"] == "BALANCE_SHEET"
    assert rows[0]["totalAssets"] == 364_000_000_000.0


async def test_financial_report_unknown_statement(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(ProviderError):
        await p.financial_report(parse_symbol("AAPL"), "bogus")


@respx.mock
async def test_news_sentiment_feed(monkeypatch):
    respx.get(BASE).respond(200, json={"feed": [
        {"title": "Apple ships", "url": "https://example.com/a",
         "time_published": "20260901T120000", "summary": "AAPL up",
         "overall_sentiment_score": "0.35",
         "ticker_sentiment": [{"ticker": "AAPL"}]}]})
    p = make_provider(monkeypatch)
    items = await p.news(parse_symbol("AAPL"), limit=5)
    params = respx.calls[0].request.url.params
    assert params["function"] == "NEWS_SENTIMENT"
    assert params["tickers"] == "AAPL" and params["limit"] == "5"
    assert items[0]["title"] == "Apple ships" and items[0]["sentiment"] == 0.35
    assert items[0]["published"] == "20260901T120000"
    assert items[0]["source"] == "alphavantage"


@respx.mock
async def test_news_empty_feed_is_not_found(monkeypatch):
    respx.get(BASE).respond(200, json={"feed": []})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.news(parse_symbol("AAPL"))


@respx.mock
async def test_economic_treasury_yield_adds_maturity(monkeypatch):
    respx.get(BASE).respond(200, json={"data": [{"date": "2026-01-01", "value": "4.25"}]})
    p = make_provider(monkeypatch)
    rows = await p.economic("TREASURY_YIELD_10Y")
    params = respx.calls[0].request.url.params
    assert params["function"] == "TREASURY_YIELD" and params["maturity"] == "10year"
    assert rows[0]["value"] == 4.25


@respx.mock
async def test_economic_cpi_monthly_interval(monkeypatch):
    respx.get(BASE).respond(200, json={"data": [{"date": "2026-01-01", "value": "315.0"}]})
    p = make_provider(monkeypatch)
    await p.economic("CPI")
    assert respx.calls[0].request.url.params["interval"] == "monthly"


async def test_economic_unknown_indicator_hints_valid_names(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(ProviderError) as ei:
        await p.economic("M2")
    assert "GDP" in str(ei.value)


@respx.mock
async def test_economic_empty_data_is_not_found(monkeypatch):
    respx.get(BASE).respond(200, json={"name": "Real GDP", "data": []})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.economic("GDP")


@respx.mock
async def test_technicals_sma_series(monkeypatch):
    respx.get(BASE).respond(200, json={
        "Meta Data": {"1: Symbol": "AAPL"},
        "Technical Analysis: SMA": {"2026-01-03": {"SMA": "188.5"},
                                    "2026-01-02": {"SMA": "188.0"}}})
    p = make_provider(monkeypatch)
    out = await p.technicals(parse_symbol("AAPL"), "SMA", interval="1d")
    params = respx.calls[0].request.url.params
    assert params["function"] == "SMA" and params["interval"] == "daily"
    assert params["time_period"] == "14" and params["series_type"] == "close"
    assert out["indicator"] == "SMA" and out["source"] == "alphavantage"
    assert out["series"]["2026-01-02"] == {"sma": 188.0}   # lower-cased inner key
    assert list(out["series"]) == ["2026-01-02", "2026-01-03"]


@respx.mock
async def test_technicals_intraday_interval_mapping(monkeypatch):
    respx.get(BASE).respond(200, json={
        "Technical Analysis: MACD": {"2026-01-02": {"MACD": "1.5", "MACD_Hist": "-0.2",
                                                    "MACD_Signal": "1.7"}}})
    p = make_provider(monkeypatch)
    out = await p.technicals(parse_symbol("AAPL"), "MACD", interval="1h")
    assert respx.calls[0].request.url.params["interval"] == "60min"
    assert out["series"]["2026-01-02"] == {"macd": 1.5, "macd_hist": -0.2, "macd_signal": 1.7}


async def test_technicals_unknown_indicator(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(ProviderError):
        await p.technicals(parse_symbol("AAPL"), "ICHIMOKU")


@respx.mock
async def test_search_best_matches(monkeypatch):
    respx.get(BASE).respond(200, json={"bestMatches": [
        {"1. symbol": "AAPL", "2. name": "Apple Inc", "3. type": "Equity",
         "4. region": "United States", "8. currency": "USD", "9. matchScore": "0.9375"}]})
    p = make_provider(monkeypatch)
    rows = await p.search("apple", limit=5)
    params = respx.calls[0].request.url.params
    assert params["function"] == "SYMBOL_SEARCH" and params["keywords"] == "apple"
    assert rows[0]["symbol"] == "AAPL" and rows[0]["name"] == "Apple Inc"
    assert rows[0]["match_score"] == 0.9375


@respx.mock
async def test_search_empty_matches_is_not_found(monkeypatch):
    respx.get(BASE).respond(200, json={"bestMatches": []})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.search("zzzz")


@respx.mock
async def test_error_message_body_is_not_found(monkeypatch):
    respx.get(BASE).respond(200, json={"Error Message": "invalid API call"})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.quote(parse_symbol("AAPL"))


@respx.mock
async def test_empty_object_body_is_not_found(monkeypatch):
    respx.get(BASE).respond(200, json={})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.quote(parse_symbol("AAPL"))


@respx.mock
async def test_rate_limited_message_carries_hint(monkeypatch):
    respx.get(BASE).respond(200, json={"Note": "rate limit exceeded"})
    p = make_provider(monkeypatch)
    with pytest.raises(RateLimited) as ei:
        await p.quote(parse_symbol("AAPL"))
    msg = str(ei.value)
    assert "quota" in msg.lower() and "rotator" in msg


async def test_non_us_symbol_is_not_found(monkeypatch):
    """AV equities are US-only: parsed.av() ValueError must become NotFound."""
    p = make_provider(monkeypatch)
    for method in (p.quote, p.company_info):
        with pytest.raises(NotFound):
            await method(parse_symbol("HK.00700"))


@respx.mock
async def test_error_messages_never_leak_the_key(monkeypatch):
    respx.get(BASE).respond(200, json={"Note": "rate limit exceeded"})
    p = make_provider(monkeypatch)
    with pytest.raises(RateLimited) as ei:
        await p.quote(parse_symbol("AAPL"))
    assert "test-key" not in str(ei.value)
    assert "test-key" not in respx.calls[0].request.url.path  # key travels in params only


@respx.mock
async def test_placeholder_apikey_when_unset(monkeypatch):
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    monkeypatch.setenv("ALPHAVANTAGE_BASE_URL", "http://api-key-rotator:8788/av")
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    respx.get("http://api-key-rotator:8788/av/query").respond(
        200, json={"Global Quote": {"05. price": "189.50"}})
    p = AlphaVantageProvider(get_settings())
    q = await p.quote(parse_symbol("AAPL"))
    assert q["price"] == 189.5
    assert respx.calls[0].request.url.params["apikey"] == "rotated-by-upstream"


async def test_available(monkeypatch):
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_BASE_URL", raising=False)
    assert not AlphaVantageProvider(get_settings()).available()
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "test-key")
    assert AlphaVantageProvider(get_settings()).available()
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    monkeypatch.setenv("ALPHAVANTAGE_BASE_URL", "http://api-key-rotator:8788/av")
    assert AlphaVantageProvider(get_settings()).available()  # rotator injects the key


def test_economic_indicator_map():
    assert ECONOMIC_INDICATORS["GDP"] == "REAL_GDP"
    assert ECONOMIC_INDICATORS["TREASURY_YIELD_10Y"] == "TREASURY_YIELD"
    assert set(ECONOMIC_INDICATORS) == {
        "GDP", "CPI", "INFLATION", "UNEMPLOYMENT", "FEDERAL_FUNDS_RATE",
        "TREASURY_YIELD_10Y", "RETAIL_SALES", "NONFARM_PAYROLL"}


CSV_BODY = ("symbol,name,reportDate,estimate\r\n"
            "AAPL,Apple Inc,2026-01-29,2.40\r\n"
            "MSFT,Microsoft Corp,2026-01-30,3.10\r\n"
            "COMI,Commercial Intl,2025-12-31,0.10\r\n")


@respx.mock
async def test_events_calendar_csv_parsed(monkeypatch):
    respx.get(BASE).respond(200, text=CSV_BODY)
    p = make_provider(monkeypatch)
    rows = await p.events_calendar("earnings")
    assert len(rows) == 3
    assert rows[0] == {"symbol": "AAPL", "name": "Apple Inc",
                       "reportDate": "2026-01-29", "estimate": "2.40"}
    assert respx.calls[0].request.url.params["function"] == "EARNINGS_CALENDAR"


@respx.mock
async def test_events_calendar_date_filtering(monkeypatch):
    respx.get(BASE).respond(200, text=CSV_BODY)
    p = make_provider(monkeypatch)
    rows = await p.events_calendar("earnings", start="2026-01-01", end="2026-01-31")
    assert [r["symbol"] for r in rows] == ["AAPL", "MSFT"]  # COMI predates start
    rows_end = await p.events_calendar("earnings", end="2026-01-29")
    assert [r["symbol"] for r in rows_end] == ["AAPL", "COMI"]  # MSFT is after end


async def test_events_calendar_non_earnings_kind_raises(monkeypatch):
    p = make_provider(monkeypatch)
    with pytest.raises(ProviderError) as ei:
        await p.events_calendar("dividends")
    assert "dividends" in str(ei.value) and "not supported" in str(ei.value)


@respx.mock
async def test_events_calendar_note_body_is_rate_limited(monkeypatch):
    respx.get(BASE).respond(200, text='{"Note": "rate limit exceeded"}')
    p = make_provider(monkeypatch)
    with pytest.raises(RateLimited):
        await p.events_calendar("earnings")


@respx.mock
async def test_events_calendar_garbage_body_is_not_found(monkeypatch):
    respx.get(BASE).respond(200, text="<html>oops</html>")
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.events_calendar("earnings")


@respx.mock
async def test_events_calendar_error_message_body_is_not_found(monkeypatch):
    respx.get(BASE).respond(200, text='{"Error Message": "invalid API call"}')
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.events_calendar("earnings")
