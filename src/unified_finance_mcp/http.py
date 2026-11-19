"""PoliteClient: shared async HTTP with per-host pacing, Retry-After and backoff.
Ported from reach-mcp's http.py; error translation goes to errors.py taxonomy."""
from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from .errors import AuthError, NotFound, RateLimited, UpstreamError

UA = "unified-finance-mcp/0.1 (+https://github.com/xyonium/finance-mcp)"
_MAX_RETRY_AFTER = 10.0


class PoliteClient:
    def __init__(self, timeout: float = 20.0, max_retries: int = 3,
                 min_host_delay: float = 0.5, proxy: str | None = None):
        # `proxy` is per-client on purpose: only the hosts that refuse this
        # deployment's default egress (e.g. BLS) should go through it.
        self._client = httpx.AsyncClient(timeout=timeout, headers={"User-Agent": UA},
                                         proxy=proxy or None)
        self._max_retries = max_retries
        self._min_gap = min_host_delay
        self._last: dict[str, float] = {}
        self._lock = asyncio.Lock()

    # PYI034 suppressed: `Self` needs py311 (or typing_extensions); this package targets py310.
    async def __aenter__(self) -> PoliteClient:  # noqa: PYI034
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _pace(self, host: str) -> None:
        async with self._lock:
            gap = time.monotonic() - self._last.get(host, 0.0)
            if gap < self._min_gap:
                await asyncio.sleep(self._min_gap - gap)
            self._last[host] = time.monotonic()

    @staticmethod
    def _retry_after(resp: httpx.Response, attempt: int) -> float:
        ra = resp.headers.get("Retry-After", "")
        if ra.replace(".", "", 1).isdigit():
            return min(float(ra), _MAX_RETRY_AFTER)
        return 0.5 * (2 ** attempt)

    async def get_response(self, url: str, params: dict | None = None,
                           headers: dict | None = None, *,
                           timeout: float | None = None,
                           max_retries: int | None = None) -> httpx.Response:
        """Raw GET returning the httpx.Response untouched — the caller maps
        status codes and error bodies itself (e.g. FRED, which puts its
        error_code JSON in a 200 body for quota/auth but a real 400 for a
        malformed api_key). Same pacing/retry discipline as get_json."""
        host = urlparse(url).netloc
        retries = self._max_retries if max_retries is None else max_retries
        last: Exception | None = None
        for attempt in range(retries + 1):
            await self._pace(host)
            try:
                kw = {"params": params, "headers": headers}
                if timeout is not None:
                    kw["timeout"] = timeout
                resp = await self._client.get(url, **kw)
            except httpx.HTTPError as e:
                last = UpstreamError(f"network error from {host}: {e}")
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            if resp.status_code in (429, 503):
                last = RateLimited(f"HTTP {resp.status_code} from {host}")
                await asyncio.sleep(self._retry_after(resp, attempt))
                continue
            return resp
        raise last if last is not None else UpstreamError(f"request to {host} failed")

    async def get_json(self, url: str, params: dict | None = None,
                       headers: dict | None = None, *,
                       timeout: float | None = None,
                       max_retries: int | None = None) -> Any:
        host = urlparse(url).netloc
        retries = self._max_retries if max_retries is None else max_retries
        last: Exception | None = None
        for attempt in range(retries + 1):
            await self._pace(host)
            try:
                kw = {"params": params, "headers": headers}
                if timeout is not None:
                    kw["timeout"] = timeout
                resp = await self._client.get(url, **kw)
            except httpx.HTTPError as e:
                last = UpstreamError(f"network error from {host}: {e}")
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            if resp.status_code in (429, 503):
                last = RateLimited(f"HTTP {resp.status_code} from {host}")
                await asyncio.sleep(self._retry_after(resp, attempt))
                continue
            if resp.status_code in (401, 403):
                raise AuthError(f"HTTP {resp.status_code} from {host}")
            if resp.status_code == 404:
                raise NotFound(f"HTTP 404 from {host}")
            if resp.status_code >= 400:
                raise UpstreamError(f"HTTP {resp.status_code} from {host}")
            return resp.json()
        raise last if last is not None else UpstreamError(f"request to {host} failed")

    async def get_text(self, url: str, params: dict | None = None,
                       headers: dict | None = None, *,
                       timeout: float | None = None,
                       max_retries: int | None = None) -> str:
        """Like get_json but returns the raw response body as text.

        For CSV/plain-text endpoints (e.g. Alpha Vantage EARNINGS_CALENDAR).
        Same pacing/retry/error discipline as get_json.
        """
        host = urlparse(url).netloc
        retries = self._max_retries if max_retries is None else max_retries
        last: Exception | None = None
        for attempt in range(retries + 1):
            await self._pace(host)
            try:
                kw = {"params": params, "headers": headers}
                if timeout is not None:
                    kw["timeout"] = timeout
                resp = await self._client.get(url, **kw)
            except httpx.HTTPError as e:
                last = UpstreamError(f"network error from {host}: {e}")
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            if resp.status_code in (429, 503):
                last = RateLimited(f"HTTP {resp.status_code} from {host}")
                await asyncio.sleep(self._retry_after(resp, attempt))
                continue
            if resp.status_code in (401, 403):
                raise AuthError(f"HTTP {resp.status_code} from {host}")
            if resp.status_code == 404:
                raise NotFound(f"HTTP 404 from {host}")
            if resp.status_code >= 400:
                raise UpstreamError(f"HTTP {resp.status_code} from {host}")
            return resp.text
        raise last if last is not None else UpstreamError(f"request to {host} failed")

    async def post_json(self, url: str, json_body: dict,
                        headers: dict | None = None) -> Any:
        """POST a JSON body and decode the JSON response.

        Same pacing / Retry-After / backoff / error discipline as get_json.
        Errors carry the host only — callers must scrub any secrets from the
        message (errors.scrub) before surfacing.
        """
        host = urlparse(url).netloc
        last: Exception | None = None
        for attempt in range(self._max_retries + 1):
            await self._pace(host)
            try:
                resp = await self._client.post(url, json=json_body, headers=headers)
            except httpx.HTTPError as e:
                last = UpstreamError(f"network error from {host}: {e}")
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            if resp.status_code in (429, 503):
                last = RateLimited(f"HTTP {resp.status_code} from {host}")
                await asyncio.sleep(self._retry_after(resp, attempt))
                continue
            if resp.status_code in (401, 403):
                raise AuthError(f"HTTP {resp.status_code} from {host}")
            if resp.status_code == 404:
                raise NotFound(f"HTTP 404 from {host}")
            if resp.status_code >= 400:
                raise UpstreamError(f"HTTP {resp.status_code} from {host}")
            return resp.json()
        raise last if last is not None else UpstreamError(f"request to {host} failed")

    async def post_form(self, url: str, fields: dict,
                        headers: dict | None = None) -> Any:
        """POST urlencoded form fields and decode the JSON response.

        For OAuth token endpoints (kimi refresh). Same pacing/retry/error
        discipline as get_json; errors carry the host only — callers scrub.
        """
        host = urlparse(url).netloc
        last: Exception | None = None
        for attempt in range(self._max_retries + 1):
            await self._pace(host)
            try:
                resp = await self._client.post(url, data=fields, headers=headers)
            except httpx.HTTPError as e:
                last = UpstreamError(f"network error from {host}: {e}")
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            if resp.status_code in (429, 503):
                last = RateLimited(f"HTTP {resp.status_code} from {host}")
                await asyncio.sleep(self._retry_after(resp, attempt))
                continue
            if resp.status_code in (401, 403):
                raise AuthError(f"HTTP {resp.status_code} from {host}")
            if resp.status_code == 404:
                raise NotFound(f"HTTP 404 from {host}")
            if resp.status_code >= 400:
                raise UpstreamError(f"HTTP {resp.status_code} from {host}")
            return resp.json()
        raise last if last is not None else UpstreamError(f"request to {host} failed")
