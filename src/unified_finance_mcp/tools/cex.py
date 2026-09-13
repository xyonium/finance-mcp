"""cex_market container: one action-routed surface over CexProvider.

Routes `quote|kline|summary|funding|open_interest|exchanges|symbols` to the
matching provider method. Like every container here, this layer never raises:
any provider failure — 404 / rate-limit / 5xx / unexpected RuntimeError — is
flattened into a `tool_error(..., source="cex")` dict.

Asset-semantics warning lives in the plan-mandated docstring (Task 4): the CL
quoted here is a USDT-settled *perpetual* (funding rate, 24/7), NOT the USD
deliverable future CL=F (yahoo) / NYMEX:CL1! (TradingView).
"""
from __future__ import annotations

from ..config import get_settings
from ..errors import NotFound, ProviderError, tool_error
from ..providers.cex import _NATIVE, normalize_symbol

_ACTIONS = ("quote", "kline", "summary", "funding", "open_interest",
            "exchanges", "symbols")

# Module-level injection point; register() closes over the real providers dict
# and tests pass a fake via the `providers=` kwarg instead.
_PROVIDERS: dict | None = None


def _clamp_limit(limit, minimum=1, maximum=200) -> int:
    """Same clamp idiom as containers.py; garbage -> the floor."""
    try:
        return max(minimum, min(int(limit), maximum))
    except (TypeError, ValueError):
        return minimum


def _resolve(explicit):
    """Call-site providers override, else the register()-installed module ref."""
    if explicit is not None:
        return explicit
    if _PROVIDERS is not None:
        return _PROVIDERS
    return {}


async def cex_market(action: str, symbol: str = "CL", exchange: str = "bitget",
                     interval: str = "1d", limit: int = 200,
                     providers: dict | None = None) -> dict:
    """CEX (crypto exchange) USDT-settled perpetual market data: quote / kline /
    technical summary / funding / open interest.

    action: quote|kline|summary|funding|open_interest|exchanges|symbols.
    symbol: a logical name like CL (WTI crude) or OIL or USOIL, an exchange-native
    form (CLUSDT / CL_USDT / USOIL_USDT), or ccxt-style "CL/USDT:USDT".
    exchange: bitget (default) | gate | mexc  — these three are whitelisted by
    default. okx | binance are quote/summary (TradingView) only and must be
    opted in via FINANCE_MCP_CEX_EXCHANGES.

    IMPORTANT — do not confuse with deliverable futures:
    - CL here is a USDT-settled PERPETUAL (24/7, carries a funding rate), NOT the
      USD deliverable future CL=F (yahoo) or NYMEX:CL1! (TradingView). Pick by need.
    - Unsure of the exact symbol? action="symbols" first, then quote.
    - funding/open_interest come from the exchange REST (TA has no such fields);
      quote/summary come from TradingView (screener=crypto).
    """
    if not isinstance(action, str) or action not in _ACTIONS:
        return tool_error(f"unknown action {action!r}",
                          hint=f"可用 action: {sorted(_ACTIONS)}", source="cex")

    if action == "exchanges":
        return {"data": {"exchanges": list(get_settings().cex_exchanges)},
                "source": "cex"}
    if action == "symbols":
        # exchange 优先,防止 exchange=kraken 时 KeyError 穿透 never-raise
        table = _NATIVE.get(exchange) or {}
        return {"data": {"exchange": exchange, "contracts": table},
                "source": "cex"}

    if not isinstance(symbol, str) or not symbol.strip():
        return tool_error("symbol is required for cex_market",
                          hint="e.g. CL / OIL_USDT / CL/USDT:USDT — "
                               "run action=\"symbols\" to list real contracts",
                          source="cex")
    try:
        logical = normalize_symbol(symbol)
    except NotFound as e:
        return tool_error(str(e),
                          hint="run action=\"symbols\" to list real contracts",
                          source="cex")

    enabled = get_settings().cex_exchanges
    if exchange not in enabled:
        return tool_error(f"exchange {exchange!r} is not enabled",
                          hint=f"可用 exchange: {sorted(enabled)} "
                               f"(FINANCE_MCP_CEX_EXCHANGES)", source="cex")

    cex = _resolve(providers).get("cex")
    if cex is None:
        return tool_error("cex provider not configured",
                          hint="FINANCE_MCP_CEX=1 (default on)", source="cex")
    try:
        if action == "quote":
            data = await cex.quote(exchange, logical)
        elif action == "kline":
            data = await cex.kline(exchange, logical, interval=interval,
                                   limit=_clamp_limit(limit))
        elif action == "summary":
            data = await cex.summary(exchange, logical, interval=interval)
        elif action == "funding":
            data = await cex.funding(exchange, logical)
        else:  # open_interest
            data = await cex.open_interest(exchange, logical)
    except ProviderError as e:
        # Keep the taxonomy kind (rate_limited / not_found / unavailable).
        return tool_error(f"{e.kind}: {str(e)[:200]}", source="cex")
    except Exception as e:  # noqa: BLE001 - containers never raise
        return tool_error(f"{action}: {type(e).__name__}: {str(e)[:200]}",
                          source="cex")
    return {"data": data, "source": "cex"}


def register(mcp, providers, settings) -> None:
    global _PROVIDERS
    _PROVIDERS = providers

    @mcp.tool(name="cex_market")
    async def cex_market_tool(action: str, symbol: str = "CL",
                              exchange: str = "bitget", interval: str = "1d",
                              limit: int = 200) -> dict:
        """CEX USDT-perp market data by action (see cex_market docstring)."""
        return await cex_market(action, symbol, exchange, interval, limit,
                                providers=providers)
