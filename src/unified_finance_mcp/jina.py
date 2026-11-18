"""Jina Reader fetch: read a URL through r.jina.ai.

Why this exists: BLS (and Census) sit behind Akamai and answer 403 to this
deployment's egress (Oracle Cloud London, AS31898) — measured 2026-11-18,
while the same URLs return 200 through the reader. reach-mcp already uses
the reader as its default read path; this is the same pattern, scoped to the
two hosts that refuse us directly.

Keyless is ~20 RPM; `JINA_API_KEY` raises it to 500 RPM (a monthly quota,
not one-time credits). `X-Return-Format: text` makes the reader return the
upstream body verbatim instead of a markdown wrapper — that is what lets a
JSON API be parsed here.

The reader is a third party: every failure is translated into this repo's
error taxonomy (`AuthError` for reader auth, `RateLimited`, `UpstreamError`)
so the macro fallback chain keeps working when it is unavailable.
"""
from __future__ import annotations

from .config import Settings
from .errors import AuthError, NotFound, UpstreamError
from .http import PoliteClient

_KEY_HINT = ("set JINA_API_KEY (jina.ai/keys) for 500 RPM, or keep the "
             "keyless 20 RPM limit")


class JinaReader:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: PoliteClient | None = None

    def _get_client(self) -> PoliteClient:
        if self._client is None:
            self._client = PoliteClient(timeout=self.settings.request_timeout,
                                        max_retries=self.settings.max_retries,
                                        min_host_delay=self.settings.min_host_delay)
        return self._client

    async def read_text(self, url: str) -> str:
        """Fetch `url` verbatim through the reader; empty base disables it."""
        base = (self.settings.jina_reader_url or "").strip().rstrip("/")
        if not base:
            raise NotFound("jina: JINA_READER_URL is empty (reader disabled)")
        headers = {"X-Return-Format": "text"}
        key = self.settings.jina_api_key
        if key:
            headers["Authorization"] = f"Bearer {key}"
        try:
            return await self._get_client().get_text(f"{base}/{url}", headers=headers)
        except AuthError as e:
            raise AuthError(f"jina: {e} [{_KEY_HINT}]") from e
        except NotFound as e:
            raise NotFound(f"jina: {e}") from e
        except UpstreamError as e:
            raise UpstreamError(f"jina: {e}") from e
