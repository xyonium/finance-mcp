"""get_ownership: holder/insider ownership, yahoo first with fmp fallback.

kind vocabulary: major | institutional | mutualfund | insider_transactions |
insider_roster. fmp only knows institutional + insider ("insider" in fmp's
vocabulary = the tool's "insider_transactions", mapped in the closure); any
other (fmp, kind) pair raises NotFound in the closure so route_and_call falls
back to yahoo naturally.
"""
from __future__ import annotations

from ..errors import NotFound, tool_error
from ..symbols import parse_symbol
from ._routing import route_and_call

CHAIN = ["yahoo", "fmp"]

KINDS = ("major", "institutional", "mutualfund", "insider_transactions",
         "insider_roster")

# fmp's vocabulary is a subset; the tool kind -> fmp kind mapping.
_FMP_KIND = {"institutional": "institutional", "insider_transactions": "insider"}


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_ownership(symbol: str, kind: str = "major",
                            source: str = "auto") -> dict:
        """Ownership breakdown for one symbol.

        `kind` is major (top holders) | institutional | mutualfund |
        insider_transactions | insider_roster. `source` may be auto | yahoo |
        fmp (fmp covers institutional and insider_transactions only). Accepts
        futu (HK.00700), yahoo (0700.HK, COMI.CA) or TradingView (EGX:COMI)
        symbol forms; bare tickers default to US. Returns {"data": [row, ...]}
        on success, or the routing error dict at the top level on failure —
        callers check `"error" in out`.
        """
        if kind not in KINDS:
            return tool_error(f"unknown ownership kind {kind!r}",
                              hint="kind 可用: " + "|".join(KINDS))
        try:
            parsed = parse_symbol(symbol)
        except ValueError as e:
            return tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                           "COMI.CA / EGX:COMI / AAPL")

        async def call(p):
            if p.name == "fmp" and kind not in _FMP_KIND:
                # fmp does not support this kind: NotFound makes route_and_call
                # fall through to yahoo instead of surfacing a ProviderError.
                raise NotFound(f"fmp: ownership kind {kind!r} not supported")
            provider_kind = _FMP_KIND.get(kind, kind) if p.name == "fmp" else kind
            return await p.ownership(parsed, provider_kind)

        rows = await route_and_call(market=parsed.market, chain=CHAIN,
                                    providers=providers, call=call,
                                    explicit_source=source)
        return rows if "error" in rows else {"data": rows}
