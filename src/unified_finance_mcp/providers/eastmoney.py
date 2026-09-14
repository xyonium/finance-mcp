"""Eastmoney provider (R19): keyless CN A-share market data via EM's public
push2 / push2his / searchapi JSON endpoints (the same endpoints akshare uses;
no login, no key — evidence docs/research/kimi-sources/stock_finance_data
.verdict.md).

Three faces only (this scope): quote / history / search. EM's datacenter
report endpoints (announcements, statements, holders) are deliberately NOT
wired — see the verdict doc's follow-up list; they need paginated report
parsers and are deferred.

Endpoint shapes (probed live 2026-09-13):

- quote: GET {quote_base}/api/qt/stock/get?secid={m}.{code}&fields=...
  Body ``{"rc": 0, "data": {...}}``; ``rc != 0`` or ``data: null`` -> NotFound.
  With ``invt=2`` the f-numbers are ints scaled by 100: f43 latest (x100),
  f44 high, f45 low, f46 open, f47 volume (hands, raw int), f57 code,
  f58 name, f60 previous close, f168 turnover rate (x100), f169 change (x100),
  f170 change percent (x100), f171 amplitude (x100).
- history: GET {history_base}/api/qt/stock/kline/get?secid=..&klt=101&fqt=1...
  ``klines`` is a list of comma strings
  ``"date,open,close,high,low,volume,amount,amplitude,pct,chg,turnover"``.
- search: GET {search_base}/api/suggest/get?input=..&type=14
  ``QuotationCodeTable.Data`` rows (Code/Name/MktNum/QuoteID/...); EM matches
  pinyin + Chinese name + bare 6-digit codes but NOT English names.

secid prefix: SH=1, SZ/BJ=0 (market field of the quote path).

EM rate-limits by IP (the verdict doc saw RemoteProtocolError after a burst);
PoliteClient's min_host_delay paces us, and CN falls through to yahoo/futu
when EM throttles (retryable UpstreamError/RateLimited walks the chain).

Anti-hallucination discipline (inherited from alphavantage.py): emit only
fields the endpoint actually returned; no interpolation, no derived rows.
"""
from __future__ import annotations

from ..config import Settings
from ..errors import NotFound, ProviderError, UpstreamError
from ..http import PoliteClient
from ..symbols import ParsedSymbol
from .base import Provider

# our interval -> EM klt (K-line type): 101 daily, 102 weekly, 103 monthly.
_EM_KLT = {"1d": "101", "1wk": "102", "1mo": "103"}

# quote path fields: f43 latest / f44 high / f45 low / f46 open / f47 volume /
# f57 code / f58 name / f60 prev close / f168 turnover / f169 change /
# f170 pct / f171 amplitude. f47 volume is in hands (100 shares) — kept raw
# as the exchange reports it; price fields are x100 ints under invt=2.
_QUOTE_FIELDS = ("f43", "f44", "f45", "f46", "f47", "f57", "f58", "f60",
                 "f168", "f169", "f170", "f171")

# kline fields2: f51 date, f52 open, f53 close, f54 high, f55 low, f56 volume,
# f57 amount, f58 amplitude, f59 pct, f60 chg, f61 turnover.
_KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"

# suggest endpoint: EM's public token (the value the web UI itself sends;
# it is not a credential — the endpoint answers without it too).
_SUGGEST_TOKEN = "D43BF722C8E33BDC906FB84D85E326E8"


def _price100(raw) -> float | None:
    """EM price fields are x100 ints ("127516" -> 1275.16). "-" -> None."""
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return int(raw) / 100.0
    except (TypeError, ValueError):
        return None


def _int(raw) -> int | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _float(raw) -> float | None:
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


class EastmoneyProvider(Provider):
    name = "eastmoney"
    markets = frozenset({"CN"})

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._client: PoliteClient | None = None

    def available(self) -> bool:
        # Keyless: always usable (base-url overrides only re-point the hosts).
        return True

    @property
    def _quote_base(self) -> str:
        return self.settings.eastmoney_quote_base_url.rstrip("/")

    @property
    def _history_base(self) -> str:
        return self.settings.eastmoney_history_base_url.rstrip("/")

    @property
    def _search_base(self) -> str:
        return self.settings.eastmoney_search_base_url.rstrip("/")

    def _get_client(self) -> PoliteClient:
        if self._client is None:
            self._client = PoliteClient(timeout=self.settings.request_timeout,
                                        max_retries=self.settings.max_retries,
                                        min_host_delay=self.settings.min_host_delay)
        return self._client

    def _secid(self, parsed: ParsedSymbol) -> str:
        """secid = {1|0}.{code}: SH -> 1, SZ/BJ -> 0."""
        if parsed.market != "CN":
            raise NotFound(f"eastmoney: market {parsed.market} not covered (CN only)")
        prefix = "1" if parsed.exchange == "SH" else "0"
        return f"{prefix}.{parsed.local}"

    async def _get_json(self, url: str, params: dict) -> dict:
        """GET and fold EM's envelope discipline: non-dict body / non-JSON ->
        UpstreamError (never a raw JSONDecodeError into the tools layer)."""
        try:
            data = await self._get_client().get_json(url, params=params)
        except UpstreamError:
            raise
        except ValueError as e:
            raise UpstreamError(f"eastmoney: non-JSON body from {url}") from e
        if not isinstance(data, dict):
            raise UpstreamError(f"eastmoney: unexpected {type(data).__name__} body from {url}")
        return data

    @staticmethod
    def _unwrap(data: dict, url: str) -> dict:
        """rc!=0 or data null -> NotFound (EM's in-band "no such code")."""
        rc = data.get("rc", 0)
        if rc != 0 or data.get("data") is None:
            raise NotFound(f"eastmoney: empty data (rc={rc}) from {url}")
        payload = data["data"]
        if not isinstance(payload, dict):
            raise UpstreamError(f"eastmoney: unexpected data shape from {url}")
        return payload

    async def quote(self, parsed: ParsedSymbol) -> dict:
        url = f"{self._quote_base}/api/qt/stock/get"
        secid = self._secid(parsed)
        data = await self._get_json(url, {
            "secid": secid, "invt": "2", "fields": ",".join(_QUOTE_FIELDS)})
        payload = self._unwrap(data, url)
        out: dict = {}
        for key, name in (("f43", "price"), ("f44", "high"), ("f45", "low"),
                          ("f46", "open"), ("f60", "previous_close")):
            out[name] = _price100(payload.get(key))
        out["volume"] = _int(payload.get("f47"))
        # f169/f170 are also x100 ints (change -997 -> -9.97 yuan,
        # pct -78 -> -0.78%); f168 turnover / f171 amplitude likewise.
        out["change"] = _price100(payload.get("f169"))
        out["change_percent"] = _price100(payload.get("f170"))
        out["turnover_rate"] = _price100(payload.get("f168"))
        out["amplitude"] = _price100(payload.get("f171"))
        if payload.get("f57") is not None:
            out["symbol"] = payload.get("f57")
        if payload.get("f58") is not None:
            out["name"] = payload.get("f58")
        return {**out, "source": self.name}

    async def history(self, parsed: ParsedSymbol, interval: str = "1d",
                      start: str | None = None, end: str | None = None) -> list[dict]:
        klt = _EM_KLT.get(interval)
        if klt is None:
            raise ProviderError(f"eastmoney: unsupported interval {interval!r}; "
                                f"valid: {sorted(_EM_KLT)}")
        url = f"{self._history_base}/api/qt/stock/kline/get"
        params = {
            "secid": self._secid(parsed), "klt": klt, "fqt": "1",  # 1 = 前复权
            "fields1": "f1,f2,f3,f4,f5,f6", "fields2": _KLINE_FIELDS2,
            "beg": (start or "19900101").replace("-", ""),
            "end": (end or "20500101").replace("-", ""),
            "lmt": "1000000",
        }
        data = await self._get_json(url, params)
        payload = self._unwrap(data, url)
        klines = payload.get("klines") or []
        rows: list[dict] = []
        for line in klines:
            # "date,open,close,high,low,volume,amount,amplitude,pct,chg,turnover"
            parts = str(line).split(",")
            if len(parts) < 6:
                continue
            rows.append({"date": parts[0],
                         "open": _float(parts[1]), "close": _float(parts[2]),
                         "high": _float(parts[3]), "low": _float(parts[4]),
                         "volume": _int(parts[5])})
        if not rows:
            raise NotFound(f"eastmoney: no klines for {params['secid']}"
                           + (f" in {start}..{end}" if start or end else ""))
        return rows

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Symbol suggest: code + pinyin + Chinese name match (no English)."""
        url = f"{self._search_base}/api/suggest/get"
        data = await self._get_json(url, {
            "input": query, "type": "14", "token": _SUGGEST_TOKEN,
            "count": str(max(1, limit))})
        table = data.get("QuotationCodeTable")
        if not isinstance(table, dict):
            raise NotFound(f"eastmoney: no suggestion table for {query!r}")
        items = table.get("Data") or []
        out: list[dict] = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            row = {"symbol": item.get("Code"), "name": item.get("Name"),
                   "exchange": item.get("SecurityTypeName"),
                   "type": item.get("Classify"), "quote_id": item.get("QuoteID"),
                   "source": self.name}
            out.append({k: v for k, v in row.items() if v is not None})
        if not out:
            raise NotFound(f"eastmoney: no symbol match for {query!r}")
        return out
