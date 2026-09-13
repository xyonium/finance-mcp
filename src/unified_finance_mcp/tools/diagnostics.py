"""get_service_status: read-only, fast health/coverage snapshot. Never raises.
Provider `available()`/`covers()` are cheap env/key checks; the FMP exchange
probe is reported from its 24h cache only (a fresh probe would be slow AND a
network write — this tool is read-only). `opend_available()` reuses the 5s
cached TCP probe from providers.futu_bridge. Kimi auth is reported as its
structural source (proxy / token / auth-file / deploy-error) — never the
value, and the auth file is never read (only a glob match via
`_auth_file_hit`, which checks that the pattern matches a path entry).

Ruling 1 (T9 R1 candidate): key/config problems are classified, not merged:
- `key: missing`          -> ConfigError (no key set) — not a deploy issue;
- `key: rotated-upstream` -> deploy-misconfiguration (a key-rotator base-url
  override injects the key upstream; if the override is present the placeholder
  key is expected, and upstream is responsible);
- provider-level `issue` marks deploy-misconfigurations only (rotator
  unreachable, kimi auth-file glob no-hit, futu OpenD unreachable).

Every status string passes errors.scrub with the configured key/token values
(a defensive scrub: no key/token value is emitted by design, so any rotation
of the values still leaks nothing).
"""
from __future__ import annotations

import logging
import time
from typing import Any

from ..config import DEFAULT_AV_BASE_URL, DEFAULT_FMP_BASE_URL, DEFAULT_MARKETAUX_BASE_URL
from ..errors import scrub
from ..providers import build_providers, futu_bridge
from ._sanitize import sanitize

log = logging.getLogger("unified_finance_mcp")

# module names listed by tools/__init__.ALL_MODULES (self + the 13 prior) —
# the full build_mcp surface, without importing each tool module here.
UNIFIED_MODULES = [
    "quote", "history", "fundamentals", "news", "technicals", "screener",
    "ownership", "calendar", "macro", "search", "intel", "containers",
    "backtest", "kimi", "diagnostics", "cex",
]
# canonical map of each unified module -> the tools it registers (verified
# against each module's register(); a drift here fails tests/test_diagnostics).
MODULE_TOOLS = {
    "quote": {"get_quote"},
    "history": {"get_history"},
    "fundamentals": {"get_company_info", "get_financial_report"},
    "news": {"get_news"},
    "technicals": {"get_technical_indicators"},
    "screener": {"run_screener"},
    "ownership": {"get_ownership"},
    "calendar": {"get_events_calendar"},
    "macro": {"get_economic_data"},
    "search": {"search_symbols"},
    "intel": {"get_symbol_intel"},
    "containers": {"tv_scan", "tv_analyze", "egx_market"},
    "backtest": {"quant_backtest"},
    "kimi": {"kimi_datasource", "get_company_risk_cn"},
    "diagnostics": {"get_service_status"},
    "cex": {"cex_market"},
}

_KEY_BASES = {
    "fmp": ("fmp_api_key", DEFAULT_FMP_BASE_URL, "fmp_base_url"),
    "alphavantage": ("alphavantage_api_key", DEFAULT_AV_BASE_URL, "alphavantage_base_url"),
    "marketaux": ("marketaux_api_token", DEFAULT_MARKETAUX_BASE_URL, "marketaux_base_url"),
}

_SCOUTED_MARKETS = ("US", "HK", "CN", "EG", "JP", "UK", "CA", "AU", "DE", "FR",
                    "SG", "MY", "GLOBAL", "FX", "CRYPTO")
_SECRET_ATTRS = ("fmp_api_key", "alphavantage_api_key",
                 "marketaux_api_token", "kimi_access_token")

_FMP_CACHE_TTL = 24 * 3600.0


def _auth_file_hit(pattern: str) -> str | None:
    """Glob the auth-file pattern; return the first existing path or None.

    Never reads file CONTENT (the cliproxy auth JSON is off-limits) — the
    glob hit is a structural fact. Callers may stub this out in tests.
    """
    import glob

    try:
        return next(iter(sorted(glob.glob(pattern))), None)
    except (OSError, TypeError):
        return None


def _kimi_auth(settings) -> dict:
    """Kimi auth SOURCE as a structural label — never the token value."""
    if settings.kimi_proxy_url:
        return {"source": "proxy"}
    if settings.kimi_access_token:
        return {"source": "token"}
    pattern = settings.kimi_auth_file
    if pattern:
        hit = _auth_file_hit(pattern)
        if hit is not None:
            return {"source": "auth-file", "file": hit}
        return {"source": "deploy-error",
                "detail": f"KIMI_AUTH_FILE={pattern!r} glob 无命中：检查 cliproxy 挂载或路径"}
    return {"source": "none"}


def _provider_entry(name: str, provider: Any, settings, secrets: tuple,
                    futu_enabled: bool = True) -> dict:
    entry: dict = {"available": False, "covers": []}
    key_cfg = _KEY_BASES.get(name)
    if key_cfg:
        key_attr, default_base, base_attr = key_cfg
        if getattr(settings, key_attr):
            entry["key"] = "set"
        elif getattr(settings, base_attr) != default_base:
            entry["key"] = "rotated-upstream"
            entry["base_override"] = True
            entry["base_url"] = scrub(str(getattr(settings, base_attr)), *secrets)
        else:
            entry["key"] = "missing"
    if name == "futu" and not futu_enabled:
        # Config choice, NOT a deploy error: no probe at all (fast/read-only).
        entry["available"] = False
        entry["issue"] = "disabled by config"
        return entry
    try:
        entry["available"] = bool(provider.available())
    except Exception as e:  # noqa: BLE001 - status never raises
        entry["issue"] = scrub(f"{type(e).__name__}: {e}", *secrets)
        return entry
    try:
        markets = provider.markets
        scouted = _SCOUTED_MARKETS if markets is None else markets
        entry["covers"] = sorted(scrub(str(m), *secrets)
                                 for m in scouted if provider.covers(m))
    except Exception as e:  # noqa: BLE001 - status never raises
        entry["issue"] = scrub(f"{type(e).__name__}: {e}", *secrets)
    if name == "kimi":
        # Label is structural; available() above is authoritative (it resolves
        # the auth file's disabled flag without any value being reported).
        entry["auth"] = _kimi_auth(settings)
        if entry["auth"]["source"] == "auth-file" and not entry["available"]:
            entry["issue"] = "auth-file 命中但不可用（可能 disabled）"
    elif name == "fmp":
        # The 24h probe cache only: read-only, no fresh probe (0 egress).
        try:
            cache = getattr(provider, "_exchanges_cache", None)
            probed = set(cache[1]) if cache else set()
            fresh = bool(cache) and time.monotonic() - cache[0] < _FMP_CACHE_TTL
        except (TypeError, IndexError):
            probed, fresh = set(), False
        entry["probed_exchanges"] = sorted(probed)
        if entry["available"] and fresh:
            entry["covers"] = sorted(set(entry["covers"]) | probed)
    elif name == "futu" and not entry["available"]:
        entry["issue"] = "OpenD 不可达（deploy-misconfiguration）"
    return entry


def _markets_matrix(providers, secrets) -> dict[str, list[str]]:
    matrix: dict[str, list[str]] = {}
    for market in _SCOUTED_MARKETS:
        covering = []
        for name, provider in providers.items():
            if name == "fmp":
                cache = getattr(provider, "_exchanges_cache", None)
                try:
                    if cache and market in cache[1] \
                            and time.monotonic() - cache[0] < _FMP_CACHE_TTL:
                        covering.append(name)
                        continue
                except (TypeError, IndexError):
                    pass
            try:
                if provider.covers(market):
                    covering.append(name)
            except Exception as e:  # noqa: BLE001 - hostile providers never raise out
                log.debug("coverage scout of %r failed: %s", name, e)
        matrix[market] = sorted(covering)
    return matrix


async def get_service_status(_providers: dict | None = None) -> dict:
    """Read-only service status: per-provider availability/coverage, the FMP
    cached exchange probe, kimi auth source (never the token value), futu
    OpenD reachability and the mounted tool counts. Never raises; no network
    I/O (the FMP probe is reported from its 24h cache only).
    """
    from ..config import get_settings

    settings = get_settings()
    providers = _providers if _providers is not None else build_providers(settings)
    secrets = tuple(getattr(settings, a, "") for a in _SECRET_ATTRS)
    entries = {name: _provider_entry(name, p, settings, secrets,
                                     settings.futu_enabled)
               for name, p in providers.items()}
    if settings.futu_enabled:
        try:
            reachable = futu_bridge.opend_available()
        except Exception:  # noqa: BLE001 - status never raises
            reachable = False
        futu = {"reachable": reachable,
                "mounted": 53 if futu_bridge.FUTU_TOOLS_AVAILABLE() else 0,
                "issue": None if reachable else "OpenD 不可达（deploy-misconfiguration）"}
        if "futu" in entries:
            entries["futu"]["available"] = reachable
            if not reachable and "issue" not in entries["futu"]:
                entries["futu"]["issue"] = futu["issue"]
    else:
        futu = {"reachable": None, "mounted": 0, "issue": None}
    unified = sum(len(MODULE_TOOLS[m]) for m in UNIFIED_MODULES)
    return sanitize({
        "providers": entries,
        "futu_opend": futu,
        "tools": {"unified": unified,
                  "futu_mounted": futu["mounted"],
                  "total": unified + futu["mounted"]},
        "markets": _markets_matrix(providers, secrets),
    })


def register(mcp, providers, settings) -> None:
    @mcp.tool(name="get_service_status")
    async def get_service_status_tool() -> dict:
        """Read-only service status: provider availability/coverage, FMP cached
        exchange probe, kimi auth source (never the token value), futu OpenD
        reachability and mounted tool counts. No network I/O.
        """
        return await get_service_status()
