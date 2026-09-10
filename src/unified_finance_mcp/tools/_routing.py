"""Market-aware source routing for unified tools. Never raises.

Never-raises scope (T10 M3 boundary, pinned by tests/test_invariants.py):
the candidate filter calls `providers[n].available()` / `.covers(market)` for
`n in chain` are guarded — chain names absent from `providers` are skipped,
and whatever these two methods raise is caught and folded into the returned
tool_error dict. Provider method bodies invoked via `call(p)` are NOT in
scope: exceptions there surface as the "all candidate sources failed"
tool_error dict. Callers may rely on: a dict is always returned; anything
outside the call(p) bodies is guarded.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from ..errors import tool_error
from ..providers.base import Provider


def _classify(e: Exception) -> str:
    return f"{getattr(e, 'kind', 'error')}: {str(e)[:200]}"


async def route_and_call(*, market: str, chain: list[str],
                         providers: dict[str, Provider],
                         call: Callable[[Provider], Awaitable[dict]],
                         explicit_source: str = "auto") -> dict:
    if explicit_source and explicit_source != "auto":
        p = providers.get(explicit_source)
        if p is None:
            return tool_error(f"unknown source {explicit_source!r}",
                              hint=f"known sources: {sorted(providers)}")
        if not p.available():
            return tool_error(f"source {explicit_source} not configured",
                              hint="configure its env, or use source='auto'")
        if not p.covers(market):
            return tool_error(f"source {explicit_source} does not cover market {market}",
                              hint="use source='auto' for market-aware routing")
        try:
            return await call(p)
        except Exception as e:  # noqa: BLE001
            return tool_error(_classify(e), source=explicit_source)
    candidates = [providers[n] for n in chain
                  if n in providers and providers[n].available() and providers[n].covers(market)]
    if not candidates:
        covering = [n for n in chain if n in providers and providers[n].covers(market)]
        return tool_error(
            f"no configured source covers market {market}",
            hint=(f"market {market} 可被 {', '.join(covering) or '无'} 覆盖；"
                  "配置对应 env 启用后重试"),
            market=market)
    source_errors: dict[str, str] = {}
    for p in candidates:
        try:
            return await call(p)
        except Exception as e:  # noqa: BLE001
            source_errors[p.name] = _classify(e)
    return tool_error("all candidate sources failed", source_errors=source_errors,
                      market=market)
