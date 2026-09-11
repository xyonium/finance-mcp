"""T14 TradingView containers: tv_scan / tv_analyze / egx_market.

Hermetic: every test stubs the complete reachable implementation face (a
module-level function of _tv_scanners or the Query/TA_Handler level). No
container test may reach real TradingView network code. Data-side tests only
read the vendored local tables (data/egx_indices.py, data/egx_sectors.py).
"""
from __future__ import annotations

import pytest

from unified_finance_mcp import tools as tools_pkg
from unified_finance_mcp.data import egx_indices, egx_sectors

# ── module surface ─────────────────────────────────────────────────────────

def test_containers_registered_in_all_modules():
    assert "containers" in tools_pkg.ALL_MODULES
    assert len(tools_pkg.ALL_MODULES) == 19
    assert len(set(tools_pkg.ALL_MODULES)) == 19  # no duplicates


# ── vendored EGX constituent tables ─────────────────────────────────────────

@pytest.mark.parametrize("name", [
    "EGX30_CONSTITUENTS", "EGX70_CONSTITUENTS", "SHARIAH33_CONSTITUENTS",
    "EGX35LV_CONSTITUENTS", "TAMAYUZ_CONSTITUENTS"])
def test_egx_index_constituent_tables_vendored(name):
    table = getattr(egx_indices, name)
    assert isinstance(table, list) and len(table) >= 5
    assert all("EGX:" not in s for s in table)  # bare tickers, per controller ruling
    assert not hasattr(egx_indices, "EGX100_CONSTITUENTS")  # EGX100 has no vendored table


def test_egx30_constituents_include_comi():
    assert "COMI" in egx_indices.EGX30_CONSTITUENTS
    assert len(egx_indices.EGX30_CONSTITUENTS) >= 30


def test_egx_prefixed_accessors():
    syms = egx_indices.get_egx30_symbols()
    assert syms and all(s.startswith("EGX:") for s in syms)
    assert "EGX:COMI" in syms
    assert egx_indices.get_egx70_symbols()
    assert egx_indices.get_shariah33_symbols()
    assert egx_indices.get_egx35lv_symbols()
    assert egx_indices.get_tamayuz_symbols()


def test_egx_indices_meta():
    for key in ("EGX30", "EGX70", "SHARIAH33", "EGX35LV", "TAMAYUZ"):
        meta = egx_indices.EGX_INDICES[key]
        assert meta["name"] and meta["description"]
        assert meta["constituents_count"] == len(meta["get_symbols"]())
    assert egx_indices.EGX_INDICES["EGX30"]["constituents_count"] == \
        len(egx_indices.EGX30_CONSTITUENTS)
    assert egx_indices.is_egx30_stock("EGX:COMI")
    assert not egx_indices.is_egx30_stock("EGX:AMER")


def test_egx_sectors_tables_vendored():
    assert len(egx_sectors.EGX_SECTORS) == 18
    assert "COMI" in egx_sectors.EGX_SECTORS["banks"]
    assert set(egx_sectors.SECTOR_DISPLAY_NAMES) == set(egx_sectors.EGX_SECTORS)
    assert egx_sectors.get_sector("EGX:COMI") == "banks"
    assert egx_sectors.get_sector("EGX:NOPE") == "other"
    assert egx_sectors.get_symbols_by_sector("banks") == \
        [f"EGX:{s}" for s in sorted(egx_sectors.EGX_SECTORS["banks"])]
    assert egx_sectors.get_all_sectors() == sorted(egx_sectors.EGX_SECTORS)
    assert egx_sectors.get_currency("EGX:COMI") == "EGP"
    assert egx_sectors.get_currency("EGX:FAITA") == "USD"


# ── tv_scan ─────────────────────────────────────────────────────────────────

async def test_tv_scan_unknown_action_lists_valid():
    from unified_finance_mcp.tools import containers as containers_mod

    out = await containers_mod.tv_scan(action="bogus")
    assert "error" in out
    assert "top_gainers" in out["hint"]
    for action in ("top_gainers", "top_losers", "bollinger_squeeze", "rating",
                   "consecutive_candles", "volume_breakout", "smart_volume"):
        assert action in out["hint"]


async def test_tv_scan_top_gainers_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    calls = {}

    def fake(exchange, timeframe, limit):
        calls.update(exchange=exchange, timeframe=timeframe, limit=limit)
        return [{"symbol": "EGX:COMI", "changePercent": 1.5}]

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.top_gainers", fake)
    out = await containers_mod.tv_scan("top_gainers", exchange="egx", timeframe="1d",
                                       limit=5)
    assert out == {"data": [{"symbol": "EGX:COMI", "changePercent": 1.5}]}
    assert calls == {"exchange": "egx", "timeframe": "1D", "limit": 5}


async def test_tv_scan_top_losers_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    calls = {}

    def fake(exchange, timeframe, limit):
        calls.update(exchange=exchange, timeframe=timeframe, limit=limit)
        return [{"symbol": "EGX:AMER", "changePercent": -3.2}]

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.top_losers", fake)
    out = await containers_mod.tv_scan("top_losers", exchange="EGX", timeframe="4h",
                                       limit=10)
    assert out == {"data": [{"symbol": "EGX:AMER", "changePercent": -3.2}]}
    assert calls == {"exchange": "egx", "timeframe": "4h", "limit": 10}


async def test_tv_scan_bollinger_squeeze_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(exchange, timeframe, bbw_filter, limit):
        captured.update(exchange=exchange, timeframe=timeframe, bbw=bbw_filter,
                        limit=limit)
        return [{"symbol": "BINANCE:BTCUSDT", "changePercent": 0.4}]

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.bollinger_squeeze", fake)
    out = await containers_mod.tv_scan("bollinger_squeeze", exchange="BINANCE",
                                       timeframe="15m", limit=7, bbw_threshold=0.05)
    assert out == {"data": [{"symbol": "BINANCE:BTCUSDT", "changePercent": 0.4}]}
    assert captured == {"exchange": "binance", "timeframe": "15m", "bbw": 0.05, "limit": 7}


async def test_tv_scan_rating_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(exchange, timeframe, rating, limit):
        captured.update(exchange=exchange, timeframe=timeframe, rating=rating, limit=limit)
        return [{"symbol": "NASDAQ:AAPL", "changePercent": 0.8}]

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.rating", fake)
    out = await containers_mod.tv_scan("rating", exchange="NASDAQ", timeframe="1h",
                                       limit=9, rating=2)
    assert out["data"][0]["symbol"] == "NASDAQ:AAPL"
    assert captured == {"exchange": "nasdaq", "timeframe": "1h", "rating": 2, "limit": 9}


async def test_tv_scan_consecutive_candles_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(exchange, timeframe, pattern_type, candle_count, min_growth, limit):
        captured.update(exchange=exchange, timeframe=timeframe, pattern=pattern_type,
                        count=candle_count, growth=min_growth, limit=limit)
        return {"total_found": 1, "data": []}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.consecutive_candles", fake)
    out = await containers_mod.tv_scan("consecutive_candles", exchange="KUCOIN",
                                       timeframe="1d", limit=5, pattern_type="bearish",
                                       candle_count=4, min_growth=1.5)
    assert out == {"data": {"total_found": 1, "data": []}}
    assert captured == {"exchange": "kucoin", "timeframe": "1D", "pattern": "bearish",
                        "count": 4, "growth": 1.5, "limit": 5}


async def test_tv_scan_volume_breakout_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(exchange, timeframe, volume_multiplier, price_change_min, limit):
        captured.update(exchange=exchange, timeframe=timeframe, mult=volume_multiplier,
                        pchg=price_change_min, limit=limit)
        return []

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.volume_breakout", fake)
    out = await containers_mod.tv_scan("volume_breakout", exchange="KUCOIN",
                                       timeframe="1d", limit=8, volume_multiplier=2.5,
                                       price_change_min=4.0)
    assert out == {"data": []}
    assert captured == {"exchange": "kucoin", "timeframe": "1D", "mult": 2.5,
                        "pchg": 4.0, "limit": 8}


async def test_tv_scan_smart_volume_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(exchange, min_volume_ratio, min_price_change, rsi_range, limit):
        captured.update(exchange=exchange, vr=min_volume_ratio, pc=min_price_change,
                        rsi=rsi_range, limit=limit)
        return []

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.smart_volume", fake)
    out = await containers_mod.tv_scan("smart_volume", exchange="KUCOIN", limit=6,
                                       min_volume_ratio=1.5, min_price_change=2.0,
                                       rsi_range="oversold")
    assert out == {"data": []}
    assert captured == {"exchange": "kucoin", "vr": 1.5, "pc": 2.0,
                        "rsi": "oversold", "limit": 6}


async def test_tv_scan_scanner_error_never_raises(monkeypatch):
    from unified_finance_mcp.errors import UpstreamError
    from unified_finance_mcp.tools import containers as containers_mod

    def fake(exchange, timeframe, limit):
        raise UpstreamError("tradingview scan: scanner down")

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.top_gainers", fake)
    out = await containers_mod.tv_scan("top_gainers")
    assert "error" in out
    assert out["source"] == "tradingview"
    assert "data" not in out


async def test_tv_scan_invalid_exchange_clamped_to_default(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(exchange, timeframe, limit):
        captured.update(exchange=exchange)
        return []

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.top_gainers", fake)
    out = await containers_mod.tv_scan("top_gainers", exchange="NOT_A_VENUE")
    assert out == {"data": []}
    assert captured["exchange"] == "nasdaq"  # sanitize_exchange: illegal -> default


async def test_tv_scan_invalid_timeframe_clamped_to_default(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(exchange, timeframe, limit):
        captured.update(timeframe=timeframe)
        return []

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.top_gainers", fake)
    out = await containers_mod.tv_scan("top_gainers", timeframe="7h")
    assert out == {"data": []}
    assert captured["timeframe"] == "1D"  # sanitize_timeframe default


@pytest.mark.parametrize("tf,expected", [
    ("1m", "1m"),      # minute, not month (project vocabulary trap)
    ("5m", "5m"), ("15m", "15m"), ("1h", "1h"), ("4h", "4h"),
    ("1d", "1D"), ("1wk", "1W"), ("1mo", "1M"),
    ("1D", "1D"),                # aliases lookup is case-insensitive
    ("1w", "1D"), ("1W", "1D"),  # legacy "1w" retired; "1wk" is the spelling
    ("3m", "1D"),                # unknown -> default, no silent month mapping
])
def test_sanitize_timeframe_vocabulary(tf, expected):
    from unified_finance_mcp.tools import containers as containers_mod

    assert containers_mod.sanitize_timeframe(tf) == expected


# ── tv_analyze ──────────────────────────────────────────────────────────────

async def test_tv_analyze_unknown_action_lists_valid():
    from unified_finance_mcp.tools import containers as containers_mod

    out = await containers_mod.tv_analyze("bogus", symbol="EGX:COMI")
    assert "error" in out
    assert "summary" in out["hint"] and "coin" in out["hint"]
    assert "multi_timeframe" in out["hint"]
    assert "volume_confirmation" in out["hint"]
    assert "candle_pattern" in out["hint"]


async def test_tv_analyze_coin_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(symbol, exchange, timeframe):
        captured.update(symbol=symbol, exchange=exchange, timeframe=timeframe)
        return {"symbol": "EGX:COMI", "price_data": {"current_price": 80.0}}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.coin", fake)
    out = await containers_mod.tv_analyze("coin", symbol="COMI", exchange="EGX",
                                          timeframe="1d")
    assert out == {"data": {"symbol": "EGX:COMI", "price_data": {"current_price": 80.0}}}
    assert captured == {"symbol": "COMI", "exchange": "egx", "timeframe": "1D"}


async def test_tv_analyze_summary_extracts_key_fields(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    full = {
        "symbol": "NASDAQ:AAPL",
        "exchange": "NASDAQ",
        "timeframe": "1d",
        "price_data": {"current_price": 250.0, "change_percent": 1.2},
        "market_sentiment": {"overall_rating": 2, "buy_sell_signal": "BUY",
                             "momentum": "Bullish"},
        "rsi": {"value": 58.0, "signal": "Neutral"},
        "macd": {"crossover": "Bullish"},
        "market_structure": {"trend": "Bullish"},
        "noise": "dropped in summary",
    }

    def fake(symbol, exchange, timeframe):
        return full

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.coin", fake)
    out = await containers_mod.tv_analyze("summary", symbol="AAPL", exchange="NASDAQ",
                                          timeframe="1d")
    assert "error" not in out
    data = out["data"]
    assert data["symbol"] == "NASDAQ:AAPL"
    assert data["price"] == 250.0
    assert data["change_percent"] == 1.2
    assert data["rating"] == 2
    assert data["signal"] == "BUY"
    assert data["momentum"] == "Bullish"
    assert data["rsi"] == 58.0
    assert data["macd_crossover"] == "Bullish"
    assert data["trend"] == "Bullish"
    assert "noise" not in data


async def test_tv_analyze_default_exchange_from_symbol(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(symbol, exchange, timeframe):
        captured.update(symbol=symbol, exchange=exchange)
        return {"symbol": symbol}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.coin", fake)
    out = await containers_mod.tv_analyze("coin", symbol="EGX:COMI")
    assert out == {"data": {"symbol": "COMI"}}
    assert captured == {"symbol": "COMI", "exchange": "egx"}


async def test_tv_analyze_candle_pattern_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(exchange, timeframe, pattern_length, min_size_increase, limit):
        captured.update(exchange=exchange, timeframe=timeframe, length=pattern_length,
                        min_inc=min_size_increase, limit=limit)
        return {"method": "multi-timeframe", "total_found": 0, "data": []}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.candle_pattern", fake)
    out = await containers_mod.tv_analyze("candle_pattern", symbol="BTCUSDT",
                                          exchange="BINANCE", timeframe="15m",
                                          pattern_length=3, min_size_increase=10.0,
                                          limit=15)
    assert out == {"data": {"method": "multi-timeframe", "total_found": 0, "data": []}}
    assert captured == {"exchange": "binance", "timeframe": "15m", "length": 3,
                        "min_inc": 10.0, "limit": 15}


async def test_tv_analyze_multi_timeframe_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(symbol, exchange, timeframe):
        captured.update(symbol=symbol, exchange=exchange, timeframe=timeframe)
        return {"alignment": {"status": "MOSTLY BULLISH"}}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.multi_timeframe", fake)
    out = await containers_mod.tv_analyze("multi_timeframe", symbol="SOLUSDT",
                                          exchange="BINANCE", timeframe="1d")
    assert out == {"data": {"alignment": {"status": "MOSTLY BULLISH"}}}
    assert captured == {"symbol": "SOLUSDT", "exchange": "binance", "timeframe": "1D"}


async def test_tv_analyze_volume_confirmation_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(symbol, exchange, timeframe):
        captured.update(symbol=symbol, exchange=exchange, timeframe=timeframe)
        return {"volume_analysis": {"volume_strength": "STRONG"}}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.volume_confirmation",
                        fake)
    out = await containers_mod.tv_analyze("volume_confirmation", symbol="BTCUSDT",
                                          exchange="KUCOIN", timeframe="1h")
    assert out == {"data": {"volume_analysis": {"volume_strength": "STRONG"}}}
    assert captured == {"symbol": "BTCUSDT", "exchange": "kucoin", "timeframe": "1h"}


async def test_tv_analyze_error_never_raises(monkeypatch):
    from unified_finance_mcp.errors import NotFound
    from unified_finance_mcp.tools import containers as containers_mod

    def fake(symbol, exchange, timeframe):
        raise NotFound("no data for EGX:NOPE")

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.coin", fake)
    out = await containers_mod.tv_analyze("coin", symbol="NOPE", exchange="EGX")
    assert "error" in out and "data" not in out


async def test_tv_analyze_missing_symbol_hint():
    from unified_finance_mcp.tools import containers as containers_mod

    out = await containers_mod.tv_analyze("coin", symbol="   ")
    assert "error" in out and "hint" in out


# ── egx_market ──────────────────────────────────────────────────────────────

async def test_egx_market_unknown_action_lists_valid():
    from unified_finance_mcp.tools import containers as containers_mod

    out = await containers_mod.egx_market("bogus")
    assert "error" in out
    for action in ("overview", "sector_scan", "index", "screener", "trade_plan",
                   "fibonacci"):
        assert action in out["hint"]


async def test_egx_market_overview_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(timeframe, limit):
        captured.update(timeframe=timeframe, limit=limit)
        return {"exchange": "EGX", "total_analyzed": 200}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.egx_overview", fake)
    out = await containers_mod.egx_market("overview", timeframe="1d", limit=10)
    assert out == {"data": {"exchange": "EGX", "total_analyzed": 200}}
    assert captured == {"timeframe": "1D", "limit": 10}


async def test_egx_market_sector_scan_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(sector, timeframe, limit):
        captured.update(sector=sector, timeframe=timeframe, limit=limit)
        return {"sector": "banks", "total_stocks": 12}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.egx_sector_scan", fake)
    out = await containers_mod.egx_market("sector_scan", sector="banks",
                                          timeframe="1d", limit=20)
    assert out == {"data": {"sector": "banks", "total_stocks": 12}}
    assert captured == {"sector": "banks", "timeframe": "1D", "limit": 20}


async def test_egx_market_index_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(index, timeframe, limit):
        captured.update(index=index, timeframe=timeframe, limit=limit)
        return {"index": "EGX30", "index_stats": {"analyzed": 30}}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.egx_index", fake)
    out = await containers_mod.egx_market("index", index="EGX30", timeframe="1d",
                                          limit=30)
    assert out == {"data": {"index": "EGX30", "index_stats": {"analyzed": 30}}}
    assert captured == {"index": "EGX30", "timeframe": "1D", "limit": 30}


async def test_egx_market_index_egx100_tool_error(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    async def boom(index, timeframe, limit):
        raise AssertionError(f"must not be called for {index}")

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.egx_index", boom)
    out = await containers_mod.egx_market("index", index="EGX100")
    assert "error" in out
    assert "EGX100" in out["error"]
    assert out.get("source") == "tradingview"


async def test_egx_market_screener_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(timeframe, min_score, index_filter, limit):
        captured.update(timeframe=timeframe, min_score=min_score, index=index_filter,
                        limit=limit)
        return {"total_passed": 5, "qualified_trades": []}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.egx_screener", fake)
    out = await containers_mod.egx_market("screener", timeframe="1d", min_score=60,
                                          index_filter="EGX30", limit=20)
    assert out == {"data": {"total_passed": 5, "qualified_trades": []}}
    assert captured == {"timeframe": "1D", "min_score": 60, "index": "EGX30", "limit": 20}


async def test_egx_market_trade_plan_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(symbol, timeframe):
        captured.update(symbol=symbol, timeframe=timeframe)
        return {"symbol": "EGX:COMI", "recommendation": "QUALIFIED"}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.egx_trade_plan", fake)
    out = await containers_mod.egx_market("trade_plan", symbol="COMI", timeframe="1d")
    assert out == {"data": {"symbol": "EGX:COMI", "recommendation": "QUALIFIED"}}
    assert captured == {"symbol": "COMI", "timeframe": "1D"}


async def test_egx_market_fibonacci_dispatches(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(symbol, lookback, timeframe):
        captured.update(symbol=symbol, lookback=lookback, timeframe=timeframe)
        return {"symbol": "EGX:TMGH", "trend": "uptrend"}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.egx_fibonacci", fake)
    out = await containers_mod.egx_market("fibonacci", symbol="TMGH", lookback="52W",
                                          timeframe="1d")
    assert out == {"data": {"symbol": "EGX:TMGH", "trend": "uptrend"}}
    assert captured == {"symbol": "TMGH", "lookback": "52W", "timeframe": "1D"}


async def test_egx_market_error_never_raises(monkeypatch):
    from unified_finance_mcp.errors import UpstreamError
    from unified_finance_mcp.tools import containers as containers_mod

    def fake(timeframe, limit):
        raise UpstreamError("egx overview: scanner down")

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.egx_overview", fake)
    out = await containers_mod.egx_market("overview")
    assert "error" in out and "data" not in out


# ── registration surface ────────────────────────────────────────────────────

def test_register_mounts_three_container_tools():
    from mcp.server.fastmcp import FastMCP

    from unified_finance_mcp.config import get_settings
    from unified_finance_mcp.tools import containers as containers_mod

    mcp = FastMCP("t14-test")
    containers_mod.register(mcp, None, get_settings())
    names = {t.name for t in mcp._tool_manager.list_tools()}
    assert {"tv_scan", "tv_analyze", "egx_market"} <= names


def test_tv_scan_schema_default_exchange_is_working_venue():
    """The registered MCP schema default must be a venue with a vendored
    symbol list ("nasdaq"), not the dead "US" path."""
    from mcp.server.fastmcp import FastMCP

    from unified_finance_mcp.config import get_settings
    from unified_finance_mcp.tools import containers as containers_mod

    mcp = FastMCP("t14-test")
    containers_mod.register(mcp, None, get_settings())
    tv_scan = {t.name: t for t in mcp._tool_manager.list_tools()}["tv_scan"]
    props = tv_scan.parameters["properties"]
    assert props["exchange"].get("default") == "nasdaq"


# ── _tv_math pure helpers (no network by construction) ─────────────────────

def test_compute_metrics_full_indicator_dict():
    from unified_finance_mcp.tools._tv_math import compute_metrics

    ind = {"open": 100.0, "close": 105.0, "SMA20": 100.0,
           "BB.upper": 104.0, "BB.lower": 96.0}
    m = compute_metrics(ind)
    assert m["price"] == 105.0
    assert m["change"] == 5.0
    assert m["bbw"] == 0.08
    assert m["rating"] in (-3, -2, -1, 0, 1, 2, 3)
    assert m["signal"] in ("BUY", "SELL", "NEUTRAL")


def test_compute_metrics_missing_keys_returns_none():
    from unified_finance_mcp.tools._tv_math import compute_metrics

    assert compute_metrics({"open": 1.0}) is None


def test_compute_bb_rating_signal():
    from unified_finance_mcp.tools._tv_math import compute_bb_rating_signal

    assert compute_bb_rating_signal(120, 110, 100, 90) == (3, "NEUTRAL")
    assert compute_bb_rating_signal(85, 110, 100, 90) == (-3, "NEUTRAL")
    assert compute_bb_rating_signal(107, 110, 100, 90) == (2, "BUY")
    assert compute_bb_rating_signal(93, 110, 100, 90) == (-2, "SELL")
    assert compute_bb_rating_signal(104, 110, 100, 90) == (1, "NEUTRAL")
    assert compute_bb_rating_signal(97, 110, 100, 90) == (-1, "NEUTRAL")
    # close between middle and middle+half-range -> rating 1 (reference behavior)
    assert compute_bb_rating_signal(101, 110, 100, 90) == (1, "NEUTRAL")
    assert compute_bb_rating_signal(100, 110, 100, 90) == (0, "NEUTRAL")


def test_candle_pattern_score_detects_strong_bullish_candle():
    from unified_finance_mcp.tools._tv_math import compute_candle_pattern_score

    ind = {"open": 100.0, "close": 108.0, "high": 108.5, "low": 99.5,
           "volume": 60000, "RSI": 60, "EMA50": 99.0}
    out = compute_candle_pattern_score(ind, pattern_length=3, min_increase=5.0)
    assert out["detected"] is True
    assert out["score"] >= 3
    assert out["price"] == 108.0
    assert out["total_change"] == 8.0


def test_candle_pattern_score_not_detected_without_ohlc():
    from unified_finance_mcp.tools._tv_math import compute_candle_pattern_score

    assert compute_candle_pattern_score({"close": 5.0}, 3, 5.0) == {
        "detected": False, "score": 0}


def test_stock_score_bullish_and_liquid():
    from unified_finance_mcp.tools._tv_math import compute_stock_score

    ind = {
        "open": 50.0, "close": 52.0,
        "EMA20": 50.0, "EMA50": 49.0, "EMA200": 45.0,
        "RSI": 60, "MACD.macd": 0.6, "MACD.signal": 0.2,
        "volume": 3_000_000, "volume.SMA20": 1_000_000,
        "ADX": 32, "ADX+DI": 25, "ADX-DI": 15,
        "ATR": 1.0, "SMA200": 45.0, "BB.upper": 54.0, "BB.lower": 50.0,
        "SMA20": 52.0,
        "Recommend.All": 0.6, "Recommend.MA": 0.4, "Recommend.Other": 0.3,
    }
    out = compute_stock_score(ind, change_pct_rank=0.95, currency="EGP")
    assert out["score"] >= 70
    assert out["grade"] in ("Strong", "Elite")
    assert "Perfect EMA alignment (Price>20>50>200)" in out["signals"]
    assert out["trend_state"] == "Strong Uptrend"
    assert out["liquidity"]["liquidity_ok"] is True


def test_stock_score_illiquid_grade_capped():
    from unified_finance_mcp.tools._tv_math import compute_stock_score

    ind = {
        "open": 50.0, "close": 52.0,
        "EMA20": 50.0, "EMA50": 49.0, "EMA200": 45.0,
        "RSI": 60, "MACD.macd": 0.6, "MACD.signal": 0.2,
        "volume": 5_000, "volume.SMA20": 8_000,
        "ADX": 32, "ADX+DI": 25, "ADX-DI": 15,
        "ATR": 1.0, "SMA200": 45.0, "BB.upper": 54.0, "BB.lower": 50.0,
        "SMA20": 52.0,
        "Recommend.All": 0.6, "Recommend.MA": 0.4, "Recommend.Other": 0.3,
    }
    out = compute_stock_score(ind, currency="EGP")
    assert out["liquidity"]["liquidity_ok"] is False
    assert out["grade"] in ("Avoid", "Watchlist")  # -20 illiquidity penalty pulls it down


def test_trade_setup_requires_atr():
    from unified_finance_mcp.tools._tv_math import compute_trade_setup

    assert compute_trade_setup({"close": 100.0}) is None
    setup = compute_trade_setup({
        "close": 100.0, "high": 102.0, "low": 98.0, "ATR": 2.0,
        "EMA20": 99.0, "EMA50": 97.0, "EMA200": 90.0,
        "BB.lower": 98.0, "BB.upper": 103.0, "P.SAR": 99.0,
        "Pivot.M.Classic.S1": 98.5, "Pivot.M.Classic.R1": 102.0,
        "Pivot.M.Classic.S2": 97.0, "Pivot.M.Classic.R2": 104.0,
        "Pivot.M.Fibonacci.S1": 98.0, "Pivot.M.Fibonacci.R1": 102.5,
    })
    assert setup is not None
    assert "breakout" in setup["setup_types"]
    assert setup["stop_loss"] is not None
    assert setup["targets"]["target_1"] and setup["targets"]["target_2"]
    assert setup["risk_reward"]["quality"] in ("Weak", "Acceptable", "Good", "Strong")
    assert setup["supports"] and setup["resistances"]


def test_fibonacci_levels_and_position():
    from unified_finance_mcp.tools._tv_math import (
        analyze_fibonacci_position,
        compute_fibonacci_levels,
    )

    levels = compute_fibonacci_levels(swing_high=200.0, swing_low=100.0,
                                      trend="uptrend")
    assert levels["retracement_levels"]["0.0"] == 200.0
    assert levels["retracement_levels"]["0.618"] == 138.2
    assert levels["retracement_levels"]["1.0"] == 100.0
    pos = analyze_fibonacci_position(close=140.0, fib_levels=levels)
    assert pos["current_zone"].startswith("Between")
    assert 0 <= pos["retracement_depth_pct"] <= 100
    assert pos["nearest_level"]["ratio"] in levels["retracement_levels"]
    assert pos["fib_supports"] and pos["fib_resistances"]


def test_analyze_timeframe_context_1d():
    from unified_finance_mcp.tools._tv_math import analyze_timeframe_context

    ind = {"close": 100.0, "EMA50": 99.0, "EMA200": 90.0, "RSI": 55,
           "MACD.macd": 0.5, "MACD.signal": 0.1, "volume": 20000,
           "volume.SMA20": 10000}
    ctx = analyze_timeframe_context(ind, "1D")
    assert ctx["bias"] == "Bullish"
    assert "Golden Cross: EMA50 > EMA200" in ctx["bias_reasons"]
    assert ctx["key_indicators_for_timeframe"]
    assert ctx["advice"]


# ── hermeticity guard (T10-C1 / controller ruling 5) ────────────────────────

def _getaddrinfo_fail(*args, **kwargs):
    raise AssertionError(f"network resolution attempted: {args[1] if len(args) > 1 else args}")


async def test_containers_do_not_touch_network(monkeypatch):
    """Import-time surface: containers and scanner impls must not resolve DNS.

    Note: this module is already imported by earlier tests, so this is a
    re-import over an installed getaddrinfo guard. The double-run harness below
    exercises the same path in a fresh process.
    """
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo_fail)
    from unified_finance_mcp.tools import _tv_scanners, containers
    assert _tv_scanners.TA_AVAILABLE is True
    assert set(containers._TV_SCAN_ROUTES) >= {
        "top_gainers", "top_losers", "bollinger_squeeze", "rating",
        "consecutive_candles", "volume_breakout", "smart_volume"}
    assert set(containers._TV_ANALYZE_ROUTES) >= {
        "summary", "coin", "candle_pattern", "multi_timeframe",
        "volume_confirmation"}
    assert set(containers._EGX_ROUTES) >= {
        "overview", "sector_scan", "index", "screener", "trade_plan", "fibonacci"}


async def test_egx_market_does_not_touch_network(monkeypatch):
    """Unknown action short-circuits before any thread/network work."""
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo_fail)
    from unified_finance_mcp.tools import containers
    out = await containers.egx_market("bogus")
    assert "error" in out


# ── R1 fixes (controller rulings F1-F4) ─────────────────────────────────────

# F1: containers never raise on garbage input.

_GARBAGE_ERROR_PROBES = [
    ("tv_analyze non-str symbol",
     lambda m: m.tv_analyze("coin", symbol=5)),
    ("tv_analyze non-str action",
     lambda m: m.tv_analyze(5, symbol="X")),
    ("tv_analyze list action",
     lambda m: m.tv_analyze(["coin"], symbol="X")),
    ("tv_analyze None symbol",
     lambda m: m.tv_analyze("coin", symbol=None)),
    ("tv_scan list action",
     lambda m: m.tv_scan(["top_gainers"])),
    ("tv_scan None action",
     lambda m: m.tv_scan(None)),
    ("tv_scan int action",
     lambda m: m.tv_scan(7)),
    ("egx_market None action",
     lambda m: m.egx_market(None)),
    ("egx_market list action",
     lambda m: m.egx_market(["overview"])),
    ("egx_market trade_plan int symbol",
     lambda m: m.egx_market("trade_plan", symbol=7)),
    ("egx_market fibonacci int symbol",
     lambda m: m.egx_market("fibonacci", symbol=7)),
    ("egx_market index int index",
     lambda m: m.egx_market("index", index=5)),
    ("egx_market garbage lookback",
     lambda m: m.egx_market("fibonacci", symbol="COMI", lookback=5)),
]


@pytest.mark.parametrize("label,call", _GARBAGE_ERROR_PROBES,
                         ids=[p[0] for p in _GARBAGE_ERROR_PROBES])
async def test_containers_never_raise_garbage_error(label, call, monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    # The lookback probe falls through to the real egx_fibonacci impl; stub it
    # (hermetic: no container test may reach real TradingView code).
    def stub_fib(symbol, lookback, timeframe):
        raise RuntimeError("stubbed egx_fibonacci (probe)")

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.egx_fibonacci",
                        stub_fib)
    out = await call(containers_mod)
    assert isinstance(out, dict), label
    assert "error" in out, label


async def test_egx_market_lookback_sanitized(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(symbol, lookback, timeframe):
        captured.update(symbol=symbol, lookback=lookback, timeframe=timeframe)
        return {"trend": "uptrend"}

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.egx_fibonacci", fake)
    for lookback, expected in ((5, "52W"), ("3m", "3M"), ("", "52W"),
                               (None, "52W")):
        out = await containers_mod.egx_market("fibonacci", symbol="COMI",
                                              lookback=lookback)
        assert out == {"data": {"trend": "uptrend"}}
        assert captured["lookback"] == expected, lookback


@pytest.mark.parametrize("kwargs,expected_ex,expected_tf", [
    # tv_scan's defaults are the bare "nasdaq"/"1D" (only str inputs are
    # lowercased/aliased by the sanitizers).
    ({"exchange": 5}, "nasdaq", "1D"),
    ({"exchange": ["egx"]}, "nasdaq", "1D"),
    ({"timeframe": 42}, "nasdaq", "1D"),
    ({"timeframe": None}, "nasdaq", "1D"),
    ({"timeframe": ["1d"]}, "nasdaq", "1D"),
])
async def test_tv_scan_sanitizers_fall_back_on_garbage(monkeypatch, kwargs,
                                                   expected_ex, expected_tf):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(exchange, timeframe, limit):
        captured.update(exchange=exchange, timeframe=timeframe, limit=limit)
        return []

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.top_gainers", fake)
    out = await containers_mod.tv_scan("top_gainers", **kwargs)
    assert out == {"data": []}
    assert captured["exchange"] == expected_ex
    assert captured["timeframe"] == expected_tf


@pytest.mark.parametrize("limit", ["x", None, ["z"], {"a": 1}])
async def test_tv_scan_clamp_limit_garbage_falls_back(monkeypatch, limit):
    from unified_finance_mcp.tools import containers as containers_mod

    captured = {}

    def fake(exchange, timeframe, limit_):
        captured.update(limit=limit_)
        return []

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.top_gainers", fake)
    out = await containers_mod.tv_scan("top_gainers", limit=limit)
    assert out == {"data": []}
    assert captured["limit"] == 1


# F2: di_signal string must match the reference exactly.

def test_extended_indicators_di_signal_reference_parity():
    from unified_finance_mcp.tools._tv_math import extract_extended_indicators

    bearish = {"close": 100.0, "open": 98.0, "ADX+DI": 10.0, "ADX-DI": 20.0}
    out = extract_extended_indicators(bearish)
    assert out["adx"]["di_signal"] == "Bearish (-DI > +DI)"  # reference :434
    bullish = {"close": 100.0, "open": 98.0, "ADX+DI": 20.0, "ADX-DI": 10.0}
    assert extract_extended_indicators(bullish)["adx"]["di_signal"] == \
        "Bullish (+DI > -DI)"
    neutral = {"close": 100.0, "open": 98.0}
    assert extract_extended_indicators(neutral)["adx"]["di_signal"] == "Neutral"


# F3: multi-TF candle pattern market lookup.

# Hardcoded reference EXCHANGE_SCREENER subset (reference validators.py:28),
# limited to the keys this project's _VALID_EXCHANGES accepts.
_REFERENCE_EXCHANGE_NAME_TO_TV_MARKET = {
    "all": "crypto", "huobi": "crypto", "kucoin": "crypto",
    "coinbase": "crypto", "gateio": "crypto", "binance": "crypto",
    "bitfinex": "crypto", "bitget": "crypto", "bybit": "crypto",
    "okx": "crypto", "mexc": "crypto",
    "bist": "turkey", "egx": "egypt",
    "nasdaq": "america", "nyse": "america", "amex": "america",
    "nysearca": "america", "pcx": "america",
    "bursa": "malaysia", "myx": "malaysia", "klse": "malaysia",
    "ace": "malaysia", "leap": "malaysia",
    "hkex": "hongkong", "hk": "hongkong", "hsi": "hongkong",
    "asx": "australia",
    "sse": "china", "szse": "china", "chn": "china",
    "twse": "taiwan", "tpex": "taiwan",
    "tadawul": "ksa", "tasi": "ksa",
}


def test_exchange_name_to_tv_market_matches_reference_subset():
    from unified_finance_mcp.tools import _tv_scanners

    assert _tv_scanners.EXCHANGE_NAME_TO_TV_MARKET == \
        _REFERENCE_EXCHANGE_NAME_TO_TV_MARKET


class FakePatternQuery:
    """Captures set_markets; get_scanner_data returns an empty frame."""

    def __init__(self):
        self.markets = None

    def set_markets(self, *markets):
        self.markets = markets
        return self

    def select(self, *cols):
        return self

    def where(self, *exprs):
        return self

    def limit(self, n):
        return self

    def get_scanner_data(self):
        import pandas as pd
        return 0, pd.DataFrame()


@pytest.mark.parametrize("exchange,expected", [
    ("egx", "egypt"), ("EGX", "egypt"), ("nasdaq", "america"),
    ("kucoin", "crypto"), ("bist", "turkey"), ("hkex", "hongkong"),
])
def test_multi_tf_patterns_market_lookup(monkeypatch, exchange, expected):
    from unified_finance_mcp.tools import _tv_scanners

    q = FakePatternQuery()
    monkeypatch.setattr("tradingview_screener.Query", lambda: q)
    out = _tv_scanners._multi_tf_patterns(exchange, [], "15m", 3, 10.0)
    assert out == []
    assert q.markets == (expected,)


def test_candle_pattern_ta_only_venue_raises_before_query(monkeypatch):
    from unified_finance_mcp.errors import ProviderError
    from unified_finance_mcp.tools import _tv_scanners

    def boom():
        raise AssertionError("Query must not be instantiated for TA-only venues")

    monkeypatch.setattr("tradingview_screener.Query", boom)
    for venue in ("oanda", "fx_idc", "fxcm", "tvc", "capitalcom"):
        with pytest.raises(ProviderError) as exc:
            _tv_scanners.candle_pattern(venue, "15m")
        assert "TA-only" in str(exc.value) or "no screener market" in str(exc.value)


async def test_tv_analyze_candle_pattern_ta_only_venue_tool_error(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod

    def boom():
        raise AssertionError("Query must not be instantiated for TA-only venues")

    monkeypatch.setattr("tradingview_screener.Query", boom)
    out = await containers_mod.tv_analyze("candle_pattern", symbol="EURUSD",
                                          exchange="oanda")
    assert isinstance(out, dict)
    assert "error" in out and "oanda" in out["error"]


# F4: container error dicts preserve the ProviderError kind.

async def test_container_preserves_rate_limited_kind(monkeypatch):
    from unified_finance_mcp.errors import RateLimited
    from unified_finance_mcp.tools import containers as containers_mod

    def boom(exchange, timeframe, limit):
        raise RateLimited("tradingview throttle")

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.top_gainers", boom)
    out = await containers_mod.tv_scan("top_gainers")
    assert out["error"].startswith("rate_limited: ")
    assert out["source"] == "tradingview"


async def test_container_preserves_not_found_kind(monkeypatch):
    from unified_finance_mcp.tools import containers as containers_mod
    from unified_finance_mcp.tools._tv_scanners import NotFoundError

    def boom(symbol, exchange, timeframe):
        raise NotFoundError("no data for EGX:NOPE")

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.coin", boom)
    out = await containers_mod.tv_analyze("coin", symbol="NOPE", exchange="egx")
    assert out["error"].startswith("not_found: ")
