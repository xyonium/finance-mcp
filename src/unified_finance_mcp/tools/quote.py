"""get_quote: latest price snapshot, auto-routed by market."""
from __future__ import annotations

from ..errors import tool_error
from ..symbols import parse_symbol
from ._routing import route_and_call

CHAIN = ["futu", "yahoo", "fmp", "alphavantage"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_quote(codes: list[str], source: str = "auto") -> dict:
        """Get latest price/quote snapshot for one or more symbols.

        Accepts futu (HK.00700), yahoo (0700.HK, COMI.CA) or TradingView
        (EGX:COMI) symbol forms; bare tickers default to US. `source` may be
        auto | futu | yahoo | fmp | alphavantage.

        IMPORTANT (read before batching):
        - Result is per-symbol partial: each key in `data` either holds a quote
          or an `error` + `source_errors` block. One symbol failing does NOT
          fail the others — check each entry, don't discard the whole batch.
        - Use REAL tickers, not display names/descriptions. `USOIL` is not a
          tradable symbol anywhere (no source covers it). For WTI crude use
          the futures `CL=F` or the ETF `USO`; brent is `BZ=F`. Unsure of the
          ticker? Call `search_symbols` first.
        - Example: codes=["AAPL", "HK.00700", "CL=F"].
        """
        out: dict[str, dict] = {}
        for code in codes:
            try:
                parsed = parse_symbol(code)
            except ValueError as e:
                out[code] = tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                                    "COMI.CA / EGX:COMI / AAPL")
                continue
            out[code] = await route_and_call(
                market=parsed.market, chain=CHAIN, providers=providers,
                call=lambda p, _s=parsed: p.quote(_s), explicit_source=source)
        return {"data": out}
