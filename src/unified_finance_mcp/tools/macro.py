"""get_economic_data: macro series, native macro-first (R18), AV fallback.

`indicator` is case-insensitive and validated against the canonical
alphavantage.ECONOMIC_INDICATORS keys (GDP, CPI, INFLATION, UNEMPLOYMENT,
FEDERAL_FUNDS_RATE, TREASURY_YIELD_10Y, RETAIL_SALES, NONFARM_PAYROLL).
Symbol-free by nature: never gated on market (T13 brief).

History: the chain used to be kimi-first (kimi.economic invoked
world_bank_open_data / imf when the describe doc matched). R3/R9 verdicts
proved both kimi macro routes were dead code paths (the api names the
candidates probed did not exist in the live describe doc), so the kimi face
was removed and alphavantage became the sole provider. R18 re-homes the
adjudicated free official endpoints as the native `macro` provider
(world_bank keyless, fred with an optional free FRED_API_KEY, imf as
supplement) ahead of alphavantage, freeing AV's ~25/day free-tier quota for
the equities/technicals face. SEC EDGAR / ECB / OECD / Eurostat are verified
keyless but tombstoned in providers/macro.py (SDMX/XBRL parsing cost) for a
follow-up task.
"""
from __future__ import annotations

from ..errors import tool_error
from ..providers.alphavantage import ECONOMIC_INDICATORS
from ._routing import route_and_call

CHAIN = ["macro", "alphavantage"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_economic_data(indicator: str, source: str = "auto") -> dict:
        """Macroeconomic series (GDP, inflation, unemployment, rates...).

        `indicator` is one of GDP | CPI | INFLATION | UNEMPLOYMENT |
        FEDERAL_FUNDS_RATE | TREASURY_YIELD_10Y | RETAIL_SALES |
        NONFARM_PAYROLL (case-insensitive). `source` may be auto | macro |
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
