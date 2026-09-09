"""futu_bridge tests: mount futu-opend-mcp tools + bridge unified calls to skills.

All futu work is mocked: no OpenD exists in this environment and no test may
open a real socket. `import futu_opend_mcp.tools` at module import is the
registration side effect that fills the package's own FastMCP singleton.
"""

import time

import futu_opend_mcp.tools  # noqa: F401 - registration side effect
import pytest
from mcp.server.fastmcp import FastMCP

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound, ProviderError
from unified_finance_mcp.providers import futu_bridge
from unified_finance_mcp.symbols import parse_symbol


@pytest.fixture(autouse=True)
def _clear_reach_cache():
    # Module-level _reach_cache persists across tests; always start fresh.
    futu_bridge._reach_cache.clear()
    yield
    futu_bridge._reach_cache.clear()


def test_mount_registers_all_futu_tools():
    mcp = FastMCP("test")
    names = futu_bridge.mount_futu_tools(mcp)
    assert len(names) >= 50 and "get_snapshot" in names and "get_kline" in names


def test_mount_skips_conflicts():
    mcp = FastMCP("test")

    @mcp.tool(name="get_snapshot")
    def mine() -> dict:
        return {"mine": True}

    names = futu_bridge.mount_futu_tools(mcp)
    assert "get_snapshot" not in names  # conflict skipped
    other = futu_bridge.mount_futu_tools(mcp)
    assert other == []  # repeat mount adds nothing new
    tool_names = {t.name for t in mcp._tool_manager.list_tools()}
    assert len(tool_names) == 53  # 1 mine + 52 futu: idempotent, no duplicates


def test_mount_noop_when_futu_tools_absent(monkeypatch):
    mcp = FastMCP("test")
    monkeypatch.setattr(futu_bridge, "FUTU_TOOLS_AVAILABLE", lambda: False)
    assert futu_bridge.mount_futu_tools(mcp) == []


def _provider_with_reachable(monkeypatch, reachable):
    monkeypatch.setattr(futu_bridge, "_opend_reachable", lambda host, port: reachable)
    return futu_bridge.FutuProvider(get_settings())


def test_unavailable_when_opend_down(monkeypatch):
    p = _provider_with_reachable(monkeypatch, False)
    assert p.available() is False


def test_available_cached_within_5s(monkeypatch):
    calls = []

    def probe(host, port):
        calls.append((host, port))
        return True

    monkeypatch.setattr(futu_bridge, "_opend_reachable", probe)
    p = futu_bridge.FutuProvider(get_settings())
    assert p.available() is True and p.available() is True
    assert calls == [("127.0.0.1", 11111)]  # second call served from the 5s cache


def test_available_cache_expires_after_5s(monkeypatch):
    monkeypatch.setattr(futu_bridge, "_reach_cache", {})
    calls = []

    def probe(host, port):
        calls.append(1)
        return True

    monkeypatch.setattr(futu_bridge, "_opend_reachable", probe)
    p = futu_bridge.FutuProvider(get_settings())
    p.available()
    monkeypatch.setattr(
        futu_bridge, "_reach_cache", {("127.0.0.1", 11111): (time.monotonic() - 10.0, True)}
    )
    p.available()
    assert len(calls) == 2  # stale entry is re-probed


async def test_quote_via_futu_skill(monkeypatch):
    calls = {}

    def fake_run(category, name, *args, **kwargs):
        calls["category"], calls["name"], calls["args"], calls["kwargs"] = (
            category,
            name,
            args,
            kwargs,
        )
        return {
            "data": [{"code": "HK.00700", "name": "TENCENT", "last_price": 380.0, "open": 375.0}]
        }

    monkeypatch.setattr(futu_bridge, "_run_skill", fake_run)
    monkeypatch.setattr(futu_bridge.FutuProvider, "available", lambda self: True)
    p = futu_bridge.FutuProvider(get_settings())
    q = await p.quote(parse_symbol("HK.00700"))
    assert calls["category"] == "quote" and calls["name"] == "get_snapshot"
    assert calls["args"] == (["HK.00700"],)
    assert q["code"] == "HK.00700" and q["last_price"] == 380.0


async def test_quote_dict_shaped_result(monkeypatch):
    def fake_run(category, name, *args, **kwargs):
        return {"HK.00700": {"last_price": 380.0}}

    monkeypatch.setattr(futu_bridge, "_run_skill", fake_run)
    p = futu_bridge.FutuProvider(get_settings())
    q = await p.quote(parse_symbol("HK.00700"))
    assert q["last_price"] == 380.0


async def test_quote_skill_error_raises_provider_error(monkeypatch):
    monkeypatch.setattr(
        futu_bridge, "_run_skill", lambda *a, **k: {"_skill_error": True, "error": "timeout"}
    )
    p = futu_bridge.FutuProvider(get_settings())
    with pytest.raises(ProviderError) as ei:
        await p.quote(parse_symbol("HK.00700"))
    assert "timeout" in str(ei.value)


async def test_quote_code_absent_raises_not_found(monkeypatch):
    monkeypatch.setattr(futu_bridge, "_run_skill", lambda *a, **k: {"data": [{"code": "HK.09988"}]})
    p = futu_bridge.FutuProvider(get_settings())
    with pytest.raises(NotFound):
        await p.quote(parse_symbol("HK.00700"))


async def test_history_ktype_map_and_passthrough(monkeypatch):
    calls = {}

    def fake_run(category, name, *args, **kwargs):
        calls["category"], calls["name"], calls["kwargs"] = category, name, kwargs
        return {
            "code": "HK.00700",
            "ktype": "1w",
            "data": [{"time_key": "2026-09-07", "close": 380.0}],
        }

    monkeypatch.setattr(futu_bridge, "_run_skill", fake_run)
    p = futu_bridge.FutuProvider(get_settings())
    rows = await p.history(
        parse_symbol("HK.00700"), interval="1wk", start="2026-01-01", end="2026-09-01"
    )
    assert calls["category"] == "quote" and calls["name"] == "get_kline"
    assert calls["kwargs"]["code"] == "HK.00700"
    assert calls["kwargs"]["ktype"] == "1w"  # 1wk mapped to futu native 1w
    assert calls["kwargs"]["start"] == "2026-01-01"
    assert calls["kwargs"]["end"] == "2026-09-01"
    assert rows[0]["close"] == 380.0


async def test_history_skill_error_raises_provider_error(monkeypatch):
    monkeypatch.setattr(
        futu_bridge, "_run_skill", lambda *a, **k: {"_skill_error": True, "error": "quota"}
    )
    p = futu_bridge.FutuProvider(get_settings())
    with pytest.raises(ProviderError) as ei:
        await p.history(parse_symbol("HK.00700"))
    assert "quota" in str(ei.value)
