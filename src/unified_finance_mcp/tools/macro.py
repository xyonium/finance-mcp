"""get_economic_data: macro series behind one tool, four vocabularies.

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
   last two ignore `period`), and `TREASURY_MTS_OUTLAYS` (Monthly Treasury
   Statement outlays by agency/function for one month).
   The curve closes a real hole: before this, the only rate in the repo was
   10Y, so 2s10s/inversion questions were unanswerable.
4. **BLS series** — `BLS:<seriesId>` (e.g. `BLS:JTS000000000000000JOL`) for
   any BLS series with monthly observations; keyless, on-demand detail only.
   Monthly rows only (OES and other annual products return not_found).

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
    "TREASURY_MTS_OUTLAYS": "mts_outlays",
}
# A World Bank code always has at least one dot ("NY.GDP.MKTP.CD",
# "SP.POP.TOTL"); the canonical 8 have none. That is what keeps the two
# vocabularies apart without a separate tool.
_WB_CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+$")
# BLS ids are short alphanumerics (JTS000000000000000JOL); the prefix keeps
# them distinct from the canonical names and from World Bank codes (dots).
_BLS_RE = re.compile(r"^BLS:([A-Za-z0-9]{1,40})$", re.IGNORECASE)
_COUNTRY_RE = re.compile(r"^[A-Za-z]{2,3}$")

_HINT = ("indicator 可用: " + ", ".join(sorted(ECONOMIC_INDICATORS))
         + "; Treasury: " + ", ".join(sorted(TREASURY_ALIASES))
         + "; 或任意 World Bank 指标码（含点号，如 NY.GDP.MKTP.CD，配 country/start/end）"
         + "; 或任意 BLS 月度序列 BLS:<seriesId>（如 BLS:JTS000000000000000JOL）"
         + "。FRED 任意序列请用 get_fred_series；BLS id 必须来自官方文档，不要臆造")


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
        """Macroeconomic series — canonical indicators, World Bank, US Treasury or BLS.

        Four vocabularies share this tool:

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
           outstanding debt (newest first); and `TREASURY_MTS_OUTLAYS` — the
           Monthly Treasury Statement's outlays for `period` (default newest
           month), top 50 lines by current-month gross outlays. MTS lines are
           **hierarchical** (totals/subtotals sit next to agency lines) and
           amounts are upstream USD strings — do not sum them. `truncated`
           says whether `total` exceeds the returned `count`. `source` may be
           auto | treasury.
        4. Any BLS series id with **monthly** observations, prefixed:
           `BLS:JTS000000000000000JOL` (JOLTS job openings),
           `BLS:LNS14000000` (unemployment). Case-insensitive; ids must come
           from BLS documentation — never invent them. Annual products such
           as OES return not_found. This is an on-demand detail lookup, not
           bulk retrieval: BLS v1 meters roughly 25 queries/day per client IP,
           and heavy use can exhaust the same channel the CPI/UNRATE/PAYEMS
           backup relies on. `source` may be auto | macro.

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
                if _m == "mts_outlays":
                    return await p.mts_outlays(period)
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

        # ── 4. BLS series passthrough (monthly observations only) ──
        if raw.upper().startswith("BLS:"):
            m_bls = _BLS_RE.match(raw)
            if m_bls is None:
                return tool_error(f"invalid BLS series id {raw[4:]!r}",
                                  hint="BLS:<seriesId>，id 只含字母数字、最多 40 位；"
                                       "必须来自 BLS 官方文档，不要臆造")
            bad = _bad_source(source, ("macro",), " BLS 序列")
            if bad:
                return bad
            sid = m_bls.group(1).upper()
            rows = await route_and_call(
                market="US", chain=["macro"], providers=providers,
                call=lambda p: p.bls_series(sid), explicit_source=source)
            return rows if "error" in rows else {
                "indicator": f"BLS:{sid}", "series_id": sid, "data": rows}

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
