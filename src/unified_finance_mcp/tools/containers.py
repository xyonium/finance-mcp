"""TradingView action containers: tv_scan / tv_analyze / egx_market.

Three routing containers over the implementations in tools/_tv_scanners.py.
Every action runs in a worker thread (anyio.to_thread.run_sync — the
tradingview provider's pattern, because tradingview_ta / tradingview-screener
are sync) and the container layer never raises: action impl failures return
the standard error dict with source="tradingview". Unknown actions list the
valid ones. Exchange/timeframe are clamped exactly like the reference
sanitize_exchange/sanitize_timeframe (illegal value -> default).

tv_scan scan actions:
  top_gainers / top_losers / bollinger_squeeze / rating / consecutive_candles
  / volume_breakout / smart_volume
tv_analyze actions:
  summary / coin / candle_pattern / multi_timeframe / volume_confirmation
egx_market actions:
  overview / sector_scan / index / screener / trade_plan / fibonacci
"""
from __future__ import annotations

from collections.abc import Callable

import anyio

from ..errors import ProviderError, tool_error
from . import _tv_scanners as _tv
from ._sanitize import sanitize

# Project interval vocabulary -> reference timeframe codes (sanitize_timeframe).
_TIMEFRAME_ALIASES = {"5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h",
                      "1d": "1D", "1w": "1W", "1m": "1M"}

# Venues the reference accepts as `exchange` values (sanitize_exchange legal
# set): stock exchanges, crypto exchanges, plus forex/cfd TA-only venues.
_VALID_EXCHANGES = {
    "kucoin", "binance", "bybit", "mexc", "okx", "gateio", "huobi",
    "bitfinex", "bitget", "coinbase",
    "egx", "bist", "nasdaq", "nyse", "amex", "nysearca", "pcx",
    "bursa", "myx", "klse", "ace", "leap", "hkex", "hk", "hsi",
    "asx", "sse", "szse", "chn", "twse", "tpex", "tadawul", "tasi",
    "oanda", "fx_idc", "fxcm", "tvc", "capitalcom",
}


def sanitize_timeframe(tf: str, default: str = "1D") -> str:
    """Reference sanitize_timeframe: alias lookup, else default.

    Non-str input falls back to the default (containers must never raise on
    garbage arguments).
    """
    if not isinstance(tf, str) or not tf:
        return default
    return _TIMEFRAME_ALIASES.get(tf.strip().lower(), default)


def sanitize_exchange(ex: str, default: str = "kucoin") -> str:
    """Reference sanitize_exchange: legal set, else default.

    Non-str input falls back to the default (containers must never raise on
    garbage arguments).
    """
    if not isinstance(ex, str) or not ex:
        return default
    exs = ex.strip().lower()
    return exs if exs in _VALID_EXCHANGES else default


async def _run(action, impl):
    try:
        return await anyio.to_thread.run_sync(impl)
    except ProviderError as e:
        # Preserve the taxonomy kind (rate_limited / not_found / ...) at the
        # container boundary, like _routing.py's "kind: msg" source_errors.
        return tool_error(f"{e.kind}: {str(e)[:200]}", source="tradingview")
    except Exception as e:  # noqa: BLE001 - containers never raise
        # Non-ProviderError has no kind; keep the type name for diagnosability.
        return tool_error(f"{action}: {type(e).__name__}: {str(e)[:200]}",
                          source="tradingview")


def _clamp_limit(limit, minimum=1, maximum=50) -> int:
    try:
        return max(minimum, min(int(limit), maximum))
    except (TypeError, ValueError):
        return minimum


def _clamp_float(value, minimum, maximum, default) -> float:
    try:
        return max(minimum, min(float(value), maximum))
    except (TypeError, ValueError):
        return default


def _clamp_int(value, minimum, maximum, default) -> int:
    try:
        return max(minimum, min(int(value), maximum))
    except (TypeError, ValueError):
        return default


def _known_action(routes: dict, action) -> bool:
    """Hash-safe unknown-action check: non-str actions are never valid keys
    and must not make the `action not in dict` lookup raise TypeError."""
    return isinstance(action, str) and action in routes


# ── tv_scan routes ──────────────────────────────────────────────────────────

_TV_SCAN_ROUTES: dict[str, Callable[[dict], object]] = {
    "top_gainers": lambda p: _tv.top_gainers(p["exchange"], p["timeframe"], p["limit"]),
    "top_losers": lambda p: _tv.top_losers(p["exchange"], p["timeframe"], p["limit"]),
    "bollinger_squeeze": lambda p: _tv.bollinger_squeeze(
        p["exchange"], p["timeframe"], p["bbw_threshold"], p["limit"]),
    "rating": lambda p: _tv.rating(p["exchange"], p["timeframe"], p["rating"],
                                   p["limit"]),
    "consecutive_candles": lambda p: _tv.consecutive_candles(
        p["exchange"], p["timeframe"], p["pattern_type"], p["candle_count"],
        p["min_growth"], p["limit"]),
    "volume_breakout": lambda p: _tv.volume_breakout(
        p["exchange"], p["timeframe"], p["volume_multiplier"],
        p["price_change_min"], p["limit"]),
    "smart_volume": lambda p: _tv.smart_volume(
        p["exchange"], p["min_volume_ratio"], p["min_price_change"],
        p["rsi_range"], p["limit"]),
}


async def tv_scan(action: str, exchange: str = "US", timeframe: str = "1d",
                  limit: int = 25, **kwargs) -> dict:
    """Scan a whole TradingView exchange by `action`.

    Actions: top_gainers, top_losers, bollinger_squeeze, rating,
    consecutive_candles, volume_breakout, smart_volume.
    """
    if not _known_action(_TV_SCAN_ROUTES, action):
        return tool_error(f"unknown action {action!r}",
                          hint=f"可用 action: {sorted(_TV_SCAN_ROUTES)}")
    params = {
        "exchange": sanitize_exchange(exchange, "US"),
        "timeframe": sanitize_timeframe(timeframe, "1D"),
        "limit": _clamp_limit(limit, 1, 100),
        "bbw_threshold": _clamp_float(kwargs.get("bbw_threshold"), 0.0, 10.0, 0.04),
        "rating": _clamp_int(kwargs.get("rating"), -3, 3, 2),
        "pattern_type": kwargs.get("pattern_type", "bullish"),
        "candle_count": _clamp_int(kwargs.get("candle_count"), 2, 5, 3),
        "min_growth": _clamp_float(kwargs.get("min_growth"), 0.5, 20.0, 2.0),
        "volume_multiplier": _clamp_float(kwargs.get("volume_multiplier"),
                                          1.5, 10.0, 2.0),
        "price_change_min": _clamp_float(kwargs.get("price_change_min"),
                                         1.0, 20.0, 3.0),
        "min_volume_ratio": _clamp_float(kwargs.get("min_volume_ratio"),
                                         1.2, 10.0, 2.0),
        "min_price_change": _clamp_float(kwargs.get("min_price_change"),
                                         0.5, 20.0, 2.0),
        "rsi_range": kwargs.get("rsi_range", "any"),
    }
    result = await _run(f"tv_scan:{action}", lambda: _TV_SCAN_ROUTES[action](params))
    return result if "error" in result else {"data": sanitize(result)}


# ── tv_analyze routes ───────────────────────────────────────────────────────

_TV_ANALYZE_ROUTES: dict[str, Callable[[dict], object]] = {
    "summary": lambda p: _summary_of(_tv.coin(p["symbol"], p["exchange"],
                                              p["timeframe"])),
    "coin": lambda p: _tv.coin(p["symbol"], p["exchange"], p["timeframe"]),
    "candle_pattern": lambda p: _tv.candle_pattern(
        p["exchange"], p["timeframe"], p["pattern_length"],
        p["min_size_increase"], p["limit"]),
    "multi_timeframe": lambda p: _tv.multi_timeframe(p["symbol"], p["exchange"],
                                                     p["timeframe"]),
    "volume_confirmation": lambda p: _tv.volume_confirmation(
        p["symbol"], p["exchange"], p["timeframe"]),
}


async def tv_analyze(action: str, symbol: str, exchange: str | None = None,
                     timeframe: str = "1d", **kwargs) -> dict:
    """Analyze one TradingView symbol by `action`.

    Actions: summary (key fields of coin), coin (full analysis dict),
    candle_pattern, multi_timeframe, volume_confirmation.
    """
    if not isinstance(symbol, str) or not symbol.strip():
        return tool_error("symbol is required for tv_analyze",
                          hint="pass a TradingView symbol like EGX:COMI, "
                               "NASDAQ:AAPL, BINANCE:BTCUSDT")
    if not _known_action(_TV_ANALYZE_ROUTES, action):
        return tool_error(f"unknown action {action!r}",
                          hint=f"可用 action: {sorted(_TV_ANALYZE_ROUTES)}")
    raw = symbol.strip()
    if exchange is None:
        # Default venue: the exchange prefix embedded in the symbol (EGX:COMI
        # -> EGX), else US.
        exchange = raw.split(":", 1)[0] if ":" in raw else "US"
    exchange = sanitize_exchange(exchange, "US")
    local = raw.split(":", 1)[1] if ":" in raw else raw
    params = {
        "symbol": local,
        "exchange": exchange,
        "timeframe": sanitize_timeframe(timeframe, "1D"),
        "pattern_length": _clamp_int(kwargs.get("pattern_length"), 2, 4, 3),
        "min_size_increase": _clamp_float(kwargs.get("min_size_increase"),
                                          5.0, 50.0, 10.0),
        "limit": _clamp_limit(kwargs.get("limit", 15), 1, 50),
    }
    result = await _run(f"tv_analyze:{action}",
                        lambda: _TV_ANALYZE_ROUTES[action](params))
    return result if "error" in result else {"data": sanitize(result)}


def _summary_of(full: dict) -> dict:
    """Reduced key-field view of the coin analysis dict."""
    price_data = full.get("price_data") or {}
    sentiment = full.get("market_sentiment") or {}
    rsi = full.get("rsi") or {}
    macd = full.get("macd") or {}
    structure = full.get("market_structure") or {}
    return {
        "symbol": full.get("symbol"),
        "exchange": full.get("exchange"),
        "timeframe": full.get("timeframe"),
        "price": price_data.get("current_price"),
        "change_percent": price_data.get("change_percent"),
        "rating": sentiment.get("overall_rating"),
        "signal": sentiment.get("buy_sell_signal"),
        "momentum": sentiment.get("momentum"),
        "volatility": sentiment.get("volatility"),
        "rsi": rsi.get("value"),
        "rsi_signal": rsi.get("signal"),
        "macd_crossover": macd.get("crossover"),
        "trend": structure.get("trend"),
        "trend_strength": structure.get("trend_strength"),
        "stock_score": full.get("stock_score"),
        "grade": full.get("grade"),
        "recommendation": (full.get("trade_setup") or {}).get("setup_types"),
    }


# ── egx_market routes ───────────────────────────────────────────────────────

def _egx_index_route(p: dict) -> dict:
    """index action: reject EGX100 (no vendored constituent table)."""
    from ..data.egx_indices import EGX_INDICES

    raw = p["index"]
    if not isinstance(raw, str) or not raw.strip():
        raise ProviderError("index is required for egx index action")
    key = raw.strip().upper()
    if key == "EGX100":
        raise ProviderError(
            f"{key} has no vendored constituent table in this package",
        )
    if key not in EGX_INDICES:
        raise ProviderError(f"Unknown index: {key}; available: "
                            f"{sorted(EGX_INDICES)}")
    return _tv.egx_index(key, p["timeframe"], p["limit"])


def _egx_trade_plan_route(p: dict) -> dict:
    symbol = p["symbol"]
    if not isinstance(symbol, str) or not symbol.strip():
        raise ProviderError("symbol is required for egx trade_plan")
    return _tv.egx_trade_plan(symbol.strip(), p["timeframe"])


def _egx_fibonacci_route(p: dict) -> dict:
    symbol = p["symbol"]
    if not isinstance(symbol, str) or not symbol.strip():
        raise ProviderError("symbol is required for egx fibonacci")
    return _tv.egx_fibonacci(symbol.strip(), p["lookback"], p["timeframe"])


_EGX_ROUTES: dict[str, Callable[[dict], object]] = {
    "overview": lambda p: _tv.egx_overview(p["timeframe"], p["limit"]),
    "sector_scan": lambda p: _tv.egx_sector_scan(p["sector"], p["timeframe"],
                                                 p["limit"]),
    "index": _egx_index_route,
    "screener": lambda p: _tv.egx_screener(p["timeframe"], p["min_score"],
                                           p["index_filter"], p["limit"]),
    "trade_plan": _egx_trade_plan_route,
    "fibonacci": _egx_fibonacci_route,
}


async def egx_market(action: str, **kwargs) -> dict:
    """Egyptian Exchange (EGX) market tools by `action`; Egypt-locked.

    Actions: overview, sector_scan, index, screener, trade_plan, fibonacci.
    """
    if not _known_action(_EGX_ROUTES, action):
        return tool_error(f"unknown action {action!r}",
                          hint=f"可用 action: {sorted(_EGX_ROUTES)}")
    params = {
        "timeframe": sanitize_timeframe(kwargs.get("timeframe", "1d"), "1D"),
        "limit": _clamp_limit(kwargs.get("limit", 20), 1, 100),
        "sector": kwargs.get("sector", ""),
        "index": kwargs.get("index", "EGX30"),
        "min_score": _clamp_int(kwargs.get("min_score"), 0, 100, 55),
        "index_filter": kwargs.get("index_filter", ""),
        "symbol": kwargs.get("symbol", ""),
        "lookback": _sanitize_lookback(kwargs.get("lookback")),
    }
    result = await _run(f"egx_market:{action}", lambda: _EGX_ROUTES[action](params))
    return result if "error" in result else {"data": sanitize(result)}


def _sanitize_lookback(lookback) -> str:
    """lookback: reference `lookback.strip().upper()`, default "52W"; non-str
    falls back to the default (containers must never raise on garbage)."""
    if not isinstance(lookback, str):
        return "52W"
    return lookback.strip().upper() or "52W"


def register(mcp, providers, settings) -> None:
    @mcp.tool(name="tv_scan")
    async def tv_scan_tool(action: str, exchange: str = "US", timeframe: str = "1d",
                           limit: int = 25, **kwargs) -> dict:
        """Scan a whole TradingView exchange by action (see tv_scan docstring)."""
        return await tv_scan(action, exchange, timeframe, limit, **kwargs)

    @mcp.tool(name="tv_analyze")
    async def tv_analyze_tool(action: str, symbol: str,
                              exchange: str | None = None,
                              timeframe: str = "1d", **kwargs) -> dict:
        """Analyze one TradingView symbol by action (see tv_analyze docstring)."""
        return await tv_analyze(action, symbol, exchange, timeframe, **kwargs)

    @mcp.tool(name="egx_market")
    async def egx_market_tool(action: str, **kwargs) -> dict:
        """Egyptian Exchange market tools by action (see egx_market docstring)."""
        return await egx_market(action, **kwargs)
