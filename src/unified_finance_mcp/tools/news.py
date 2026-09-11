"""get_news: headline news for one symbol or the global feed, auto-routed.

With a symbol the chain is alphavantage -> yahoo -> marketaux (updated
2026-09-11: FMP free keys paywall every news endpoint with HTTP 402, so
FmpProvider.news short-circuits NotFound locally and fmp never enters the
candidate set; ordering by field richness: alphavantage has summary +
per-ticker sentiment, yahoo/marketaux have neither). Without a symbol only
marketaux has a global feed, so the chain is ["marketaux"].
"""
from __future__ import annotations

from ..symbols import parse_symbol
from ._routing import route_and_call

SYMBOL_CHAIN = ["alphavantage", "yahoo", "marketaux"]
GLOBAL_CHAIN = ["marketaux"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_news(symbol: str | None = None, limit: int = 10,
                       source: str = "auto") -> dict:
        """Latest news: symbol-specific, or global headlines when symbol=None.

        Auto-routes by field richness: alphavantage (summary + per-ticker
        sentiment) -> yahoo -> marketaux. FMP is excluded because free-tier
        keys paywall every news endpoint (HTTP 402): FmpProvider.news
        short-circuits NotFound locally, so explicit source="fmp" returns a
        clean not_found error dict while auto never wastes a request on it.
        `limit` items are returned (bounded to 50). `source` may be auto |
        fmp | alphavantage | marketaux | yahoo. Accepts futu (HK.00700), yahoo
        (0700.HK, COMI.CA) or TradingView (EGX:COMI) symbol forms; bare tickers
        default to US. Returns {"data": [item, ...]} on success, or the routing
        error dict at the top level on failure — callers check `"error" in out`.

        For Chinese 快讯/flash headlines from the Futu ecosystem (热度排序,
        view_count, no summary/sentiment), call the mounted `search_news`
        tool instead — it speaks Futu's own shape, not the unified news-item
        contract used here.
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
        return await p.news(parsed, limit)

    items = await route_and_call(market=market, chain=chain, providers=providers,
                                 call=call, explicit_source=source)
    return items if "error" in items else {"data": items}
