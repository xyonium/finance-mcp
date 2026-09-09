"""TradingView TA ratings + screener (sync libs -> anyio.to_thread)."""
from __future__ import annotations

import anyio
from tradingview_screener import Column, Query
from tradingview_ta import Interval, TA_Handler

from ..errors import NotFound, ProviderError
from ..symbols import ParsedSymbol
from .base import Provider

_INTERVAL = {"1m": Interval.INTERVAL_1_MINUTE, "5m": Interval.INTERVAL_5_MINUTES,
             "15m": Interval.INTERVAL_15_MINUTES, "1h": Interval.INTERVAL_1_HOUR,
             "4h": Interval.INTERVAL_4_HOURS, "1d": Interval.INTERVAL_1_DAY,
             "1wk": Interval.INTERVAL_1_WEEK, "1mo": Interval.INTERVAL_1_MONTH}

# our market code -> tradingview-screener country slug
MARKET_TO_TV_SCREENER = {
    "US": "america", "HK": "hongkong", "CN": "china", "EG": "egypt",
    "JP": "japan", "UK": "uk", "CA": "canada", "AU": "australia",
    "DE": "germany", "FR": "france", "KR": "korea", "TW": "taiwan",
    "IN": "india", "SG": "singapore", "MY": "malaysia", "TR": "turkey",
}

# canonical filter field -> (screener column, fmp fallback handled elsewhere)
FILTER_COLUMNS = {"price": "close", "market_cap": "market_cap_basic",
                  "pe_ratio": "price_earnings_ttm", "change_percent": "change",
                  "volume": "volume", "dividend_yield": "dividend_yield_current",
                  "rsi": "RSI"}
SORT_COLUMNS = {**FILTER_COLUMNS, "name": "name"}

# tradingview exchange -> tradingview_ta screener slug. Slugs mirror the scanner
# country names; "egypt" (not "cfd") serves EGX, "america" (not "nasdaq") serves
# NASDAQ/NYSE/AMEX. Verified live against scanner.tradingview.com (see Task 5 report).
EXCHANGE_TO_TV_SCREENER = {
    "NASDAQ": "america", "NYSE": "america", "AMEX": "america", "HKEX": "hongkong",
    "SSE": "china", "SZSE": "china", "EGX": "egypt", "TSE": "japan", "LSE": "uk",
    "TSX": "canada", "ASX": "australia", "XETR": "germany", "EURONEXT": "france",
    "KRX": "korea", "TWSE": "taiwan", "TPEX": "taiwan", "NSE": "india",
    "SGX": "singapore", "MYX": "malaysia", "BIST": "turkey",
}


def _get_analysis(exchange: str, symbol: str, interval: str):
    h = TA_Handler(symbol=symbol, exchange=exchange,
                   screener=EXCHANGE_TO_TV_SCREENER.get(exchange, exchange.lower()),
                   interval=_INTERVAL.get(interval, Interval.INTERVAL_1_DAY))
    return h.get_analysis()


class TradingViewProvider(Provider):
    name = "tradingview"
    markets = None  # global; screener gated by MARKET_TO_TV_SCREENER

    def covers(self, market: str) -> bool:
        return True  # TA works for any tv() form; screener checks slug itself

    async def technicals(self, parsed: ParsedSymbol, interval: str = "1d") -> dict:
        exchange, symbol = parsed.tv()
        if exchange == "HKEX":
            # Task 3 gap: tv() keeps futu's 5-digit HK local (00700); TradingView
            # expects the unpadded code (700). Normalize here, not in symbols.py.
            symbol = symbol.lstrip("0") or symbol
        try:
            a = await anyio.to_thread.run_sync(_get_analysis, exchange, symbol, interval)
        except Exception as e:
            raise ProviderError(f"tradingview TA: {e}") from e
        return {"symbol": symbol, "exchange": exchange, "interval": interval,
                "summary": a.summary, "oscillators": a.oscillators,
                "moving_averages": a.moving_averages,
                "indicators": {k: v for k, v in a.indicators.items() if v is not None},
                "source": self.name}

    async def screener(self, market="US", filters=None, sort="market_cap",
                       order="desc", limit=25) -> list[dict]:
        slug = MARKET_TO_TV_SCREENER.get(market)
        if slug is None:
            raise NotFound(f"tradingview screener has no market slug for {market!r}")
        col = SORT_COLUMNS.get(sort, "market_cap_basic")
        # Dedupe: sort="name" would otherwise select "name" twice and pandas
        # collapses duplicate frame columns with a UserWarning.
        cols = list(dict.fromkeys(["name", "description", col, "close", "change", "volume"]))

        def _query():
            q = Query().set_markets(slug).select(*cols).order_by(
                col, ascending=(order == "asc")).limit(limit)
            for field, rng in (filters or {}).items():
                screener_col = FILTER_COLUMNS.get(field)
                if screener_col is None:
                    continue
                c = Column(screener_col)
                if "min" in rng:
                    q = q.where(c >= rng["min"])
                if "max" in rng:
                    q = q.where(c <= rng["max"])
            return q.get_scanner_data()

        try:
            _, df = await anyio.to_thread.run_sync(_query)
        except Exception as e:
            raise ProviderError(f"tradingview screener: {e}") from e
        return df.to_dict("records")
