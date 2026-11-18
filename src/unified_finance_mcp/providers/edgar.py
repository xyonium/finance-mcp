"""SEC EDGAR provider: filing index + as-reported XBRL facts (keyless).

Access policy — measured, not assumed (2026-11-18, local host and dockerno1
behind the same egress). SEC answers 403 "Undeclared Automated Tool" for
user agents it classifies as undeclared. Matrix against data.sec.gov:

  "unified-finance-mcp/0.1 (+https://github.com/xyonium/finance-mcp)" -> 403
  "unified-finance-mcp/0.1"                                          -> 200
  "unified-finance-mcp/0.1 eli@example.com"                          -> 200

So the shared `http.UA` (which contains github.com) can NEVER be reused
here; this provider always sends `SEC_EDGAR_USER_AGENT`. A URL on another
domain (example.com) passes, which is why the failure is easy to
misdiagnose as "SEC is down". SEC documents a site-wide 10 req/s ceiling;
PoliteClient's per-host pace (0.5 s by default) keeps us at 2 req/s.

Endpoints — data.sec.gov only. `efts.sec.gov` full-text search is
deliberately NOT used: it is not a stable public contract.
  GET /submissions/CIK##########.json
  GET /api/xbrl/companyconcept/CIK##########/{taxonomy}/{tag}.json
  ticker->CIK: www.sec.gov/files/company_tickers.json

`companyfacts` (3.8 MB for AAPL) is deliberately not fetched: callers pass a
tag whitelist and this provider issues one small companyconcept per tag
(2-50 KB each, depending on the concept's history), so one tool call can never balloon to megabytes.

Anti-hallucination discipline (same as fred.py): rows are exactly what SEC
returns — no interpolation, no restatement, no gap-filling. `val` is left as
the upstream integer; `accn`/`filed`/`form` stay attached so a consumer can
cite the filing instead of trusting a vendor-normalized statement.
"""
from __future__ import annotations

import re
import time
from typing import Any

from ..config import DEFAULT_SEC_EDGAR_USER_AGENT, Settings
from ..errors import AuthError, NotFound, UpstreamDrift, UpstreamError
from ..http import PoliteClient
from .base import Provider

_TICKERS_TTL = 24 * 3600.0  # company_tickers.json is a ~800 KB snapshot
_CIK_RE = re.compile(r"^(?:cik)?(\d{1,10})$", re.IGNORECASE)
_TICKER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9.\-]{0,9}$")
_TAG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-\.]{0,127}$")
_TAXONOMY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]{0,31}$")

_UA_HINT = ('SEC 要求声明式 UA；export SEC_EDGAR_USER_AGENT="unified-finance-mcp '
            'your@email"。注意 UA 里带 github.com 会被 SEC 判为未声明工具（403）')


def normalize_cik(value: str) -> str:
    """'CIK0000320193' / 320193 / '0000320193' -> '0000320193'."""
    m = _CIK_RE.match(str(value).strip())
    if not m:
        raise NotFound(f"edgar: {value!r} is not a CIK")
    return m.group(1).zfill(10)


def _at(vals: list, idx: int):
    """Parallel-array access that survives short arrays."""
    return vals[idx] if idx < len(vals) else None


def _trim(row: dict) -> dict:
    """One XBRL fact -> the provenance-bearing fields only."""
    out = {}
    for k in ("start", "end", "val", "fy", "fp", "form", "filed", "accn", "frame"):
        if k in row:
            out[k] = row[k]
    return out


class EdgarProvider(Provider):
    name = "edgar"
    markets = frozenset({"US"})  # SEC registrants: US-listed tickers/ADRs

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._client: PoliteClient | None = None
        self._tickers: dict[str, str] | None = None
        self._tickers_at = 0.0

    def available(self) -> bool:
        # Keyless. The UA is a header, not a credential: an unconfigured UA
        # still works (default), it is only less SEC-policy-friendly.
        return True

    def _get_client(self) -> PoliteClient:
        if self._client is None:
            self._client = PoliteClient(timeout=self.settings.request_timeout,
                                        max_retries=self.settings.max_retries,
                                        min_host_delay=self.settings.min_host_delay)
        return self._client

    def _ua(self) -> str:
        return (self.settings.sec_edgar_user_agent or "").strip() \
            or DEFAULT_SEC_EDGAR_USER_AGENT

    async def _get_json(self, url: str, params: dict | None = None) -> Any:
        """GET with the declared SEC user agent; maps SEC's status codes.

        403 is the one that needs a real hint: it means "your UA is not a
        declared tool", not "wrong endpoint". Routing it to AuthError keeps
        the taxonomy honest (an actionable configuration problem).
        """
        host = url.split("/")[2] if "//" in url else url
        try:
            resp = await self._get_client().get_response(
                url, params=params, headers={"User-Agent": self._ua()})
        except UpstreamError as e:
            raise UpstreamError(f"edgar: {e}") from e
        if resp.status_code == 403:
            raise AuthError(f"edgar: HTTP 403 from {host} — SEC 判定 UA 未声明 "
                            f"[{_UA_HINT}]")
        if resp.status_code == 404:
            raise NotFound(f"edgar: HTTP 404 from {host}")
        if resp.status_code >= 400:
            raise UpstreamError(f"edgar: HTTP {resp.status_code} from {host}")
        try:
            return resp.json()
        except ValueError as e:
            raise UpstreamDrift(f"edgar: non-JSON body from {host}") from e

    async def _tickers_map(self) -> dict[str, str]:
        now = time.monotonic()
        if self._tickers is not None and now - self._tickers_at < _TICKERS_TTL:
            return self._tickers
        data = await self._get_json(self.settings.sec_edgar_tickers_url)
        if not isinstance(data, dict):
            raise UpstreamDrift("edgar: unexpected ticker-map body")
        out: dict[str, str] = {}
        for row in data.values():
            if not isinstance(row, dict):
                continue
            ticker = str(row.get("ticker") or "").strip().upper()
            cik = row.get("cik_str")
            if ticker and str(cik or "").isdigit():
                out[ticker] = str(cik).zfill(10)
        if not out:
            raise UpstreamError("edgar: ticker map carried no usable rows")
        self._tickers, self._tickers_at = out, now
        return out

    async def resolve_cik(self, value: str) -> str:
        """CIK passthrough, or a ticker resolved through company_tickers.json."""
        raw = str(value or "").strip()
        if _CIK_RE.match(raw):
            return normalize_cik(raw)
        if _TICKER_RE.match(raw):
            ticker = raw.upper()
            cik = (await self._tickers_map()).get(ticker)
            if cik is None:
                raise NotFound(f"edgar: ticker {ticker!r} not in the SEC map")
            return cik
        raise NotFound(f"edgar: {value!r} is neither a CIK nor a ticker")

    async def submissions(self, value: str, form_type: str | None = None,
                          limit: int = 20) -> dict:
        """Recent filings for a CIK/ticker, optionally filtered by form type.

        `form_type` accepts a comma-separated list ("10-K,10-Q"); a bare form
        also matches its amendments ("10-K" matches "10-K/A"). Only EDGAR's
        `filings.recent` block is read (the latest ~1000 filings); older
        paginated archives are not followed, and the docstring says so.
        """
        cik = await self.resolve_cik(value)
        data = await self._get_json(
            f"{self.settings.sec_edgar_base_url.rstrip('/')}/submissions/CIK{cik}.json")
        if not isinstance(data, dict):
            raise UpstreamDrift("edgar: unexpected submissions body")
        recent = (data.get("filings") or {}).get("recent")
        if not isinstance(recent, dict):
            raise UpstreamError("edgar: submissions body has no filings.recent")
        forms = [f.strip().upper() for f in (form_type or "").split(",") if f.strip()]
        n = max(1, min(int(limit), 100))

        def col(name: str) -> list:
            value_ = recent.get(name)
            return value_ if isinstance(value_, list) else []

        cols = {k: col(k) for k in ("form", "filingDate", "reportDate",
                                    "accessionNumber", "primaryDocument",
                                    "primaryDocDescription", "items", "isXBRL")}
        rows = []
        for i, form in enumerate(cols["form"]):
            if not isinstance(form, str):
                continue
            if forms and not any(form.upper() == f or form.upper().startswith(f + "/")
                                 for f in forms):
                continue
            rows.append({"form": form,
                         "filing_date": _at(cols["filingDate"], i),
                         "report_date": _at(cols["reportDate"], i),
                         "accession_number": _at(cols["accessionNumber"], i),
                         "primary_document": _at(cols["primaryDocument"], i),
                         "description": _at(cols["primaryDocDescription"], i),
                         "items": _at(cols["items"], i),
                         "is_xbrl": _at(cols["isXBRL"], i)})
            if len(rows) >= n:
                break
        if not rows:
            raise NotFound(f"edgar: no filings for {value!r}"
                           + (f" matching {form_type!r}" if form_type else ""))
        return {"cik": cik, "name": data.get("name"),
                "tickers": data.get("tickers"), "exchanges": data.get("exchanges"),
                "sic_description": data.get("sicDescription"),
                "filings": rows, "count": len(rows)}

    async def company_concept(self, value: str, tag: str,
                              taxonomy: str = "us-gaap",
                              limit: int = 20) -> dict:
        """One XBRL concept's time series (as reported, with accession numbers)."""
        if not _TAG_RE.match(tag or ""):
            raise NotFound(f"edgar: invalid XBRL tag {tag!r}")
        if not _TAXONOMY_RE.match(taxonomy or ""):
            raise NotFound(f"edgar: invalid taxonomy {taxonomy!r}")
        cik = await self.resolve_cik(value)
        url = (f"{self.settings.sec_edgar_base_url.rstrip('/')}"
               f"/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{tag}.json")
        try:
            data = await self._get_json(url)
        except NotFound as e:
            raise NotFound(f"edgar: tag {tag!r} not reported by CIK {cik} "
                           f"({taxonomy})") from e
        if not isinstance(data, dict):
            raise UpstreamDrift("edgar: unexpected companyconcept body")
        units = data.get("units")
        if not isinstance(units, dict) or not units:
            raise NotFound(f"edgar: tag {tag!r} has no unit series for CIK {cik}")
        n = max(1, min(int(limit), 100))
        trimmed: dict[str, list] = {}
        for unit, rows in units.items():
            if not isinstance(rows, list):
                continue
            kept = [_trim(r) for r in rows if isinstance(r, dict)]
            if kept:
                trimmed[str(unit)] = kept[-n:]  # SEC orders oldest -> newest
        if not trimmed:
            raise NotFound(f"edgar: tag {tag!r} has no usable rows for CIK {cik}")
        return {"cik": cik, "entity_name": data.get("entityName"),
                "tag": data.get("tag") or tag,
                "label": data.get("label"), "units": trimmed}

    async def facts(self, value: str, tags: list[str],
                    taxonomy: str = "us-gaap", limit: int = 20) -> dict:
        """Whitelisted tags, one companyconcept each — never companyfacts.

        A tag the filer does not report is collected in `missing_tags`
        (a legitimate answer, e.g. older filers use `Revenues` where newer
        ones use `RevenueFromContractWithCustomerExcludingAssessedTax`);
        hard upstream failures still propagate.
        """
        if not tags:
            raise NotFound("edgar: no XBRL tags requested")
        facts: dict[str, dict] = {}
        missing: list[str] = []
        cik = await self.resolve_cik(value)
        name = None
        for tag in tags:
            try:
                concept = await self.company_concept(cik, tag, taxonomy, limit)
            except NotFound:
                missing.append(tag)
                continue
            name = name or concept.get("entity_name")
            facts[tag] = concept
        if not facts:
            raise NotFound(f"edgar: none of {tags} reported by CIK {cik} "
                           f"({taxonomy}); missing={missing}")
        return {"cik": cik, "entity_name": name, "facts": facts,
                "missing_tags": missing}
