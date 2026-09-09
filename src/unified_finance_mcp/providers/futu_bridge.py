"""Mount futu-opend-mcp's tools and bridge unified calls into futu skills.

Facts verified against the installed futu_opend_mcp 0.1.2 package:
- ``skill_fn(category, name)`` returns a lazy SYNC callable; importing the
  skill script sys.exits when OpenD is unreachable, so the import is deferred
  until invocation.
- ``skill_runner._run_skill_json(fn, *args, **kwargs)`` (sync) captures the
  skill's stdout and returns a parsed dict: success payloads, or
  ``{"_skill_error": True, "error": ...}`` on failure (a dict carrying an
  ``error`` key is also stamped ``_skill_error``).
- ``get_snapshot(codes: list[str])`` takes PLURAL codes and returns
  ``{"data": [row, ...]}`; ``get_kline(code, ktype=..., ...)`` uses lowercase
  native ktype values (1m/3m/5m/15m/30m/60m/1d/1w/1M/1Q/1Y) and returns
  ``{"code": ..., "ktype": ..., "data": [bar, ...]}``.
- Availability uses the same env vars futu_opend_mcp itself reads
  (FUTU_OPEND_HOST/FUTU_OPEND_PORT, 127.0.0.1:11111), with a 5s cache so the
  readiness gate in build_mcp() doesn't TCP-connect per request.
"""

from __future__ import annotations

import logging
import os
import socket
import time

from ..errors import NotFound, ProviderError
from ..symbols import ParsedSymbol
from .base import Provider

log = logging.getLogger(__name__)

# unified interval -> futu native ktype (futu_opend_mcp/tools/quote.py docstring)
_KTYPE = {
    "1d": "1d",
    "1wk": "1w",
    "1mo": "1M",
    "1h": "60m",
    "30m": "30m",
    "15m": "15m",
    "5m": "5m",
    "1m": "1m",
}
_KLINE_ROW_KEY = "data"

_reach_cache: dict[tuple[str, int], tuple[float, bool]] = {}


def _opend_reachable(host: str, port: int) -> bool:
    """TCP-connect probe of OpenD; True on success, False on any OSError."""
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def opend_available() -> bool:
    """OpenD reachability with a 5s monotonic cache (same env vars futu reads)."""
    host = os.environ.get("FUTU_OPEND_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("FUTU_OPEND_PORT", "11111") or 11111)
    except ValueError:
        port = 11111
    key = (host, port)
    ts, ok = _reach_cache.get(key, (0.0, False))
    if time.monotonic() - ts > 5:
        ok = _opend_reachable(host, port)
        _reach_cache[key] = (time.monotonic(), ok)
    return ok


def FUTU_TOOLS_AVAILABLE() -> bool:
    """True when the futu_opend_mcp package imports in this environment."""
    try:
        import futu_opend_mcp  # noqa: F401
    except ImportError:
        return False
    return True


def mount_futu_tools(mcp) -> list[str]:
    """Re-register every futu-opend-mcp tool onto `mcp`; return mounted names.

    Importing ``futu_opend_mcp.tools`` fills the package's FastMCP singleton
    via @mcp.tool registration side effects. Importing that package in an
    environment without it would fail with ImportError, which server.py's
    guard swallows; inside the function we skip defensively instead, so a
    bare `build_mcp()` can still serve unified tools without futu.
    """
    if not FUTU_TOOLS_AVAILABLE():
        log.info("futu_opend_mcp not importable; no futu tools mounted")
        return []
    import futu_opend_mcp.tools  # noqa: F401 - registration side effect
    from futu_opend_mcp.tools import _base as futu_base

    mounted: list[str] = []
    existing = {t.name: t for t in mcp._tool_manager.list_tools()}
    for t in futu_base.mcp._tool_manager.list_tools():
        prev = existing.get(t.name)
        if prev is not None:
            if prev.fn is not t.fn:  # same fn = our own earlier mount: silent no-op
                log.warning("futu tool %r conflicts with unified tool, skipped", t.name)
            continue
        mcp.add_tool(t.fn, name=t.name, description=t.description, annotations=t.annotations)
        existing[t.name] = t
        mounted.append(t.name)
    log.info("mounted %d futu-opend-mcp tools", len(mounted))
    return mounted


def _run_skill(category: str, name: str, *args, **kwargs):
    """Run a futu-opend-mcp skill synchronously; returns its parsed result dict.

    Never raises for skill failures - they surface as ``_skill_error``.

    ``connection.get_context()`` must run before the skill: it is the only
    path that patches the vendored ``common`` module (encryption-aware
    ``create_quote_context`` honoring FUTU_OPEND_ENCRYPT/RSA key envs,
    ``check_ret`` raising ApiError, ``ensure_futu_api``/``safe_close``
    no-ops). Without it, an unpatched skill would create an UNENCRYPTED
    context against an encryption-expecting OpenD (package default
    FUTU_OPEND_ENCRYPT=true). An unreachable OpenD raises
    ``connection.ApiError`` here, mapped to ``_skill_error`` so providers
    surface it uniformly as ProviderError.
    """
    from futu_opend_mcp import connection, skill_runner
    from futu_opend_mcp.tools._base import skill_fn

    try:
        connection.get_context()
    except connection.ApiError as e:
        return {"_skill_error": True, "error": str(e)}
    return skill_runner._run_skill_json(skill_fn(category, name), *args, **kwargs)


def _skill_result(result: dict) -> dict:
    if result.get("_skill_error"):
        raise ProviderError(f"futu: {result['error']}")
    return result


class FutuProvider(Provider):
    name = "futu"
    markets = frozenset({"US", "HK", "CN", "SG", "MY", "JP"})

    def available(self) -> bool:
        return opend_available()

    async def quote(self, parsed: ParsedSymbol) -> dict:
        result = _skill_result(_run_skill("quote", "get_snapshot", [parsed.futu()]))
        rows = result.get("data")
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and row.get("code") == parsed.futu():
                    return row
            raise NotFound(f"futu: no snapshot row for {parsed.futu()}")
        if isinstance(result, dict) and parsed.futu() in result:
            return result[parsed.futu()]
        raise NotFound(f"futu: no snapshot data for {parsed.futu()}")

    async def history(
        self, parsed: ParsedSymbol, interval="1d", start=None, end=None
    ) -> list[dict]:
        ktype = _KTYPE.get(interval)
        if ktype is None:
            raise ProviderError(
                f"futu: unsupported interval {interval!r}; use one of {sorted(_KTYPE)}"
            )
        kwargs: dict = {"code": parsed.futu(), "ktype": ktype}
        if start:
            kwargs["start"] = start
        if end:
            kwargs["end"] = end
        result = _skill_result(_run_skill("quote", "get_kline", **kwargs))
        rows = result.get(_KLINE_ROW_KEY)
        if isinstance(rows, list):
            return rows
        if isinstance(result, list):
            return result
        raise ProviderError(f"futu: unexpected kline result shape: {type(result).__name__}")
