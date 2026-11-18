"""get_economic_data: macro series behind one tool, three vocabularies.

Merged surface (2026-11-18, "prefer existing tools" ruling) — no new macro
tool was added for the K-Dense gaps; instead the same tool grew:

1. **canonical 8** (GDP/CPI/... via macro -> alphavantage), unchanged.
2. **any World Bank indicator x country** — pass a WB code (it contains a
   dot, e.g. "NY.GDP.MKTP.CD") plus `country`/`start`/`end`. Keyless, annual
   granularity. Replaces the former "World Bank passthrough" tool idea.
3. **US Treasury** — two pseudo-indicators served by providers/treasury.py:
   `TREASURY_YIELD_CURVE` (full 1 Mo..30 Yr par curve for one `period`
   YYYY-MM), `TREASURY_DEBT` (daily debt to the penny) and
   `TREASURY_AVG_INTEREST_RATE` (average coupon on the outstanding debt; the
   last two ignore `period`).
   The curve closes a real hole: before this, the only rate in the repo was
   10Y, so 2s10s/inversion questions were unanswerable.

`source` is validated per vocabulary so a pinned wrong source returns a
readable tool_error instead of an AttributeError envelope.

History: the chain used to be kimi-first (kimi.economic invoked
world_bank_open_data / imf when the describe doc matched). R3/R9 verdicts
proved both kimi macro routes were dead code paths, so the kimi face was
removed. R18 re-homed the adjudicated free official endpoints as the native
`macro` provider ahead of alphavantage, freeing AV's ~25/day free-tier quota
for the equities/technicals face.
"""
from __future__ import annotations

import re

from ..errors import tool_error
from ..providers.alphavantage import ECONOMIC_INDICATORS
from ._routing import route_and_call

CHAIN = ["macro", "alphavantage"]
TREASURY_CHAIN = ["treasury"]
# treasury pseudo-indicator -> TreasuryProvider method
TREASURY_ALIASES: dict[str, str] = {
    "TREASURY_YIELD_CURVE": "yield_curve",
    "TREASURY_DEBT": "debt_to_penny",
    "TREASURY_AVG_INTEREST_RATE": "avg_interest_rates",
}
# A World Bank code always has at least one dot ("NY.GDP.MKTP.CD",
# "SP.POP.TOTL"); the canonical 8 have none. That is what keeps the two
# vocabularies apart without a separate tool.
_WB_CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")
_COUNTRY_RE = re.compile(r"^[A-Za-z]{2,3}$")

_HINT = ("indicator 可用: " + ", ".join(sorted(ECONOMIC_INDICATORS))
         + "; Treasury: " + ", ".join(sorted(TREASURY_ALIASES))
         + "; 或任意 World Bank 指标码（含点号，如 NY.GDP.MKTP.CD，配 country/start/end）"
         + "。FRED 任意序列请用 get_fred_series")


def _bad_source(source: str, allowed: tuple[str, ...], what: str) -> dict | None:
    if source in ("auto", *allowed):
        return None
    return tool_error(f"source {source!r} 不服务{what}",
                      hint="可用 source: auto, " + ", ".join(allowed))


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_economic_data(indicator: str, source: str = "auto",
                                country: str = "WLD", start: int = 1980,
                                end: int = 2026,
                                period: str | None = None) -> dict:
        """Macroeconomic series — canonical indicators, World Bank codes, or US Treasury.

        Three vocabularies share this tool:

        1. Canonical 8 (case-insensitive): GDP | CPI | INFLATION |
           UNEMPLOYMENT | FEDERAL_FUNDS_RATE | TREASURY_YIELD_10Y |
           RETAIL_SALES | NONFARM_PAYROLL. `source` may be auto | macro |
           alphavantage.
        2. Any World Bank indicator code — it contains a dot, e.g.
           "NY.GDP.MKTP.CD" (GDP current US$), "SP.POP.TOTL" (population),
           "FP.CPI.TOTL.ZG" (inflation). `country` is ISO3 or a WB aggregate
           ("WLD", "CHN", "EAP"); `start`/`end` are years (1960-2100, default
           1980-2026). Keyless, annual rows. `source` may be auto | macro.
        3. US Treasury pseudo-indicators: `TREASURY_YIELD_CURVE` — the daily
           par curve for `period` (YYYY-MM, default current month), one row
           per day with tenor columns 1M/1.5M/2M/3M/4M/6M/1Y/2Y/3Y/5Y/7Y/10Y/
           20Y/30Y; `TREASURY_DEBT` — daily federal debt to the penny; and
           `TREASURY_AVG_INTEREST_RATE` — the average interest rate on the
           outstanding debt (newest first). `source` may be auto | treasury.

        Returns {"data": [...]} on success (plus indicator/country/period
        metadata where relevant), or the routing error dict at the top level
        — callers check `"error" in out`. Rows are exactly what the upstream
        returns; nothing is interpolated or gap-filled.
        """
        raw = (indicator or "").strip()
        key = raw.upper()

        # ── 3. Treasury pseudo-indicators ──
        method = TREASURY_ALIASES.get(key)
        if method is not None:
            bad = _bad_source(source, ("treasury",), " Treasury 指标")
            if bad:
                return bad
            async def call(p, _m=method):
                if _m == "yield_curve":
                    return await p.yield_curve(period)
                return await p.fiscal(_m)
            out = await route_and_call(market="US", chain=TREASURY_CHAIN,
                                       providers=providers, call=call,
                                       explicit_source=source)
            return out if "error" in out else {"indicator": key, **out}

        # ── 1. canonical 8 ──
        if key in ECONOMIC_INDICATORS:
            bad = _bad_source(source, ("macro", "alphavantage"), "")
            if bad:
                return bad
            rows = await route_and_call(
                market="US", chain=CHAIN, providers=providers,
                call=lambda p: p.economic(key), explicit_source=source)
            return rows if "error" in rows else {"data": rows}

        # ── 2. World Bank passthrough ──
        if _WB_CODE_RE.match(raw):
            bad = _bad_source(source, ("macro",), " World Bank 指标")
            if bad:
                return bad
            iso = (country or "WLD").strip().upper()
            if not _COUNTRY_RE.match(iso):
                return tool_error(f"country {country!r} 不合法",
                                  hint="ISO3（CHN/USA）或世界银行聚合（WLD/EAP/EMU）")
            try:
                lo, hi = int(start), int(end)
            except (TypeError, ValueError):
                return tool_error(f"start/end 必须是年份整数，收到 {start!r}/{end!r}")
            if not (1960 <= lo <= hi <= 2100):
                return tool_error(f"年份窗口不合法: {lo}..{hi}",
                                  hint="1960 <= start <= end <= 2100")
            rows = await route_and_call(
                market="US", chain=["macro"], providers=providers,
                call=lambda p: p.world_bank_series(key, iso, lo, hi),
                explicit_source=source)
            return rows if "error" in rows else {
                "indicator": key, "country": iso, "start": lo, "end": hi,
                "data": rows}

        return tool_error(f"unknown economic indicator {indicator!r}", hint=_HINT)
