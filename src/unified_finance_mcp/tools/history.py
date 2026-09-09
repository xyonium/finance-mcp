"""get_history: OHLCV bars, auto-routed by market (same chain as get_quote)."""
from __future__ import annotations

from ..errors import tool_error
from ..symbols import parse_symbol
from ._routing import route_and_call

CHAIN = ["futu", "yahoo", "fmp", "alphavantage"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_history(code: str, interval: str = "1d", start: str | None = None,
                          end: str | None = None, source: str = "auto") -> dict:
        """Get OHLCV history (K-line) for one symbol.

        `interval` is a yfinance-style interval (1d/1wk/1mo/1h/30m/15m/5m/1m);
        each source maps the subset it supports. `start`/`end` are inclusive
        YYYY-MM-DD strings; omitted means the source's default window. Accepts
        futu (HK.00700), yahoo (0700.HK, COMI.CA) or TradingView (EGX:COMI)
        symbol forms; bare tickers default to US. `source` may be auto | futu |
        yahoo | fmp | alphavantage. Returns {"data": [bar, ...]}.
        """
        try:
            parsed = parse_symbol(code)
        except ValueError as e:
            return tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                           "COMI.CA / EGX:COMI / AAPL")
        # futu's markets are a subset; non-futu markets are skipped by covers().
        bars = await route_and_call(
            market=parsed.market, chain=CHAIN, providers=providers,
            call=lambda p: p.history(parsed, interval, start, end),
            explicit_source=source)
        return bars if "error" in bars else {"data": bars}
