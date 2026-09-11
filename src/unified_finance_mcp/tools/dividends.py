"""get_dividend_split_history: corporate actions (dividends, splits, next dates).

Chain is ["yahoo", "fmp"]: yahoo is free/global via yfinance
(t.dividends/t.splits/t.calendar); fmp is US-only and its dividends/splits
endpoints are NOT yet in the verified free-tier matrix, so a 402 there folds
into RateLimited without breaking routing. futu never enters this chain —
its corporate-action tools live on the mount (e.g. futu capital-flow).
"""
from __future__ import annotations

from ..errors import tool_error
from ..symbols import parse_symbol
from ._routing import route_and_call

CHAIN = ["yahoo", "fmp"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_dividend_split_history(symbol: str,
                                         source: str = "auto") -> dict:
        """Dividend/split history plus next scheduled dividend/earnings dates.

        Returns {"data": {symbol, dividends, splits, next_events, source}}:
        dividends/splits are [{"kind","date","value","source"}]; next_events
        (yahoo only) holds the upcoming dividend/ex-div dates and the next
        earnings date with EPS/revenue estimates. `source` may be auto |
        yahoo | fmp. Accepts futu (HK.00700), yahoo (0700.HK, COMI.CA) or
        TradingView (EGX:COMI) symbol forms; bare tickers default to US.
        Callers check `"error" in out`.
        """
        try:
            parsed = parse_symbol(symbol)
        except ValueError as e:
            return tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                           "COMI.CA / EGX:COMI / AAPL")

        async def call(p):
            return await p.dividend_split_history(parsed)

        out = await route_and_call(market=parsed.market, chain=CHAIN,
                                   providers=providers, call=call,
                                   explicit_source=source)
        return out if "error" in out else {"data": out}
