"""search_symbols: symbol lookup, fmp -> alphavantage -> yahoo.

Symbol-free by nature: never gated on market.
"""
from __future__ import annotations

from ..errors import tool_error
from ._routing import route_and_call

CHAIN = ["fmp", "alphavantage", "yahoo"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def search_symbols(query: str, limit: int = 10,
                             source: str = "auto") -> dict:
        """Search for symbols by company name or ticker.

        `limit` results are returned (bounded to 50). `source` may be auto |
        fmp | alphavantage | yahoo. Returns {"data": [match, ...]} on success,
        or the routing error dict at the top level on failure — callers check
        `"error" in out`.
        """
        query = query.strip()
        if not query:
            return tool_error("empty search query",
                              hint="query 用公司名或代码, e.g. 'apple' 或 'AAPL'")
        limit = max(1, min(limit, 50))
        rows = await route_and_call(
            market="US", chain=CHAIN, providers=providers,
            call=lambda p: p.search(query, limit), explicit_source=source)
        return rows if "error" in rows else {"data": rows}
