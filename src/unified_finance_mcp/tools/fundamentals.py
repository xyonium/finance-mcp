"""get_company_info / get_financial_report: fundamentals, auto-routed by market.

Chain order: company info prefers yahoo (keyless, global), financial reports
prefer fmp (US keyed) — both follow the T11 brief.
"""
from __future__ import annotations

from ..errors import tool_error
from ..symbols import parse_symbol
from ._routing import route_and_call

INFO_CHAIN = ["yahoo", "fmp", "alphavantage"]
REPORT_CHAIN = ["fmp", "yahoo", "alphavantage"]

_STATEMENTS = ("income", "balance", "cashflow")
_PERIODS = ("annual", "quarterly")


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_company_info(symbol: str, source: str = "auto") -> dict:
        """Company profile: name, sector, market cap, description, etc.

        `source` may be auto | yahoo | fmp | alphavantage. Accepts futu
        (HK.00700), yahoo (0700.HK, COMI.CA) or TradingView (EGX:COMI) symbol
        forms; bare tickers default to US. Returns {"data": {...}} on success,
        or the routing error dict at the top level on failure — callers check
        `"error" in out`.
        """
        try:
            parsed = parse_symbol(symbol)
        except ValueError as e:
            return tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                           "COMI.CA / EGX:COMI / AAPL")
        info = await route_and_call(
            market=parsed.market, chain=INFO_CHAIN, providers=providers,
            call=lambda p: p.company_info(parsed), explicit_source=source)
        return info if "error" in info else {"data": info}


    @mcp.tool()
    async def get_financial_report(symbol: str, statement: str = "income",
                                   period: str = "annual", source: str = "auto") -> dict:
        """Financial statements (rows per reporting period, newest first).

        `statement` is income | balance | cashflow; `period` is annual |
        quarterly. `source` may be auto | fmp | yahoo | alphavantage. Accepts
        futu (HK.00700), yahoo (0700.HK, COMI.CA) or TradingView (EGX:COMI)
        symbol forms; bare tickers default to US. Returns {"data": [row, ...]}
        on success, or the routing error dict at the top level on failure —
        callers check `"error" in out`.
        """
        if statement not in _STATEMENTS:
            return tool_error(f"invalid statement {statement!r}",
                              hint="income|balance|cashflow")
        if period not in _PERIODS:
            return tool_error(f"invalid period {period!r}", hint="annual|quarterly")
        try:
            parsed = parse_symbol(symbol)
        except ValueError as e:
            return tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                           "COMI.CA / EGX:COMI / AAPL")
        rows = await route_and_call(
            market=parsed.market, chain=REPORT_CHAIN, providers=providers,
            call=lambda p: p.financial_report(parsed, statement, period),
            explicit_source=source)
        return rows if "error" in rows else {"data": rows}
