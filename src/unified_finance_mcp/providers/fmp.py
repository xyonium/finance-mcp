"""FMP (Financial Modeling Prep) provider: stable REST API + exchange probing.

Auth: `apikey` query param on every call. Value is settings.fmp_api_key or the
placeholder "rotated-by-upstream" when a base-url override (api-key-rotator)
injects the real key upstream — see spec section 3.3. Endpoint paths follow
https://financialmodelingprep.com/developer/docs (stable), which names the
history endpoint `historical-price-eod/light` and cashflow `cash-flow-statement`.
"""
from __future__ import annotations

import logging
import time
from datetime import date

from ..config import DEFAULT_FMP_BASE_URL, Settings
from ..errors import NotFound, ProviderError, RateLimited, UpstreamError, scrub
from ..http import PoliteClient
from ..symbols import ParsedSymbol
from .base import Provider

log = logging.getLogger("unified_finance_mcp")

_CACHE_TTL = 24 * 3600.0

# fmp exchange name -> our market code (probe_exchanges mapping)
EXCHANGE_TO_MARKET = {
    "NASDAQ": "US", "NYSE": "US", "AMEX": "US", "HKEX": "HK",
    "SSE": "CN", "SZSE": "CN", "EGX": "EG", "TSX": "CA", "LSE": "UK",
    "TSE": "JP", "XETR": "DE", "EURONEXT": "FR", "ASX": "AU", "SGX": "SG",
    "BURSA": "MY",
}

_REPORT_PATH = {"income": "income-statement", "balance": "balance-sheet-statement",
                "cashflow": "cash-flow-statement"}
_EVENTS_PATH = {"earnings": "earnings-calendar", "dividends": "dividends-calendar",
                "ipo": "ipos-calendar"}


class FmpProvider(Provider):
    name = "fmp"
    markets = frozenset({"US"})

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._client: PoliteClient | None = None
        self._exchanges_cache: tuple[float, set[str]] | None = None

    def available(self) -> bool:
        # A base-url override means an upstream key rotator injects the key for us.
        return bool(self.settings.fmp_api_key) or \
            self.settings.fmp_base_url != DEFAULT_FMP_BASE_URL

    @property
    def _base(self) -> str:
        return self.settings.fmp_base_url.rstrip("/")

    def _get_client(self) -> PoliteClient:
        if self._client is None:
            self._client = PoliteClient(timeout=self.settings.request_timeout,
                                        max_retries=self.settings.max_retries,
                                        min_host_delay=self.settings.min_host_delay)
        return self._client

    @property
    def _apikey(self) -> str:
        return self.settings.fmp_api_key or "rotated-by-upstream"

    async def _get(self, path: str, empty_ok: bool = False, **params):
        """GET /stable/{path} with the apikey injected.

        PoliteClient already maps 404/401/403/429/503; FMP's quota-exhausted
        HTTP 402 lands in UpstreamError and is re-classified to RateLimited
        here. An empty list body maps to NotFound unless empty_ok (probe).
        """
        url = f"{self._base}/stable/{path}"
        try:
            data = await self._get_client().get_json(
                url, params={**params, "apikey": self._apikey})
        except UpstreamError as e:
            if "HTTP 402" in str(e):  # FMP quota exhausted
                raise RateLimited("fmp: HTTP 402 quota exhausted") from e
            raise
        if isinstance(data, list) and not data and not empty_ok:
            raise NotFound(f"fmp: empty result from {scrub(url, self._apikey)}")
        return data

    def covers(self, market: str) -> bool:
        if market in self.markets:
            return True
        cache = self._exchanges_cache
        if cache is None:
            return False
        probed_at, markets = cache
        return market in markets and time.monotonic() - probed_at < _CACHE_TTL

    async def probe_exchanges(self) -> set[str]:
        """Fetch available-exchanges and refresh the 24h coverage cache.

        Best-effort: on upstream failure the previous cache (if any) is kept
        and the error is logged, so a transient outage never shrinks coverage
        or crashes a startup probe.
        """
        try:
            data = await self._get("available-exchanges", empty_ok=True)
        except Exception as e:  # noqa: BLE001 - swallow upstream flake, keep old cache
            log.debug("fmp exchange probe failed: %s", scrub(str(e), self._apikey))
            return set(self._exchanges_cache[1]) if self._exchanges_cache else set()
        markets = {EXCHANGE_TO_MARKET[x] for x in ({d.get("exchange") for d in data}
                                                   & set(EXCHANGE_TO_MARKET))}
        self._exchanges_cache = (time.monotonic(), markets)
        return markets

    async def quote(self, parsed: ParsedSymbol) -> dict:
        rows = await self._get("quote", symbol=parsed.fmp())
        return {**rows[0], "source": self.name}

    async def history(self, parsed: ParsedSymbol, interval="1d", start=None,
                      end=None) -> list[dict]:
        # FMP's EOD-light endpoint is daily only; intraday is left to yahoo/av.
        if interval != "1d":
            raise ProviderError(f"fmp: interval {interval!r} not supported "
                                f"(daily EOD only)")
        params = {"symbol": parsed.fmp()}
        if start:
            params["from"] = start
        if end:
            params["to"] = end
        return await self._get("historical-price-eod/light", **params)

    async def company_info(self, parsed: ParsedSymbol) -> dict:
        rows = await self._get("profile", symbol=parsed.fmp())
        return rows[0]

    async def financial_report(self, parsed: ParsedSymbol, statement: str,
                               period: str = "annual") -> list[dict]:
        path = _REPORT_PATH.get(statement)
        if path is None:
            raise ProviderError(f"fmp: unknown statement {statement!r}")
        period = "quarter" if period == "quarterly" else "annual"
        return await self._get(path, symbol=parsed.fmp(), period=period)

    async def news(self, parsed: ParsedSymbol, limit: int = 10) -> list[dict]:
        return await self._get("news/stock", symbols=parsed.fmp(), limit=limit)

    async def ownership(self, parsed: ParsedSymbol, kind: str) -> list[dict]:
        if kind == "institutional":
            today = date.today()  # noqa: DTZ011 - local date per FMP 13F year/quarter
            return await self._get(
                "institutional-ownership/symbol-positions-summary",
                symbol=parsed.fmp(), year=today.year, quarter=(today.month - 1) // 3 + 1)
        if kind == "insider":
            return await self._get("insider-trading/search", symbol=parsed.fmp())
        raise ProviderError(f"fmp: unknown ownership kind {kind!r}")

    async def events_calendar(self, kind: str, start: str | None = None,
                              end: str | None = None) -> list[dict]:
        path = _EVENTS_PATH.get(kind)
        if path is None:
            raise ProviderError(f"fmp: unknown events kind {kind!r}")
        params = {}
        if start:
            params["from"] = start
        if end:
            params["to"] = end
        return await self._get(path, **params)

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        return await self._get("search-name", query=query, limit=limit)
