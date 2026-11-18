"""Market-aware source routing for unified tools. Never raises.

Never-raises scope (T10 M3 boundary, pinned by tests/test_invariants.py):
the candidate-filter calls `providers[n].available()` / `.covers(market)` are
NOT wrapped in try/except (candidate list comp and the explicit-source
guard) — an exception raised by either propagates to the caller. The
"Never raises" contract therefore holds only on the convention that
available()/covers() never raise (all registry providers comply: no network
I/O; local cached probe/file read, never raises). Only `call(p)` bodies are
caught and folded into the returned tool_error dict ("all candidate sources
failed" / explicit-source tool_error). Chain names absent from `providers`
are skipped, and unknown/explicit-source configuration problems return
tool_error dicts.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from ..errors import tool_error
from ..providers.base import Provider


def _classify(e: Exception) -> str:
    return f"{getattr(e, 'kind', 'error')}: {str(e)[:200]}"


_DRIFT_HINT = ("上游返回的结构与适配层预期不符（疑似接口漂移，不是网络/限流问题，"
               "重试通常无效）。请告知用户：联系管理员核查该源的 provider 适配层。")


def _drift_sources(source_errors: dict[str, str]) -> list[str]:
    return [name for name, msg in source_errors.items()
            if msg.startswith("upstream_drift:")]


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
            out = tool_error(_classify(e), source=explicit_source)
            if getattr(e, "kind", "") == "upstream_drift":
                out.update(hint=_DRIFT_HINT, action="contact_admin",
                           drifted_sources=[explicit_source])
            return out
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
    extra: dict = {"source_errors": source_errors, "market": market}
    drifted = _drift_sources(source_errors)
    if drifted:
        extra.update(hint=_DRIFT_HINT, action="contact_admin",
                     drifted_sources=drifted)
    return tool_error("all candidate sources failed", **extra)
