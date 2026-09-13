"""Native macro provider (R18): keyless World Bank + optional-key FRED, IMF
DataMapper as supplement. One class, `name="macro"`, so tools/macro.py CHAIN
grows a single entry and route_and_call keeps its shape.

Provenance: the 6 macro APIs the kimi datasource once wrapped were adjudicated
free-of-key official endpoints (docs/research/kimi-sources/*.verdict.md) and
removed from kimi. This provider re-homes the useful ones as direct REST calls:

- **world_bank** (keyless): GET {base}/country/WLD/indicator/{code}
  ?format=json&per_page=200&date=1980:2026 — JSON `[meta, rows]`, each row
  carries `date`/`value`/`countryiso3code`. Covers GDP, CPI/INFLATION (growth
  form), UNEMPLOYMENT for the World aggregate.
- **fred** (free 5-minute registration key, 120 req/min): GET
  {base}/series/observations?series_id={id}&api_key={key}&file_type=json —
  covers all 8 canonical indicators. Skipped silently without FRED_API_KEY.
  ToS: this product uses the FRED® API but is not endorsed or certified by
  the Federal Reserve Bank of St. Louis.
- **imf** DataMapper (keyless, JSON): GET {base}/{indicator}/{area} — annual
  WEO series. Used as a supplement for GDP growth only; the canonical CPI/
  rate indicators have no DataMapper equivalent with matching semantics.

Per-indicator fallback order lives in MACRO_INDICATORS: fred first when a key
is configured, then world_bank, then imf. An indicator no sub-source can serve
raises NotFound so route_and_call walks on to alphavantage; an indicator no
sub-source knows at all raises ProviderError (never falls through, the chain
cannot know it either).

Tombstones (verified keyless in the R17 verdicts but NOT wired here —
SDMX/XBRL parsing cost is out of scope for this task, follow-up work):
- ecb (data-api.ecb.europa.eu, SDMX 2.1): EXR/MIR/FM/ICP flows.
- oecd (sdmx.oecd.org, SDMX 3.0): EO/QNA flows.
- eurostat (dissemination API, JSON-stat 2.0): nama_10_gdp et al.
- sec_edgar (data.sec.gov XBRL): filing-level companyfacts, nothing to do
  with national macro series — belongs in a future fundamentals provider.

Anti-hallucination discipline (inherited from alphavantage.py): rows are
exactly what the upstream API returns. No interpolation, no gap-filling, no
re-basing; `value: None` observations are passed through as-is and dates keep
the upstream spelling (WB/FRED yearly "2025", monthly "2025-01").
"""
from __future__ import annotations

from ..config import Settings
from ..errors import NotFound, ProviderError, RateLimited, UpstreamError, scrub
from ..http import PoliteClient
from .base import Provider

# canonical indicator -> (source, upstream code) candidates, in fallback
# order. fred comes first because with a key it covers all 8 indicators
# monthly/quarterly and at 120 req/min; world_bank is the keyless floor.
# imf DataMapper only carries GDP growth (NGDP_RPCH) with matching semantics.
MACRO_INDICATORS: dict[str, tuple[tuple[str, str], ...]] = {
    "GDP": (("fred", "GDP"), ("world_bank", "NY.GDP.MKTP.CD"),
            ("imf", "NGDP_RPCH")),
    "CPI": (("fred", "CPIAUCSL"), ("world_bank", "FP.CPI.TOTL.ZG")),
    "INFLATION": (("fred", "CPIAUCSL"), ("world_bank", "FP.CPI.TOTL.ZG")),
    "UNEMPLOYMENT": (("fred", "UNRATE"), ("world_bank", "SL.UEM.TOTL.ZS")),
    "FEDERAL_FUNDS_RATE": (("fred", "FEDFUNDS"),),
    "TREASURY_YIELD_10Y": (("fred", "DGS10"),),
    "RETAIL_SALES": (("fred", "RSAFS"),),
    "NONFARM_PAYROLL": (("fred", "PAYEMS"),),
}

# World Bank series have annual granularity: 1980:2026 keeps every WLD
# observation in one page at per_page=200 (WLD starts ~1960; the tool surface
# takes no date window, so wide-then-return is fine).
_WB_COUNTRY = "WLD"
_WB_DATE_RANGE = "1980:2026"
_WB_PER_PAGE = 200

_RATE_LIMIT_HINT = ("fred 429 (120 req/min limit); back off or rely on the "
                    "world_bank fallback in this provider")


def _wb_row(raw: dict) -> dict:
    """World Bank observation -> {date, value, ...passthrough metadata}.

    `value` may legitimately be null (year not yet reported) — kept as None,
    never dropped or fabricated. `decimal` is coerced to a number like AV's
    numeric fields; the rest keep their upstream spelling.
    """
    out = {"date": raw.get("date"), "value": raw.get("value")}
    iso3 = raw.get("countryiso3code")
    if iso3:
        out["country"] = iso3
    unit = (raw.get("indicator") or {}).get("id")
    if unit:
        out["indicator"] = unit
    return out


def _num(raw) -> float | None:
    """FRED emits every observation as a string ("30000.0"); "." is its
    missing marker. Non-numeric text returns None so callers keep it."""
    if raw is None or isinstance(raw, bool):
        return None
    s = str(raw).strip().replace(",", "")
    if s in ("", ".", "-", "None", "NaN"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _fred_row(raw: dict) -> dict:
    """FRED observation -> {date, value}. value "." is FRED's missing marker."""
    return {"date": raw.get("date"), "value": _num(raw.get("value"))}


class MacroProvider(Provider):
    name = "macro"
    markets = None  # global macro series: never gated on market

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._client: PoliteClient | None = None

    def available(self) -> bool:
        # The keyless world_bank/imf sub-endpoints are always usable; fred is
        # simply skipped when FRED_API_KEY is unset.
        return True

    def _get_client(self) -> PoliteClient:
        if self._client is None:
            self._client = PoliteClient(timeout=self.settings.request_timeout,
                                        max_retries=self.settings.max_retries,
                                        min_host_delay=self.settings.min_host_delay)
        return self._client

    # ── world_bank (keyless) ────────────────────────────────────────────────

    async def _world_bank(self, code: str) -> list[dict]:
        url = (f"{self.settings.world_bank_base_url.rstrip('/')}"
               f"/country/{_WB_COUNTRY}/indicator/{code}")
        try:
            data = await self._get_client().get_json(url, params={
                "format": "json", "per_page": _WB_PER_PAGE,
                "date": _WB_DATE_RANGE})
        except UpstreamError as e:
            raise UpstreamError(f"macro/world_bank: {e}") from e
        # WB answers /indicator/{code} with [meta, rows]; an unknown code
        # returns [meta, []] (200) — both handled below. A non-list body is a
        # gateway problem, not a "no data" answer.
        if not isinstance(data, list) or len(data) < 2 or not isinstance(data[1], list):
            raise UpstreamError(f"macro/world_bank: unexpected body from {url}")
        meta = data[0] if isinstance(data[0], dict) else {}
        # paged responses (pages > 1) would mean silent truncation at
        # per_page; refuse rather than return partial data.
        if str(meta.get("pages", "1")) not in ("1",):
            raise UpstreamError(f"macro/world_bank: response for {code} spans "
                                f"{meta.get('pages')} pages; refusing partial data")
        rows = [_wb_row(r) for r in data[1] if isinstance(r, dict)]
        if not rows:
            raise NotFound(f"macro/world_bank: no {code} data for {_WB_COUNTRY}")
        return rows

    # ── fred (free registration key) ───────────────────────────────────────

    async def _fred(self, series_id: str) -> list[dict]:
        key = self.settings.fred_api_key
        if not key:
            # No key configured: not an error — the fallback list just skips
            # fred (route_and_call keeps walking the chain on NotFound, and
            # world_bank below may still serve the indicator).
            raise NotFound("macro/fred: FRED_API_KEY not configured")
        url = f"{self.settings.fred_base_url.rstrip('/')}/series/observations"
        try:
            data = await self._get_client().get_json(url, params={
                "series_id": series_id, "api_key": key, "file_type": "json"})
        except UpstreamError as e:
            raise UpstreamError(scrub(f"macro/fred: {e}", key)) from e
        except ValueError as e:
            # 200 with a non-JSON body must not escape as raw JSONDecodeError.
            raise UpstreamError(f"macro/fred: non-JSON body from "
                                f"{scrub(url, key)}") from e
        if not isinstance(data, dict):
            raise UpstreamError(f"macro/fred: unexpected "
                                f"{type(data).__name__} body from {scrub(url, key)}")
        # FRED signals auth/quota problems as HTTP 200 + error_code body.
        err = data.get("error_message")
        if err:
            code = data.get("error_code")
            msg = scrub(str(err)[:200], key)
            if code == 429 or "rate" in str(err).lower():
                raise RateLimited(f"macro/fred: {msg} [{_RATE_LIMIT_HINT}]")
            if code == 400 and "api_key" in str(err):
                raise NotFound(f"macro/fred: {msg}")
            raise UpstreamError(f"macro/fred: {msg}")
        rows = [_fred_row(r) for r in (data.get("observations") or [])
                if isinstance(r, dict)]
        if not rows:
            raise NotFound(f"macro/fred: no {series_id} observations")
        return rows

    # ── imf DataMapper (keyless) ───────────────────────────────────────────

    async def _imf(self, indicator: str) -> list[dict]:
        url = (f"{self.settings.imf_base_url.rstrip('/')}"
               f"/{indicator}/{_WB_COUNTRY}")
        try:
            data = await self._get_client().get_json(url)
        except UpstreamError as e:
            raise UpstreamError(f"macro/imf: {e}") from e
        if not isinstance(data, dict):
            raise UpstreamError(f"macro/imf: unexpected body from {url}")
        series = ((data.get("values") or {}).get(indicator) or {}).get(_WB_COUNTRY)
        if not isinstance(series, dict) or not series:
            raise NotFound(f"macro/imf: no {indicator} series for {_WB_COUNTRY}")
        return [{"date": period, "value": value}
                for period, value in sorted(series.items())]

    # ── public face ────────────────────────────────────────────────────────

    async def economic(self, indicator: str) -> list[dict]:
        """Macro series by canonical indicator. Returns exactly what the
        upstream API returns — no interpolation, no gap-filling.

        Unknown indicator -> ProviderError (chain cannot know it either).
        Known-but-unservable -> NotFound (route_and_call walks to alphavantage).
        """
        key = indicator.strip().upper()
        candidates = MACRO_INDICATORS.get(key)
        if candidates is None:
            raise ProviderError(f"macro: unknown economic indicator {indicator!r}; "
                                f"valid: {sorted(MACRO_INDICATORS)}")
        sub_sources = {
            "world_bank": self._world_bank,
            "fred": self._fred,
            "imf": self._imf,
        }
        last: Exception | None = None
        for source, code in candidates:
            try:
                rows = await sub_sources[source](code)
            except NotFound as e:  # includes keyless fred skip; try next
                last = e
                continue
            except (RateLimited, UpstreamError) as e:
                # Retryable upstream trouble on this sub-source: fall through
                # to the next one, but remember it (surfaced if all fail).
                last = e
                continue
            return rows
        raise last if last is not None else NotFound(
            f"macro: no sub-source serves {key}")
