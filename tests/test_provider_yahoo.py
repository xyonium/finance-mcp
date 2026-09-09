from unittest.mock import MagicMock

import pytest

from unified_finance_mcp.config import get_settings
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
