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
                 min_host_delay: float = 0.5):
        self._client = httpx.AsyncClient(timeout=timeout, headers={"User-Agent": UA})
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

    async def get_json(self, url: str, params: dict | None = None,
                       headers: dict | None = None) -> Any:
        host = urlparse(url).netloc
        last: Exception | None = None
        for attempt in range(self._max_retries + 1):
            await self._pace(host)
            try:
                resp = await self._client.get(url, params=params, headers=headers)
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
