from unittest.mock import MagicMock

import pytest

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound
from unified_finance_mcp.providers.yahoo import YahooProvider
from unified_finance_mcp.symbols import parse_symbol


def make_provider(monkeypatch, ticker_mock=None, search_mock=None):
    import yfinance as yf
    monkeypatch.setattr(yf, "Ticker", lambda s: ticker_mock)
    monkeypatch.setattr(yf, "Search", lambda q, **kw: search_mock)
    return YahooProvider(get_settings())


async def test_quote_maps_fast_info(monkeypatch):
    t = MagicMock()
    t.fast_info = {"lastPrice": 189.5, "marketCap": 2.9e12, "currency": "USD"}
    t.info = {"shortName": "Apple Inc.", "regularMarketPrice": 189.5}
    p = make_provider(monkeypatch, t)
    q = await p.quote(parse_symbol("AAPL"))
    assert q["symbol"] == "AAPL" and q["price"] == 189.5 and q["currency"] == "USD"
    assert q["market_cap"] == 2.9e12 and q["source"] == "yahoo"


async def test_quote_accepts_snake_case_fast_info(monkeypatch):
    # yfinance FastInfo exposes snake_case keys (last_price / market_cap).
    t = MagicMock()
    t.fast_info = {"last_price": 12.25, "market_cap": 5_000, "currency": "HKD"}
    p = make_provider(monkeypatch, t)
    q = await p.quote(parse_symbol("HK.00700"))
    assert q["symbol"] == "0700.HK" and q["price"] == 12.25 and q["market_cap"] == 5_000


class FakeFastInfo:
    """Mimics yfinance FastInfo: lazy per-key fetch via .get(), camelCase key space.

    dict(FastInfo) would fetch once per key; we assert quote() goes through .get()
    inside the worker thread instead.
    """

    def __init__(self, values):
        self._values = values
        self.get_calls = []

    def keys(self):
        return list(self._values)

    def get(self, key, default=None):
        self.get_calls.append(key)
        return self._values.get(key, default)

    def __iter__(self):
        raise AssertionError("FastInfo must not be iterated (blocking fetch per key)")

    def __getitem__(self, key):
        raise AssertionError("FastInfo must not be indexed on the event loop")


async def test_quote_reads_fastinfo_object_via_get(monkeypatch):
    fi = FakeFastInfo({"last_price": 123.45, "market_cap": 999, "currency": "USD"})
    t = MagicMock()
    type(t).fast_info = property(lambda s: fi)
    p = make_provider(monkeypatch, t)
    q = await p.quote(parse_symbol("AAPL"))
    assert q["price"] == 123.45 and q["market_cap"] == 999 and q["currency"] == "USD"
    # proves the object's .get() path was used, not dict(...)
    assert "last_price" in fi.get_calls and "lastPrice" in fi.get_calls


async def test_history_rows(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.history.return_value = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [100]},
        index=pd.to_datetime(["2026-01-02"]))
    p = make_provider(monkeypatch, t)
    rows = await p.history(parse_symbol("AAPL"), interval="1d")
    assert rows == [{"date": "2026-01-02", "open": 1.0, "high": 2.0,
                     "low": 0.5, "close": 1.5, "volume": 100}]


async def test_history_named_date_index(monkeypatch):
    # Real yfinance names the daily index "Date".
    import pandas as pd
    t = MagicMock()
    t.history.return_value = pd.DataFrame(
        {"Open": [1.0], "Close": [1.5], "Volume": [9]},
        index=pd.to_datetime(["2026-01-02"]).rename("Date"))
    p = make_provider(monkeypatch, t)
    rows = await p.history(parse_symbol("AAPL"), interval="1d")
    assert rows == [{"date": "2026-01-02", "open": 1.0, "close": 1.5, "volume": 9}]


async def test_history_intraday_datetime_index(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.history.return_value = pd.DataFrame(
        {"Open": [1.0], "Close": [1.5], "Volume": [7]},
        index=pd.to_datetime(["2026-01-02 09:30:00"]).rename("Datetime"))
    p = make_provider(monkeypatch, t)
    rows = await p.history(parse_symbol("AAPL"), interval="1h")
    assert rows == [{"date": "2026-01-02", "open": 1.0, "close": 1.5, "volume": 7}]


async def test_history_empty_frame(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.history.return_value = pd.DataFrame()
    p = make_provider(monkeypatch, t)
    assert await p.history(parse_symbol("AAPL")) == []


async def test_company_info(monkeypatch):
    t = MagicMock()
    t.info = {"shortName": "Apple Inc.", "sector": "Technology"}
    p = make_provider(monkeypatch, t)
    info = await p.company_info(parse_symbol("AAPL"))
    assert info["shortName"] == "Apple Inc." and info["sector"] == "Technology"


async def test_financial_report_columns_to_records(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.get_income_stmt.return_value = pd.DataFrame(
        {"2025-09-30": {"Total Revenue": 100, "Net Income": 20}})
    p = make_provider(monkeypatch, t)
    rows = await p.financial_report(parse_symbol("AAPL"), "income", "annual")
    assert rows[0]["date"] == "2025-09-30" and rows[0]["Total Revenue"] == 100
    assert t.get_income_stmt.call_args.kwargs["freq"] == "yearly"


async def test_financial_report_quarterly_freq_and_statement_map(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.get_balance_sheet.return_value = pd.DataFrame({"2025-06-30": {"Total Assets": 42}})
    p = make_provider(monkeypatch, t)
    rows = await p.financial_report(parse_symbol("AAPL"), "balance", "quarterly")
    assert rows == [{"date": "2025-06-30", "Total Assets": 42}]
    assert t.get_balance_sheet.call_args.kwargs["freq"] == "quarterly"


async def test_news_maps_nested_content(monkeypatch):
    # yfinance >=1.0 nests article fields under "content".
    t = MagicMock()
    t.news = [
        {"id": "1", "content": {
            "title": "Apple ships something",
            "provider": {"displayName": "Reuters"},
            "canonicalUrl": {"url": "https://example.com/a"},
            "pubDate": "2026-01-07T22:00:38Z"}},
        {"id": "2", "content": {"title": "Second", "provider": {"displayName": "AP"},
                                "previewUrl": "https://example.com/b",
                                "pubDate": "2026-01-08T01:00:00Z"}},
    ]
    p = make_provider(monkeypatch, t)
    items = await p.news(parse_symbol("AAPL"), limit=1)
    assert items == [{"title": "Apple ships something", "publisher": "Reuters",
                      "link": "https://example.com/a", "published": "2026-01-07T22:00:38Z",
                      "source": "yahoo"}]


async def test_news_maps_legacy_flat_items(monkeypatch):
    # Older yfinance returned flat keys; keep reading them.
    t = MagicMock()
    t.news = [{"title": "Old shape", "publisher": "Bloomberg",
               "link": "https://example.com/c", "providerPublishTime": 1767830400}]
    p = make_provider(monkeypatch, t)
    items = await p.news(parse_symbol("AAPL"))
    assert items == [{"title": "Old shape", "publisher": "Bloomberg",
                      "link": "https://example.com/c", "published": 1767830400,
                      "source": "yahoo"}]


async def test_ownership_rows(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.institutional_holders = pd.DataFrame({"Holder": ["Vanguard"], "Shares": [1234]})
    p = make_provider(monkeypatch, t)
    rows = await p.ownership(parse_symbol("AAPL"), "institutional")
    assert rows[0]["Holder"] == "Vanguard" and rows[0]["Shares"] == "1234"


async def test_ownership_none_is_empty(monkeypatch):
    t = MagicMock()
    t.insider_roster_holders = None
    p = make_provider(monkeypatch, t)
    assert await p.ownership(parse_symbol("AAPL"), "insider_roster") == []


async def test_search_maps_quotes(monkeypatch):
    s = MagicMock()
    s.quotes = [{"symbol": "AAPL", "shortname": "Apple Inc.",
                 "exchange": "NMS", "quoteType": "EQUITY"},
                {"symbol": "AAPL.MX", "longname": "Apple Inc. (MX)",
                 "exchange": "MEX", "quoteType": "EQUITY"}]
    p = make_provider(monkeypatch, search_mock=s)
    rows = await p.search("apple", limit=5)
    assert rows[0] == {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NMS",
                       "type": "EQUITY", "source": "yahoo"}
    assert rows[1]["name"] == "Apple Inc. (MX)"


async def test_error_wraps_as_provider_error(monkeypatch):
    from unified_finance_mcp.errors import ProviderError
    t = MagicMock()
    t.fast_info = property(lambda s: (_ for _ in ()).throw(RuntimeError("boom")))
    type(t).fast_info = property(lambda s: (_ for _ in ()).throw(RuntimeError("boom")))
    p = make_provider(monkeypatch, t)
    with pytest.raises(ProviderError):
        await p.quote(parse_symbol("AAPL"))


async def test_unknown_statement_and_holder_kind_raise_provider_error(monkeypatch):
    from unified_finance_mcp.errors import ProviderError
    t = MagicMock()
    p = make_provider(monkeypatch, t)
    with pytest.raises(ProviderError):
        await p.financial_report(parse_symbol("AAPL"), "nope", "annual")
    with pytest.raises(ProviderError):
        await p.ownership(parse_symbol("AAPL"), "nope")


# ── option_chain / short_interest / analyst_estimates / insider_summary ────

async def test_option_chain_nearest_expiry(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.options = ("2025-09-19", "2025-09-26")
    calls = pd.DataFrame({"strike": [220.0], "lastPrice": [14.2],
                          "openInterest": [29512], "impliedVolatility": [0.313]})
    puts = pd.DataFrame({"strike": [220.0], "lastPrice": [1.1]})
    underlying = {"regularMarketPrice": 232.5, "currency": "USD",
                  "fullExchangeName": "NasdaqGS", "shortName": "Apple Inc."}
    t.option_chain = lambda d: type("OC", (), {"calls": calls, "puts": puts,
                                               "underlying": underlying})
    p = make_provider(monkeypatch, t)
    out = await p.option_chain(parse_symbol("AAPL"))
    assert out["underlying"] == "AAPL" and out["expiration"] == "2025-09-19"
    assert out["available_expirations"] == ["2025-09-19", "2025-09-26"]
    assert out["calls"][0]["strike"] == 220.0 and out["puts"][0]["lastPrice"] == 1.1
    assert out["quote"]["price"] == 232.5 and out["source"] == "yahoo"


async def test_option_chain_no_listed_raises_not_found(monkeypatch):
    from unified_finance_mcp.errors import NotFound
    t = MagicMock()
    t.options = ()
    p = make_provider(monkeypatch, t)
    with pytest.raises(NotFound):
        await p.option_chain(parse_symbol("AAPL"))


async def test_option_chain_bad_expiration_raises_not_found(monkeypatch):
    from unified_finance_mcp.errors import NotFound
    t = MagicMock()
    t.options = ("2025-09-19",)
    p = make_provider(monkeypatch, t)
    with pytest.raises(NotFound) as exc_info:
        await p.option_chain(parse_symbol("AAPL"), "2025-12-31")
    assert "2025-09-19" in str(exc_info.value)


async def test_short_interest_maps_info_keys(monkeypatch):
    t = MagicMock()
    t.info = {"sharesShort": 11345000, "sharesShortPriorMonth": 10900000,
              "shortRatio": 0.97, "shortPercentOfFloat": 0.0731,
              "shortPercentOfSharesOutstanding": 0.0455,
              "dateShortInterest": 1756252800, "sharesFloat": 155200000,
              "sharesOutstanding": 421800000,
              "heldPercentInsiders": 0.113, "heldPercentInstitutions": 0.62}
    p = make_provider(monkeypatch, t)
    out = await p.short_interest(parse_symbol("GME"))
    assert out["symbol"] == "GME" and out["shares_short"] == 11345000
    assert out["short_percent_of_float"] == 0.0731
    assert out["short_ratio"] == 0.97 and out["source"] == "yahoo"


async def test_short_interest_no_data_not_found(monkeypatch):
    from unified_finance_mcp.errors import NotFound
    t = MagicMock()
    t.info = {}
    p = make_provider(monkeypatch, t)
    with pytest.raises(NotFound):
        await p.short_interest(parse_symbol("AAPL"))


async def test_analyst_estimates_full_shape(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.analyst_price_targets = {"current": 232.5, "mean": 245.3,
                               "high": 280.0, "low": 180.0,
                               "numberOfAnalysts": 34}
    t.earnings_estimate = pd.DataFrame({"period": ["0q"], "avg": [1.65]})
    t.revenue_estimate = pd.DataFrame({"period": ["0q"], "avg": [94e9]})
    t.growth_estimates = pd.DataFrame({"period": ["0q"], "stockTrend": [0.08]})
    t.eps_trend = pd.DataFrame({"period": ["0q"], "current": [1.65]})
    t.recommendations = pd.DataFrame({"period": ["0m"], "strongBuy": [12]})
    p = make_provider(monkeypatch, t)
    out = await p.analyst_estimates(parse_symbol("AAPL"))
    assert out["symbol"] == "AAPL" and out["price_targets"]["mean"] == 245.3
    assert out["earnings_estimate"][0]["avg"] == 1.65
    assert len(out["recommendations"]) <= 20 and out["source"] == "yahoo"


async def test_analyst_estimates_nothing_raises_not_found(monkeypatch):
    from unified_finance_mcp.errors import NotFound
    t = MagicMock()
    t.analyst_price_targets = {}
    t.earnings_estimate = None
    t.revenue_estimate = t.growth_estimates = t.eps_trend = t.recommendations = None
    p = make_provider(monkeypatch, t)
    with pytest.raises(NotFound):
        await p.analyst_estimates(parse_symbol("AAPL"))


async def test_ownership_insider_summary_aggregates(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.insider_purchases = pd.DataFrame({
        "Net Sh Activity": [-312000], "Net %": [-0.041],
        "Purchases": [12000], "Sales": [324000]})
    p = make_provider(monkeypatch, t)
    rows = await p.ownership(parse_symbol("AAPL"), "insider_summary")
    assert rows == [{"symbol": "AAPL",
                     "net_sh_activity": -312000, "net_percent": -0.041,
                     "purchases": 12000, "sales": 324000, "source": "yahoo"}]



async def test_ownership_insider_summary_empty(monkeypatch):
    t = MagicMock()
    t.insider_purchases = None
    p = make_provider(monkeypatch, t)
    assert await p.ownership(parse_symbol("AAPL"), "insider_summary") == []


# ── dividend_split_history / earnings_history ───────────────────────────────

async def test_dividend_split_history_full_payload(monkeypatch):
    import datetime as _dt

    import pandas as pd
    t = MagicMock()
    t.dividends = pd.Series(
        [0.26, 0.27],
        index=pd.to_datetime(["2026-05-11", "2026-08-10"]))
    t.splits = pd.Series([4.0], index=pd.to_datetime(["2020-08-31"]))
    t.calendar = {"Dividend Date": _dt.date(2026, 8, 13),
                  "Ex-Dividend Date": _dt.date(2026, 8, 10),
                  "Earnings Date": [_dt.date(2026, 10, 30)],
                  "Earnings High": 2.07, "Earnings Low": 1.93,
                  "Earnings Average": 1.98124,
                  "Revenue High": 117219700000, "Revenue Low": 112248100000,
                  "Revenue Average": 113624521680}
    p = make_provider(monkeypatch, t)
    out = await p.dividend_split_history(parse_symbol("AAPL"))
    assert out["symbol"] == "AAPL" and out["source"] == "yahoo"
    kinds = [e["kind"] for e in out["next_events"]]
    assert kinds == ["dividend", "earnings"]
    assert out["dividends"][-1] == {"kind": "dividend", "date": "2026-08-10",
                                    "value": 0.27, "source": "yahoo"}
    assert out["splits"] == [{"kind": "split", "date": "2020-08-31",
                              "value": 4.0, "source": "yahoo"}]
    earn = out["next_events"][1]
    # Dates must come back ISO-stringified for JSON-RPC (live-verified bug fix).
    assert earn["date"] == "2026-10-30"
    assert out["next_events"][0]["date"] == "2026-08-13"
    assert out["next_events"][0]["ex_date"] == "2026-08-10"
    assert earn["eps_estimate_avg"] == 1.98124
    assert earn["revenue_estimate_avg"] == 113624521680


async def test_dividend_split_history_no_calendar(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.dividends = pd.Series([0.5], index=pd.to_datetime(["2025-01-10"]))
    t.splits = pd.Series([], dtype=float)
    t.calendar = None  # some tickers 404 on calendar
    p = make_provider(monkeypatch, t)
    out = await p.dividend_split_history(parse_symbol("AAPL"))
    assert out["next_events"] == []
    assert out["dividends"][0]["value"] == 0.5


async def test_dividend_split_history_nothing_raises_not_found(monkeypatch):
    t = MagicMock()
    t.dividends = None
    t.splits = None
    t.calendar = None
    p = make_provider(monkeypatch, t)
    with pytest.raises(NotFound):
        await p.dividend_split_history(parse_symbol("AAPL"))


async def test_earnings_history_maps_frame(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.earnings_dates = pd.DataFrame(
        {"EPS Estimate": [1.98, 1.89], "Reported EPS": [None, 2.02],
         "Surprise(%)": [None, 6.74]},
        index=pd.to_datetime(["2026-10-29", "2026-07-30"]).rename("Earnings Date"))
    p = make_provider(monkeypatch, t)
    rows = await p.earnings_history(parse_symbol("AAPL"), limit=12)
    assert rows[0]["date"] == "2026-10-29" and rows[0]["eps_estimate"] == 1.98
    assert rows[0]["reported_eps"] is None
    assert rows[1]["reported_eps"] == 2.02 and rows[1]["surprise_pct"] == 6.74
    assert rows[0]["source"] == "yahoo"


async def test_earnings_history_empty_raises_not_found(monkeypatch):
    t = MagicMock()
    t.earnings_dates = None
    p = make_provider(monkeypatch, t)
    with pytest.raises(NotFound):
        await p.earnings_history(parse_symbol("AAPL"))


async def test_earnings_history_limit_applied(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.earnings_dates = pd.DataFrame(
        {"EPS Estimate": [1.0] * 20, "Reported EPS": [1.1] * 20,
         "Surprise(%)": [10.0] * 20},
        index=pd.date_range("2025-01-01", periods=20, freq="30D"))
    p = make_provider(monkeypatch, t)
    rows = await p.earnings_history(parse_symbol("AAPL"), limit=5)
    assert len(rows) == 5
