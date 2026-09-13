"""T18 kimi L2 container (kimi_datasource) + get_company_risk_cn.

Hermetic (T10-C1 hardening): every test stubs the COMPLETE reachable kimi
provider face at the instance level and forces availability — results are
identical keyless or keyed. The getaddrinfo-guard harness runs this file in a
fresh process twice (keyless + dummy keys + dummy KIMI_PROXY_URL), proving 0
egress; no test may reach the real api.kimi.com / proxy / auth.kimi.com.
"""
from __future__ import annotations

import socket
from unittest.mock import AsyncMock

from unified_finance_mcp import tools as tools_pkg
from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import AuthError, NotFound, ProviderError, UpstreamError
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import kimi as kimi_mod
from unified_finance_mcp.tools import macro as macro_mod
from unified_finance_mcp.tools import ownership as ownership_mod

ALL_ASPECTS = ("profile", "shareholders", "executives", "judicial",
               "operation", "equity_penetration", "related_graph")


def _capture(results):
    class FakeMCP:
        def tool(self):
            def deco(fn):
                results[fn.__name__] = fn
                return fn
            return deco
    return FakeMCP()


def _set_available(providers, names, value=True):
    for name in names:
        providers[name].available = lambda v=value: v


def make_kimi(monkeypatch):
    """Real KimiProvider instance with the whole network face stubbed."""
    monkeypatch.setenv("KIMI_ACCESS_TOKEN", "tok")
    p = build_providers(get_settings())["kimi"]
    p.available = lambda: True
    p.describe = AsyncMock(return_value="mock tianyancha doc")
    p.call = AsyncMock(side_effect=NotFound("kimi: API_NOT_FOUND"))
    p.list_sources = lambda: ["tianyancha", "wind"]
    return p


# ── module surface ──────────────────────────────────────────────────────────

def test_kimi_module_registered_in_all_modules():
    assert "kimi" in tools_pkg.ALL_MODULES
    assert len(tools_pkg.ALL_MODULES) == 17
    assert len(set(tools_pkg.ALL_MODULES)) == 17  # no duplicates


# ── kimi_datasource ─────────────────────────────────────────────────────────

async def test_datasource_list_actions(monkeypatch):
    p = make_kimi(monkeypatch)
    out = await kimi_mod.kimi_datasource("list", _provider=p)
    assert out["sources"] == ["tianyancha", "wind"]
    assert "describe" in out["hint"]


async def test_datasource_describe_action(monkeypatch):
    p = make_kimi(monkeypatch)
    p.describe = AsyncMock(return_value="# tianyancha doc")
    out = await kimi_mod.kimi_datasource("describe", source="tianyancha",
                                         _provider=p)
    assert out["source"] == "tianyancha" and out["doc"] == "# tianyancha doc"


async def test_datasource_call_action(monkeypatch):
    p = make_kimi(monkeypatch)
    p.call = AsyncMock(return_value={"data_preview": "x", "saved_files": []})
    out = await kimi_mod.kimi_datasource("call", source="tianyancha",
                                         api="search_company",
                                         params={"keyword": "腾讯"}, _provider=p)
    assert out["data_preview"] == "x"
    assert p.call.await_args.args[:2] == ("tianyancha", "search_company")
    assert p.call.await_args.args[2] == {"keyword": "腾讯"}


async def test_datasource_unknown_action_hint(monkeypatch):
    p = make_kimi(monkeypatch)
    out = await kimi_mod.kimi_datasource("bogus", _provider=p)
    assert "error" in out
    for action in ("list", "describe", "call"):
        assert action in out["hint"]


async def test_datasource_missing_params_hint(monkeypatch):
    p = make_kimi(monkeypatch)
    for kwargs in ({"action": "describe"}, {"action": "call", "source": "x"}):
        out = await kimi_mod.kimi_datasource(_provider=p, **kwargs)
        assert "error" in out and "hint" in out


async def test_datasource_unconfigured_hint(monkeypatch):
    monkeypatch.delenv("KIMI_PROXY_URL", raising=False)
    monkeypatch.delenv("KIMI_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("KIMI_AUTH_FILE", raising=False)
    for kwargs in ({"action": "list"}, {"action": "describe", "source": "x"},
                   {"action": "call", "source": "x", "api": "y"}):
        out = await kimi_mod.kimi_datasource(**kwargs)
        assert "error" in out
        for env in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN", "KIMI_AUTH_FILE"):
            assert env in out["hint"]


async def test_datasource_never_raises_on_provider_error_kind_preserved(monkeypatch):
    p = make_kimi(monkeypatch)
    p.describe = AsyncMock(side_effect=ProviderError("kimi: boom"))
    out = await kimi_mod.kimi_datasource("describe", source="x", _provider=p)
    assert out["error"].startswith("error: ")
    assert "traceback" not in out["error"]


async def test_datasource_auth_error_kind_preserved(monkeypatch):
    p = make_kimi(monkeypatch)
    p.describe = AsyncMock(side_effect=AuthError("kimi: bad creds"))
    out = await kimi_mod.kimi_datasource("describe", source="x", _provider=p)
    assert out["error"].startswith("auth: ")


# ── get_company_risk_cn ─────────────────────────────────────────────────────

async def test_company_risk_cn_resolves_full_name_first(monkeypatch):
    p = make_kimi(monkeypatch)
    responses = []

    def fake_call(source, api, params, **_kw):
        responses.append((api, params))
        if api == "tianyancha_company_search":
            return {"data_preview": "regStatus,name\n存续,深圳市腾讯计算机系统有限公司",
                    "saved_files": []}
        return {"data_preview": f"{params['api_call_name']} rows",
                "saved_files": []}

    p.call = AsyncMock(side_effect=fake_call)
    out = await kimi_mod.get_company_risk_cn("腾讯", _provider=p)
    assert "error" not in out
    search_call = responses[0]
    assert search_call == ("tianyancha_company_search", {"search_keyword": "腾讯"})
    assert out["company"] == "深圳市腾讯计算机系统有限公司"
    aspect_calls = dict((params["api_call_name"], params)
                        for api, params in responses[1:])
    for aspect in ALL_ASPECTS:
        api_name = kimi_mod.ASPECT_APIS[aspect][0]
        assert out["aspects"][aspect]["data_preview"] == f"{api_name} rows"
        assert aspect_calls[api_name]["api_call_params"] == \
            {"keyword": "深圳市腾讯计算机系统有限公司"}
    assert out["aspect_errors"] == {}


async def test_company_risk_cn_full_name_from_saved_csv(monkeypatch, tmp_path):
    p = make_kimi(monkeypatch)
    csv_file = tmp_path / "tyc.csv"
    csv_file.write_text("name,id\n深圳市腾讯计算机系统有限公司,1", encoding="utf-8")

    def fake_call(source, api, params, **_kw):
        if api == "tianyancha_company_search":
            # payload landed on disk, not inline (search CSV > preview size)
            return {"data_preview": "", "saved_files": [str(csv_file)]}
        return {"data_preview": "rows", "saved_files": []}

    p.call = AsyncMock(side_effect=fake_call)
    out = await kimi_mod.get_company_risk_cn("腾讯", aspects=["profile"], _provider=p)
    assert out["company"] == "深圳市腾讯计算机系统有限公司"
    assert "profile" in out["aspects"]


async def test_company_risk_cn_aspects_subset(monkeypatch):
    p = make_kimi(monkeypatch)

    def fake_call(source, api, params, **_kw):
        if api == "tianyancha_company_search":
            return {"data_preview": "name\n阿里巴巴（中国）有限公司", "saved_files": []}
        return {"data_preview": "rows", "saved_files": []}

    p.call = AsyncMock(side_effect=fake_call)
    out = await kimi_mod.get_company_risk_cn("阿里巴巴", aspects=["shareholders", "judicial"],
                                             _provider=p)
    assert set(out["aspects"]) == {"shareholders", "judicial"}
    assert "profile" not in out["aspects"]


async def test_company_risk_cn_partial_failures_recorded(monkeypatch):
    p = make_kimi(monkeypatch)

    def fake_call(source, api, params, **_kw):
        if api == "tianyancha_company_search":
            return {"data_preview": "name\n腾讯科技（深圳）有限公司", "saved_files": []}
        if api == "tianyancha_api_call" and params["api_call_name"] == "工商信息-企业股东":
            raise UpstreamError("kimi: shareholders down")
        return {"data_preview": "rows", "saved_files": []}

    p.call = AsyncMock(side_effect=fake_call)
    out = await kimi_mod.get_company_risk_cn("腾讯科技", aspects=["shareholders", "profile"],
                                             _provider=p)
    assert "error" not in out
    assert "profile" in out["aspects"]
    assert "shareholders" in out["aspect_errors"]
    assert "shareholders" not in out["aspects"]


async def test_company_risk_cn_api_search_fallback_and_error_payload(monkeypatch):
    """Prefix candidates miss -> api_search discovers the drifted name."""
    p = make_kimi(monkeypatch)
    called = []

    async def fake_call(source, api, params, **_kw):
        called.append(api)
        if api == "tianyancha_company_search":
            return {"data_preview": "name\n腾讯科技（深圳）有限公司", "saved_files": []}
        if api == "tianyancha_api_search":
            assert params["query"] in kimi_mod.ASPECT_APIS["shareholders"]
            return {"data_preview": "0  工商信息-企业股东    keyword\n"
                                    "1  工商信息-历史股东信息  keyword",
                    "saved_files": []}
        raise NotFound("kimi: API_NOT_FOUND")

    p.call = AsyncMock(side_effect=fake_call)
    out = await kimi_mod.get_company_risk_cn("腾讯科技", aspects=["shareholders"],
                                             _provider=p)
    assert "error" not in out
    assert called == ["tianyancha_company_search",
                      "tianyancha_api_call", "tianyancha_api_call",  # both prefixes miss
                      "tianyancha_api_search",
                      "tianyancha_api_call", "tianyancha_api_call",  # both discovered names miss
                      "tianyancha_api_search",
                      "tianyancha_api_call", "tianyancha_api_call"]  # phrasing 2: same names, miss
    assert "shareholders" in out["aspect_errors"]  # api_call never succeeded
    # self-description: the failing error embeds the live api_search output
    assert "工商信息-企业股东" in out["aspect_errors"]["shareholders"]


async def test_company_risk_cn_api_search_self_heals(monkeypatch):
    """The api_search-discovered name is actually used for the data call."""
    p = make_kimi(monkeypatch)
    aspect_calls = []

    async def fake_call(source, api, params, **_kw):
        if api == "tianyancha_company_search":
            return {"data_preview": "name\n腾讯科技（深圳）有限公司", "saved_files": []}
        if api == "tianyancha_api_search":
            return {"data_preview": "0  工商信息-股东信息总览  keyword", "saved_files": []}
        if api == "tianyancha_api_call":
            aspect_calls.append(params["api_call_name"])
            if params["api_call_name"] == "工商信息-股东信息总览":
                return {"data_preview": "rows", "saved_files": []}
        raise NotFound("kimi: API_NOT_FOUND")

    p.call = AsyncMock(side_effect=fake_call)
    out = await kimi_mod.get_company_risk_cn("腾讯科技", aspects=["shareholders"],
                                             _provider=p)
    assert "error" not in out
    assert out["aspects"]["shareholders"] == {"data_preview": "rows", "saved_files": []}
    assert aspect_calls == ["工商信息-企业股东", "股东信息", "工商信息-股东信息总览"]


async def test_company_risk_cn_unknown_aspect_hint(monkeypatch):
    p = make_kimi(monkeypatch)
    p.call = AsyncMock(side_effect=AssertionError("must not be called"))
    out = await kimi_mod.get_company_risk_cn("腾讯", aspects=["bogus"], _provider=p)
    assert "error" in out and "hint" in out


async def test_company_risk_cn_kimi_unconfigured(monkeypatch):
    monkeypatch.delenv("KIMI_PROXY_URL", raising=False)
    monkeypatch.delenv("KIMI_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("KIMI_AUTH_FILE", raising=False)
    out = await kimi_mod.get_company_risk_cn("腾讯")
    assert "error" in out
    for env in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN", "KIMI_AUTH_FILE"):
        assert env in out["hint"]


async def test_company_risk_cn_never_raises(monkeypatch):
    p = make_kimi(monkeypatch)
    p.call = AsyncMock(side_effect=RuntimeError("unexpected"))
    out = await kimi_mod.get_company_risk_cn("腾讯", _provider=p)
    assert "error" in out


async def test_company_risk_cn_search_failure_falls_back_to_input(monkeypatch):
    """F5: company_search errors -> use the user input as the name."""
    p = make_kimi(monkeypatch)
    aspect_params = {}

    async def fake_call(source, api, params, **_kw):
        if api == "tianyancha_company_search":
            raise NotFound("kimi: API_NOT_FOUND")
        if api == "tianyancha_api_call":
            aspect_params[api] = params
        return {"data_preview": "rows", "saved_files": []}

    p.call = AsyncMock(side_effect=fake_call)
    out = await kimi_mod.get_company_risk_cn("腾讯", aspects=["shareholders"],
                                             _provider=p)
    assert "error" not in out
    assert out["company"] == "腾讯"  # original input, not an error dict
    assert "shareholders" in out["aspects"]
    assert aspect_params["tianyancha_api_call"]["api_call_params"] == \
        {"keyword": "腾讯"}


# ── macro/ownership wiring (controller ruling 6) ────────────────────────────

async def test_economic_data_chain_kimi_first(monkeypatch):
    providers = build_providers(get_settings())
    kimi = providers["kimi"]
    rows = [{"date": "2025-01-01", "value": 1.0}]
    kimi.economic = AsyncMock(return_value=rows)
    providers["alphavantage"].economic = AsyncMock(
        side_effect=AssertionError("alphavantage must not be called (kimi first)"))
    _set_available(providers, ("kimi", "alphavantage"))
    results = {}
    macro_mod.register(_capture(results), providers, get_settings())
    out = await results["get_economic_data"]("GDP")
    assert out == {"data": rows}
    providers["alphavantage"].economic.assert_not_called()
    assert kimi.economic.await_args.args[0] == "GDP"


async def test_economic_data_kimi_describe_miss_falls_back_to_av(monkeypatch):
    providers = build_providers(get_settings())
    kimi = providers["kimi"]
    kimi.economic = AsyncMock(side_effect=NotFound("kimi: indicator not in tianyancha doc"))
    rows = [{"date": "2025-01-01", "value": 2.0}]
    providers["alphavantage"].economic = AsyncMock(return_value=rows)
    _set_available(providers, ("kimi", "alphavantage"))
    results = {}
    macro_mod.register(_capture(results), providers, get_settings())
    out = await results["get_economic_data"]("GDP")
    assert out == {"data": rows}


async def test_ownership_cn_name_major_routes_to_kimi(monkeypatch):
    providers = build_providers(get_settings())
    kimi = providers["kimi"]
    kimi.shareholders = AsyncMock(
        return_value={"company": "腾讯科技（深圳）有限公司",
                      "aspects": {"shareholders": {"data_preview": "rows"}},
                      "aspect_errors": {}})
    _set_available(providers, ("kimi",))
    results = {}
    ownership_mod.register(_capture(results), providers, get_settings())
    out = await results["get_ownership"]("腾讯科技", "major")
    assert "error" not in out
    kimi.shareholders.assert_awaited_once_with("腾讯科技")


async def test_ownership_cn_name_major_kimi_unavailable_falls_back(monkeypatch):
    providers = build_providers(get_settings())
    kimi = providers["kimi"]
    kimi.shareholders = AsyncMock(
        side_effect=AssertionError("kimi must not be called when unavailable"))
    rows = [{"Holder": "x", "pctHeld": 0.1}]
    providers["yahoo"].ownership = AsyncMock(return_value=rows)
    _set_available(providers, ("yahoo",))
    _set_available(providers, ("kimi",), False)  # pin unavailability (env-independent)
    results = {}
    ownership_mod.register(_capture(results), providers, get_settings())
    out = await results["get_ownership"]("腾讯科技", "major")
    assert out == {"data": rows}
    kimi.shareholders.assert_not_called()


# ── registration surface ────────────────────────────────────────────────────

def test_register_mounts_kimi_tools():
    from mcp.server.fastmcp import FastMCP

    from unified_finance_mcp.tools import kimi as kimi_mod_

    mcp = FastMCP("t18-test")
    kimi_mod_.register(mcp, None, get_settings())
    names = {t.name for t in mcp._tool_manager.list_tools()}
    assert {"kimi_datasource", "get_company_risk_cn"} <= names


# ── hermeticity guard (T10-C1, in-process getaddrinfo guard) ────────────────

def _getaddrinfo_fail(*args, **kwargs):
    raise AssertionError(f"network resolution attempted: {args[:2]}")


async def test_kimi_tools_import_and_unknown_action_no_network(monkeypatch):
    """Import-time + unknown-action surface must not resolve DNS."""
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo_fail)
    from unified_finance_mcp.tools import kimi as kimi_mod_

    assert set(kimi_mod_.ASPECT_APIS) == set(ALL_ASPECTS)
    out = await kimi_mod_.kimi_datasource(action="bogus")
    assert "error" in out
