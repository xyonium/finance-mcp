"""run_screener: stock screener, tradingview first with fmp fallback (US).

filters is {"field": {"min": x, "max": y}}; fields are the FILTER_COLUMNS keys
(price, market_cap, pe_ratio, change_percent, volume, dividend_yield, rsi).
The fmp fallback (FmpProvider.screener) maps only the native company-screener
params (marketCapMoreThan/LowerThan, priceMoreThan/LowerThan,
volumeMoreThan/LowerThan, dividendMoreThan/LowerThan, limit) — other fields
are tv-only and make the fmp path raise NotFound so routing surfaces it.
"""
from __future__ import annotations

from ..errors import tool_error
from ..providers.tradingview import FILTER_COLUMNS, SORT_COLUMNS
from ._routing import route_and_call
from ._sanitize import sanitize

CHAIN = ["tradingview", "fmp"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def run_screener(market: str = "US", filters: dict | None = None,
                           sort: str = "market_cap", order: str = "desc",
                           limit: int = 25, source: str = "auto") -> dict:
        """Screen stocks by market and numeric filters.

        `filters` is {"field": {"min": x, "max": y}}; available fields:
        price, market_cap, pe_ratio, change_percent, volume, dividend_yield,
        rsi (pe_ratio/change_percent/rsi are tv-only). `sort` may be any
        filter field or "name"; `order` is asc | desc. `source` may be auto |
        tradingview | fmp (fmp is US-centric and maps only market_cap, price,
        volume, dividend_yield). Returns {"data": [row, ...]} on success, or
        the routing error dict at the top level on failure — callers check
        `"error" in out`.
        """
        filters = filters or {}
        if not isinstance(filters, dict):
            return tool_error(f"filters must be a dict, got {type(filters).__name__}",
                              hint="格式: {\"field\": {\"min\": x, \"max\": y}}")
        for field, rng in filters.items():
            if field not in FILTER_COLUMNS:
                return tool_error(f"unknown filter field {field!r}",
                                  hint="可用 FILTER 字段: "
                                       + ", ".join(sorted(FILTER_COLUMNS)))
            if not isinstance(rng, dict) or not (set(rng) <= {"min", "max"}):
                return tool_error(f"invalid range for {field!r}: {rng!r}",
                                  hint="range 用 {\"min\": x, \"max\": y}")
        if sort not in SORT_COLUMNS:
            return tool_error(f"unknown sort field {sort!r}",
                              hint="sort 可用: " + ", ".join(sorted(SORT_COLUMNS)))
        if order not in ("asc", "desc"):
            return tool_error(f"invalid order {order!r}", hint="order 用 asc|desc")
        if not isinstance(limit, int) or limit <= 0:
            return tool_error(f"invalid limit {limit!r}", hint="limit 为正整数")

        rows = await route_and_call(
            market=market, chain=CHAIN, providers=providers,
            call=lambda p: p.screener(market=market, filters=filters, sort=sort,
                                      order=order, limit=limit),
            explicit_source=source)
        if "error" in rows:
            return rows
        if not isinstance(rows, list):
            return tool_error(f"provider returned {type(rows).__name__}, expected rows",
                              hint="请检查上游源", source=source)
        return {"data": sanitize(rows)}
