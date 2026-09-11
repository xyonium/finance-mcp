"""get_earnings_history: historical earnings dates with EPS estimate/reported/surprise.

Chain is ["yahoo", "fmp"]: yahoo (t.earnings_dates frame) is free/global;
fmp (stable `earnings`) is US-only and not in the verified free-tier matrix
(402 folds into RateLimited). Complements get_events_calendar (forward-looking
earnings-calendar) and get_analyst_estimates (forward estimates).
"""
from __future__ import annotations

from ..errors import tool_error
from ..symbols import parse_symbol
from ._routing import route_and_call

CHAIN = ["yahoo", "fmp"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_earnings_history(symbol: str, limit: int = 12,
                                   source: str = "auto") -> dict:
        """Historical earnings dates: reported date, EPS estimate vs reported,
        surprise %. Up to `limit` rows (default 12). `source` may be auto |
        yahoo | fmp. Accepts futu (HK.00700), yahoo (0700.HK, COMI.CA) or
        TradingView (EGX:COMI) symbol forms; bare tickers default to US.
        Returns {"data": [...]} on success or the routing error dict.
        """
        try:
            parsed = parse_symbol(symbol)
        except ValueError as e:
            return tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                           "COMI.CA / EGX:COMI / AAPL")

        async def call(p):
            return await p.earnings_history(parsed, limit)

        out = await route_and_call(market=parsed.market, chain=CHAIN,
                                   providers=providers, call=call,
                                   explicit_source=source)
        return out if "error" in out else {"data": out}
