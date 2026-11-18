"""get_sec_filing tool wiring: kind routing, validation, never-raises.

Provider face is stubbed (AsyncMock); no network.
"""
from unittest.mock import AsyncMock

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import AuthError, UpstreamDrift
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import edgar as edgar_mod


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


def _register(providers, seen=None):
    results = {}
    edgar_mod.register(_capture(results), providers, get_settings())
    return results["get_sec_filing"]


def test_edgar_module_registered_in_all_modules():
    from unified_finance_mcp import tools as tools_pkg
    assert "edgar" in tools_pkg.ALL_MODULES
    assert len(set(tools_pkg.ALL_MODULES)) == len(tools_pkg.ALL_MODULES)


async def test_filings_kind_returns_provider_dict():
    providers = build_providers(get_settings())
    payload = {"cik": "0000320193", "name": "Apple Inc.",
               "filings": [{"form": "10-K"}], "count": 1}
    providers["edgar"].submissions = AsyncMock(return_value=payload)
    _set_available(providers, ("edgar",))
    tool = _register(providers)
    out = await tool("aapl", kind="filings", form_type="10-K", limit=5)
    assert out == payload
    call = providers["edgar"].submissions.await_args
    assert call.args[0] == "aapl"
    assert call.kwargs == {"form_type": "10-K", "limit": 5}


async def test_facts_kind_parses_default_tag_whitelist():
    providers = build_providers(get_settings())
    payload = {"cik": "0000320193", "facts": {"NetIncomeLoss": {}},
               "missing_tags": []}
    providers["edgar"].facts = AsyncMock(return_value=payload)
    _set_available(providers, ("edgar",))
    tool = _register(providers)
    out = await tool("320193", kind="facts", limit=3)
    assert out == payload
    call = providers["edgar"].facts.await_args
    assert call.args[0] == "320193"
    assert call.args[1] == ["Revenues", "NetIncomeLoss", "EarningsPerShareDiluted"]
    assert call.kwargs == {"limit": 3}


async def test_facts_kind_rejects_path_like_tag_before_network():
    providers = build_providers(get_settings())
    providers["edgar"].facts = AsyncMock(side_effect=AssertionError("must not call"))
    tool = _register(providers)
    out = await tool("320193", kind="facts", tags="NetIncomeLoss/../../etc")
    assert "error" in out and "data" not in out
    assert "XBRL tag" in out["error"]


async def test_facts_kind_caps_tag_count():
    providers = build_providers(get_settings())
    providers["edgar"].facts = AsyncMock(side_effect=AssertionError("must not call"))
    tool = _register(providers)
    out = await tool("320193", kind="facts", tags=",".join(f"Tag{i}" for i in range(9)))
    assert "error" in out and "8" in out["error"]


async def test_unknown_kind_lists_valid_kinds():
    providers = build_providers(get_settings())
    tool = _register(providers)
    out = await tool("320193", kind="ownership")
    assert "error" in out
    assert "filings" in out["hint"] and "facts" in out["hint"]


async def test_limit_out_of_range_is_tool_error():
    providers = build_providers(get_settings())
    providers["edgar"].submissions = AsyncMock(side_effect=AssertionError("must not call"))
    tool = _register(providers)
    out = await tool("320193", kind="filings", limit=500)
    assert "error" in out and "1..100" in out["error"]


async def test_empty_symbol_is_tool_error():
    providers = build_providers(get_settings())
    tool = _register(providers)
    out = await tool("   ")
    assert "error" in out


async def test_provider_auth_error_becomes_error_dict_not_raise():
    """SEC 403 (undeclared UA) must surface as data, with the hint intact."""
    providers = build_providers(get_settings())
    providers["edgar"].submissions = AsyncMock(
        side_effect=AuthError("edgar: HTTP 403 — set SEC_EDGAR_USER_AGENT"))
    _set_available(providers, ("edgar",))
    tool = _register(providers)
    out = await tool("320193")
    assert "error" in out
    # route_and_call folds a single-source failure into source_errors; the
    # classifier prefix ("auth:") and the actionable UA hint must survive.
    assert out["source_errors"]["edgar"].startswith("auth:")
    assert "SEC_EDGAR_USER_AGENT" in out["source_errors"]["edgar"]


async def test_unknown_explicit_source_is_tool_error():
    providers = build_providers(get_settings())
    tool = _register(providers)
    out = await tool("320193", source="nope")
    assert "error" in out and "unknown source" in out["error"]


async def test_provider_drift_surfaces_contact_admin_action():
    """A schema break must reach the model as an admin escalation, not as a
    generic 'unavailable' that invites a pointless retry."""
    providers = build_providers(get_settings())
    providers["edgar"].submissions = AsyncMock(
        side_effect=UpstreamDrift("edgar: non-JSON body from data.sec.gov"))
    _set_available(providers, ("edgar",))
    tool = _register(providers)
    out = await tool("320193")
    assert out["action"] == "contact_admin"
    assert out["drifted_sources"] == ["edgar"]
    assert "联系管理员" in out["hint"]
