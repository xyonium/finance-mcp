"""Alpha Vantage provider. Keyed, US equities + macro; one `function=` endpoint.

Auth: `apikey` query param on every call, value = settings.alphavantage_api_key or
the placeholder "rotated-by-upstream" when a base-url override (api-key-rotator)
injects the real key upstream — see spec section 3.3. The request URL is
`{alphavantage_base_url}/query` (the default base has no path), so a rotator
prefix such as http://api-key-rotator:8788/av receives `/av/query?...`.

Rate limiting (spec section 3.2): AV answers a throttled call with **HTTP 200**
and a body of `{"Note": ...}` or `{"Information": ...}`; that shape is mapped to
`RateLimited`. `{"Error Message": ...}` and empty bodies map to `NotFound`.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import date

from ..config import DEFAULT_AV_BASE_URL, Settings
from ..errors import NotFound, ProviderError, RateLimited, UpstreamError, scrub
from ..http import PoliteClient
from ..symbols import ParsedSymbol
from .base import Provider

# Canonical indicator -> AV `function`. Keys are the vocabulary get_economic_data
# (Task 13) validates against, so renaming one is a cross-task change.
ECONOMIC_INDICATORS = {
    "GDP": "REAL_GDP",
    "CPI": "CPI",
    "INFLATION": "INFLATION",
    "UNEMPLOYMENT": "UNEMPLOYMENT",
    "FEDERAL_FUNDS_RATE": "FEDERAL_FUNDS_RATE",
    "TREASURY_YIELD_10Y": "TREASURY_YIELD",
    "RETAIL_SALES": "RETAIL_SALES",
    "NONFARM_PAYROLL": "NONFARM_PAYROLL",
}

# REAL_GDP is the only macro endpoint whose default (and coarsest useful) period
# is quarterly; everything else is read monthly.
_ECON_INTERVAL = {"GDP": "quarterly"}
_ECON_DEFAULT_INTERVAL = "monthly"

_STATEMENT = {"income": "INCOME_STATEMENT", "balance": "BALANCE_SHEET",
              "cashflow": "CASH_FLOW"}

# our interval -> AV `interval` for TIME_SERIES_INTRADAY (AV supports 1/5/15/30/60min)
_AV_INTRADAY = {"1m": "1min", "5m": "5min", "15m": "15min", "30m": "30min",
                "1h": "60min", "60m": "60min"}
# ...and for the technical-indicator endpoints, which spell non-intraday out.
_AV_TA_INTERVAL = {"1d": "daily", "1wk": "weekly", "1mo": "monthly", **_AV_INTRADAY}

_TECHNICALS = frozenset({"SMA", "EMA", "RSI", "MACD", "BBANDS", "STOCH", "ADX",
                         "CCI", "AROON", "OBV"})

# GLOBAL_QUOTE's numbered keys -> our snake_case
_GLOBAL_QUOTE = {"01. symbol": "symbol", "02. open": "open", "03. high": "high",
                 "04. low": "low", "05. price": "price", "06. volume": "volume",
                 "07. latest trading day": "latest_trading_day",
                 "08. previous close": "previous_close", "09. change": "change",
                 "10. change percent": "change_percent"}
# quote fields that are numbers-as-strings; the rest (symbol, trading day) stay text
_QUOTE_NUMERIC = frozenset({"open", "high", "low", "price", "volume",
                            "previous_close", "change", "change_percent"})
# AV's in-band markers for "no value", e.g. OVERVIEW's "DividendPerShare": "None"
_MISSING = frozenset({"", "-", "None", "null"})
# SYMBOL_SEARCH bestMatches keys -> our snake_case
_BEST_MATCH = {"1. symbol": "symbol", "2. name": "name", "3. type": "type",
               "4. region": "region", "5. marketOpen": "market_open",
               "6. marketClose": "market_close", "7. timezone": "timezone",
               "8. currency": "currency", "9. matchScore": "match_score"}

_RATE_LIMIT_HINT = ("alphavantage daily quota exhausted; it resets tomorrow (UTC) "
                    "or point ALPHAVANTAGE_BASE_URL at an api-key-rotator")


def _num(raw) -> float | None:
    """AV emits every number as a string, using "" / "-" / "None" for missing.

    Trailing "%" is stripped (change percent). Non-numeric text (dates, tickers,
    currency codes) returns None so callers keep the original value.
    """
    if raw is None or isinstance(raw, bool):
        return None
    s = str(raw).strip().replace(",", "")
    if s.rstrip("%") in _MISSING:
        return None
    try:
        return float(s.rstrip("%"))
    except ValueError:
        return None


def _numeric_fields(row: dict) -> dict:
    """Coerce every number-as-string (and AV's in-band "None") to a float/None.

    Text fields (dates, tickers, sector names) keep their original string.
    """
    out = dict(row)
    for key, value in out.items():
        if isinstance(value, str) and value.strip() in _MISSING:
            out[key] = None
            continue
        n = _num(value)
        if n is not None:
            out[key] = n
    return out


def _series(data: dict, prefix: str) -> dict:
    """Pick the one `prefix*` object out of an AV response (time series / TA)."""
    for key, value in data.items():
        if key.startswith(prefix) and isinstance(value, dict):
            return value
    raise NotFound(f"alphavantage: response has no {prefix!r} object")


def _in_window(raw_date, start, end) -> bool:
    """reportDate within [start, end] (inclusive). Unparseable -> dropped."""
    if not raw_date:
        return False
    try:
        d = date.fromisoformat(str(raw_date)[:10])
    except ValueError:
        return False
    return not ((start and d.isoformat() < start) or (end and d.isoformat() > end))


class AlphaVantageProvider(Provider):
    name = "alphavantage"
    markets = frozenset({"US", "FX", "CRYPTO"})

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._client: PoliteClient | None = None

    def available(self) -> bool:
        # A base-url override means an upstream key rotator injects the key for us.
        return (bool(self.settings.alphavantage_api_key)
                or self.settings.alphavantage_base_url != DEFAULT_AV_BASE_URL)

    @property
    def _base(self) -> str:
        return self.settings.alphavantage_base_url.rstrip("/")

    @property
    def _apikey(self) -> str:
        return self.settings.alphavantage_api_key or "rotated-by-upstream"

    def _get_client(self) -> PoliteClient:
        if self._client is None:
            self._client = PoliteClient(timeout=self.settings.request_timeout,
                                        max_retries=self.settings.max_retries,
                                        min_host_delay=self.settings.min_host_delay)
        return self._client

    def _symbol(self, parsed: ParsedSymbol) -> str:
        try:
            return parsed.av()
        except ValueError as e:  # non-US: AV equities are US-only
            raise NotFound(f"alphavantage: {e}") from e

    async def _get(self, **params) -> dict:
        """GET {base}/query?...&apikey=... and map AV's 200-body error shapes."""
        url = f"{self._base}/query"
        try:
            data = await self._get_client().get_json(
                url, params={**params, "apikey": self._apikey})
        except UpstreamError as e:
            raise UpstreamError(scrub(f"alphavantage: {e}", self._apikey)) from e
        if not isinstance(data, dict):
            raise UpstreamError(f"alphavantage: unexpected {type(data).__name__} body "
                                f"from {scrub(url, self._apikey)}")
        note = data.get("Note") or data.get("Information")
        if note:
            raise RateLimited(f"alphavantage: {scrub(str(note)[:200], self._apikey)} "
                              f"[{_RATE_LIMIT_HINT}]")
        if data.get("Error Message"):
            raise NotFound("alphavantage: "
                           f"{scrub(str(data['Error Message'])[:200], self._apikey)}")
        if not data:
            raise NotFound(f"alphavantage: empty response from {scrub(url, self._apikey)}")
        return data

    async def quote(self, parsed: ParsedSymbol) -> dict:
        symbol = self._symbol(parsed)
        data = await self._get(function="GLOBAL_QUOTE", symbol=symbol)
        raw = data.get("Global Quote") or {}
        if not raw:
            raise NotFound(f"alphavantage: no quote for {symbol}")
        out = {}
        for key, name in _GLOBAL_QUOTE.items():
            value = raw.get(key)
            if name not in _QUOTE_NUMERIC:
                out[name] = value
                continue
            n = _num(value)
            out[name] = int(n) if name == "volume" and n is not None else n
        return {**out, "source": self.name}

    async def history(self, parsed: ParsedSymbol, interval: str = "1d",
                      start: str | None = None, end: str | None = None) -> list[dict]:
        symbol = self._symbol(parsed)
        if interval == "1d":
            # AV has no date params: compact = last ~100 daily bars, full = 20y.
            # A start date can predate the compact window, so widen to full then.
            params = {"function": "TIME_SERIES_DAILY",
                      "outputsize": "full" if start else "compact"}
        else:
            av_interval = _AV_INTRADAY.get(interval)
            if av_interval is None:
                raise ProviderError(f"alphavantage: unsupported interval {interval!r}; "
                                    f"valid: {sorted(_AV_INTRADAY)}")
            params = {"function": "TIME_SERIES_INTRADAY", "interval": av_interval,
                      "outputsize": "full"}
        data = await self._get(symbol=symbol, **params)
        series = _series(data, "Time Series")
        rows = []
        for ts, ohlcv in sorted(series.items()):
            day = ts[:10]
            if start and day < start:
                continue
            if end and day > end:
                continue
            row = {"date": ts}
            for key, value in ohlcv.items():
                label = key.split(". ", 1)[-1].lower()  # "1. open" -> "open"
                n = _num(value)
                row[label] = int(n) if label == "volume" and n is not None else n
            rows.append(row)
        if not rows:
            raise NotFound(f"alphavantage: no history for {symbol}"
                           + (f" in {start}..{end}" if start or end else ""))
        return rows

    async def company_info(self, parsed: ParsedSymbol) -> dict:
        data = await self._get(function="OVERVIEW", symbol=self._symbol(parsed))
        return {**_numeric_fields(data), "source": self.name}

    async def financial_report(self, parsed: ParsedSymbol, statement: str,
                               period: str = "annual") -> list[dict]:
        symbol = self._symbol(parsed)
        fn = _STATEMENT.get(statement)
        if fn is None:
            raise ProviderError(f"alphavantage: unknown statement {statement!r}; "
                                f"valid: {sorted(_STATEMENT)}")
        data = await self._get(function=fn, symbol=symbol)
        bucket = "quarterlyReports" if period == "quarterly" else "annualReports"
        rows = data.get(bucket) or []
        if not rows:
            raise NotFound(f"alphavantage: no {statement} {bucket} for {symbol}")
        return [_numeric_fields(r) for r in rows]

    async def news(self, parsed: ParsedSymbol, limit: int = 10) -> list[dict]:
        symbol = self._symbol(parsed)
        data = await self._get(function="NEWS_SENTIMENT", tickers=symbol, limit=limit)
        feed = data.get("feed") or []
        if not feed:
            raise NotFound(f"alphavantage: no news for {symbol}")
        return [self._news_item(i) for i in feed[:limit]]

    def _news_item(self, item: dict) -> dict:
        return {"title": item.get("title"), "summary": item.get("summary"),
                "url": item.get("url"), "published": item.get("time_published"),
                "source_name": item.get("source"),
                "sentiment": _num(item.get("overall_sentiment_score")),
                "tickers": item.get("ticker_sentiment") or [],
                "source": self.name}

    async def economic(self, indicator: str) -> list[dict]:
        """Macro series. Symbol-free by nature: never gated on market."""
        key = indicator.strip().upper()
        fn = ECONOMIC_INDICATORS.get(key)
        if fn is None:
            raise ProviderError(f"alphavantage: unknown economic indicator "
                                f"{indicator!r}; valid: {sorted(ECONOMIC_INDICATORS)}")
        params = {"function": fn,
                  "interval": _ECON_INTERVAL.get(key, _ECON_DEFAULT_INTERVAL)}
        if fn == "TREASURY_YIELD":
            params["maturity"] = "10year"
        data = await self._get(**params)
        rows = [_numeric_fields(r) for r in (data.get("data") or [])]
        if not rows:
            raise NotFound(f"alphavantage: no {key} data")
        return rows

    async def technicals(self, parsed: ParsedSymbol, indicator: str,
                         interval: str = "1d") -> dict:
        symbol = self._symbol(parsed)
        fn = indicator.strip().upper()
        if fn not in _TECHNICALS:
            raise ProviderError(f"alphavantage: unsupported indicator {indicator!r}; "
                                f"valid: {sorted(_TECHNICALS)}")
        av_interval = _AV_TA_INTERVAL.get(interval)
        if av_interval is None:
            raise ProviderError(f"alphavantage: unsupported interval {interval!r}; "
                                f"valid: {sorted(_AV_TA_INTERVAL)}")
        data = await self._get(function=fn, symbol=symbol, interval=av_interval,
                               time_period=14, series_type="close")
        series = _series(data, "Technical Analysis")
        return {"symbol": symbol, "indicator": fn, "interval": interval,
                "time_period": 14,
                "series": {ts: {k.lower(): _num(v) for k, v in vals.items()}
                           for ts, vals in sorted(series.items())},
                "source": self.name}

    async def search(self, query: str, limit: int = 10) -> list[dict]:
        """Symbol lookup. Symbol-free by nature: never gated on market."""
        data = await self._get(function="SYMBOL_SEARCH", keywords=query)
        matches = data.get("bestMatches") or []
        if not matches:
            raise NotFound(f"alphavantage: no symbol match for {query!r}")
        out = []
        for m in matches[:limit]:
            row = {_BEST_MATCH.get(k, k): v for k, v in m.items()}
            row["match_score"] = _num(row.get("match_score"))
            out.append(row)
        return out

    async def events_calendar(self, kind: str, start=None, end=None) -> list[dict]:
        """Earnings calendar only: EARNINGS_CALENDAR returns CSV text.

        fmp covers dividends/ipo, so a non-earnings kind raises ProviderError
        and route_and_call falls back naturally. AV has no date params for this
        endpoint, so start/end filter rows in-process by `reportDate` (rows
        with unparseable dates are ignored).
        """
        if kind != "earnings":
            raise ProviderError(f"alphavantage: events kind {kind!r} not supported")
        url = f"{self._base}/query"
        try:
            text = await self._get_client().get_text(
                url, params={"function": "EARNINGS_CALENDAR", "apikey": self._apikey})
        except UpstreamError as e:
            raise UpstreamError(scrub(f"alphavantage: {e}", self._apikey)) from e
        # Same 200-body discipline as _get: a throttled EARNINGS_CALENDAR
        # returns a plain-text Note/Information JSON, not CSV.
        if text.lstrip().startswith("{"):
            try:
                data = json.loads(text)
            except ValueError as e:
                raise UpstreamError(f"alphavantage: non-CSV body from "
                                    f"{scrub(url, self._apikey)}") from e
            note = data.get("Note") or data.get("Information")
            if note:
                raise RateLimited(f"alphavantage: {scrub(str(note)[:200], self._apikey)} "
                                  f"[{_RATE_LIMIT_HINT}]")
            if data.get("Error Message"):
                raise NotFound("alphavantage: "
                               f"{scrub(str(data['Error Message'])[:200], self._apikey)}")
            raise NotFound(f"alphavantage: unexpected body from {scrub(url, self._apikey)}")
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
        if not rows or reader.fieldnames is None:
            raise NotFound(f"alphavantage: empty earnings calendar from "
                           f"{scrub(url, self._apikey)}")
        if start or end:
            rows = [r for r in rows if _in_window(r.get("reportDate"), start, end)]
        return rows
