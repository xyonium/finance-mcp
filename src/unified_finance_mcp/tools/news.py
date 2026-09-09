"""get_news: headline news for one symbol or the global feed, auto-routed.

With a symbol the chain is fmp -> alphavantage -> marketaux -> yahoo (T11
brief). Without a symbol only marketaux has a global feed, so the chain is
["marketaux", "fmp"] and the closure raises NotFound for fmp when parsed is
None (fmp's news requires a symbol), which lets route_and_call skip it cleanly.
"""
from __future__ import annotations

from ..errors import NotFound
from ..symbols import parse_symbol
from ._routing import route_and_call

SYMBOL_CHAIN = ["fmp", "alphavantage", "marketaux", "yahoo"]
GLOBAL_CHAIN = ["marketaux", "fmp"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_news(symbol: str | None = None, limit: int = 10,
                       source: str = "auto") -> dict:
        """Latest news: symbol-specific, or global headlines when symbol=None.

        `limit` items are returned (bounded to 50). `source` may be auto |
        fmp | alphavantage | marketaux | yahoo. Accepts futu (HK.00700), yahoo
        (0700.HK, COMI.CA) or TradingView (EGX:COMI) symbol forms; bare tickers
        default to US. Returns {"data": [item, ...]} on success, or the routing
        error dict at the top level on failure — callers check `"error" in out`.
        """
        limit = max(1, min(limit, 50))
        if symbol is None:
            return await _route(parsed=None, market="GLOBAL", chain=GLOBAL_CHAIN,
                                providers=providers, source=source, limit=limit)
        try:
            parsed = parse_symbol(symbol)
        except ValueError as e:
            return {"error": str(e),
                    "hint": "symbol 写法: HK.00700 / 0700.HK / COMI.CA / EGX:COMI / AAPL"}
        return await _route(parsed=parsed, market=parsed.market, chain=SYMBOL_CHAIN,
                            providers=providers, source=source, limit=limit)


async def _route(*, parsed, market, chain, providers, source, limit) -> dict:
    async def call(p):
        if parsed is None and p.name == "fmp":
            # fmp.news requires a symbol: no global feed. NotFound makes
            # route_and_call skip fmp cleanly instead of passing it None.
            raise NotFound("fmp: no global news feed (symbol required)")
        return await p.news(parsed, limit)

    items = await route_and_call(market=market, chain=chain, providers=providers,
                                 call=call, explicit_source=source)
    return items if "error" in items else {"data": items}
