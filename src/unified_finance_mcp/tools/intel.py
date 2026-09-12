"""get_symbol_intel: per-symbol single-indicator queries behind one container.

Folds the five one-symbol/one-metric tools into a `kind`-routed container:

  kind=options    option chain at one expiration (+ `expiration` param)
  kind=short      short-interest snapshot
  kind=analyst    analyst estimates, price targets, recommendations
  kind=dividends  dividend/split history + next scheduled dates
  kind=earnings   historical earnings dates: EPS est. vs reported, surprise %

Chains are ["yahoo", "fmp"] for every kind: yahoo is free/global (yfinance);
fmp is US-only and these endpoints are NOT yet in the verified free-tier
matrix, so a 402 there folds into RateLimited without breaking routing.
futu's same-name data lives on the mounted/grouped futu tools (different
schemas) and never enters these chains. Replaces the former
get_option_chain / get_short_interest / get_analyst_estimates /
get_dividend_split_history / get_earnings_history tools (futu chains and
provider methods unchanged).
"""
from __future__ import annotations

from ..errors import tool_error
from ..symbols import parse_symbol
from ._routing import route_and_call

# kind -> (provider method name, list-shaped data?)
_KINDS: dict[str, tuple[str, bool]] = {
    "options": ("option_chain", False),
    "short": ("short_interest", False),
    "analyst": ("analyst_estimates", False),
    "dividends": ("dividend_split_history", False),
    "earnings": ("earnings_history", True),
}

_CHAIN = ["yahoo", "fmp"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_symbol_intel(symbol: str, kind: str = "options",
                               expiration: str | None = None, limit: int = 12,
                               source: str = "auto") -> dict:
        """Per-symbol indicator queries, selected by `kind`.

        kind=options   — option chain at one expiration (calls/puts, IV/OI);
                         `expiration` is ISO YYYY-MM-DD, omit for nearest.
        kind=short     — short-interest snapshot (shares short, days-to-cover,
                         % of float).
        kind=analyst   — analyst earnings/revenue estimates, price targets,
                         recommendations.
        kind=dividends — dividend/split history plus next scheduled
                         dividend/earnings dates.
        kind=earnings  — historical earnings dates: EPS estimate vs reported
                         and surprise %, up to `limit` rows (default 12).

        `source` may be auto | yahoo | fmp (fmp is US-only; its endpoints for
        these kinds are NOT in the verified free-tier matrix, so a 402 there
        folds into RateLimited without breaking routing). Accepts futu
        (HK.00700), yahoo (0700.HK, COMI.CA) or TradingView (EGX:COMI)
        symbol forms; bare tickers default to US. Returns {"data": ...} on
        success or the routing error dict at the top level — callers check
        `"error" in out`.
        """
        entry = _KINDS.get(kind) if isinstance(kind, str) else None
        if entry is None:
            return tool_error(f"unknown kind {kind!r}",
                              hint=f"kind: {sorted(_KINDS)}")
        method, _ = entry
        try:
            parsed = parse_symbol(symbol)
        except ValueError as e:
            return tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                           "COMI.CA / EGX:COMI / AAPL")

        async def call(p):
            fn = getattr(p, method)
            if method == "option_chain":
                return await fn(parsed, expiration)
            if method == "earnings_history":
                return await fn(parsed, limit)
            return await fn(parsed)

        out = await route_and_call(market=parsed.market, chain=_CHAIN,
                                   providers=providers, call=call,
                                   explicit_source=source)
        return out if "error" in out else {"data": out}
