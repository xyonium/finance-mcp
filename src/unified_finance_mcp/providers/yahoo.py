"""Yahoo Finance via yfinance (sync lib -> anyio.to_thread). Keyless, global."""
from __future__ import annotations

import anyio.to_thread
import pandas as pd
import yfinance as yf

from ..errors import NotFound, ProviderError
from ..symbols import ParsedSymbol
from .base import Provider

_STMT = {"income": "get_income_stmt", "balance": "get_balance_sheet",
         "cashflow": "get_cashflow"}
_HOLDER = {"major": "major_holders", "institutional": "institutional_holders",
           "mutualfund": "mutualfund_holders",
           "insider_transactions": "insider_transactions",
           "insider_roster": "insider_roster_holders",
           "insider_summary": "insider_summary"}  # handled separately, not a df property


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
        if kind == "insider_summary":
            # Insider summary is not a DataFrame property: pull Purchases/Sales
            # from `insider_purchases` (pandas df) and collapse to one dict.
            df = await self._run(lambda: t.insider_purchases)
            if df is None or (hasattr(df, "empty") and df.empty):
                return []
            row = df.iloc[0].to_dict()
            return [{"symbol": parsed.yahoo(),
                     "net_sh_activity": row.get("Net Sh Activity"),
                     "net_percent": row.get("Net %"),
                     "purchases": row.get("Purchases"),
                     "sales": row.get("Sales"),
                     "source": self.name}]
        df = await self._run(lambda: getattr(t, _HOLDER[kind]))
        if df is None or (hasattr(df, "empty") and df.empty):
            return []
        return df.reset_index().astype(str).to_dict("records")

    async def search(self, query, limit=10) -> list[dict]:
        s = await self._run(lambda: yf.Search(query, max_results=limit))
        return [{"symbol": q.get("symbol"), "name": q.get("shortname") or q.get("longname"),
                 "exchange": q.get("exchange"), "type": q.get("quoteType"),
                 "source": self.name} for q in (s.quotes or [])]

    async def option_chain(self, parsed: ParsedSymbol,
                           expiration: str | None = None) -> dict:
        t = await self._ticker(parsed)
        expirations = await self._run(lambda: t.options)
        if not expirations:
            raise NotFound(f"yahoo: no options listed for {parsed.yahoo()}")
        chosen = expiration or expirations[0]
        if chosen not in expirations:
            raise NotFound(
                f"yahoo: expiration {chosen!r} not available "
                f"(have: {', '.join(expirations[:6])}{'...' if len(expirations) > 6 else ''})")
        oc = await self._run(t.option_chain, chosen)
        if oc is None or (oc.calls is None and oc.puts is None):
            raise NotFound(f"yahoo: empty option chain for {parsed.yahoo()} {chosen}")
        # All NaN/NaT/Timestamp-normalization happens inside the worker thread:
        # namedtuple fields are pandas DataFrames whose cells are numpy scalars,
        # un-JSON-serializable outside to_thread conversion.
        return await self._run(self._option_payload, oc, chosen, list(expirations),
                               parsed.yahoo())

    @staticmethod
    def _option_payload(oc, expiration: str, available: list[str], yahoo: str) -> dict:
        def rows(df):
            return [] if df is None or df.empty else df.where(pd.notna(df), None).to_dict("records")

        underlying = oc.underlying or {}
        return {"underlying": yahoo,
                "quote": {"price": underlying.get("regularMarketPrice"),
                          "currency": underlying.get("currency"),
                          "exchange": underlying.get("fullExchangeName"),
                          "name": underlying.get("shortName") or underlying.get("longName")},
                "expiration": expiration,
                "available_expirations": available,
                "calls": rows(oc.calls),
                "puts": rows(oc.puts),
                "source": "yahoo"}

    async def short_interest(self, parsed: ParsedSymbol) -> dict:
        t = await self._ticker(parsed)
        info = await self._run(lambda: t.info)
        keys = ("sharesShort", "sharesShortPriorMonth", "shortRatio",
                "shortPercentOfFloat", "shortPercentOfSharesOutstanding",
                "dateShortInterest", "sharesFloat", "sharesOutstanding",
                "heldPercentInsiders", "heldPercentInstitutions")
        if all(info.get(k) is None for k in keys[:5]):
            raise NotFound(f"yahoo: no short-interest data for {parsed.yahoo()}")
        return {"symbol": parsed.yahoo(),
                "shares_short": info.get("sharesShort"),
                "shares_short_prior_month": info.get("sharesShortPriorMonth"),
                "short_ratio": info.get("shortRatio"),
                "short_percent_of_float": info.get("shortPercentOfFloat"),
                "short_percent_of_shares_outstanding": info.get("shortPercentOfSharesOutstanding"),
                "date_short_interest": info.get("dateShortInterest"),
                "shares_float": info.get("sharesFloat"),
                "shares_outstanding": info.get("sharesOutstanding"),
                "held_percent_insiders": info.get("heldPercentInsiders"),
                "held_percent_institutions": info.get("heldPercentInstitutions"),
                "source": self.name}

    async def analyst_estimates(self, parsed: ParsedSymbol) -> dict:
        t = await self._ticker(parsed)

        def fetch_all():
            pt = t.analyst_price_targets or {}
            def df_to_records(df):
                if df is None or (hasattr(df, "empty") and df.empty):
                    return []
                return df.reset_index().where(pd.notna(df), None).to_dict("records")
            return {"price_targets": pt,
                    "earnings_estimate": df_to_records(t.earnings_estimate),
                    "revenue_estimate": df_to_records(t.revenue_estimate),
                    "growth_estimates": df_to_records(t.growth_estimates),
                    "eps_trend": df_to_records(t.eps_trend),
                    "recommendations": df_to_records(t.recommendations)[:20]}

        out = await self._run(fetch_all)
        if not out["price_targets"] and not out["earnings_estimate"]:
            raise NotFound(f"yahoo: no analyst estimates for {parsed.yahoo()}")
        return {"symbol": parsed.yahoo(), **out, "source": self.name}
