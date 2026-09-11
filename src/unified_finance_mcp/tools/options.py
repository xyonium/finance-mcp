"""get_option_chain: option chain for one symbol and expiration.

Chain is ["yahoo", "fmp"]: yahoo is free/global via yfinance; fmp is US-only
and its options endpoints are NOT yet in the verified free-tier matrix, so a
402 there folds into RateLimited without breaking routing. futu's option
methods live on the mounted `futu_get_option_chain` style tools (path-based
HK codes) and never enter this chain — this tool's contract is the yahoo
_DataFrame-based shape, which futu can't fill.
"""
from __future__ import annotations

from ..errors import tool_error
from ..symbols import parse_symbol
from ._routing import route_and_call

CHAIN = ["yahoo", "fmp"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_option_chain(symbol: str, expiration: str | None = None,
                               source: str = "auto") -> dict:
        """Option chain for one symbol at one expiration date.

        `expiration` is ISO `YYYY-MM-DD`; omit to use the nearest expiry.
        `source` may be auto | yahoo | fmp (fmp is US-only and its options
        endpoint is NOT in the verified free-tier matrix, so a 402 there
        folds into RateLimited without breaking routing). Accepts futu
        (HK.00700), yahoo (0700.HK, COMI.CA) or TradingView (EGX:COMI)
        symbol forms; bare tickers default to US. Returns {"data": {...}} on
        success — keys: underlying, quote, expiration, available_expirations,
        calls, puts — or the routing error dict at the top level on failure,
        callers check `"error" in out`.
        """
        try:
            parsed = parse_symbol(symbol)
        except ValueError as e:
            return tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                           "COMI.CA / EGX:COMI / AAPL")

        async def call(p):
            return await p.option_chain(parsed, expiration)

        out = await route_and_call(market=parsed.market, chain=CHAIN,
                                   providers=providers, call=call,
                                   explicit_source=source)
        return out if "error" in out else {"data": out}
