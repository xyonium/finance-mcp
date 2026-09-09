"""Marketaux provider: news only, global coverage.

Auth: `api_token` query param on every call. Value is settings.marketaux_api_token
or the placeholder "rotated-by-upstream" when a base-url override (api-key-rotator)
injects the real token upstream — see spec section 3.3. Endpoint per
https://www.marketaux.com/documentation (GET /v1/news/all).

Why `parsed.yahoo()` for the `symbols` param: Marketaux is a **global** news API
whose entity symbols are exchange-suffixed (0700.HK, 7203.T), i.e. Yahoo's form,
not a US bare ticker — hence `markets = None` (symbol-agnostic) and no market
gating. `parsed is None` is legal and means general/global news; the tools layer
(Task 13) is the only caller that sends it.

Unlike AV, Marketaux signals throttling and bad tokens with **HTTP status**
(429 / 401 or 403), not a 200 body, so PoliteClient's own mapping already yields
RateLimited / AuthError and this module does not re-classify them — it only has to
scrub the token out of any message that could carry an URL or upstream text
(PoliteClient does not scrub; see T2 ledger).
"""
from __future__ import annotations

from ..config import DEFAULT_MARKETAUX_BASE_URL, Settings
from ..errors import UpstreamError, scrub
from ..http import PoliteClient
from ..symbols import ParsedSymbol
from .base import Provider

# Response keys -> our news item keys. Unmapped keys are dropped, so upstream
# adds (snippet, image, similar...) never leak into a caller's payload.
_NEWS_FIELDS = {
    "title": "title", "url": "url", "description": "summary",
    "published_at": "published", "entities": "entities", "source": "source_name",
}


class MarketauxProvider(Provider):
    name = "marketaux"
    markets = None  # global coverage

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._client: PoliteClient | None = None

    def available(self) -> bool:
        # A base-url override means an upstream key rotator injects the token for us.
        return (bool(self.settings.marketaux_api_token)
                or self.settings.marketaux_base_url != DEFAULT_MARKETAUX_BASE_URL)

    @property
    def _base(self) -> str:
        return self.settings.marketaux_base_url.rstrip("/")

    @property
    def _token(self) -> str:
        return self.settings.marketaux_api_token or "rotated-by-upstream"

    def _get_client(self) -> PoliteClient:
        if self._client is None:
            self._client = PoliteClient(timeout=self.settings.request_timeout,
                                        max_retries=self.settings.max_retries,
                                        min_host_delay=self.settings.min_host_delay)
        return self._client

    async def _get(self, **params) -> dict:
        """GET {base}/v1/news/all with the token injected and errors scrubbed."""
        url = f"{self._base}/v1/news/all"
        try:
            data = await self._get_client().get_json(
                url, params={**params, "api_token": self._token})
        except UpstreamError as e:
            raise UpstreamError(scrub(f"marketaux: {e}", self._token)) from e
        except ValueError as e:
            # A 200 with a non-JSON body (HTML error page from a rotator/gateway)
            # must not escape as a raw JSONDecodeError into the tools layer.
            raise UpstreamError(f"marketaux: non-JSON body from "
                                f"{scrub(url, self._token)}") from e
        if not isinstance(data, dict):
            raise UpstreamError("marketaux: unexpected "
                                f"{type(data).__name__} body from {scrub(url, self._token)}")
        return data

    async def news(self, parsed: ParsedSymbol | None, limit: int = 10) -> list[dict]:
        """Market news, newest first. `parsed=None` -> general news (no `symbols`).

        An empty `data` array is a legit answer (quiet ticker), so it returns []
        rather than NotFound, letting the tools layer fall through to the next source.
        """
        params = {"language": "en", "limit": limit}
        if parsed is not None:
            params["symbols"] = parsed.yahoo()
        data = await self._get(**params)
        rows = data.get("data")
        if not isinstance(rows, list):
            raise UpstreamError("marketaux: unexpected "
                                f"{type(rows).__name__} 'data' from "
                                f"{scrub(f'{self._base}/v1/news/all', self._token)}")
        return [self._news_item(r) for r in rows[:limit]]

    def _news_item(self, item: dict) -> dict:
        out = {name: item.get(key) for key, name in _NEWS_FIELDS.items()}
        return {**out, "source": self.name}
