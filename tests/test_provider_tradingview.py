"""TradingView provider tests: TA ratings + screener (libs mocked; no network)."""
from unittest.mock import MagicMock

import pandas as pd
import pytest

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound, ProviderError
from unified_finance_mcp.providers.tradingview import MARKET_TO_TV_SCREENER, TradingViewProvider
from unified_finance_mcp.symbols import parse_symbol


def make_provider():
    return TradingViewProvider(get_settings())


def analysis_stub(**indicators):
    a = MagicMock()
    a.summary = {}
    a.oscillators = {}
    a.moving_averages = {}
    a.indicators = indicators
    return a


async def test_technicals_summary(monkeypatch):
    analysis = MagicMock()
    analysis.summary = {"RECOMMENDATION": "BUY", "BUY": 12, "SELL": 3, "NEUTRAL": 11}
    analysis.oscillators = {"RECOMMENDATION": "NEUTRAL"}
    analysis.moving_averages = {"RECOMMENDATION": "BUY"}
    analysis.indicators = {"RSI": 55.0, "close": 100.0, "open": None}
    monkeypatch.setattr(
        "unified_finance_mcp.providers.tradingview._get_analysis",
        lambda exch, sym, interval: analysis)
    p = make_provider()
    out = await p.technicals(parse_symbol("EGX:COMI"))
    assert out["summary"]["RECOMMENDATION"] == "BUY" and out["exchange"] == "EGX"
    assert out["oscillators"]["RECOMMENDATION"] == "NEUTRAL"
    assert out["moving_averages"]["RECOMMENDATION"] == "BUY"
    assert out["source"] == "tradingview"
    assert out["interval"] == "1d"
    assert out["indicators"] == {"RSI": 55.0, "close": 100.0}  # None values dropped
    assert out["symbol"] == "COMI"


async def test_technicals_hk_strips_zero_padding(monkeypatch):
    # HK.00700 -> tv() gives HKEX:00700; TradingView expects 700 (Task 3 known gap).
    captured = {}

    def fake(exch, sym, interval):
        captured.update(exch=exch, sym=sym, interval=interval)
        return analysis_stub()

    monkeypatch.setattr("unified_finance_mcp.providers.tradingview._get_analysis", fake)
    p = make_provider()
    await p.technicals(parse_symbol("HK.00700"))
    assert captured == {"exch": "HKEX", "sym": "700", "interval": "1d"}


async def test_technicals_non_hk_local_passthrough(monkeypatch):
    captured = {}

    def fake(exch, sym, interval):
        captured.update(exch=exch, sym=sym)
        return analysis_stub()

    monkeypatch.setattr("unified_finance_mcp.providers.tradingview._get_analysis", fake)
    p = make_provider()
    await p.technicals(parse_symbol("AAPL"))
    assert captured == {"exch": "NASDAQ", "sym": "AAPL"}


async def test_technicals_custom_interval(monkeypatch):
    captured = {}

    def fake(exch, sym, interval):
        captured.update(interval=interval)
        return analysis_stub()

    monkeypatch.setattr("unified_finance_mcp.providers.tradingview._get_analysis", fake)
    p = make_provider()
    await p.technicals(parse_symbol("AAPL"), interval="4h")
    assert captured["interval"] == "4h"


async def test_technicals_error_wraps_as_provider_error(monkeypatch):
    def boom(exch, sym, interval):
        raise RuntimeError("boom")

    monkeypatch.setattr("unified_finance_mcp.providers.tradingview._get_analysis", boom)
    p = make_provider()
    with pytest.raises(ProviderError):
        await p.technicals(parse_symbol("AAPL"))


class FakeQuery:
    """Stand-in for tradingview_screener.Query capturing the chain calls."""

    def __init__(self):
        self.captured = {}

    def set_markets(self, *markets):
        self.captured["markets"] = markets
        return self

    def select(self, *cols):
        self.captured["cols"] = cols
        return self

    def order_by(self, col, ascending=True, **kwargs):
        self.captured["sort"] = (col, ascending)
        return self

    def where(self, *exprs):
        self.captured.setdefault("wheres", []).extend(exprs)
        return self

    def limit(self, n):
        self.captured["limit"] = n
        return self

    def get_scanner_data(self):
        return 1, self.captured["df"]


def patch_query(monkeypatch, q):
    # The provider binds Query via "from tradingview_screener import Query", so we
    # patch the provider's own binding, not the tradingview_screener module attribute.
    monkeypatch.setattr("unified_finance_mcp.providers.tradingview.Query", lambda: q)
    return q


async def test_screener_egypt_market_slug(monkeypatch):
    q = patch_query(monkeypatch, FakeQuery())
    q.captured["df"] = pd.DataFrame(
        [{"name": "COMI", "close": 80.0, "market_cap_basic": 2.4e11}])
    p = make_provider()
    rows = await p.screener(market="EG", limit=5)
    assert q.captured["markets"] == ("egypt",) and rows[0]["name"] == "COMI"
    assert rows[0]["market_cap_basic"] == 2.4e11
    assert q.captured["limit"] == 5
    assert "name" in q.captured["cols"] and "close" in q.captured["cols"]
    # default sort desc -> ascending=False on the real lib signature
    assert q.captured["sort"] == ("market_cap_basic", False)


class FakeColumn:
    def __init__(self, name):
        self.name = name

    def __ge__(self, other):
        return {"left": self.name, "operation": "egreater", "right": other}

    def __le__(self, other):
        return {"left": self.name, "operation": "eless", "right": other}


async def test_screener_filters_map_to_screener_columns(monkeypatch):
    q = patch_query(monkeypatch, FakeQuery())
    q.captured["df"] = pd.DataFrame()
    monkeypatch.setattr("unified_finance_mcp.providers.tradingview.Column", FakeColumn)
    p = make_provider()
    await p.screener(market="US", filters={"price": {"min": 10, "max": 20},
                                           "market_cap": {"min": 1e9},
                                           "bogus_field": {"min": 1}})
    exprs = q.captured["wheres"]
    assert [e["left"] for e in exprs] == ["close", "close", "market_cap_basic"]
    assert [e["operation"] for e in exprs] == ["egreater", "eless", "egreater"]
    assert [e["right"] for e in exprs] == [10, 20, 1e9]


async def test_screener_sort_maps_field_and_asc_order(monkeypatch):
    q = patch_query(monkeypatch, FakeQuery())
    q.captured["df"] = pd.DataFrame()
    p = make_provider()
    await p.screener(market="US", sort="price", order="asc")
    assert q.captured["sort"] == ("close", True)


async def test_screener_name_sort_dedupes_columns(monkeypatch):
    q = patch_query(monkeypatch, FakeQuery())
    q.captured["df"] = pd.DataFrame()
    p = make_provider()
    await p.screener(market="US", sort="name")
    assert q.captured["cols"].count("name") == 1
    assert q.captured["sort"] == ("name", False)


async def test_screener_unsupported_market():
    p = make_provider()
    with pytest.raises(NotFound):
        await p.screener(market="ANTARCTICA")


async def test_screener_error_wraps_as_provider_error(monkeypatch):
    class FailingQuery(FakeQuery):
        def get_scanner_data(self):
            raise RuntimeError("scanner down")

    patch_query(monkeypatch, FailingQuery())
    p = make_provider()
    with pytest.raises(ProviderError):
        await p.screener(market="US")


def test_market_slug_map_covers_major_markets():
    assert MARKET_TO_TV_SCREENER["US"] == "america"
    assert MARKET_TO_TV_SCREENER["HK"] == "hongkong"
    assert MARKET_TO_TV_SCREENER["EG"] == "egypt"
    assert MARKET_TO_TV_SCREENER["KR"] == "korea"
    assert MARKET_TO_TV_SCREENER["JP"] == "japan"
    assert set(MARKET_TO_TV_SCREENER) >= {
        "US", "HK", "CN", "EG", "JP", "UK", "CA", "AU", "DE", "FR",
        "KR", "TW", "IN", "SG", "MY", "TR"}
