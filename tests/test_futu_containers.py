"""Grouped futu mount: 9 domain containers over the 53 futu-opend-mcp tools.

No OpenD and no real socket anywhere: container `call` tests monkeypatch the
extracted tool fns with fakes; registration tests only enumerate names/layout.
Module-level _DOMAINS/_CONTAINERS import futu_opend_mcp at most once (the
registration side effect fills the package's own FastMCP singleton).
"""

import json

import futu_opend_mcp.tools  # noqa: F401 - registration side effect
import pytest
from futu_opend_mcp.tools._base import mcp as futu_pkg_mcp
from mcp.server.fastmcp import FastMCP

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.providers import futu_bridge
from unified_finance_mcp.tools import futu_containers

ALL_FUTU = {t.name for t in futu_pkg_mcp._tool_manager.list_tools()}


def _settings(layout: str):
    s = get_settings()
    object.__setattr__(s, "futu_mount_layout", layout)
    return s


def _registered_names(mcp) -> set[str]:
    return {t.name for t in mcp._tool_manager.list_tools()}


# ── static layout facts ─────────────────────────────────────────────────────

def test_domains_partition_all_futu_tools():
    grouped = {n for names in futu_containers._CONTAINERS.values() for n in names}
    assert set(futu_containers._DOMAINS) == grouped  # internal consistency
    # get_snapshot lives in the unified quote chain, never in a container.
    assert grouped == ALL_FUTU - {"get_snapshot"}
    assert len(grouped) == 52


def test_register_noop_in_flat_layout():
    mcp = FastMCP("test")
    futu_containers.register(mcp, providers=None, settings=_settings("flat"))
    assert _registered_names(mcp) == set()


def test_register_grouped_mounts_nine_containers_only():
    mcp = FastMCP("test")
    futu_containers.register(mcp, providers=None, settings=_settings("grouped"))
    assert _registered_names(mcp) == set(futu_containers._CONTAINERS)
    # none of the 53 flat futu tool names leaked in
    assert not (_registered_names(mcp) & ALL_FUTU)


def test_grouped_mount_build_mcp_shrinks_tool_surface():
    from unified_finance_mcp.server import build_mcp

    mcp = build_mcp(_settings("grouped"))
    names = _registered_names(mcp)
    # 19 unified + 7 futu containers (6 primary + futu_reference) = 26;
    # no flat futu tool names.
    assert len(names) == 26
    assert "futu_reference" in names and "futu_company" not in names
    assert not (names & ALL_FUTU)
    # unified surface untouched; get_snapshot absent (it is never a unified
    # tool name — the quote chain reaches futu via FutuProvider instead).
    for n in ("get_quote", "get_news", "quant_backtest",
              "tv_scan", "get_service_status"):
        assert n in names
    assert "get_snapshot" not in names


# ── extract_futu_tools ───────────────────────────────────────────────────────

def test_extract_resolves_real_futu_tools():
    table = futu_bridge.extract_futu_tools(["get_kline", "get_capital_flow"],
                                           {"get_snapshot"})
    assert set(table) == {"get_kline", "get_capital_flow"}
    fn, desc = table["get_kline"]
    assert callable(fn) and "K-line" in (desc or "")


def test_extract_skips_existing_and_missing(caplog):
    import logging

    with caplog.at_level(logging.WARNING,
                         logger="unified_finance_mcp.providers.futu_bridge"):
        table = futu_bridge.extract_futu_tools(
            ["get_kline", "no_such_tool_xyz"], {"get_kline"})
    assert table == {}  # get_kline skipped (existing), missing one skipped too
    assert any("no_such_tool_xyz" in r.message for r in caplog.records)


# ── container behaviour (fns monkeypatched; zero futu I/O) ──────────────────

async def _call(mcp, name, **kwargs):
    tool = mcp._tool_manager.get_tool(name)
    return await tool.fn(**kwargs)


@pytest.fixture
def grouped_mcp():
    mcp = FastMCP("test")
    futu_containers.register(mcp, providers=None, settings=_settings("grouped"))
    return mcp


async def test_container_list_action(grouped_mcp):
    out = await _call(grouped_mcp, "futu_market", action="list")
    tools = out["data"]["tools"]
    assert "get_kline" in tools and "search_news" in tools
    assert "get_snapshot" not in tools
    assert out["data"]["container"] == "futu_market"


async def test_container_describe_action(grouped_mcp):
    out = await _call(grouped_mcp, "futu_market", action="describe",
                      tool="get_kline")
    assert out["data"]["tool"] == "get_kline"
    assert "code" in out["data"]["signature"]  # real signature params visible
    assert "rehab" in out["data"]["signature"]
    assert "K-line" in out["data"]["description"]


async def test_container_describe_unknown_tool(grouped_mcp):
    out = await _call(grouped_mcp, "futu_market", action="describe",
                      tool="get_warrant")  # exists, but belongs to futu_options
    assert "error" in out and "available" in out["hint"]


async def test_container_unknown_action_lists_valid(grouped_mcp):
    out = await _call(grouped_mcp, "futu_macro", action="bogus")
    assert "error" in out and "list" in out["hint"]


async def test_container_call_routes_params(grouped_mcp, monkeypatch):
    captured = {}

    def fake_kline(code, ktype="1d", num=10, start=None, end=None,
                   rehab="forward"):
        captured.update(code=code, ktype=ktype, num=num)
        return {"code": code, "ktype": ktype, "data": [{"close": 380.0}]}

    table = {"get_kline": (fake_kline, "fake")}
    monkeypatch.setattr(futu_bridge, "extract_futu_tools", lambda names, ex: table)
    mcp = FastMCP("test")
    futu_containers.register(mcp, providers=None, settings=_settings("grouped"))
    out = await _call(mcp, "futu_market", action="call", tool="get_kline",
                      params={"code": "HK.00700", "ktype": "1w", "num": 3})
    assert captured == {"code": "HK.00700", "ktype": "1w", "num": 3}
    assert out == {"data": {"code": "HK.00700", "ktype": "1w",
                            "data": [{"close": 380.0}]}}


async def test_container_call_decodes_json_string(grouped_mcp, monkeypatch):
    monkeypatch.setattr(
        futu_bridge, "extract_futu_tools",
        lambda names, ex: {"get_quota_status": (
            lambda: json.dumps({"used": 3, "remain": 7}), "fake")})
    mcp = FastMCP("test")
    futu_containers.register(mcp, providers=None, settings=_settings("grouped"))
    out = await _call(mcp, "futu_macro", action="call", tool="get_quota_status")
    assert out == {"data": {"used": 3, "remain": 7}}


async def test_container_call_rejects_non_dict_params(grouped_mcp, monkeypatch):
    monkeypatch.setattr(
        futu_bridge, "extract_futu_tools",
        lambda names, ex: {"get_kline": (lambda **kw: {}, "fake")})
    mcp = FastMCP("test")
    futu_containers.register(mcp, providers=None, settings=_settings("grouped"))
    out = await _call(mcp, "futu_market", action="call", tool="get_kline",
                      params=["HK.00700"])
    assert "error" in out and "params" in out["error"]


async def test_container_call_bad_kwargs_hint_signature(monkeypatch):
    def fake_kline(code, ktype="1d"):
        raise AssertionError("unreachable")

    monkeypatch.setattr(futu_bridge, "extract_futu_tools",
                        lambda names, ex: {"get_kline": (fake_kline, "fake")})
    mcp = FastMCP("test")
    futu_containers.register(mcp, providers=None, settings=_settings("grouped"))
    out = await _call(mcp, "futu_market", action="call", tool="get_kline",
                      params={"bogus": 1})
    assert "error" in out and "(code, ktype='1d')" in out["hint"]


async def test_container_call_exception_becomes_error_dict(monkeypatch):
    def boom():
        raise RuntimeError("opend gone")

    monkeypatch.setattr(futu_bridge, "extract_futu_tools",
                        lambda names, ex: {"get_quota_status": (boom, "fake")})
    mcp = FastMCP("test")
    futu_containers.register(mcp, providers=None, settings=_settings("grouped"))
    out = await _call(mcp, "futu_macro", action="call", tool="get_quota_status")
    assert out["source"] == "futu" and "opend gone" in out["error"]


async def test_container_skill_error_surfaces(monkeypatch):
    monkeypatch.setattr(
        futu_bridge, "extract_futu_tools",
        lambda names, ex: {"get_quota_status": (
            lambda: {"_skill_error": True, "error": "quota exceeded"}, "fake")})
    mcp = FastMCP("test")
    futu_containers.register(mcp, providers=None, settings=_settings("grouped"))
    out = await _call(mcp, "futu_macro", action="call", tool="get_quota_status")
    assert out["source"] == "futu" and "quota exceeded" in out["error"]
