"""T16 get_service_status diagnostics.

Hermetic (T10-C1): the autouse fixture installs an in-process getaddrinfo
guard and stubs futu reachability, so NO test may open a socket or resolve
DNS; provider probes are mocked (or proven not to fire). The double-run
harness runs this file in a fresh process keyless AND with dummy keys +
dummy KIMI_PROXY_URL — results must be identical, 0 egress.

No key/token value may appear in any status output (structural labels only).
"""
from __future__ import annotations

import socket
import time

import pytest

from unified_finance_mcp import tools as tools_pkg
from unified_finance_mcp.config import get_settings
from unified_finance_mcp.providers import build_providers, futu_bridge
from unified_finance_mcp.tools import diagnostics


def _getaddrinfo_fail(*args, **kwargs):
    raise AssertionError(f"network resolution attempted: {args[:2]}")


@pytest.fixture(autouse=True)
def _hermetic_env(monkeypatch):
    """Blanket hermeticity: no DNS, no futu socket, no ambient credentials."""
    futu_bridge._reach_cache.clear()
    monkeypatch.setattr(futu_bridge, "opend_available", lambda: False)
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo_fail)
    for k in ("FMP_API_KEY", "FMP_BASE_URL", "ALPHAVANTAGE_API_KEY",
              "ALPHAVANTAGE_BASE_URL", "MARKETAUX_API_TOKEN",
              "MARKETAUX_BASE_URL", "KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN",
              "KIMI_AUTH_FILE", "FINANCE_MCP_FUTU"):
        monkeypatch.delenv(k, raising=False)


def _capture(results):
    class FakeMCP:
        def tool(self, name=None):
            def deco(fn):
                results[name or fn.__name__] = fn
                return fn
            return deco
    return FakeMCP()


def _register():
    results = {}
    diagnostics.register(_capture(results), None, get_settings())
    return results["get_service_status"]


def _mock_kimi(monkeypatch, source):
    """Force the kimi auth branch; _auth_file_hit is stubbed (never real
    files). `available()` is forced too — hermetic, no real auth resolution.

    Returns the providers dict (build_providers is stubbed onto diagnostics).
    """
    hit = None
    if source == "proxy":
        monkeypatch.setenv("KIMI_PROXY_URL", "http://127.0.0.1:8765/kimi")
    elif source == "token":
        monkeypatch.setenv("KIMI_ACCESS_TOKEN", "dummy-kimi-token")
    elif source == "auth-file":
        monkeypatch.setenv("KIMI_AUTH_FILE", "/tmp/kimi-*.json")
        hit = "/tmp/kimi-1.json"
    elif source == "deploy-error":
        monkeypatch.setenv("KIMI_AUTH_FILE", "/tmp/kimi-*.json")
    monkeypatch.setattr(diagnostics, "_auth_file_hit", lambda pattern: hit)
    providers = build_providers(get_settings())
    providers["kimi"].available = lambda: source in ("proxy", "token", "auth-file")
    monkeypatch.setattr(diagnostics, "build_providers", lambda s: providers)
    return providers


def _with_fmp_cache(monkeypatch, providers, markets, ts=None):
    providers["fmp"]._exchanges_cache = (time.monotonic() if ts is None else ts, markets)
    monkeypatch.setattr(diagnostics, "build_providers", lambda s: providers)


# ── shape & content ─────────────────────────────────────────────────────────

async def test_status_shape(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "dummy")
    providers = _mock_kimi(monkeypatch, "proxy")
    _with_fmp_cache(monkeypatch, providers, {"HK"})
    monkeypatch.setattr(futu_bridge, "opend_available", lambda: True)
    out = await _register()()
    assert set(out) == {"providers", "futu_opend", "tools", "markets"}
    for name, status in out["providers"].items():
        assert isinstance(status["available"], bool), name
        assert isinstance(status["covers"], list), name
    assert out["futu_opend"]["reachable"] is True
    assert out["tools"]["unified"] == 18  # exact pin: 18 expected unified tools
    assert out["tools"]["futu_mounted"] >= 53
    assert out["tools"]["total"] == out["tools"]["unified"] + out["tools"]["futu_mounted"]


async def test_all_providers_reported(monkeypatch):
    _mock_kimi(monkeypatch, None)
    out = await _register()()
    assert set(out["providers"]) == {"yahoo", "tradingview", "fmp", "alphavantage",
                                     "marketaux", "futu", "kimi"}


async def test_fmp_cached_probe_reported_no_fresh_probe(monkeypatch):
    """The cached 24h probe list is reported; a fresh probe must NOT fire
    (the active getaddrinfo guard would surface it as an entry issue)."""
    monkeypatch.setenv("FMP_API_KEY", "dummy")
    providers = _mock_kimi(monkeypatch, None)
    _with_fmp_cache(monkeypatch, providers, {"HK", "UK", "MY"})
    out = await _register()()
    entry = out["providers"]["fmp"]
    assert entry["probed_exchanges"] == ["HK", "MY", "UK"]
    assert "HK" in entry["covers"]  # cache within 24h TTL extends coverage
    assert "issue" not in entry


async def test_no_fresh_probe_when_cache_empty(monkeypatch):
    _mock_kimi(monkeypatch, None)
    out = await _register()()
    entry = out["providers"]["fmp"]
    assert entry["probed_exchanges"] == []
    assert "issue" not in entry  # guard active: any probe attempt would surface


async def test_stale_fmp_cache_not_reported_as_coverage(monkeypatch):
    """A >24h cache is expired: reported as probed history, but not covers."""
    monkeypatch.setenv("FMP_API_KEY", "dummy")
    providers = _mock_kimi(monkeypatch, None)
    _with_fmp_cache(monkeypatch, providers, {"HK"}, ts=time.monotonic() - 25 * 3600)
    out = await _register()()
    entry = out["providers"]["fmp"]
    assert entry["probed_exchanges"] == ["HK"]  # history is still visible
    assert "HK" not in entry["covers"]  # but no longer extends coverage
    assert "fmp" not in out["markets"]["HK"]


async def test_markets_coverage_matrix(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "dummy")
    providers = _mock_kimi(monkeypatch, "proxy")
    _with_fmp_cache(monkeypatch, providers, {"HK"})
    monkeypatch.setattr(futu_bridge, "opend_available", lambda: True)
    out = await _register()()
    markets = {m: set(v) for m, v in out["markets"].items()}
    assert markets["US"] >= {"yahoo", "tradingview", "fmp", "alphavantage", "futu"}
    assert markets["HK"] >= {"futu", "fmp"}  # fmp via cached probe
    assert markets["EG"] >= {"yahoo", "tradingview"}
    assert markets["CN"] >= {"futu", "kimi"}


# ── kimi auth source: structural labels only ────────────────────────────────

@pytest.mark.parametrize("source,expected", [
    ("proxy", ("proxy", True)),
    ("token", ("token", True)),
    ("auth-file", ("auth-file", True)),
    ("deploy-error", ("deploy-error", False)),
    (None, ("none", False)),
])
async def test_kimi_auth_source(monkeypatch, source, expected):
    _mock_kimi(monkeypatch, source)
    out = await _register()()
    auth = out["providers"]["kimi"]["auth"]
    assert auth["source"] == expected[0]
    assert out["providers"]["kimi"]["available"] is expected[1]
    assert "value" not in auth and "token" not in {k for k in auth if k != "source"}


async def test_kimi_auth_file_hit_is_path_only(monkeypatch):
    _mock_kimi(monkeypatch, "auth-file")
    out = await _register()()
    assert out["providers"]["kimi"]["auth"] == {"source": "auth-file",
                                                "file": "/tmp/kimi-1.json"}


async def test_kimi_deploy_error_details_glob_miss(monkeypatch):
    _mock_kimi(monkeypatch, "deploy-error")
    out = await _register()()
    auth = out["providers"]["kimi"]["auth"]
    assert "无命中" in auth["detail"]


# ── ConfigError vs deploy-misconfiguration (T9 R1) ──────────────────────────

async def test_key_states_classify_config(monkeypatch):
    """key missing (config) vs rotated-upstream (deploy rotator) vs set."""
    _mock_kimi(monkeypatch, None)
    out = await _register()()
    entry = out["providers"]["fmp"]
    assert entry["key"] == "missing" and entry["available"] is False
    assert "issue" not in entry  # config-missing is NOT a deploy error

    monkeypatch.setenv("FMP_API_KEY", "dummy")
    _mock_kimi(monkeypatch, None)  # rebuild providers with the fresh settings
    out = await _register()()
    entry = out["providers"]["fmp"]
    assert entry["key"] == "set" and entry["available"] is True
    assert "base_override" not in entry

    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.setenv("FMP_BASE_URL", "http://api-key-rotator:8788/fmp")
    _mock_kimi(monkeypatch, None)  # rebuild providers with the fresh settings
    out = await _register()()
    entry = out["providers"]["fmp"]
    assert entry["key"] == "rotated-upstream" and entry["available"] is True
    assert entry["base_override"] is True
    assert entry["base_url"] == "http://api-key-rotator:8788/fmp"


async def test_deploy_misconfiguration_classified(monkeypatch):
    _mock_kimi(monkeypatch, "deploy-error")
    out = await _register()()
    assert out["providers"]["kimi"]["auth"]["source"] == "deploy-error"
    assert out["providers"]["futu"]["issue"] == "OpenD 不可达（deploy-misconfiguration）"
    assert out["futu_opend"]["reachable"] is False
    assert out["futu_opend"]["issue"] is not None
    assert out["futu_opend"]["mounted"] >= 53  # package present: still mounted


async def test_futu_disabled_skips_probe(monkeypatch):
    """FINANCE_MCP_FUTU=0 is a config choice, not a deploy error: the futu
    provider's available() must NOT be called (no TCP probe, fast/read-only)
    and the classification must be config-disable, not deploy-error."""
    _mock_kimi(monkeypatch, None)
    monkeypatch.setenv("FINANCE_MCP_FUTU", "0")
    calls = []
    real_available = build_providers(get_settings())["futu"].available
    monkeypatch.setattr(diagnostics, "build_providers",
                        lambda s: _providers_with_futu_avail_spy(monkeypatch, calls,
                                                                real_available))
    out = await _register()()
    assert calls == []  # available() never invoked while futu is disabled
    assert out["futu_opend"]["reachable"] is None
    assert out["futu_opend"]["mounted"] == 0
    assert out["tools"]["futu_mounted"] == 0
    entry = out["providers"]["futu"]
    assert entry["available"] is False
    assert entry["issue"] == "disabled by config"  # not deploy-misconfiguration


def _providers_with_futu_avail_spy(monkeypatch, calls, real_available):
    """Fresh providers whose futu.available records each invocation."""
    providers = build_providers(get_settings())
    providers["futu"].available = lambda: calls.append(1) or real_available()
    return providers


# ── never raises + no secrets ───────────────────────────────────────────────

async def test_never_raises_on_hostile_provider(monkeypatch):
    _mock_kimi(monkeypatch, None)

    class Hostile:
        name = "hostile"
        markets = None

        def available(self):
            raise RuntimeError("boom")

        def covers(self, market):
            return True

    monkeypatch.setattr(diagnostics, "build_providers", lambda s: {"hostile": Hostile()})
    out = await _register()()
    assert out["providers"]["hostile"]["issue"].startswith("RuntimeError: boom")
    assert "error" not in out  # top level still healthy


async def test_secrets_scrubbed_from_output(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "SUPERSECRET")
    _mock_kimi(monkeypatch, "token")  # dummy-kimi-token must never leak either

    class Hostile:
        name = "hostile"
        markets = None

        def available(self):
            raise RuntimeError("rotator unreachable SUPERSECRET")

        def covers(self, market):
            return True

    monkeypatch.setattr(diagnostics, "build_providers", lambda s: {"hostile": Hostile()})
    out = await _register()()
    text = repr(out)
    assert "SUPERSECRET" not in text
    assert "dummy-kimi-token" not in text


async def test_status_never_resolves_dns(monkeypatch):
    """Full status collection under the (autouse) getaddrinfo guard."""
    monkeypatch.setenv("FMP_API_KEY", "dummy")
    providers = _mock_kimi(monkeypatch, "proxy")
    _with_fmp_cache(monkeypatch, providers, {"HK"})
    monkeypatch.setattr(futu_bridge, "opend_available", lambda: True)
    out = await _register()()
    assert "error" not in out


# ── module surface ──────────────────────────────────────────────────────────

def test_module_registered_and_mounts_tool():
    from mcp.server.fastmcp import FastMCP

    assert "diagnostics" in tools_pkg.ALL_MODULES
    assert len(tools_pkg.ALL_MODULES) == 14
    assert len(set(tools_pkg.ALL_MODULES)) == 14  # no duplicates

    mcp = FastMCP("t16-test")
    diagnostics.register(mcp, None, get_settings())
    assert "get_service_status" in {t.name for t in mcp._tool_manager.list_tools()}
