"""Standalone FRED provider (task ④): arbitrary series_id passthrough.

Boundary with providers/macro.py (user ruling 2026-09-14): **macro owns the
canonical-8 indicator vocabulary** (GDP/CPI/... via get_economic_data, with
world_bank/imf fallbacks); **this provider owns generic FRED access** — any of
the 800k+ FRED series by raw series_id, plus series search. The two error
mappings differ deliberately: macro maps a bad key to NotFound so
route_and_call walks its sub-source candidates; here there is no chain, so a
bad key is AuthError with the key-acquisition URL.

Requires FRED_API_KEY (free 5-minute registration, 120 req/min):
https://fredaccount.stlouisfed.org/apikeys

ToS: this product uses the FRED® API but is not endorsed or certified by the
Federal Reserve Bank of St. Louis.

Anti-hallucination discipline (same as macro.py): rows are exactly what FRED
returns. "." (FRED's missing marker) becomes None; dates keep the upstream
spelling; no interpolation, no gap-filling, no re-basing.
"""
from __future__ import annotations

from ..config import Settings
from ..errors import AuthError, NotFound, RateLimited, UpstreamError, scrub
from ..http import PoliteClient
from .base import Provider

_KEY_HINT = ("get a free key (5-minute registration, 120 req/min) at "
             "https://fredaccount.stlouisfed.org/apikeys")
_RATE_LIMIT_HINT = "fred 429 (120 req/min limit); back off and retry"


def _num(raw) -> float | None:
    """FRED emits every observation as a string ("30000.0"); "." is its
    missing marker. Non-numeric text returns None so callers keep it.
    (Mirror of macro._num — kept local so this provider stays standalone.)"""
    if raw is None or isinstance(raw, bool):
        return None
    s = str(raw).strip().replace(",", "")
    if s in ("", ".", "-", "None", "NaN"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


class FredProvider(Provider):
    name = "fred"
    markets = None  # national series: never gated on market

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._client: PoliteClient | None = None

    def available(self) -> bool:
        return bool(self.settings.fred_api_key)

    def _get_client(self) -> PoliteClient:
        if self._client is None:
            self._client = PoliteClient(timeout=self.settings.request_timeout,
                                        max_retries=self.settings.max_retries,
                                        min_host_delay=self.settings.min_host_delay)
        return self._client

    async def _get(self, endpoint: str, params: dict) -> dict:
        """GET {base}/fred/{endpoint} with the FRED error-body mapping.

        FRED signals auth/quota problems as HTTP 200 + error_code body, so
        status-code handling alone is not enough. But a **malformed key**
        (wrong length/charset) is a real HTTP 400 with the same error_code
        JSON body — PoliteClient turns that into a blunt UpstreamError
        before we ever see the body. So the client is asked for the raw
        response here and the error mapping runs on both paths.
        """
        key = self.settings.fred_api_key
        if not key:
            raise NotFound(f"fred: FRED_API_KEY not configured [{_KEY_HINT}]")
        url = f"{self.settings.fred_base_url.rstrip('/')}/{endpoint}"
        try:
            resp = await self._get_client().get_response(
                url, params={**params, "api_key": key, "file_type": "json"})
        except UpstreamError as e:
            raise UpstreamError(scrub(f"fred: {e}", key)) from e
        try:
            data = resp.json()
        except ValueError as e:
            raise UpstreamError(f"fred: non-JSON body from "
                                f"{scrub(url, key)}") from e
        if not isinstance(data, dict):
            raise UpstreamError(f"fred: unexpected {type(data).__name__} body "
                                f"from {scrub(url, key)}")
        err = data.get("error_message")
        if err:
            code = data.get("error_code")
            msg = scrub(str(err)[:200], key)
            if code == 429 or "rate" in str(err).lower():
                raise RateLimited(f"fred: {msg} [{_RATE_LIMIT_HINT}]")
            if code == 400 and "api_key" in str(err):
                raise AuthError(f"fred: {msg} [{_KEY_HINT}]")
            raise UpstreamError(f"fred: {msg}")
        if resp.status_code >= 400:
            raise UpstreamError(scrub(
                f"fred: HTTP {resp.status_code} from {url.split('/')[2]}", key))
        return data

    async def series_observations(self, series_id: str,
                                  observation_start: str | None = None,
                                  observation_end: str | None = None,
                                  limit: int = 120,
                                  sort_order: str = "desc") -> dict:
        """Observations for any FRED series_id (e.g. "CPIAUCSL", "DGS10").

        sort_order "desc" + limit N = the latest N observations (the default
        is tuned for model consumption, not bulk download). observation_start/
        end are FRED's YYYY-MM-DD window filters, passed through verbatim.
        """
        sid = series_id.strip().upper()
        if not sid:
            raise NotFound("fred: empty series_id")
        if sort_order not in ("asc", "desc"):
            raise NotFound(f"fred: sort_order must be asc|desc, got {sort_order!r}")
        params: dict = {"series_id": sid, "limit": int(limit),
                        "sort_order": sort_order}
        if observation_start:
            params["observation_start"] = observation_start
        if observation_end:
            params["observation_end"] = observation_end
        data = await self._get("series/observations", params)
        rows = [{"date": r.get("date"), "value": _num(r.get("value"))}
                for r in (data.get("observations") or [])
                if isinstance(r, dict)]
        if not rows:
            raise NotFound(f"fred: no {sid} observations")
        return {"series_id": sid,
                "units": data.get("units"),
                "observation_start": data.get("observation_start"),
                "observation_end": data.get("observation_end"),
                "count": data.get("count"),
                "data": rows}

    async def series_search(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search over FRED series metadata (the `seriess` body)."""
        q = query.strip()
        if not q:
            raise NotFound("fred: empty search query")
        data = await self._get("series/search",
                               {"search_text": q, "limit": int(limit)})
        out = []
        for s in (data.get("seriess") or []):
            if not isinstance(s, dict):
                continue
            out.append({"id": s.get("id"), "title": s.get("title"),
                        "frequency": s.get("frequency"),
                        "units": s.get("units"),
                        "seasonal_adjustment": s.get("seasonal_adjustment"),
                        "popularity": s.get("popularity"),
                        "observation_start": s.get("observation_start"),
                        "observation_end": s.get("observation_end")})
        if not out:
            raise NotFound(f"fred: no series matching {q!r}")
        return out
