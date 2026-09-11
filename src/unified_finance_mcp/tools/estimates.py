"""get_analyst_estimates: analyst estimates + price targets for one symbol.

Chain is ["yahoo", "fmp"]: yahoo's `earningsTrend` quoteSummary module
carries the full block; fmp's /stable/analyst-estimates is NOT yet in the
verified free-tier matrix, so a 402 there folds into RateLimited without
breaking routing. futu's CN/HK analyst-consensus tool lives on the mounted
`get_analyst_consensus` and never enters this chain (different schema).
"""
from __future__ import annotations

from ..errors import tool_error
from ..symbols import parse_symbol
from ._routing import route_and_call

CHAIN = ["yahoo", "fmp"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_analyst_estimates(symbol: str, source: str = "auto") -> dict:
        """Analyst earnings/revenue estimates, price targets, recommendations.

        `source` may be auto | yahoo | fmp (fmp is US-only and its analyst
        endpoints are NOT in the verified free-tier matrix, so a 402 there
        folds into RateLimited without breaking routing). Accepts futu
        (HK.00700), yahoo (0700.HK, COMI.CA) or TradingView (EGX:COMI)
        symbol forms; bare tickers default to US. Returns {"data": {...}} on
        success — yahoo keys: price_targets, earnings_estimate,
        revenue_estimate, growth_estimates, eps_trend, recommendations — or
        the routing error dict at the top level on failure, callers check
        `"error" in out`.
        """
        try:
            parsed = parse_symbol(symbol)
        except ValueError as e:
            return tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                           "COMI.CA / EGX:COMI / AAPL")

        async def call(p):
            return await p.analyst_estimates(parsed)

        out = await route_and_call(market=parsed.market, chain=CHAIN,
                                   providers=providers, call=call,
                                   explicit_source=source)
        return out if "error" in out else {"data": out}
