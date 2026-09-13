"""CEX USDT-perpetual provider: TradingView TA first, bare REST for the rest.

⚠️ 资产语义(防幻觉): 这里取的是 **USDT 计价的永续合约**(Bitget `CLUSDT` /
Gate `CL_USDT` / MEXC `OIL_USDT`,TradingView 上为 `CLUSDT.P`),**不是** NYMEX
交割原油期货(`CL=F` / `CL1!` / `NYMEX:CL1!`)。永续无到期日、价格靠资金费率
锚定标的;交割期货有到期与展期结构。两者价格、持仓量语义都不同,不要混用。

Two internal paths:
- **TV path** (quote/summary): `tradingview_ta.TA_Handler` with the screener
  pinned to the crypto screener slug (default `crypto`; `cfd`/`america` are
  live-verified to return "Exchange or symbol not found" for `CLUSDT.P`).
  Gives OHLCV + indicators + rating in one call.
- **Bare REST path** (kline/funding/open_interest): TA has no history and no
  derivatives data, so those go straight to the exchange REST endpoints through
  the shared `PoliteClient`, failing over in `settings.cex_exchanges` order.

This module owns its own symbol table: crypto symbols never go through
`symbols.parse_symbol` (its `_TV` map has no OKX/BITGET/BINANCE, so a CEX ticker
would be mis-routed to a stock market slug).
"""
from __future__ import annotations

from datetime import datetime, timezone

import anyio
from tradingview_ta import Interval, TA_Handler

from ..config import Settings
from ..errors import AuthError, NotFound, ProviderError, UpstreamError
from ..http import PoliteClient
from .base import Provider

# Crypto-perpetual screener slug — deliberately NOT imported from
# providers/tradingview.py (that table maps stock country slugs). Overridable
# via FINANCE_MCP_CEX_TV_SCREENER, but "crypto" is the only value the spike
# verified works for CLUSDT.P.
_TV_SCREENER = "crypto"

_INTERVAL = {"1m": Interval.INTERVAL_1_MINUTE, "5m": Interval.INTERVAL_5_MINUTES,
             "15m": Interval.INTERVAL_15_MINUTES, "1h": Interval.INTERVAL_1_HOUR,
             "4h": Interval.INTERVAL_4_HOURS, "1d": Interval.INTERVAL_1_DAY,
             "1wk": Interval.INTERVAL_1_WEEK, "1mo": Interval.INTERVAL_1_MONTH}

# interval -> native REST candle granularity (per exchange). MEXC does NOT
# have Min60 — the hourly grain is Hour1 (live-verified 2026-09-13).
_GRAN = {
    "bitget": {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H",
               "1d": "1D", "1wk": "1W", "1mo": "1M"},
    "gate": {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h",
             "1d": "1d", "1wk": "7d", "1mo": "30d"},
    "mexc": {"1m": "Min1", "5m": "Min5", "15m": "Min15", "1h": "Hour1",
             "4h": "Hour4", "1d": "Day1", "1wk": "Week1", "1mo": "Month1"},
}

# logical name -> the exchanges that list it, native contract id per exchange.
# MEXC renamed the WTI-crude perp from OIL_USDT to USOIL_USDT (verified live
# 2026-09-13: the old code 1001s, USOIL_USDT's displayName is "OIL(WTI)_USDT
# 永续"). UKOIL_USDT is Brent — a different asset, so it stays unmapped.
_NATIVE = {
    "bitget": {"CL": "CLUSDT", "BTC": "BTCUSDT", "ETH": "ETHUSDT"},
    "gate": {"CL": "CL_USDT", "BTC": "BTC_USDT", "ETH": "ETH_USDT"},
    "mexc": {"CL": "USOIL_USDT", "BTC": "BTC_USDT", "ETH": "ETH_USDT"},
    "okx": {"CL": "CLUSDT", "BTC": "BTCUSDT", "ETH": "ETHUSDT"},
    "binance": {"CL": "CLUSDT", "BTC": "BTCUSDT", "ETH": "ETHUSDT"},
}

# Raw spellings seen in the wild -> logical name. Aliases (mexc's OIL/USOIL)
# collapse onto the same logical name so failover can jump exchanges for one
# instrument. MEXC's USOIL_USDT is WTI crude — collapsing to CL is identity,
# not hallucination. XBR (Brent) and NG (natural gas) stay absent: mapping
# them onto WTI here would be exactly the wrong-asset hallucination this
# table exists to prevent.
_ALIASES = {
    "CL": "CL", "CLUSDT": "CL", "CL_USDT": "CL", "CL-USDT": "CL", "CL/USDT": "CL",
    "CLUDT": "CL", "OIL": "CL", "OILUSDT": "CL", "OIL_USDT": "CL", "OIL-USDT": "CL",
    "OIL/USDT": "CL", "WTI": "CL", "WTIUSDT": "CL",
    "USOIL": "CL", "USOILUSDT": "CL", "USOIL_USDT": "CL",
    "BTC": "BTC", "BTCUSDT": "BTC", "BTC_USDT": "BTC", "BTC-USDT": "BTC",
    "BTC/USDT": "BTC", "XBT": "BTC",
    "ETH": "ETH", "ETHUSDT": "ETH", "ETH_USDT": "ETH", "ETH-USDT": "ETH",
    "ETH/USDT": "ETH",
}

# Known hallucination / wrong-asset names: rejected here, the container turns
# the NotFound into a hint pointing at the `symbols` action. USOIL is NOT
# here — MEXC's live WTI contract is literally USOIL_USDT (identity, not
# hallucination), so it resolves to CL via _ALIASES. UKOIL stays rejected:
# it's Brent, a different asset.
_REJECTED = {"UKOIL", "UKOILUSDT", "US30", "SPX500", "XAUUSD", "CL1", "CL=F"}

# Bare-REST adapter table: base_url + per-action paths. Shapes are pinned in
# docs/superpowers/specs/2026-09-12-crypto-cex-design.md §1b.
_REST = {
    "bitget": {
        "base": "https://api.bitget.com",
        "candles": "/api/v2/mix/market/candles",
        "ticker": "/api/v2/mix/market/ticker",
    },
    "gate": {
        "base": "https://api.gateio.ws",
        "candles": "/api/v4/futures/usdt/candlesticks",
        "ticker": "/api/v4/futures/usdt/tickers",
    },
    "mexc": {
        "base": "https://contract.mexc.com",
        "candles": "/api/v1/contract/kline/{symbol}",
        # MEXC's per-contract ticker is the query form; the /{symbol} path 404s
        # even for BTC_USDT (live-verified 2026-09-13).
        "ticker": "/api/v1/contract/ticker",
    },
}

# Exchanges with a TradingView crypto-screener listing. gate/mexc are REST-only
# here, so a TV action for them is a NotFound the container can explain.
_TV_EXCHANGES = {"bitget": "BITGET", "okx": "OKX", "binance": "BINANCE"}


def normalize_symbol(raw: str) -> str:
    """Raw contract spelling (native / ccxt-style / alias) -> logical name.

    Raises NotFound for names that are known to be wrong asset entirely
    (USOIL, CL=F, ...): silently mapping those onto WTI crude would be exactly
    the hallucination this feature is meant to kill.
    """
    key = (raw or "").strip().upper()
    if not key:
        raise NotFound("cex: empty symbol")
    if key in _REJECTED:
        raise NotFound(f"cex: {key!r} is not a USDT perp contract "
                       f"(use the `symbols` action to list real contracts)")
    if "/" in key and ":" in key:          # ccxt form CL/USDT:USDT
        key = key.split("/")[0].strip()
    key = key.replace(".P", "")
    for suffix in ("_USDT", "-USDT", "/USDT", "USDT"):
        if key.endswith(suffix) and len(key) > len(suffix):
            key = key[: -len(suffix)]
            break
    logical = _ALIASES.get(key)
    if logical is None:
        raise NotFound(f"cex: unknown contract {raw!r}")
    return logical


def _native(exchange: str, logical: str) -> str:
    table = _NATIVE.get(exchange)
    if table is None:
        raise NotFound(f"cex: unknown exchange {exchange!r}")
    sym = table.get(logical)
    if sym is None:
        raise NotFound(f"cex: {logical} is not listed on {exchange}")
    return sym


def _tv_symbol(logical: str) -> str:
    """USDT perpetual on TradingView: `CLUSDT.P` (`.P` = perpetual)."""
    return f"{logical}USDT.P"


def _screener() -> str:
    """FINANCE_MCP_CEX_TV_SCREENER, falling back to the crypto slug."""
    from ..config import get_settings  # local: keeps module import side-effect free

    return get_settings().cex_tv_screener or _TV_SCREENER


def _get_analysis(exchange: str, symbol: str, interval: str):
    """Sync TV call; wrapped in anyio.to_thread by the caller.

    `symbol` is the already-suffixed TV ticker (CLUSDT.P). Signature is pinned
    to (exchange, symbol, interval) so tests/containers can substitute it with a
    plain 3-arg callable — the screener is resolved internally.
    """
    h = TA_Handler(symbol=symbol, exchange=exchange, screener=_screener(),
                   interval=_INTERVAL.get(interval, Interval.INTERVAL_1_DAY))
    return h.get_analysis()


def _iso(ms_or_s: object) -> str:
    """Exchange timestamps -> ISO-8601 UTC. Bitget sends ms, gate/mexc seconds.

    Unit detection is by magnitude, not by exchange: a seconds value is ~1.7e9
    and a milliseconds value ~1.7e12 today, so 1e11 (year 5138 in seconds,
    1973 in ms) is the split point. Anything that cannot be an epoch reaches the
    caller verbatim rather than raising — a malformed timestamp must not take
    down a whole kline response.
    """
    try:
        value = float(ms_or_s)
    except (TypeError, ValueError):
        return str(ms_or_s)
    if value >= 1e11:  # milliseconds
        value /= 1000.0
    try:
        return datetime.fromtimestamp(value, timezone.utc).isoformat()
    except (OverflowError, OSError, ValueError):
        return str(ms_or_s)


class CexProvider(Provider):
    name = "cex"
    markets = frozenset({"CRYPTO"})

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._client: PoliteClient | None = None

    def available(self) -> bool:
        return self.settings.cex_enabled

    def _get_client(self) -> PoliteClient:
        if self._client is None:
            self._client = PoliteClient(timeout=self.settings.request_timeout,
                                        max_retries=self.settings.max_retries,
                                        min_host_delay=self.settings.min_host_delay)
        return self._client

    def _chain(self, exchange: str) -> tuple[str, ...]:
        """Bare-REST failover order: start at the requested exchange, then the
        rest of settings.cex_exchanges in order. An exchange that is not
        whitelisted is a NotFound — we never call an unlisted venue.
        """
        enabled = tuple(self.settings.cex_exchanges)
        if exchange not in enabled:
            raise NotFound(f"cex: exchange {exchange!r} is not enabled "
                           f"(enabled: {list(enabled)})")
        start = enabled.index(exchange)
        return enabled[start:] + enabled[:start]

    async def _rest(self, exchange: str, action: str, logical: str,
                    params: dict | None = None) -> object:
        spec = _REST.get(exchange)
        if spec is None:  # TV-only exchange (okx/binance) has no bare adapter
            raise NotFound(f"cex: {exchange} has no REST adapter "
                           f"(kline/funding/OI are bitget/gate/mexc only)")
        native = _native(exchange, logical)
        path = spec["candles" if action == "candles" else "ticker"]
        url = spec["base"] + path.format(symbol=native)
        try:
            return await self._get_client().get_json(
                url, params=params or self._ticker_params(exchange, logical))
        except ValueError as e:
            raise UpstreamError(f"cex: non-JSON body from {exchange}") from e

    def _parse_rest(self, ex: str, action: str, raw: object) -> object:
        """Shape a bare-REST body into rows/ticker dict. Lives inside the
        failover loop so a parse-stage NotFound advances to the next venue
        (previously it leaked out past _rest_chain)."""
        if action == "candles":
            return self._parse_candles(ex, raw)
        return self._parse_ticker(ex, raw)

    async def _rest_chain(self, exchange: str, action: str, logical: str,
                          params_for) -> tuple[str, object]:
        """Try each whitelisted exchange in failover order; return (exchange, data).

        NotFound (404 / unlisted contract / parse-stage empty) advances to the
        next venue, as does AuthError — keyless exchanges often geo-block with a
        bare 401/403, and one venue's WAF must not freeze the whole chain. Any
        other non-retryable ProviderError is re-raised immediately.
        """
        last: ProviderError | None = None
        for ex in self._chain(exchange):
            try:
                raw = await self._rest(ex, action, logical, params_for(ex))
                return ex, self._parse_rest(ex, action, raw)
            except NotFound as e:
                last = e
            except AuthError as e:  # geo / WAF block → keep failing over
                last = e
            except ProviderError as e:
                last = e
                if not e.retryable:
                    raise
        raise last if last is not None else NotFound(f"cex: no data for {logical}")

    def _candle_params(self, ex: str, logical: str, interval: str, limit: int) -> dict:
        gran = _GRAN.get(ex, {}).get(interval)
        if gran is None:
            raise ProviderError(f"cex: interval {interval!r} unsupported on {ex}")
        native = _native(ex, logical)
        if ex == "bitget":
            return {"symbol": native, "productType": self.settings.cex_product,
                    "granularity": gran, "limit": limit}
        if ex == "gate":
            return {"contract": native, "interval": gran, "limit": limit}
        # mexc kline takes the contract in the path; it ignores `limit` and
        # always returns ~2000 bars (trimmed client-side by the caller).
        return {"interval": gran}

    def _ticker_params(self, ex: str, logical: str) -> dict:
        """One-contract ticker params. Bitget 400s without symbol+productType;
        gate returns ALL 981 contracts without `contract` (then data[0] is the
        wrong asset). Both live-verified 2026-09-13.
        """
        native = _native(ex, logical)
        if ex == "bitget":
            return {"symbol": native, "productType": self.settings.cex_product}
        if ex == "gate":
            return {"contract": native}
        return {"symbol": native}  # mexc: query form (path-style 404s)

    @staticmethod
    def _rows_from_columnar(data: object) -> list[dict]:
        """MEXC kline body `data` is columnar: {\"time\":[...], \"open\":[...],
        \"high\": [...], \"low\": [...], \"close\": [...], \"vol\": [...]} — zip the
        parallel arrays into row dicts. (Live-verified 2026-09-13.)"""
        if not isinstance(data, dict):
            return []
        t = data.get("time") or []
        o = data.get("open") or []
        h = data.get("high") or []
        lo = data.get("low") or []
        c = data.get("close") or []
        v = data.get("vol") or data.get("volume") or []
        rows = []
        for row in zip(t, o, h, lo, c, v):
            rows.append({"t": row[0], "o": row[1], "h": row[2],
                         "l": row[3], "c": row[4], "v": row[5]})
        return rows

    @staticmethod
    def _parse_candles(ex: str, data: object) -> list[dict]:
        rows = data
        if isinstance(rows, dict):  # bitget/mexc wrapper {"code","data"}
            if str(rows.get("code")) not in ("00000", "0", ""):
                raise NotFound(f"cex: {ex} candles error {rows.get('code')}")
            rows = rows.get("data") or []
        if isinstance(rows, dict):  # mexc columnar body, not a row list
            rows = CexProvider._rows_from_columnar(rows)
        if not isinstance(rows, list):
            raise UpstreamError(f"cex: unexpected candles shape from {ex}")
        out = []
        for r in rows:
            if isinstance(r, dict):  # gate (and mexc, post-zip): {t,o,h,l,c,v}
                out.append({"date": _iso(r.get("t")), "open": r.get("o"),
                            "high": r.get("h"), "low": r.get("l"),
                            "close": r.get("c"),
                            "volume": r.get("v", r.get("vol"))})
            elif isinstance(r, (list, tuple)) and len(r) >= 6:
                # bitget: [ts_ms, o, h, l, c, vol, turnover]
                out.append({"date": _iso(r[0]), "open": r[1], "high": r[2],
                            "low": r[3], "close": r[4], "volume": r[5]})
        if not out:
            raise NotFound(f"cex: {ex} returned no candles")
        return out

    @staticmethod
    def _parse_ticker(ex: str, data: object) -> dict:
        if isinstance(data, dict):  # bitget/mexc wrapper {"code","data"}
            if str(data.get("code")) not in ("00000", "0", ""):
                raise NotFound(f"cex: {ex} ticker error {data.get('code')}")
            inner = data.get("data")
            if isinstance(inner, list):  # bitget: data is a 1-element list
                data = inner[0] if inner else {}
            elif isinstance(inner, dict):  # mexc query form: data is the ticker
                data = inner
        elif isinstance(data, list):  # gate: bare list of tickers
            data = data[0] if data else {}
        if not isinstance(data, dict) or not data:
            raise NotFound(f"cex: {ex} ticker empty")
        # Defense-in-depth: a venue filter that silently widens (e.g. gate
        # returns ALL contracts, so data[0] is whatever sorted first — the C1
        # wrong-asset bug) must not pass as the requested contract. Fields:
        # bitget symbol/gate contract/mexc symbol.
        ident = (data.get("contract") or data.get("symbol")
                 or data.get("instrument_id"))
        if ident is not None and ident not in _NATIVE.get(ex, {}).values():
            raise NotFound(f"cex: {ex} ticker for {ident}, not a whitelisted "
                           f"contract")
        return data

    async def quote(self, exchange: str, logical: str, interval: str = "1d") -> dict:
        """TV snapshot; the bare ticker only adds `mark` (best-effort)."""
        logical = normalize_symbol(logical)
        tv_exchange = _TV_EXCHANGES.get(exchange)
        if tv_exchange is None:
            raise NotFound(f"cex: {exchange} has no TradingView crypto screener "
                           f"(TV path: {sorted(_TV_EXCHANGES)})")
        try:
            a = await anyio.to_thread.run_sync(
                _get_analysis, tv_exchange, _tv_symbol(logical), interval)
        except Exception as e:
            raise ProviderError(f"tradingview TA cex: {e}") from e
        ind = dict(a.indicators or {})
        out = {"symbol": logical, "exchange": exchange,
               "price": ind.get("close"), "mark": None,
               "open": ind.get("open"), "high": ind.get("high"),
               "low": ind.get("low"), "volume": ind.get("volume"),
               "change": ind.get("change"), "source": self.name}
        try:
            raw = await self._rest(exchange, "ticker", logical, {})
            tick = self._parse_ticker(exchange, raw)
        except ProviderError:
            return out  # mark is optional; never let the bare path break quote
        out["mark"] = (tick.get("markPrice") or tick.get("mark_price")
                       or tick.get("fairPrice") or tick.get("mark"))
        return out

    async def kline(self, exchange: str, logical: str, interval: str = "1d",
                    limit: int = 200) -> list[dict]:
        logical = normalize_symbol(logical)
        _ex, rows = await self._rest_chain(
            exchange, "candles", logical,
            lambda src: self._candle_params(src, logical, interval, limit))
        # MEXC ignores `limit` and always returns ~2000 bars; trim client-side.
        return rows[-limit:] if isinstance(rows, list) else rows

    async def funding(self, exchange: str, logical: str) -> dict:
        logical = normalize_symbol(logical)
        ex, tick = await self._rest_chain(exchange, "ticker", logical,
                                          lambda e: {})
        rate = (tick.get("fundingRate") or tick.get("funding_rate"))
        if rate is None:
            raise NotFound(f"cex: {ex} ticker has no funding rate")
        return {"symbol": logical, "funding_rate": rate, "source": self.name}

    async def open_interest(self, exchange: str, logical: str) -> dict:
        logical = normalize_symbol(logical)
        ex, tick = await self._rest_chain(exchange, "ticker", logical,
                                          lambda e: {})
        oi = (tick.get("holdingAmount") or tick.get("total_size")
              or tick.get("holdVol"))
        if oi is None:
            raise NotFound(f"cex: {ex} ticker has no open interest")
        return {"symbol": logical, "open_interest": oi, "source": self.name}

    async def summary(self, exchange: str, logical: str, interval: str = "1d") -> dict:
        """Same shape as TradingViewProvider.technicals (TV has no REST
        substitute here, so a TV failure is the error, not a failover)."""
        logical = normalize_symbol(logical)
        tv_exchange = _TV_EXCHANGES.get(exchange)
        if tv_exchange is None:
            raise NotFound(f"cex: {exchange} has no TradingView crypto screener "
                           f"(TV path: {sorted(_TV_EXCHANGES)})")
        if interval not in _INTERVAL:
            raise ProviderError(f"cex: interval {interval!r} unsupported "
                                f"(have {sorted(_INTERVAL)})")
        try:
            a = await anyio.to_thread.run_sync(
                _get_analysis, tv_exchange, _tv_symbol(logical), interval)
        except Exception as e:
            raise ProviderError(f"tradingview TA cex: {e}") from e
        return {"symbol": logical, "exchange": exchange, "interval": interval,
                "summary": a.summary, "oscillators": a.oscillators,
                "moving_averages": a.moving_averages,
                "indicators": {k: v for k, v in (a.indicators or {}).items()
                               if v is not None},
                "source": self.name}
