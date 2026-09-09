"""get_technical_indicators: tv default, per-indicator AV aggregation, fully stubbed.

Hermeticity (T10-C1 lesson): tradingview is always available()+covers();
alphavantage becomes a candidate the moment its key env is set, so both chain
members are stubbed and availability is forced at instance level
(_set_available) so results are identical keyless or keyed.
"""
import json
from unittest.mock import AsyncMock

import pytest

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound, ProviderError
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import technicals as technicals_mod


def _capture(results):
    class FakeMCP:
        def tool(self):
            def deco(fn):
                results[fn.__name__] = fn
                return fn
            return deco
    return FakeMCP()


def _set_available(providers, names, value=True):
    """Force env-dependent availability at provider-instance level."""
    for name in names:
        providers[name].available = lambda v=value: v


TV_FULL = {"symbol": "AAPL", "exchange": "NASDAQ", "interval": "1d",
           "summary": {"RECOMMENDATION": "BUY", "BUY": 12, "SELL": 3, "NEUTRAL": 11},
           "oscillators": {"RECOMMENDATION": "NEUTRAL"},
           "moving_averages": {"RECOMMENDATION": "BUY"},
           "indicators": {"RSI": 55.0, "MACD.macd": 1.2, "close": 100.0},
           "source": "tradingview"}


def _av_result(indicator):
    return {"symbol": "AAPL", "indicator": indicator, "interval": "1d",
            "time_period": 14, "series": {"2026-01-03": {"rsi": 60.0}},
            "source": "alphavantage"}


async def test_technicals_summary_default_to_tv(monkeypatch):
    # summary: tv succeeds -> alphavantage must not be called.
    providers = build_providers(get_settings())
    providers["tradingview"].technicals = AsyncMock(return_value=dict(TV_FULL))
    providers["alphavantage"].technicals = AsyncMock(
        side_effect=AssertionError("alphavantage must not be called"))
    _set_available(providers, ("alphavantage",))
    results = {}
    technicals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_technical_indicators"]("AAPL")
    assert out == {"data": TV_FULL}
    providers["alphavantage"].technicals.assert_not_called()
    providers["tradingview"].technicals.assert_awaited_once()


async def test_technicals_explicit_list_from_tv_subset(monkeypatch):
    # tv's indicators dict already contains everything: subset by requested names
    # ("MACD" matches tv's dotted keys MACD.macd/MACD.signal), no av call.
    providers = build_providers(get_settings())
    providers["tradingview"].technicals = AsyncMock(return_value=dict(TV_FULL))
    providers["alphavantage"].technicals = AsyncMock(
        side_effect=AssertionError("alphavantage must not be called"))
    _set_available(providers, ("alphavantage",))
    results = {}
    technicals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_technical_indicators"]("AAPL", indicators="RSI,MACD")
    assert set(out["data"]["indicators"]) == {"RSI", "MACD.macd"}
    assert out["data"]["summary"]["RECOMMENDATION"] == "BUY"  # rest of tv payload kept


async def test_technicals_explicit_list_falls_back_to_av(monkeypatch):
    providers = build_providers(get_settings())
    providers["tradingview"].technicals = AsyncMock(side_effect=NotFound("tv: down"))
    av = AsyncMock(side_effect=lambda parsed, ind, interval: _av_result(ind))
    providers["alphavantage"].technicals = av
    _set_available(providers, ("alphavantage",))
    results = {}
    technicals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_technical_indicators"]("AAPL", indicators="RSI,MACD")
    data = out["data"]
    assert set(data["indicators"]) == {"RSI", "MACD"}
    assert data["source"] == "alphavantage" and data["symbol"] == "AAPL"
    assert av.call_count == 2
    indicators_asked = [c.args[1] for c in av.await_args_list]
    assert indicators_asked == ["RSI", "MACD"]


async def test_technicals_summary_falls_back_to_av_aggregate(monkeypatch):
    # summary with tv down: av aggregates every canonical indicator.
    providers = build_providers(get_settings())
    providers["tradingview"].technicals = AsyncMock(side_effect=NotFound("tv: down"))
    av = AsyncMock(side_effect=lambda parsed, ind, interval: _av_result(ind))
    providers["alphavantage"].technicals = av
    _set_available(providers, ("alphavantage",))
    results = {}
    technicals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_technical_indicators"]("AAPL")
    assert set(out["data"]["indicators"]) == set(technicals_mod.CANONICAL_TECHNICALS)
    assert out["data"]["source"] == "alphavantage"


async def test_technicals_explicit_list_unknown_indicator_partial(monkeypatch):
    providers = build_providers(get_settings())
    providers["tradingview"].technicals = AsyncMock(side_effect=NotFound("tv: down"))

    def av_side(parsed, ind, interval):
        if ind == "VWAP":
            raise ProviderError("alphavantage: unsupported indicator 'VWAP'")
        return _av_result(ind)

    providers["alphavantage"].technicals = AsyncMock(side_effect=av_side)
    _set_available(providers, ("alphavantage",))
    results = {}
    technicals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_technical_indicators"]("AAPL", indicators="RSI,VWAP")
    assert set(out["data"]["indicators"]) == {"RSI"}  # good one survives
    assert any("VWAP" in f for f in out["data"]["partial_failures"])


async def test_technicals_all_requested_fail_hints(monkeypatch):
    providers = build_providers(get_settings())
    providers["tradingview"].technicals = AsyncMock(side_effect=NotFound("tv: down"))
    providers["alphavantage"].technicals = AsyncMock(
        side_effect=ProviderError("alphavantage: unsupported indicator 'VWAP'"))
    _set_available(providers, ("alphavantage",))
    results = {}
    technicals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_technical_indicators"]("AAPL", indicators="VWAP")
    assert "error" in out and "data" not in out
    assert "VWAP" in str(out["failures"])
    assert "hint" in out


async def test_technicals_empty_list_hint(monkeypatch):
    providers = build_providers(get_settings())
    providers["tradingview"].technicals = AsyncMock(
        side_effect=AssertionError("must not be called"))
    results = {}
    technicals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_technical_indicators"]("AAPL", indicators=" , ")
    assert "error" in out and "hint" in out


async def test_technicals_bad_symbol_never_raises(monkeypatch):
    # "???bad" US-defaults through parse_symbol; tv fails and the per-indicator
    # av fallback fails too, so the outcome is an error dict, never a raise.
    providers = build_providers(get_settings())
    providers["tradingview"].technicals = AsyncMock(side_effect=NotFound("tv: no data"))
    providers["alphavantage"].technicals = AsyncMock(side_effect=NotFound("av: no data"))
    _set_available(providers, ("alphavantage",))
    results = {}
    technicals_mod.register(_capture(results), providers, get_settings())
    out = await results["get_technical_indicators"]("???bad")
    assert "error" in out and "data" not in out
    assert "tradingview_error" in out  # tv's failure is reported alongside


def test_sanitize_numpy_payload_is_json_safe():
    # numpy is a transitive dep (tvdatafeed), present in the venv but NOT in
    # pyproject.toml — production code must not import it; sanitize duck-types.
    np = pytest.importorskip("numpy")
    from unified_finance_mcp.tools._sanitize import sanitize

    payload = {"symbol": "AAPL",
               "indicators": {"RSI": np.float64(55.5), "count": np.int64(7)},
               "rows": [{"close": np.float64(np.nan)}, {"close": np.float64(100.0)}],
               "weird": {"nested": (np.float32(1.5),)}}
    clean = sanitize(payload)
    json.dumps(clean)  # must not raise
    assert clean["indicators"]["RSI"] == 55.5
    assert clean["indicators"]["count"] == 7
    assert clean["rows"][0]["close"] is None
    assert clean["rows"][1]["close"] == 100.0
    assert clean["weird"]["nested"] == [1.5]
