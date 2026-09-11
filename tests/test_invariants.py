"""Tool-surface invariants (T16): the final 18-tool unified surface + futu mount.

These pin the contract between build_mcp and the tool modules:
- no duplicate tool names (unified vs futu conflict-skip relies on it),
- the expected unified surface is a subset of the mounted surface,
- futu-opend-mcp tools are mounted when the bridge is available,
- the FastMCP internal `_tool_manager` attribute stays callable
  (futu_bridge.mount_futu_tools + this module both enumerate through it;
  an mcp-major bump removing it must fail here, not at mount time),
- INSTRUCTIONS mentions the full final surface (incl. get_service_status,
  get_company_risk_cn and the futu mount).

Routing docstring note (T10 M3 candidate; final-fix tightened the convention
line to "no network I/O; local cached probe/file read"): tools/_routing.py
documents route_and_call as "Never raises." The exact never-raises scope is
bounded by the `available()`/`covers()` candidate-filter calls in
route_and_call and by `chain` entries that do not exist in `providers` —
those are guarded (lookups skipped / ProviderError-ish results returned as
tool_error dicts). Provider method bodies invoked via `call(p)` are NOT in
scope: any exception they raise is caught and folded into tool_error
("all candidate sources failed"). This docstring documents the tested
boundary; no test pins undocumented behaviour here by design.
"""
from __future__ import annotations

import socket

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.server import INSTRUCTIONS, build_mcp
from unified_finance_mcp.tools import _routing as routing

EXPECTED_UNIFIED = {
    "get_quote", "get_history", "get_company_info", "get_financial_report",
    "get_news", "get_technical_indicators", "run_screener", "get_ownership",
    "get_events_calendar", "get_economic_data", "search_symbols",
    "get_option_chain", "get_short_interest", "get_analyst_estimates",
    "get_dividend_split_history", "get_earnings_history",
    "get_company_risk_cn", "quant_backtest", "kimi_datasource",
    "get_service_status", "tv_scan", "tv_analyze", "egx_market",
}

FUTU_MUST_HAVE = {"get_snapshot", "get_kline", "futu_get_option_chain"}


def tool_names(mcp):
    return {t.name for t in mcp._tool_manager.list_tools()}


def test_no_duplicate_tool_names():
    mcp = build_mcp(get_settings())
    names = [t.name for t in mcp._tool_manager.list_tools()]
    assert len(names) == len(set(names))


def test_expected_tool_surface():
    mcp = build_mcp(get_settings())
    assert EXPECTED_UNIFIED <= tool_names(mcp)


def test_expected_tool_count_exact():
    """22 prior unified tools + get_service_status = exactly 23."""
    mcp = build_mcp(get_settings())
    unified = [t.name for t in mcp._tool_manager.list_tools()
               if not t.fn.__module__.startswith("futu_opend_mcp")]
    assert len(unified) == 23


def test_futu_tools_mounted():
    mcp = build_mcp(get_settings())
    names = tool_names(mcp)
    assert FUTU_MUST_HAVE <= names
    futu = [t.name for t in mcp._tool_manager.list_tools()
            if t.fn.__module__.startswith("futu_opend_mcp")]
    assert len(futu) >= 50  # futu-opend-mcp ships 50+ tools


def test_every_tool_has_description():
    mcp = build_mcp(get_settings())
    for t in mcp._tool_manager.list_tools():
        assert (t.description or "").strip(), t.name


def test_fastmcp_internal_attr_pinned():
    """Pin the mcp>=1.27 internal enumeration attribute (futu mount depends)."""
    mcp = build_mcp(get_settings())
    assert hasattr(mcp, "_tool_manager")
    manager = mcp._tool_manager
    assert callable(manager.list_tools)
    tools = manager.list_tools()
    assert isinstance(tools, list) and tools
    for t in tools:
        assert t.name and isinstance(t.description, (str, type(None)))


def test_instructions_cover_final_surface():
    for name in EXPECTED_UNIFIED:
        assert name in INSTRUCTIONS
    for marker in ("futu_", "get_snapshot", "action='help'",
                   "action='list'", "action='describe'", "action='call'",
                   "vary per tool"):
        assert marker in INSTRUCTIONS, marker


def test_instructions_reference_routing_note_docstring():
    """The T10 M3 boundary note lives in the routing module docstring
    (code unchanged). The true boundary — available()/covers() candidate
    filters NOT wrapped — is pinned so it can never be written inverted."""
    doc = routing.__doc__ or ""
    assert "Never raises" in doc
    assert "available()" in doc
    assert "covers(market)" in doc
    assert "NOT wrapped" in doc  # real boundary: filter raises propagate


def test_build_mcp_and_futu_import_resolve_no_dns(monkeypatch):
    """build_mcp (incl. the futu mount import) must not touch the network."""

    def _getaddrinfo_fail(*args, **kwargs):
        raise AssertionError(f"network resolution attempted: {args[:2]}")

    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo_fail)
    mcp = build_mcp(get_settings())
    assert EXPECTED_UNIFIED <= tool_names(mcp)
