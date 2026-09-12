"""get_technical_indicators: TradingView default, Alpha Vantage per-indicator fallback.

auto routing: tradingview first (its `indicators` dict already holds the full
set — subset by requested name, with "MACD" matching tv's dotted keys
MACD.macd / MACD.signal / MACD.hist). When tv fails, alphavantage is asked per
indicator (av.technicals is single-indicator) and the series are aggregated.
`summary` means every canonical AV indicator on fallback, or the untouched tv
payload on success. tv is the only member of the route_and_call chain; av is
always reached through _av_aggregate so its (parsed, indicator, interval)
signature never collides with tv's (parsed, interval).
"""
from __future__ import annotations

from ..errors import tool_error
from ..providers.alphavantage import _TECHNICALS
from ..symbols import parse_symbol
from ._routing import route_and_call
from ._sanitize import sanitize

TV_CHAIN = ["tradingview"]

# The AV vocabulary that `summary` aggregates when tv is unavailable.
CANONICAL_TECHNICALS = frozenset(_TECHNICALS)

_REPORT_HINT = ("请检查上游源；indicators 只能是 RSI,MACD,SMA,EMA,BBANDS,STOCH,"
                "ADX,CCI,AROON,OBV（无 ATR），且不要和 summary 混传；期货/商品符号请用 "
                "source='auto' 走 tradingview，alphavantage 不覆盖")


# _parse_indicators sentinel for the "summary" mode (vs None = empty/invalid).
SUMMARY = object()


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_technical_indicators(symbol: str, indicators: str = "summary",
                                       interval: str = "1d", source: str = "auto") -> dict:
        """Technical indicators for one symbol: ratings summary + indicator values.

        `indicators` is either `"summary"` (default: TradingView ratings +
        oscillator/moving-average values) OR a comma list of indicator names.
        Do NOT mix them — pass `"summary"` alone, or names without "summary".

        Valid indicator names (anything else is rejected): RSI, MACD, SMA, EMA,
        BBANDS, STOCH, ADX, CCI, AROON, OBV. There is no "ATR". Wrong example:
        indicators="summary,RSI,MACD,ATR" → every entry fails. Right:
        indicators="summary"  or  indicators="RSI,MACD,SMA".

        `interval` is 1m/5m/15m/1h/4h/1d/1wk/1mo. `source` may be auto |
        tradingview | alphavantage. Prefer source="auto"/"tradingview":
        TradingView computes all indicators in one call for any symbol
        (including futures like CL=F and EGX). The alphavantage fallback is
        per-indicator, covers only its equity/forex universe (futures/commodity
        symbols like CL=F return not_found), and is rate-limited — don't send
        long indicator lists through it.

        Accepts futu (HK.00700), yahoo (0700.HK, COMI.CA) or TradingView
        (EGX:COMI) symbol forms; bare tickers default to US. Returns
        {"data": {...}} on success, or the routing error dict at the top level
        on failure — callers check `"error" in out`.
        """
        wanted = _parse_indicators(indicators)
        if wanted is None:
            return tool_error("empty indicators list",
                              hint="use 'summary' or a comma list of indicator names")
        try:
            parsed = parse_symbol(symbol)
        except ValueError as e:
            return tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                           "COMI.CA / EGX:COMI / AAPL")
        if source == "alphavantage":
            return await _av_aggregate(parsed, wanted, interval, providers)
        if source not in ("auto", "tradingview"):
            return tool_error(f"unknown source {source!r}",
                              hint="source 可用: auto|tradingview|alphavantage")
        tv = await route_and_call(
            market=parsed.market, chain=TV_CHAIN, providers=providers,
            call=lambda p: p.technicals(parsed, interval), explicit_source=source)
        if "error" not in tv:
            tv = sanitize(tv)
            if wanted is not SUMMARY:  # explicit list: subset tv's indicators
                inds = tv.get("indicators") or {}
                picked = {k: v for k, v in inds.items()
                          if any(k == w or k.startswith(w + ".") for w in wanted)}
                tv["indicators"] = picked
                tv["requested_indicators"] = wanted
            return {"data": tv}
        if source == "tradingview":
            return tv  # explicit choice: no silent av fallback
        if wanted is SUMMARY:
            # summary with tv down: aggregate every canonical AV indicator.
            wanted = sorted(CANONICAL_TECHNICALS)
        out = await _av_aggregate(parsed, wanted, interval, providers)
        if "error" in out:
            out["tradingview_error"] = tv.get("error", "")
        return out


def _parse_indicators(indicators: str):
    if not indicators.strip():
        return None
    if indicators.strip().lower() == "summary":
        return SUMMARY
    parts = [p.strip().upper() for p in indicators.split(",") if p.strip()]
    return parts or None


async def _av_aggregate(parsed, wanted, interval, providers) -> dict:
    if wanted is SUMMARY:
        wanted = sorted(CANONICAL_TECHNICALS)
    if not providers["alphavantage"].available():
        return tool_error("no indicator source available",
                          hint="tradingview failed and alphavantage is not configured")
    if not providers["alphavantage"].covers(parsed.market):
        return tool_error(f"alphavantage does not cover market {parsed.market}",
                          hint="use source='auto' for market-aware routing")
    av = providers["alphavantage"]
    results: dict[str, dict] = {}
    failures: list[str] = []
    for ind in wanted:
        try:
            results[ind] = await av.technicals(parsed, ind, interval)
        except Exception as e:  # noqa: BLE001 - one bad indicator must not sink the rest
            failures.append(f"{ind}: {getattr(e, 'kind', 'error')}: {str(e)[:120]}")
    if not results:
        return tool_error(f"all requested indicators failed for {parsed.local}",
                          hint=_REPORT_HINT, failures=failures)
    first = next(iter(results.values()))
    merged = {"symbol": first.get("symbol", parsed.local),
              "interval": interval,
              "indicators": {ind: results[ind]["series"] for ind in sorted(results)},
              "requested_indicators": wanted,
              "source": "alphavantage"}
    if failures:
        merged["partial_failures"] = failures
    return {"data": sanitize(merged)}
