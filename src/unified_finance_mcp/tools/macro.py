"""get_economic_data: macro series from Alpha Vantage (v1 chain: av only).

`indicator` is case-insensitive and validated against the canonical
alphavantage.ECONOMIC_INDICATORS keys (GDP, CPI, INFLATION, UNEMPLOYMENT,
FEDERAL_FUNDS_RATE, TREASURY_YIELD_10Y, RETAIL_SALES, NONFARM_PAYROLL).
Symbol-free by nature: never gated on market (T13 brief; a kimi macro chain
arrives in T18).
"""
from __future__ import annotations

from ..errors import tool_error
from ..providers.alphavantage import ECONOMIC_INDICATORS
from ._routing import route_and_call

CHAIN = ["alphavantage"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_economic_data(indicator: str, source: str = "auto") -> dict:
        """Macroeconomic series (GDP, inflation, unemployment, rates...).

        `indicator` is one of GDP | CPI | INFLATION | UNEMPLOYMENT |
        FEDERAL_FUNDS_RATE | TREASURY_YIELD_10Y | RETAIL_SALES |
        NONFARM_PAYROLL (case-insensitive). `source` may be auto |
        alphavantage. Returns {"data": [point, ...]} on success, or the
        routing error dict at the top level on failure — callers check
        `"error" in out`.
        """
        key = indicator.strip().upper()
        if key not in ECONOMIC_INDICATORS:
            return tool_error(f"unknown economic indicator {indicator!r}",
                              hint="indicator 可用: "
                                   + ", ".join(sorted(ECONOMIC_INDICATORS)))
        rows = await route_and_call(
            market="US", chain=CHAIN, providers=providers,
            call=lambda p: p.economic(key), explicit_source=source)
        return rows if "error" in rows else {"data": rows}
