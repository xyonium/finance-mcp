"""TradingView scanner/analysis implementations backing the tv_scan, tv_analyze
and egx_market containers (ported from the reference tradingview-mcp
core/services/{screener_service,scanner_service,egx_service}.py).

Porting discipline (Task 14 rulings):
- every public function is sync and the container wraps it in
  anyio.to_thread.run_sync (same pattern as providers/tradingview.py) — the
  sync body runs the vendored symbol lists through tradingview_ta's
  get_multiple_analysis;
- returns are plain dict/list, never the reference project's error envelope;
- exceptions raised here are ProviderError (no internal paths, no keys —
  errors.scrub discipline);
- TA_Handler/Query/_INTERVAL facilities reuse the tradingview provider's,
  not new ones;
- every output row that passed through a TradingView data surface is run
  through tools/_sanitize.py::sanitize.
"""
from __future__ import annotations

import tradingview_ta

from ..errors import ProviderError
from ._sanitize import sanitize

TA_AVAILABLE = tradingview_ta is not None  # pragma: no cover - import-time check


def _symbols_for(exchange: str) -> list[str]:
    """Vendored symbol list for *exchange*, or raise ProviderError."""
    from ..data.coinlist import load_symbols
    symbols = load_symbols(exchange)
    if not symbols:
        raise ProviderError(f"No symbols found for exchange: {exchange}")
    return symbols


def _screener_for(exchange: str) -> str:
    from ..providers.tradingview import EXCHANGE_TO_TV_SCREENER
    return EXCHANGE_TO_TV_SCREENER.get(exchange, exchange.lower())


_CODE_BY_PROJECT_INTERVAL = {"1m": "1", "5m": "5", "15m": "15", "1h": "60",
                             "4h": "240", "1d": "1D", "1wk": "1W", "1mo": "1M"}


def _fetch_analysis(screener: str, interval: str, symbols: list[str], context: str):
    """tradingview_ta.get_multiple_analysis with interval-mapped codes.

    The reference timeframes are TradingView codes ("1D", "4h", ...) while the
    container surface uses the project's interval vocabulary ("1d", "1h", ...);
    the provider's _INTERVAL map is reused here to translate. On any upstream
    failure the message is folded into a ProviderError (no internals leaked).
    """
    code = _CODE_BY_PROJECT_INTERVAL.get(interval, interval)
    try:
        return tradingview_ta.get_multiple_analysis(
            screener=screener, interval=code, symbols=symbols)
    except Exception as e:
        raise ProviderError(f"{context} failed: {str(e)[:200]}") from e


def _scan_batches(context: str, exchange: str, timeframe: str,
                  batch_size: int, cap: int):
    """Yield (batch, analysis) for the vendored symbol list.

    Fast-fail guards from the reference: stop after N consecutive failed
    batches or when every batch failed, raising ProviderError; partial
    results are yielded up to that point. Wall-clock budget guard omitted on
    purpose: reference behaviour, still bounded by per-call HTTP timeouts.
    """
    symbols = _symbols_for(exchange)[:cap]
    screener = _screener_for(exchange)
    failures = 0
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        try:
            analysis = _fetch_analysis(screener, timeframe, batch, context)
        except ProviderError:
            failures += 1
            if failures >= 2:  # reference default batch_max_consecutive_fails
                raise
            continue
        failures = 0
        yield batch, analysis
    if failures and len(symbols) // batch_size + 1 <= failures:
        raise ProviderError(f"{context} failed for every batch")


# ── scan actions ────────────────────────────────────────────────────────────

def top_gainers(exchange: str, timeframe: str = "1D", limit: int = 25) -> list[dict]:
    """Top movers for *exchange*, sorted by changePercent descending."""
    return _trending_rows(exchange, timeframe, limit, desc=True)


def top_losers(exchange: str, timeframe: str = "1D", limit: int = 25) -> list[dict]:
    """Top losers for *exchange*, sorted by changePercent ascending."""
    return _trending_rows(exchange, timeframe, limit, desc=False)


def _trending_rows(exchange: str, timeframe: str, limit: int, desc: bool) -> list[dict]:
    from ._tv_math import compute_metrics

    rows: list[dict] = []
    for _batch, analysis in _scan_batches("trending", exchange, timeframe, 200, 10**9):
        for key, value in analysis.items():
            try:
                if value is None:
                    continue
                indicators = value.indicators
                metrics = compute_metrics(indicators)
                if not metrics or metrics.get("bbw") is None:
                    continue
                rows.append({
                    "symbol": key,
                    "changePercent": metrics["change"],
                    "indicators": {
                        "open": metrics.get("open"),
                        "close": metrics.get("price"),
                        "SMA20": indicators.get("SMA20"),
                        "BB_upper": indicators.get("BB.upper"),
                        "BB_lower": indicators.get("BB.lower"),
                        "EMA50": indicators.get("EMA50"),
                        "RSI": indicators.get("RSI"),
                        "volume": indicators.get("volume"),
                    },
                })
            except (TypeError, ZeroDivisionError, KeyError):
                continue
    rows.sort(key=lambda x: x["changePercent"], reverse=desc)
    return sanitize(rows[:limit])


def bollinger_squeeze(exchange: str, timeframe: str = "4h", bbw_filter: float = 0.04,
                      limit: int = 50) -> list[dict]:
    """Bollinger Band Width squeeze scan for a whole exchange."""
    from ._tv_math import compute_metrics

    rows: list[dict] = []
    symbols = _symbols_for(exchange)[:limit * 2]
    screener = _screener_for(exchange)
    analysis = _fetch_analysis(screener, timeframe, symbols, "bollinger_scan")
    for key, value in analysis.items():
        try:
            if value is None:
                continue
            indicators = value.indicators
            metrics = compute_metrics(indicators)
            if not metrics or metrics.get("bbw") is None:
                continue
            if bbw_filter is not None and (metrics["bbw"] >= bbw_filter
                                           or metrics["bbw"] <= 0):
                continue
            if not (indicators.get("EMA50") and indicators.get("RSI")):
                continue
            rows.append({
                "symbol": key,
                "changePercent": metrics["change"],
                "indicators": {
                    "open": metrics.get("open"),
                    "close": metrics.get("price"),
                    "SMA20": indicators.get("SMA20"),
                    "BB_upper": indicators.get("BB.upper"),
                    "BB_lower": indicators.get("BB.lower"),
                    "EMA50": indicators.get("EMA50"),
                    "RSI": indicators.get("RSI"),
                    "volume": indicators.get("volume"),
                },
            })
        except (TypeError, ZeroDivisionError, KeyError):
            continue
    rows.sort(key=lambda x: x["changePercent"], reverse=True)
    return sanitize(rows[:limit])


def rating(exchange: str, timeframe: str = "5m", rating_filter: int = 2,
           limit: int = 25) -> list[dict]:
    """Filter symbols by Bollinger Band rating (-3..3)."""
    from ._tv_math import compute_metrics

    rows: list[dict] = []
    for _batch, analysis in _scan_batches("rating", exchange, timeframe, 200, 10**9):
        for key, value in analysis.items():
            try:
                if value is None:
                    continue
                indicators = value.indicators
                metrics = compute_metrics(indicators)
                if not metrics or metrics.get("bbw") is None:
                    continue
                if metrics["rating"] != rating_filter:
                    continue
                rows.append({
                    "symbol": key,
                    "changePercent": metrics["change"],
                    "indicators": {
                        "open": metrics.get("open"),
                        "close": metrics.get("price"),
                        "SMA20": indicators.get("SMA20"),
                        "BB_upper": indicators.get("BB.upper"),
                        "BB_lower": indicators.get("BB.lower"),
                        "EMA50": indicators.get("EMA50"),
                        "RSI": indicators.get("RSI"),
                        "volume": indicators.get("volume"),
                    },
                })
            except (TypeError, ZeroDivisionError, KeyError):
                continue
    rows.sort(key=lambda x: x["changePercent"], reverse=True)
    return sanitize(rows[:limit])


def consecutive_candles(exchange: str, timeframe: str, pattern_type: str = "bullish",
                        candle_count: int = 3, min_growth: float = 2.0,
                        limit: int = 20) -> dict:
    """Consecutive growing/shrinking candle pattern scan."""
    from ._tv_math import compute_metrics

    symbols = _symbols_for(exchange)[:min(limit * 3, 200)]
    screener = _screener_for(exchange)
    analysis = _fetch_analysis(screener, timeframe, symbols, "consecutive_candles")

    pattern_coins: list[dict] = []
    for symbol, data in analysis.items():
        if data is None:
            continue
        try:
            indicators = data.indicators
            open_price = indicators.get("open")
            close_price = indicators.get("close")
            high_price = indicators.get("high")
            low_price = indicators.get("low")
            volume = indicators.get("volume", 0)

            if not all([open_price, close_price, high_price, low_price]):
                continue

            current_change = ((close_price - open_price) / open_price) * 100
            candle_body = abs(close_price - open_price)
            candle_range = high_price - low_price
            body_to_range_ratio = candle_body / candle_range if candle_range > 0 else 0

            rsi = indicators.get("RSI", 50)
            sma20 = indicators.get("SMA20", close_price)
            ema50 = indicators.get("EMA50", close_price)

            price_above_sma = close_price > sma20
            price_above_ema = close_price > ema50

            if pattern_type == "bullish":
                conditions = [
                    current_change > min_growth,
                    body_to_range_ratio > 0.6,
                    price_above_sma,
                    45 < rsi < 80,
                    volume > 1000,
                ]
            elif pattern_type == "bearish":
                conditions = [
                    current_change < -min_growth,
                    body_to_range_ratio > 0.6,
                    not price_above_sma,
                    20 < rsi < 55,
                    volume > 1000,
                ]
            else:
                continue

            pattern_strength = sum(conditions)
            if pattern_strength < 3:
                continue

            metrics = compute_metrics(indicators)
            pattern_coins.append({
                "symbol": symbol,
                "price": round(close_price, 6),
                "current_change": round(current_change, 3),
                "candle_body_ratio": round(body_to_range_ratio, 3),
                "pattern_strength": pattern_strength,
                "volume": volume,
                "bollinger_rating": metrics.get("rating", 0) if metrics else 0,
                "rsi": round(rsi, 2),
                "price_levels": {
                    "open": round(open_price, 6),
                    "high": round(high_price, 6),
                    "low": round(low_price, 6),
                    "close": round(close_price, 6),
                },
                "momentum_signals": {
                    "above_sma20": price_above_sma,
                    "above_ema50": price_above_ema,
                    "strong_volume": volume > 5000,
                },
            })
        except Exception:  # noqa: BLE001, S112 - one bad row must not sink the scan
            continue

    if pattern_type == "bullish":
        pattern_coins.sort(key=lambda x: (x["pattern_strength"], x["current_change"]),
                           reverse=True)
    else:
        pattern_coins.sort(key=lambda x: (x["pattern_strength"], -x["current_change"]),
                           reverse=True)

    return sanitize({
        "exchange": exchange,
        "timeframe": timeframe,
        "pattern_type": pattern_type,
        "candle_count": candle_count,
        "min_growth": min_growth,
        "total_found": len(pattern_coins),
        "data": pattern_coins[:limit],
    })


def volume_breakout(exchange: str, timeframe: str = "15m", volume_multiplier: float = 2.0,
                    price_change_min: float = 3.0, limit: int = 25) -> list[dict]:
    """Volume + price breakout scan (reference volume_breakout_scan)."""
    volume_breakouts: list[dict] = []
    for _batch, analysis in _scan_batches("volume_breakout", exchange, timeframe,
                                          100, 500):
        for symbol, data in analysis.items():
            try:
                if not data or not hasattr(data, "indicators"):
                    continue
                ind = data.indicators

                volume = ind.get("volume", 0)
                close = ind.get("close", 0)
                open_price = ind.get("open", 0)
                sma20_volume = ind.get("volume.SMA20", 0)

                if not all([volume, close, open_price]) or volume <= 0:
                    continue

                price_change = ((close - open_price) / open_price) * 100 \
                    if open_price > 0 else 0

                if sma20_volume and sma20_volume > 0:
                    volume_ratio = volume / sma20_volume
                else:
                    avg_estimate = volume / 2
                    volume_ratio = volume / avg_estimate if avg_estimate > 0 else 1

                if abs(price_change) >= price_change_min \
                        and volume_ratio >= volume_multiplier:
                    rsi = ind.get("RSI", 50)
                    bb_upper = ind.get("BB.upper", 0)
                    bb_lower = ind.get("BB.lower", 0)
                    volume_strength = min(10, volume_ratio)

                    volume_breakouts.append({
                        "symbol": symbol,
                        "changePercent": price_change,
                        "volume_ratio": round(volume_ratio, 2),
                        "volume_strength": round(volume_strength, 1),
                        "current_volume": volume,
                        "breakout_type": "bullish" if price_change > 0 else "bearish",
                        "indicators": {
                            "close": close,
                            "RSI": rsi,
                            "BB_upper": bb_upper,
                            "BB_lower": bb_lower,
                            "volume": volume,
                        },
                    })
            except Exception:  # noqa: BLE001, S112 - one bad row must not sink the scan
                continue

    volume_breakouts.sort(key=lambda x: (x["volume_strength"], abs(x["changePercent"])),
                          reverse=True)
    return sanitize(volume_breakouts[:limit])


def smart_volume(exchange: str, min_volume_ratio: float = 2.0,
                 min_price_change: float = 2.0, rsi_range: str = "any",
                 limit: int = 20) -> list[dict]:
    """Volume breakout + RSI filter + trading recommendation."""
    breakouts = volume_breakout(
        exchange=exchange,
        volume_multiplier=min_volume_ratio,
        price_change_min=min_price_change,
        limit=limit * 2,
    )
    if not breakouts:
        return []

    filtered: list[dict] = []
    for coin in breakouts:
        rsi = coin["indicators"].get("RSI", 50)

        if rsi_range == "oversold" and rsi >= 30:
            continue
        if rsi_range == "overbought" and rsi <= 70:
            continue
        if rsi_range == "neutral" and (rsi <= 30 or rsi >= 70):
            continue

        recommendation = ""
        if coin["changePercent"] > 0 and coin["volume_ratio"] >= 2.0:
            recommendation = "STRONG BUY" if rsi < 70 else "OVERBOUGHT - CAUTION"
        elif coin["changePercent"] < 0 and coin["volume_ratio"] >= 2.0:
            recommendation = "STRONG SELL" if rsi > 30 else "OVERSOLD - OPPORTUNITY?"

        coin["trading_recommendation"] = recommendation
        filtered.append(coin)

    return sanitize(filtered[:limit])


# ── analyze actions ─────────────────────────────────────────────────────────

def _normalize_symbol(symbol: str, exchange: str) -> str:
    """Fully-qualified EXCHANGE:SYMBOL form, via the reference alias table.

    Symbol aliases (XAUUSD -> TVC:GOLD, ...) and commodity soft aliases are
    applied like the reference normalize_tradingview_symbol.
    """
    raw = (symbol or "").strip().upper()
    if raw in _TV_SYMBOL_ALIASES:
        return _TV_SYMBOL_ALIASES[raw]
    if ":" in raw:
        return raw
    if raw in _COMMODITY_SOFT_ALIASES and not _is_stock_exchange(exchange):
        return _COMMODITY_SOFT_ALIASES[raw]
    return f"{_tv_prefix(exchange)}:{raw}"


_TV_SYMBOL_ALIASES = {
    "TAIEX": "TWSE:IX0001",
    "TAIEX.TW": "TWSE:IX0001",
    "^TWII": "TWSE:IX0001",
    "IX0001": "TWSE:IX0001",
    "TWSE:TAIEX": "TWSE:IX0001",
    "TWSE:IX0001": "TWSE:IX0001",
    "XAUUSD": "TVC:GOLD",
    "XAGUSD": "TVC:SILVER",
    "GC1!": "TVC:GOLD", "GC2!": "TVC:GOLD", "MGC1!": "TVC:GOLD",
    "GCUSD": "TVC:GOLD",
    "SI1!": "TVC:SILVER", "SIL1!": "TVC:SILVER", "SIUSD": "TVC:SILVER",
    "PL1!": "TVC:PLATINUM", "XPTUSD": "TVC:PLATINUM",
    "PA1!": "TVC:PALLADIUM", "XPDUSD": "TVC:PALLADIUM",
}

_COMMODITY_SOFT_ALIASES = {
    "GOLD": "TVC:GOLD",
    "XAU": "TVC:GOLD",
    "SILVER": "TVC:SILVER",
    "XAG": "TVC:SILVER",
    "DXY": "TVC:DXY",
}

_STOCK_EXCHANGES = {
    "egx", "bist", "nasdaq", "nyse", "amex", "nysearca", "pcx",
    "bursa", "myx", "klse", "ace", "leap", "hkex", "hk", "hsi",
    "asx", "sse", "szse", "chn", "twse", "tpex", "tadawul", "tasi",
}

_TV_EXCHANGE_PREFIX = {
    "amex": "AMEX", "nysearca": "AMEX", "pcx": "AMEX",
    "nasdaq": "NASDAQ", "nyse": "NYSE", "egx": "EGX", "bist": "BIST",
    "bursa": "MYX", "myx": "MYX", "klse": "MYX", "ace": "MYX", "leap": "MYX",
    "hkex": "HKEX", "hk": "HKEX", "hsi": "HSI",
    "asx": "ASX", "sse": "SSE", "szse": "SZSE", "chn": "SSE",
    "twse": "TWSE", "tpex": "TPEX", "tadawul": "TADAWUL", "tasi": "TADAWUL",
}


def _tv_prefix(exchange: str) -> str:
    return _TV_EXCHANGE_PREFIX.get(exchange.strip().lower(), exchange.upper())


def _is_stock_exchange(exchange: str) -> bool:
    return exchange.strip().lower() in _STOCK_EXCHANGES


def _resolve_screener_for_symbol(full_symbol: str, exchange: str) -> str:
    """Screener market following the RESOLVED symbol's venue, not the caller's
    exchange guess (XAUUSD -> TVC:GOLD -> "cfd", EURUSD -> FX_IDC -> "forex").
    """
    from ..providers.tradingview import EXCHANGE_TO_TV_SCREENER
    prefix = (full_symbol.split(":", 1)[0] if ":" in full_symbol
              else (exchange or "")).strip().lower()
    return (EXCHANGE_TO_TV_SCREENER.get(prefix)
            or _TA_ONLY_SCREENERS.get(prefix) or "crypto")


_TA_ONLY_SCREENERS = {"oanda": "forex", "fx_idc": "forex", "fxcm": "forex",
                      "tvc": "cfd", "capitalcom": "cfd"}


def _fallback_venues(symbol: str, requested: str) -> list[str]:
    """Other exchanges (per vendored coinlists) that list *symbol*."""
    from ..data.coinlist import exchanges_listing_symbol
    listed = [e.upper() for e in exchanges_listing_symbol(symbol)]
    req = (requested or "").upper()
    return [e for e in listed if e != req]


def _fallback_preference(venues: list[str]) -> str | None:
    for pref in ("KUCOIN", "MEXC", "GATEIO", "BYBIT", "OKX", "HUOBI"):
        if pref in venues:
            return pref
    return venues[0] if venues else None


def coin(symbol: str, exchange: str, timeframe: str = "1D") -> dict:
    """Full technical analysis for one symbol (reference analyze_coin)."""
    from ._tv_math import (
        analyze_timeframe_context,
        compute_metrics,
        compute_stock_score,
        compute_trade_quality,
        compute_trade_setup,
        extract_extended_indicators,
    )

    return _analyze_coin_inner(symbol, exchange, timeframe, allow_fallback=True,
                               compute_metrics=compute_metrics,
                               analyze_timeframe_context=analyze_timeframe_context,
                               compute_stock_score=compute_stock_score,
                               compute_trade_setup=compute_trade_setup,
                               compute_trade_quality=compute_trade_quality,
                               extract_extended_indicators=extract_extended_indicators)


def _analyze_coin_inner(symbol, exchange, timeframe, allow_fallback, **maths):
    full_symbol = _normalize_symbol(symbol, exchange)
    screener = _resolve_screener_for_symbol(full_symbol, exchange)

    try:
        analysis = _fetch_analysis(screener, timeframe, [full_symbol], "coin_analysis")
    except ProviderError as e:
        raise ProviderError(str(e)) from e

    if full_symbol not in analysis or analysis[full_symbol] is None:
        if allow_fallback:
            alt = _fallback_preference(_fallback_venues(symbol, exchange))
            if alt:
                result = _analyze_coin_inner(symbol, alt, timeframe,
                                             allow_fallback=False, **maths)
                if "error" not in result:
                    result["requested_exchange"] = exchange
                    result["resolved_exchange"] = alt
                    result["resolution_note"] = (
                        f"{symbol} is not listed on {exchange}; analysis was run on "
                        f"{alt}, which lists it. Pass exchange=\"{alt}\" to silence "
                        "this note.")
                    return result
        raise NotFoundError(f"No data found for {symbol} on {exchange}.")

    data = analysis[full_symbol]
    indicators = data.indicators
    metrics = maths["compute_metrics"](indicators)

    if not metrics:
        raise ProviderError(f"Could not compute metrics for {symbol}")

    volume = indicators.get("volume", 0)
    high = indicators.get("high", 0)
    low = indicators.get("low", 0)
    open_price = indicators.get("open", 0)
    close_price = indicators.get("close", 0)

    extended = maths["extract_extended_indicators"](indicators)
    tf_context = maths["analyze_timeframe_context"](indicators, timeframe)

    trade_data: dict = {}
    if _is_stock_exchange(exchange):
        score_result = maths["compute_stock_score"](indicators)
        if score_result:
            trade_data["stock_score"] = score_result["score"]
            trade_data["grade"] = score_result["grade"]
            trade_data["trend_state"] = score_result["trend_state"]
            setup = maths["compute_trade_setup"](indicators)
            if setup:
                trade_data["trade_setup"] = {
                    "setup_types": setup["setup_types"],
                    "entry_points": setup["entry_points"],
                    "stop_loss": setup["stop_loss"],
                    "stop_distance_pct": setup["stop_distance_pct"],
                    "targets": setup["targets"],
                    "risk_reward": setup["risk_reward"],
                    "supports": setup["supports"],
                    "resistances": setup["resistances"],
                }
                quality = maths["compute_trade_quality"](indicators,
                                                         score_result["score"], setup)
                if quality:
                    trade_data["trade_quality_score"] = quality["trade_quality_score"]
                    trade_data["trade_quality"] = quality["quality"]
                    trade_data["trade_notes"] = quality["notes"]

    return sanitize({
        "symbol": full_symbol,
        "exchange": exchange,
        "timeframe": timeframe,
        "timestamp": "real-time",
        "price_data": {
            "current_price": metrics["price"],
            "open": round(open_price, 6) if open_price else None,
            "high": round(high, 6) if high else None,
            "low": round(low, 6) if low else None,
            "close": round(close_price, 6) if close_price else None,
            "change_percent": metrics["change"],
            "volume": volume,
        },
        "timeframe_context": tf_context,
        "rsi": extended["rsi"],
        "macd": extended["macd"],
        "sma": extended["sma"],
        "ema": extended["ema"],
        "bollinger_bands": extended["bollinger_bands"],
        "atr": extended["atr"],
        "volume_analysis": extended["volume"],
        "obv": extended["obv"],
        "support_resistance": extended["support_resistance"],
        "stochastic": extended["stochastic"],
        "adx": extended["adx"],
        "market_structure": extended["market_structure"],
        **({"vwap": extended["vwap"]} if "vwap" in extended else {}),
        "market_sentiment": {
            "overall_rating": metrics["rating"],
            "buy_sell_signal": metrics["signal"],
            "volatility": (
                "High" if metrics["bbw"] and metrics["bbw"] > 0.05
                else "Medium" if metrics["bbw"] and metrics["bbw"] > 0.02
                else "Low"
            ),
            "momentum": "Bullish" if metrics["change"] > 0 else "Bearish",
        },
        **trade_data,
    })


class NotFoundError(ProviderError):
    kind = "not_found"


def candle_pattern(exchange: str, timeframe: str = "15m", pattern_length: int = 3,
                   min_size_increase: float = 10.0, limit: int = 15) -> dict:
    """Advanced candle pattern scan: TradingView screener (Query) first, then
    tradingview_ta single-timeframe fallback (reference advanced_candle_pattern).
    """
    symbols = _symbols_for(exchange)
    symbols = symbols[:min(limit * 2, 100)]
    try:
        results = _multi_tf_patterns(exchange, symbols, timeframe, pattern_length,
                                     min_size_increase)
    except ProviderError:
        results = None
    if results:
        return sanitize({
            "exchange": exchange,
            "base_timeframe": timeframe,
            "pattern_length": pattern_length,
            "min_size_increase": min_size_increase,
            "method": "multi-timeframe",
            "total_found": len(results),
            "data": results[:limit],
        })
    return _single_tf_patterns(exchange, symbols, timeframe, pattern_length,
                               min_size_increase, limit)


def _multi_tf_patterns(exchange: str, symbols: list[str], base_tf: str,
                       length: int, min_increase: float) -> list[dict]:
    from tradingview_screener import Column, Query

    from ._tv_math import compute_candle_pattern_score

    tf_map = {"5m": "5", "15m": "15", "1h": "60", "4h": "240", "1D": "1D"}
    tv_interval = tf_map.get(base_tf, "15")

    cols = [
        f"open|{tv_interval}", f"close|{tv_interval}",
        f"high|{tv_interval}", f"low|{tv_interval}",
        f"volume|{tv_interval}", "RSI",
    ]

    from ..providers.tradingview import MARKET_TO_TV_SCREENER
    market = MARKET_TO_TV_SCREENER.get(exchange.upper(), "crypto")
    q = (Query().set_markets(market).select(*cols)
         .where(Column("exchange") == exchange.upper()).limit(len(symbols)))

    _total, df = q.get_scanner_data()
    if df is None or df.empty:
        return []

    results = []
    for _, row in df.iterrows():
        symbol = row.get("ticker", "")
        try:
            ind = {
                "open": row.get(f"open|{tv_interval}"),
                "close": row.get(f"close|{tv_interval}"),
                "high": row.get(f"high|{tv_interval}"),
                "low": row.get(f"low|{tv_interval}"),
                "volume": row.get(f"volume|{tv_interval}", 0),
                "RSI": row.get("RSI", 50),
            }
            if not all([ind["open"], ind["close"], ind["high"], ind["low"]]):
                continue

            pattern_score = compute_candle_pattern_score(ind, length, min_increase)
            if pattern_score["detected"]:
                results.append({
                    "symbol": symbol,
                    "pattern_score": pattern_score["score"],
                    "price": pattern_score["price"],
                    "change": pattern_score["total_change"],
                    "body_ratio": pattern_score["body_ratio"],
                    "volume": ind["volume"],
                    "rsi": round(ind["RSI"], 2),
                    "details": pattern_score["details"],
                })
        except Exception:  # noqa: BLE001, S112 - one bad row must not sink the scan
            continue

    return sorted(results, key=lambda x: x["pattern_score"], reverse=True)


def _single_tf_patterns(exchange: str, symbols: list[str], base_tf: str,
                        pattern_length: int, min_size_increase: float,
                        limit: int) -> dict:
    from ._tv_math import compute_candle_pattern_score, compute_metrics

    screener = _screener_for(exchange)
    analysis = _fetch_analysis(screener, base_tf, symbols, "candle_pattern")
    pattern_results: list[dict] = []

    for symbol, data in analysis.items():
        if data is None:
            continue
        try:
            indicators = data.indicators
            pattern_score = compute_candle_pattern_score(indicators, pattern_length,
                                                         min_size_increase)
            if pattern_score["detected"]:
                metrics = compute_metrics(indicators)
                pattern_results.append({
                    "symbol": symbol,
                    "pattern_score": pattern_score["score"],
                    "pattern_details": pattern_score["details"],
                    "current_price": pattern_score["price"],
                    "total_change": pattern_score["total_change"],
                    "volume": indicators.get("volume", 0),
                    "bollinger_rating": metrics.get("rating", 0) if metrics else 0,
                    "technical_strength": {
                        "rsi": round(indicators.get("RSI", 50), 2),
                        "momentum": ("Strong" if abs(pattern_score["total_change"])
                                     > min_size_increase else "Moderate"),
                        "volume_trend": ("High" if indicators.get("volume", 0) > 10000
                                         else "Low"),
                    },
                })
        except Exception:  # noqa: BLE001, S112 - one bad row must not sink the scan
            continue

    pattern_results.sort(key=lambda x: (x["pattern_score"], abs(x["total_change"])),
                         reverse=True)
    return sanitize({
        "exchange": exchange,
        "base_timeframe": base_tf,
        "pattern_length": pattern_length,
        "min_size_increase": min_size_increase,
        "method": "enhanced-single-timeframe",
        "total_found": len(pattern_results),
        "data": pattern_results[:limit],
    })


def multi_timeframe(symbol: str, exchange: str, timeframe: str = "1D") -> dict:
    """Multi-timeframe alignment analysis (Weekly → Daily → 4H → 1H → 15m).

    *timeframe* is accepted for container uniformity; like the reference the
    analysis itself always covers the fixed five timeframes.
    """
    from ._tv_math import analyze_timeframe_context, compute_metrics, extract_extended_indicators

    full_symbol = _normalize_symbol(symbol, exchange)
    screener = _resolve_screener_for_symbol(full_symbol, exchange)
    timeframes = ["1W", "1D", "4h", "1h", "15m"]
    tf_labels = {
        "1W": "Weekly (Trend Bias)",
        "1D": "Daily (Swing Setup)",
        "4h": "4-Hour (Refinement)",
        "1h": "1-Hour (Entry Timing)",
        "15m": "15-Min (Execution)",
    }

    tf_results: dict = {}
    alignment_scores: list[int] = []
    consecutive_failures = 0

    for tf in timeframes:
        try:
            analysis = _fetch_analysis(screener, tf, [full_symbol],
                                       "multi_timeframe")
        except ProviderError as e:
            tf_results[tf] = {"error": str(e)[:200]}
            consecutive_failures += 1
            if consecutive_failures >= 2:  # reference default fast-fail
                for skip_tf in timeframes:
                    if skip_tf not in tf_results:
                        tf_results[skip_tf] = {"error": "skipped: upstream cliff"}
                break
            continue

        if full_symbol not in analysis or analysis[full_symbol] is None:
            tf_results[tf] = {"error": f"No data for {tf}"}
            consecutive_failures = 0
            continue
        consecutive_failures = 0

        data = analysis[full_symbol]
        indicators = data.indicators
        metrics = compute_metrics(indicators)
        extended = extract_extended_indicators(indicators)
        tf_context = analyze_timeframe_context(indicators, tf)

        bias_num = (1 if tf_context["bias"] == "Bullish"
                    else -1 if tf_context["bias"] == "Bearish" else 0)
        alignment_scores.append(bias_num)

        tf_results[tf] = {
            "label": tf_labels.get(tf, tf),
            "bias": tf_context["bias"],
            "bias_reasons": tf_context["bias_reasons"],
            "key_indicators": tf_context["key_indicators_for_timeframe"],
            "advice": tf_context["advice"],
            "price": metrics.get("price") if metrics else None,
            "change_pct": metrics.get("change") if metrics else None,
            "rsi": extended["rsi"],
            "macd_crossover": extended["macd"]["crossover"],
            "ema_trend": {
                "ema20": extended["ema"].get("ema20"),
                "ema50": extended["ema"].get("ema50"),
                "ema200": extended["ema"].get("ema200"),
            },
            "volume_signal": extended["volume"]["signal"],
            "market_structure": extended["market_structure"]["trend"],
            "trend_strength": extended["market_structure"]["trend_strength"],
            "momentum_aligned": extended["market_structure"]["momentum_aligned"],
        }

    total_score = sum(alignment_scores)
    all_bullish = all(s > 0 for s in alignment_scores) if alignment_scores else False
    all_bearish = all(s < 0 for s in alignment_scores) if alignment_scores else False

    if all_bullish:
        alignment, confidence, action = (
            "FULLY ALIGNED BULLISH", "Very High",
            "STRONG BUY - All timeframes bullish. Look for pullback entry on 1H/15m.")
    elif all_bearish:
        alignment, confidence, action = (
            "FULLY ALIGNED BEARISH", "Very High",
            "STRONG SELL - All timeframes bearish. Avoid longs.")
    elif total_score >= 3:
        alignment, confidence, action = (
            "MOSTLY BULLISH", "High",
            "BUY - Majority of timeframes bullish. Enter on 4H/1H pullback to support.")
    elif total_score <= -3:
        alignment, confidence, action = (
            "MOSTLY BEARISH", "High",
            "SELL - Majority of timeframes bearish. Avoid catching the falling knife.")
    elif total_score > 0:
        alignment, confidence, action = (
            "LEAN BULLISH", "Medium",
            "CAUTIOUS BUY - Some bullish signals but not fully aligned. Wait for better setup.")
    elif total_score < 0:
        alignment, confidence, action = (
            "LEAN BEARISH", "Medium",
            "CAUTIOUS SELL - Some bearish signals. Reduce position or wait.")
    else:
        alignment, confidence, action = (
            "MIXED/RANGING", "Low",
            "HOLD/NO TRADE - Timeframes conflict. Wait for alignment.")

    higher_tf_bias = alignment_scores[0] if alignment_scores else 0
    divergent_tfs = [
        timeframes[i]
        for i, score in enumerate(alignment_scores)
        if score != 0 and score != higher_tf_bias and higher_tf_bias != 0
    ]

    return sanitize({
        "symbol": full_symbol,
        "exchange": exchange,
        "analysis_type": "Multi-Timeframe Alignment",
        "timeframes": tf_results,
        "alignment": {
            "status": alignment,
            "confidence": confidence,
            "net_score": total_score,
            "scores_by_tf": dict(zip(timeframes, alignment_scores)),
            "divergent_timeframes": divergent_tfs,
        },
        "recommendation": {
            "action": action,
            "entry_timeframe": ("1H or 4H pullback" if total_score > 0
                                else "Wait for alignment"),
            "rules": [
                "Weekly sets BIAS (direction only, not entries)",
                "Daily finds SETUP (swing level, confluence)",
                "4H refines entry zone",
                "1H/15m triggers entry with tight stop",
                "Never trade against Weekly + Daily combined direction",
            ],
        },
    })


def volume_confirmation(symbol: str, exchange: str, timeframe: str = "15m") -> dict:
    """Volume confirmation analysis for one symbol."""
    return _volume_confirmation_inner(symbol, exchange, timeframe,
                                      allow_fallback=True)


def _volume_confirmation_inner(symbol: str, exchange: str, timeframe: str,
                               allow_fallback: bool) -> dict:
    full_symbol = _normalize_symbol(symbol, exchange)
    screener = _resolve_screener_for_symbol(full_symbol, exchange)

    try:
        analysis = _fetch_analysis(screener, timeframe, [full_symbol],
                                   "volume_confirmation")
    except ProviderError as e:
        raise ProviderError(str(e)) from e

    if not analysis or full_symbol not in analysis:
        if allow_fallback:
            alt = _fallback_preference(_fallback_venues(symbol, exchange))
            if alt:
                result = _volume_confirmation_inner(symbol, alt, timeframe,
                                                    allow_fallback=False)
                if "error" not in result:
                    result["requested_exchange"] = exchange
                    result["resolved_exchange"] = alt
                    result["resolution_note"] = (
                        f"{symbol} has no usable data on {exchange}; analysis was run "
                        f"on {alt}, which lists it. Pass exchange='{alt}' to silence "
                        "this note.")
                    return result
        raise NotFoundError(f"No data found for {symbol} on {exchange}.")

    data = analysis[full_symbol]
    if not data or not hasattr(data, "indicators"):
        raise ProviderError(f"No indicator data for {full_symbol}")

    ind = data.indicators
    volume = ind.get("volume", 0)
    close = ind.get("close", 0)
    open_price = ind.get("open", 0)
    high = ind.get("high", 0)
    low = ind.get("low", 0)

    price_change = ((close - open_price) / open_price) * 100 if open_price > 0 else 0
    candle_range = ((high - low) / low) * 100 if low > 0 else 0

    sma20_volume = ind.get("volume.SMA20", 0)
    volume_ratio = volume / sma20_volume if sma20_volume > 0 else 1

    rsi = ind.get("RSI", 50)
    bb_upper = ind.get("BB.upper", 0)
    bb_lower = ind.get("BB.lower", 0)

    signals: list[str] = []
    if volume_ratio >= 2.0 and abs(price_change) >= 3.0:
        signals.append(f"STRONG BREAKOUT: {volume_ratio:.1f}x volume + "
                       f"{price_change:.1f}% price")
    if volume_ratio >= 1.5 and abs(price_change) < 1.0:
        signals.append(f"VOLUME DIVERGENCE: High volume ({volume_ratio:.1f}x) but "
                       "low price movement")
    if abs(price_change) >= 2.0 and volume_ratio < 0.8:
        signals.append(f"WEAK SIGNAL: Price moved but volume is low "
                       f"({volume_ratio:.1f}x)")
    if close > bb_upper and volume_ratio >= 1.5:
        signals.append("BB BREAKOUT CONFIRMED: Upper band breakout + volume "
                       "confirmation")
    elif close < bb_lower and volume_ratio >= 1.5:
        signals.append("BB SELL CONFIRMED: Lower band breakout + volume confirmation")
    if rsi > 70 and volume_ratio >= 2.0:
        signals.append(f"OVERBOUGHT + VOLUME: RSI {rsi:.1f} + {volume_ratio:.1f}x "
                       "volume")
    elif rsi < 30 and volume_ratio >= 2.0:
        signals.append(f"OVERSOLD + VOLUME: RSI {rsi:.1f} + {volume_ratio:.1f}x "
                       "volume")

    if volume_ratio >= 3.0:
        volume_strength = "VERY STRONG"
    elif volume_ratio >= 2.0:
        volume_strength = "STRONG"
    elif volume_ratio >= 1.5:
        volume_strength = "MEDIUM"
    elif volume_ratio >= 1.0:
        volume_strength = "NORMAL"
    else:
        volume_strength = "WEAK"

    return sanitize({
        "symbol": full_symbol,
        "price_data": {
            "close": close,
            "change_percent": round(price_change, 2),
            "candle_range_percent": round(candle_range, 2),
        },
        "volume_analysis": {
            "current_volume": volume,
            "volume_ratio": round(volume_ratio, 2),
            "volume_strength": volume_strength,
            "average_volume": sma20_volume,
        },
        "technical_indicators": {
            "RSI": round(rsi, 1),
            "BB_position": ("ABOVE" if close > bb_upper
                            else "BELOW" if close < bb_lower else "WITHIN"),
            "BB_upper": bb_upper,
            "BB_lower": bb_lower,
        },
        "signals": signals,
        "overall_assessment": {
            "bullish_signals": len([s for s in signals
                                    if any(e in s for e in ("BREAKOUT", "BB BREAKOUT",
                                                            "OVERSOLD"))]),
            "bearish_signals": len([s for s in signals
                                    if any(e in s for e in ("BB SELL", "WEAK SIGNAL",
                                                            "OVERBOUGHT"))]),
            "warning_signals": len([s for s in signals if "DIVERGENCE" in s]),
        },
    })


# ── egx actions ─────────────────────────────────────────────────────────────

def egx_overview(timeframe: str = "1D", limit: int = 10) -> dict:
    """EGX market overview: top gainers / losers / most active + market stats."""
    from ._tv_math import compute_metrics

    _symbols_for("egx")  # vendored-list existence check (empty list raises)
    all_stocks: list[dict] = []
    for _batch, analysis in _scan_batches("egx_overview", "egx", timeframe, 200,
                                          10**9):
        for sym, data in analysis.items():
            if data is None:
                continue
            try:
                ind = data.indicators
                metrics = compute_metrics(ind)
                if not metrics:
                    continue
                all_stocks.append({
                    "symbol": sym,
                    "price": metrics.get("price", 0),
                    "changePercent": metrics.get("change", 0),
                    "volume": ind.get("volume", 0),
                    "rsi": round(ind.get("RSI", 0) or 0, 2),
                    "bbw": metrics.get("bbw", 0),
                    "rating": metrics.get("rating", 0),
                    "signal": metrics.get("signal", "N/A"),
                })
            except Exception:  # noqa: BLE001, S112 - one bad row must not sink the scan
                continue

    if not all_stocks:
        raise ProviderError("No data returned for EGX stocks")

    by_change = sorted(all_stocks, key=lambda x: x["changePercent"], reverse=True)
    by_volume = sorted(all_stocks, key=lambda x: x["volume"] or 0, reverse=True)

    return sanitize({
        "exchange": "EGX",
        "timeframe": timeframe,
        "total_analyzed": len(all_stocks),
        "top_gainers": by_change[:limit],
        "top_losers": by_change[-limit:][::-1],
        "most_active": by_volume[:limit],
        "market_stats": {
            "advancing": len([s for s in all_stocks if s["changePercent"] > 0]),
            "declining": len([s for s in all_stocks if s["changePercent"] < 0]),
            "unchanged": len([s for s in all_stocks if s["changePercent"] == 0]),
            "avg_change": (
                round(sum(s["changePercent"] for s in all_stocks) / len(all_stocks), 2)
                if all_stocks else 0
            ),
        },
    })


def egx_sector_scan(sector: str = "", timeframe: str = "1D", limit: int = 20) -> dict:
    """Scan EGX stocks by sector (live via Query().set_markets("egypt") and
    tradingview_ta — no hardcoded result tables), or list available sectors."""
    from ..data.egx_sectors import get_all_sectors, get_sector, get_symbols_by_sector
    from ._tv_math import compute_metrics

    if not sector:
        return {
            "available_sectors": get_all_sectors(),
            "usage": "Pass a sector name to scan. Example: sector='banks'",
        }

    sector_key = sector.strip().lower().replace(" ", "_")
    symbols = get_symbols_by_sector(sector_key)

    if not symbols:
        return {
            "error": f"Unknown sector: {sector}",
            "available_sectors": get_all_sectors(),
        }

    screener = _screener_for("egx")
    analysis = _fetch_analysis(screener, timeframe, symbols, "egx_sector_scan")

    results: list[dict] = []
    for sym, data in analysis.items():
        if data is None:
            continue
        try:
            ind = data.indicators
            metrics = compute_metrics(ind)
            if not metrics:
                continue
            results.append({
                "symbol": sym,
                "sector": get_sector(sym),
                "price": metrics.get("price", 0),
                "changePercent": metrics.get("change", 0),
                "volume": ind.get("volume", 0),
                "rsi": round(ind.get("RSI", 0) or 0, 2),
                "bbw": metrics.get("bbw", 0),
                "rating": metrics.get("rating", 0),
                "signal": metrics.get("signal", "N/A"),
                "bb_upper": round(ind.get("BB.upper", 0) or 0, 4),
                "bb_lower": round(ind.get("BB.lower", 0) or 0, 4),
                "sma20": round(ind.get("SMA20", 0) or 0, 4),
                "ema50": round(ind.get("EMA50", 0) or 0, 4),
            })
        except Exception:  # noqa: BLE001, S112 - one bad row must not sink the scan
            continue

    results.sort(key=lambda x: x["changePercent"], reverse=True)
    sector_changes = [r["changePercent"] for r in results
                      if r["changePercent"] is not None]
    avg_change = round(sum(sector_changes) / len(sector_changes), 2) \
        if sector_changes else 0

    return sanitize({
        "exchange": "EGX",
        "sector": sector_key,
        "timeframe": timeframe,
        "total_stocks": len(results),
        "sector_avg_change": avg_change,
        "sector_sentiment": ("Bullish" if avg_change > 0.5
                             else "Bearish" if avg_change < -0.5 else "Neutral"),
        "data": results[:limit],
    })


def egx_index(index: str = "EGX30", timeframe: str = "1D", limit: int = 30) -> dict:
    """EGX index constituent performance with full indicators."""
    from ..data.egx_indices import EGX_INDICES, is_egx30_stock
    from ..data.egx_sectors import get_sector
    from ._tv_math import compute_metrics, extract_extended_indicators

    index_key = index.strip().upper()
    if index_key not in EGX_INDICES:
        raise ProviderError(f"Unknown index: {index}; available: "
                            f"{sorted(EGX_INDICES)}")

    index_info = EGX_INDICES[index_key]
    symbols = index_info["get_symbols"]()
    screener = _screener_for("egx")

    all_stocks: list[dict] = []
    for i in range(0, len(symbols), 200):
        batch = symbols[i:i + 200]
        try:
            analysis = _fetch_analysis(screener, timeframe, batch, "egx_index")
        except ProviderError:
            continue

        for sym, data in analysis.items():
            if data is None:
                continue
            try:
                ind = data.indicators
                metrics = compute_metrics(ind)
                if not metrics:
                    continue
                extended = extract_extended_indicators(ind)
                all_stocks.append({
                    "symbol": sym,
                    "sector": get_sector(sym),
                    "is_egx30": is_egx30_stock(sym),
                    "price": metrics.get("price", 0),
                    "changePercent": metrics.get("change", 0),
                    "volume": ind.get("volume", 0),
                    "rsi": extended["rsi"]["value"],
                    "rsi_signal": extended["rsi"]["signal"],
                    "sma20": extended["sma"]["sma20"],
                    "sma50": extended["sma"]["sma50"],
                    "sma200": extended["sma"]["sma200"],
                    "atr": extended["atr"]["value"],
                    "atr_volatility": extended["atr"]["volatility"],
                    "macd_crossover": extended["macd"]["crossover"],
                    "volume_signal": extended["volume"]["signal"],
                    "bbw": metrics.get("bbw", 0),
                    "bb_rating": metrics.get("rating", 0),
                    "bb_signal": metrics.get("signal", "N/A"),
                })
            except Exception:  # noqa: BLE001, S112 - one bad row must not sink the scan
                continue

    if not all_stocks:
        raise ProviderError(f"No data returned for {index_key} constituents")

    changes = [s["changePercent"] for s in all_stocks]
    avg_change = sum(changes) / len(changes)
    advancing = len([c for c in changes if c > 0])
    declining = len([c for c in changes if c < 0])
    unchanged = len([c for c in changes if c == 0])

    sector_perf: dict = {}
    for s in all_stocks:
        sec = s["sector"]
        if sec not in sector_perf:
            sector_perf[sec] = {"stocks": 0, "total_change": 0.0}
        sector_perf[sec]["stocks"] += 1
        sector_perf[sec]["total_change"] += s["changePercent"]

    sector_summary = [
        {
            "sector": sec,
            "stocks_count": data["stocks"],
            "avg_change": round(data["total_change"] / data["stocks"], 2),
        }
        for sec, data in sorted(
            sector_perf.items(),
            key=lambda x: x[1]["total_change"] / x[1]["stocks"],
            reverse=True,
        )
    ]

    by_change = sorted(all_stocks, key=lambda x: x["changePercent"], reverse=True)

    return sanitize({
        "index": index_key,
        "index_name": index_info["name"],
        "description": index_info["description"],
        "timeframe": timeframe,
        "index_stats": {
            "total_constituents": index_info["constituents_count"],
            "analyzed": len(all_stocks),
            "avg_change": round(avg_change, 2),
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "breadth": round(advancing / len(all_stocks) * 100, 1)
            if all_stocks else 0,
            "sentiment": ("Bullish" if avg_change > 0.5
                          else "Bearish" if avg_change < -0.5 else "Neutral"),
        },
        "sector_breakdown": sector_summary,
        "top_gainers": by_change[:5],
        "top_losers": by_change[-5:][::-1],
        "all_stocks": by_change[:limit],
    })


def egx_screener(timeframe: str = "1D", min_score: int = 55, index_filter: str = "",
                 limit: int = 20) -> dict:
    """EGX stock ranking engine: qualified trades, watchlist, grade
    distribution (live scoring — no hardcoded result tables)."""
    from ..data.egx_indices import EGX_INDICES
    from ..data.egx_sectors import get_currency, get_sector
    from ._tv_math import (
        compute_metrics,
        compute_stock_score,
        compute_trade_quality,
        compute_trade_setup,
    )

    if index_filter:
        idx_key = index_filter.strip().upper()
        if idx_key in EGX_INDICES:
            symbols = EGX_INDICES[idx_key]["get_symbols"]()
            source_label = idx_key
        else:
            raise ProviderError(f"Unknown index: {index_filter}; available: "
                                f"{sorted(EGX_INDICES)}")
    else:
        symbols = _symbols_for("egx")
        source_label = "All EGX"

    screener = _screener_for("egx")
    raw_results: list[tuple] = []

    for i in range(0, len(symbols), 200):
        batch = symbols[i:i + 200]
        try:
            analysis = _fetch_analysis(screener, timeframe, batch, "egx_screener")
        except ProviderError:
            continue

        for sym, data in analysis.items():
            if data is None:
                continue
            try:
                ind = data.indicators
                o = ind.get("open")
                c = ind.get("close")
                if not o or not c or o <= 0:
                    continue
                raw_results.append((sym, ind, ((c - o) / o) * 100))
            except Exception:  # noqa: BLE001, S112 - one bad row must not sink the scan
                continue

    if not raw_results:
        raise ProviderError("No data returned for EGX stocks")

    changes = sorted([r[2] for r in raw_results])
    n = len(changes)

    def _pct_rank(val: float) -> float:
        return sum(1 for c in changes if c < val) / n if n > 0 else 0.5

    scored_stocks: list[dict] = []
    for sym, ind, change in raw_results:
        try:
            pct_rank = _pct_rank(change)
            ccy = get_currency(sym)
            result = compute_stock_score(ind, change_pct_rank=pct_rank, currency=ccy)
            if not result or result["score"] < min_score:
                continue
            metrics = compute_metrics(ind)
            if not metrics:
                continue

            vol_sma = ind.get("volume.SMA20")
            liquidity_status = "Pass"
            if vol_sma and vol_sma < 10000:
                liquidity_status = "Fail - Very Low"
                if min_score >= 55:
                    continue

            stock_entry: dict = {
                "symbol": sym,
                "sector": get_sector(sym),
                "price": metrics["price"],
                "stock_score": result["score"],
                "grade": result["grade"],
                "trend_state": result["trend_state"],
                "change_pct": result["change_pct"],
                "score_breakdown": result["breakdown"],
                "signals": result["signals"],
                "penalties": result["penalties"],
                "liquidity_status": liquidity_status,
            }

            if result["score"] >= 70:
                setup = compute_trade_setup(ind)
                if setup:
                    quality = compute_trade_quality(ind, result["score"], setup)
                    stock_entry["trade_setup"] = {
                        "setup_types": setup["setup_types"],
                        "entry_points": setup["entry_points"],
                        "stop_loss": setup["stop_loss"],
                        "stop_distance_pct": setup["stop_distance_pct"],
                        "targets": setup["targets"],
                        "risk_reward": setup["risk_reward"],
                        "supports": setup["supports"],
                        "resistances": setup["resistances"],
                    }
                    stock_entry["trade_quality_score"] = quality["trade_quality_score"]
                    stock_entry["trade_quality"] = quality["quality"]
                    stock_entry["trade_notes"] = quality["notes"]
                    stock_entry["trade_quality_breakdown"] = quality["breakdown"]

            scored_stocks.append(stock_entry)
        except Exception:  # noqa: BLE001, S112 - one bad row must not sink the scan
            continue

    scored_stocks.sort(key=lambda x: (x["stock_score"],
                                      x.get("trade_quality_score", 0)), reverse=True)

    grades: dict = {}
    for s in scored_stocks:
        g = s["grade"]
        grades[g] = grades.get(g, 0) + 1

    qualified = [s for s in scored_stocks
                 if s["stock_score"] >= 70 and s.get("trade_quality_score", 0) >= 65]
    watchlist = [s for s in scored_stocks
                 if s["stock_score"] < 70 or s.get("trade_quality_score", 0) < 65]

    return sanitize({
        "source": source_label,
        "timeframe": timeframe,
        "min_score": min_score,
        "total_scanned": len(raw_results),
        "total_passed": len(scored_stocks),
        "grade_distribution": grades,
        "qualified_trades": qualified[:limit],
        "qualified_count": len(qualified),
        "watchlist": watchlist[:max(5, limit - len(qualified))],
        "execution_rules": {
            "trade_threshold": "Stock Score >= 70 AND Trade Quality >= 65",
            "risk_reward_min": "R:R to Target 2 >= 2.0 preferred",
            "disclaimer": "For educational/informational purposes only. "
                          "Not financial advice.",
        },
    })


def egx_trade_plan(symbol: str, timeframe: str = "1D") -> dict:
    """Full trade plan for one EGX stock (score, setup, targets, quality)."""
    from ..data.egx_sectors import get_currency, get_sector
    from ._tv_math import (
        compute_metrics,
        compute_stock_score,
        compute_trade_quality,
        compute_trade_setup,
        extract_extended_indicators,
    )

    full_symbol = symbol.upper() if ":" in symbol else f"EGX:{symbol.upper()}"
    screener = _screener_for("egx")

    analysis = _fetch_analysis(screener, timeframe, [full_symbol], "egx_trade_plan")

    if full_symbol not in analysis or analysis[full_symbol] is None:
        raise NotFoundError(f"No data found for {full_symbol}")

    ind = analysis[full_symbol].indicators
    metrics = compute_metrics(ind)
    if not metrics:
        raise ProviderError(f"Could not compute metrics for {full_symbol}")

    ccy = get_currency(full_symbol)
    score_result = compute_stock_score(ind, currency=ccy)
    if not score_result:
        raise ProviderError(f"Could not compute stock score for {full_symbol}")

    setup = compute_trade_setup(ind)
    quality = compute_trade_quality(ind, score_result["score"], setup) if setup else None
    extended = extract_extended_indicators(ind)

    output: dict = {
        "symbol": full_symbol,
        "sector": get_sector(full_symbol),
        "currency": ccy,
        "timeframe": timeframe,
        "price": metrics["price"],
        "change_pct": score_result["change_pct"],
        "stock_score": score_result["score"],
        "grade": score_result["grade"],
        "trend_state": score_result["trend_state"],
        "score_breakdown": score_result["breakdown"],
        "signals": score_result["signals"],
        "penalties": score_result["penalties"],
        "liquidity": score_result.get("liquidity", {}),
        "rsi": extended["rsi"],
        "macd": extended["macd"],
        "adx": extended["adx"],
        "volume": extended["volume"],
        "ema": extended["ema"],
        "bollinger_bands": extended["bollinger_bands"],
        "tv_recommendation": extended["tv_recommendation"],
    }

    if setup:
        output["trade_setup"] = {
            "setup_types": setup["setup_types"],
            "entry_points": setup["entry_points"],
            "stop_loss": setup["stop_loss"],
            "stop_distance_pct": setup["stop_distance_pct"],
            "targets": setup["targets"],
            "risk_reward": setup["risk_reward"],
            "supports": setup["supports"],
            "resistances": setup["resistances"],
        }

    if quality:
        output["trade_quality_score"] = quality["trade_quality_score"]
        output["trade_quality"] = quality["quality"]
        output["trade_quality_breakdown"] = quality["breakdown"]
        output["trade_notes"] = quality["notes"]

    ss = score_result["score"]
    tq = quality["trade_quality_score"] if quality else 0
    rr2 = setup["risk_reward"]["to_target_2"] if setup else 0

    if ss >= 70 and tq >= 65 and rr2 and rr2 >= 2.0:
        recommendation = "QUALIFIED - Strong stock with actionable setup"
    elif ss >= 70 and tq >= 50:
        recommendation = "CONDITIONAL - Good stock but setup needs improvement"
    elif ss >= 55:
        recommendation = "WATCHLIST - Monitor for better entry"
    else:
        recommendation = "AVOID - Does not meet momentum/quality criteria"

    output["recommendation"] = recommendation
    output["disclaimer"] = "For educational/informational purposes only. Not financial advice."
    return sanitize(output)


def egx_fibonacci(symbol: str, lookback: str = "52W", timeframe: str = "1D") -> dict:
    """Fibonacci retracement analysis for one EGX stock.

    Swing high/low come from the live scanner (Query with period high/low
    columns), falling back to TradingView pivot points.
    """
    from ..data.egx_sectors import get_sector
    from ._tv_math import (
        analyze_fibonacci_position,
        compute_fibonacci_levels,
        detect_trend_for_fibonacci,
    )

    valid_lookbacks = {"1M", "3M", "6M", "52W", "ALL"}
    if lookback not in valid_lookbacks:
        raise ProviderError(f"Invalid lookback: {lookback}; valid: "
                            f"{sorted(valid_lookbacks)}")

    full_symbol = symbol.upper() if ":" in symbol else f"EGX:{symbol.upper()}"
    screener = _screener_for("egx")

    lookback_columns = {
        "1M": ("High.1M", "Low.1M"),
        "3M": ("High.3M", "Low.3M"),
        "6M": ("High.6M", "Low.6M"),
        "52W": ("price_52_week_high", "price_52_week_low"),
        "ALL": ("High.All", "Low.All"),
    }

    swing_high: float | None = None
    swing_low: float | None = None
    swing_source: str | None = None

    try:
        from tradingview_screener import Query
        high_col, low_col = lookback_columns[lookback]
        q = (Query().set_markets("egypt").select("close", high_col, low_col)
             .set_tickers([full_symbol]))
        _, df = q.get_scanner_data()
        if df is not None and not df.empty:
            row = df.iloc[0]
            h = row.get(high_col)
            ll = row.get(low_col)
            if h is not None and ll is not None and h > ll:
                swing_high = float(h)
                swing_low = float(ll)
                swing_source = f"screener ({lookback} period high/low)"
    except Exception:  # noqa: BLE001, S110 - fall back to pivot points
        pass

    analysis = _fetch_analysis(screener, timeframe, [full_symbol], "egx_fibonacci")

    if full_symbol not in analysis or analysis[full_symbol] is None:
        raise NotFoundError(f"No data found for {full_symbol}")

    ind = analysis[full_symbol].indicators
    close = ind.get("close")
    if not close:
        raise ProviderError(f"No price data for {full_symbol}")

    if swing_high is None or swing_low is None:
        fib_r3 = ind.get("Pivot.M.Fibonacci.R3")
        fib_s3 = ind.get("Pivot.M.Fibonacci.S3")
        classic_r3 = ind.get("Pivot.M.Classic.R3")
        classic_s3 = ind.get("Pivot.M.Classic.S3")
        h_candidate = fib_r3 or classic_r3
        l_candidate = fib_s3 or classic_s3
        if h_candidate and l_candidate and h_candidate > l_candidate:
            swing_high = float(h_candidate)
            swing_low = float(l_candidate)
            swing_source = "pivot points (R3/S3 fallback)"
        else:
            raise ProviderError("Could not determine swing high/low for "
                                "Fibonacci calculation")

    swing_range_pct = ((swing_high - swing_low) / swing_low) * 100
    if swing_range_pct < 2:
        raise ProviderError(
            f"Swing range too narrow ({swing_range_pct:.1f}%) for meaningful "
            "Fibonacci levels")

    ema50 = ind.get("EMA50")
    ema200 = ind.get("EMA200")
    trend, trend_reasoning = detect_trend_for_fibonacci(close, swing_high, swing_low,
                                                        ema50, ema200)
    fib_levels = compute_fibonacci_levels(swing_high, swing_low, trend)
    position = analyze_fibonacci_position(close, fib_levels)

    rsi_val = ind.get("RSI")
    atr_val = ind.get("ATR")
    vol = ind.get("volume")
    vol_sma = ind.get("volume.SMA20")
    vol_ratio = round(vol / vol_sma, 2) if vol and vol_sma and vol_sma > 0 else None
    change_pct = (
        round(((close - ind.get("open", close)) / ind.get("open", close)) * 100, 2)
        if ind.get("open") else None
    )

    interp_parts = [
        f"Price is at {position['retracement_depth_pct']}% retracement of the {trend}."
    ]
    if position.get("key_zone"):
        interp_parts.append(f"Currently in {position['key_zone']}.")
    if position.get("fib_supports"):
        nearest_s = position["fib_supports"][0]
        interp_parts.append(
            f"Key Fib support at {nearest_s['price']} ({nearest_s['ratio']}).")
    if position.get("fib_resistances"):
        nearest_r = position["fib_resistances"][0]
        interp_parts.append(
            f"Key Fib resistance at {nearest_r['price']} ({nearest_r['ratio']}).")

    return sanitize({
        "symbol": full_symbol,
        "sector": get_sector(full_symbol),
        "timeframe": timeframe,
        "lookback_period": lookback,
        "price": round(close, 2),
        "change_pct": change_pct,
        "swing_high": round(swing_high, 2),
        "swing_low": round(swing_low, 2),
        "swing_range_pct": round(swing_range_pct, 1),
        "swing_source": swing_source,
        "trend": trend,
        "trend_reasoning": trend_reasoning,
        "retracement_levels": fib_levels["retracement_levels"],
        "extension_levels": fib_levels["extension_levels"],
        "price_position": position,
        "context": {
            "rsi": round(rsi_val, 1) if rsi_val else None,
            "ema50": round(ema50, 2) if ema50 else None,
            "ema200": round(ema200, 2) if ema200 else None,
            "atr": round(atr_val, 2) if atr_val else None,
            "volume_ratio": vol_ratio,
        },
        "interpretation": " ".join(interp_parts),
        "disclaimer": "For educational/informational purposes only. Not financial advice.",
    })
