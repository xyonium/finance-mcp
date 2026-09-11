"""get_short_interest: short-interest snapshot for one symbol.

Chain is ["yahoo", "fmp"]: yahoo's `info` dict carries the short keys from
the defaultKeyStatistics quoteSummary module; fmp has a stable short-interest
endpoint that is NOT yet in the verified free-tier matrix, so a 402 there
folds into RateLimited without breaking routing. futu's HK short data lives
on the mounted `get_short_data` tool and never enters this chain (not the
same schema).
"""
from __future__ import annotations

from ..errors import tool_error
from ..symbols import parse_symbol
from ._routing import route_and_call

CHAIN = ["yahoo", "fmp"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_short_interest(symbol: str, source: str = "auto") -> dict:
        """Short-interest snapshot: shares short, days-to-cover, % of float.

        `source` may be auto | yahoo | fmp (fmp's short-interest endpoint is
        NOT yet in the verified free-tier matrix, so a 402 there folds into
        RateLimited without breaking routing). Accepts futu (HK.00700),
        yahoo (0700.HK, COMI.CA) or TradingView (EGX:COMI) symbol forms;
        bare tickers default to US. Returns {"data": {...}} on success, or
        the routing error dict at the top level on failure — callers check
        `"error" in out`.
        """
        try:
            parsed = parse_symbol(symbol)
        except ValueError as e:
            return tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                           "COMI.CA / EGX:COMI / AAPL")

        async def call(p):
            return await p.short_interest(parsed)

        out = await route_and_call(market=parsed.market, chain=CHAIN,
                                   providers=providers, call=call,
                                   explicit_source=source)
        return out if "error" in out else {"data": out}
