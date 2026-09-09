"""Yahoo Finance via yfinance (sync lib -> anyio.to_thread). Keyless, global."""
from __future__ import annotations

import anyio.to_thread
import yfinance as yf

from ..errors import ProviderError
from ..symbols import ParsedSymbol
from .base import Provider

_STMT = {"income": "get_income_stmt", "balance": "get_balance_sheet",
         "cashflow": "get_cashflow"}
_HOLDER = {"major": "major_holders", "institutional": "institutional_holders",
           "mutualfund": "mutualfund_holders",
           "insider_transactions": "insider_transactions",
           "insider_roster": "insider_roster_holders"}


class YahooProvider(Provider):
    name = "yahoo"
    markets = None  # global fallback

    async def _ticker(self, parsed: ParsedSymbol):
        return yf.Ticker(parsed.yahoo())

    @staticmethod
    async def _run(fn, *args, **kwargs):
        try:
            return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
        except Exception as e:  # yfinance raises bare Exception subclasses
            raise ProviderError(f"yahoo: {e}") from e

    async def quote(self, parsed: ParsedSymbol) -> dict:
        t = await self._ticker(parsed)
        # Read every key inside the worker thread: FastInfo fetches lazily per key, so
        # iterating/indexing it on the event loop would block. FastInfo.get() exposes
        # camelCase keys; snake_case is read too for dict-shaped / older yfinance results.
        keys = ("lastPrice", "last_price", "currency", "marketCap", "market_cap")
        info = await self._run(lambda: {k: t.fast_info.get(k) for k in keys})
        return {"symbol": parsed.yahoo(),
                "price": info.get("lastPrice") or info.get("last_price"),
                "currency": info.get("currency"),
                "market_cap": info.get("marketCap") or info.get("market_cap"),
                "source": self.name}

    async def history(self, parsed, interval="1d", start=None, end=None) -> list[dict]:
        t = await self._ticker(parsed)
        df = await self._run(t.history, interval=interval, start=start, end=end)
        if df is None or df.empty:
            return []
        df = df.reset_index()
        df.columns = [str(c).lower() for c in df.columns]
        # yfinance names the index Date (daily) or Datetime (intraday); "index" if unnamed.
        date_col = next((c for c in ("date", "datetime", "index") if c in df.columns), None)
        if date_col is None:
            raise ProviderError("yahoo: history frame has no date column")
        df[date_col] = df[date_col].astype(str).str[:10]
        keep = [date_col, "open", "high", "low", "close", "volume"]
        out = df[[c for c in keep if c in df.columns]].rename(columns={date_col: "date"})
        return out.to_dict("records")

    async def company_info(self, parsed) -> dict:
        t = await self._ticker(parsed)
        return dict(await self._run(lambda: t.info))

    async def financial_report(self, parsed, statement, period) -> list[dict]:
        t = await self._ticker(parsed)
        if statement not in _STMT:
            raise ProviderError(f"yahoo: unknown statement {statement!r}")
        fn = getattr(t, _STMT[statement])
        df = await self._run(fn, freq="yearly" if period == "annual" else "quarterly")
        if df is None or df.empty:
            return []
        return [dict({"date": str(c)[:10]}, **{str(k): v for k, v in df[c].dropna().items()})
                for c in df.columns]

    async def news(self, parsed, limit=10) -> list[dict]:
        t = await self._ticker(parsed)
        items = await self._run(lambda: t.news) or []
        return [self._news_item(i) for i in items[:limit]]

    def _news_item(self, item: dict) -> dict:
        # yfinance >=1.0 nests article fields under "content"; older versions were flat.
        c = item.get("content") or item
        provider = c.get("provider") or {}
        link = c.get("link") or c.get("previewUrl") or (c.get("canonicalUrl") or {}).get("url")
        return {"title": c.get("title"),
                "publisher": c.get("publisher") or provider.get("displayName"),
                "link": link,
                "published": c.get("providerPublishTime") or c.get("pubDate"),
                "source": self.name}

    async def ownership(self, parsed, kind) -> list[dict]:
        t = await self._ticker(parsed)
        if kind not in _HOLDER:
            raise ProviderError(f"yahoo: unknown ownership kind {kind!r}")
        df = await self._run(lambda: getattr(t, _HOLDER[kind]))
        if df is None or (hasattr(df, "empty") and df.empty):
            return []
        return df.reset_index().astype(str).to_dict("records")

    async def search(self, query, limit=10) -> list[dict]:
        s = await self._run(lambda: yf.Search(query, max_results=limit))
        return [{"symbol": q.get("symbol"), "name": q.get("shortname") or q.get("longname"),
                 "exchange": q.get("exchange"), "type": q.get("quoteType"),
                 "source": self.name} for q in (s.quotes or [])]
