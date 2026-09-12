"""Grouped futu mount: 7 domain containers over the 53 futu-opend-mcp tools.

Active when ``FINANCE_MCP_FUTU_MOUNT_LAYOUT=grouped`` (default ``flat``
mounts every futu-opend-mcp tool side-by-side, unchanged). Grouped mode
folds the futu tools into 6 primary containers (market-analysis related:
market, fundamentals, corporate, capital, options, macro) plus one
secondary reference container (`futu_reference`) for everything lookup- or
profile-shaped that is not market analysis: company profile/executives/
operational-efficiency, sector & industry-chain structure, and the
institution directory/profile/holdings reverse lookups. The model sees
7 futu tools instead of 53 and pulls reference data on demand via
`action=list|describe|call` (76 -> 28 tools total, then 47 of the futu
names collapse into the containers' hints).

The vendored skill pack is never patched: a container is a thin async
wrapper that holds the futu tool's own fn and runs it under a timeout.
``action="list"`` enumerates a container's tools;
``action="describe", tool=<name>`` returns the futu tool's own docstring
(which documents its parameters, mostly bilingually);
``action="call", tool=<name>, params={...}`` invokes it with kwargs.

get_snapshot is NOT mounted as a container name: the unified quote chain
registers it first for US/HK/CN symbol speed, and mount_futu_tools skips
name collisions — same behaviour as flat mode.
"""
from __future__ import annotations

import inspect
import json

import anyio

from ..errors import tool_error

_DOMAINS: dict[str, str] = {
    "get_kline": "klines/candles (ktype 1m..1Y, rehab none/forward/backward)",
    "get_market_state": "market session state per market code",
    "search_quote": "search & filter listed securities",
    "search_news": "Chinese 快讯/flash headlines (热度, view_count)",
    "futu_get_stock_info": "static security info (lot size, board, listing date)",
    "screen_stocks": "condition screener (market cap, PE, volume, ...)",
    "get_financial_statements": "income/balance/cashflow statements",
    "get_revenue_breakdown": "revenue by segment/region",
    "get_earnings_calendar": "earnings release calendar",
    "get_earnings_price_history": "price reaction around past earnings",
    "get_analyst_consensus": "analyst ratings & target prices",
    "get_morningstar_report": "Morningstar qualitative report",
    "get_valuation_detail": "valuation metrics detail (PE/PB/PS bands)",
    "get_corporate_actions": "dividends/splits/corporate action history",
    "get_shareholder_overview": "shareholding structure overview",
    "get_holding_changes": "institutional holding changes",
    "get_holder_detail": "single holder detail",
    "get_institutional_holdings": "institutional holders list",
    "get_insider_data": "insider transactions",
    "get_company_profile": "company profile & business summary",
    "get_company_executives": "executive/officer roster",
    "get_executive_background": "executive career background",
    "get_operational_efficiency": "operational efficiency ratios",
    "get_capital_flow": "main-force capital flow time series",
    "get_capital_distribution": "capital distribution by order size",
    "get_top_brokers": "broker seat rankings (HK)",
    "get_short_data": "short-sale daily data (HK) / short interest (US)",
    "resolve_option_code": "resolve an option contract code",
    "futu_get_option_chain": "option chain by expiry window (HK/US)",
    "get_option_expiration_date": "option expiration dates for underlying",
    "get_option_quote": "option quotes incl. greeks/IV",
    "get_option_volatility": "option implied-volatility surface",
    "get_option_strategy_analysis": "option strategy payoff analysis",
    "get_option_underlying": "optionable underlyings",
    "get_warrant": "warrants & CBBC (HK)",
    "get_future_info": "futures contract info",
    "get_reference_securities": "related/linked securities",
    "get_plate_list": "sector/plate lists (industry, concept, region)",
    "get_plate_stocks": "constituents of a plate",
    "get_owner_plate": "plates a stock belongs to",
    "get_industrial_chains": "industry chain tree (upstream/downstream)",
    "get_industrial_plate": "industry-chain plate members",
    "get_institution_list": "known institutions list",
    "get_institution_profile": "institution profile",
    "get_institution_holdings": "institution's portfolio holdings",
    "get_institution_distribution": "holdings distribution stats",
    "get_economic_calendar": "macro events calendar",
    "get_macro_indicator": "macro indicator time series",
    "get_fed_watch": "CME FedWatch rate probabilities",
    "get_dividend_calendar": "upcoming dividends calendar",
    "get_ipo_list": "recent/upcoming IPOs",
    "get_quota_status": "futu subscription quota status (diagnostic)",
}

_CONTAINERS: dict[str, list[str]] = {
    # primary: market-analysis related (what a trading agent reaches for)
    "futu_market": ["get_kline", "get_market_state", "search_quote",
                    "search_news", "futu_get_stock_info", "screen_stocks"],
    "futu_fundamentals": ["get_financial_statements", "get_revenue_breakdown",
                          "get_earnings_calendar", "get_earnings_price_history",
                          "get_analyst_consensus", "get_morningstar_report",
                          "get_valuation_detail"],
    "futu_corporate": ["get_corporate_actions", "get_shareholder_overview",
                       "get_holding_changes", "get_holder_detail",
                       "get_institutional_holdings", "get_insider_data"],
    "futu_capital": ["get_capital_flow", "get_capital_distribution",
                     "get_top_brokers", "get_short_data"],
    "futu_options": ["resolve_option_code", "futu_get_option_chain",
                     "get_option_expiration_date", "get_option_quote",
                     "get_option_volatility", "get_option_strategy_analysis",
                     "get_option_underlying", "get_warrant", "get_future_info",
                     "get_reference_securities"],
    "futu_macro": ["get_economic_calendar", "get_macro_indicator",
                   "get_fed_watch", "get_dividend_calendar", "get_ipo_list",
                   "get_quota_status"],
    # secondary: reference/lookup data, not market analysis — pulled on demand
    "futu_reference": ["get_company_profile", "get_company_executives",
                       "get_executive_background", "get_operational_efficiency",
                       "get_plate_list", "get_plate_stocks", "get_owner_plate",
                       "get_industrial_chains", "get_industrial_plate",
                       "get_institution_list", "get_institution_profile",
                       "get_institution_holdings",
                       "get_institution_distribution"],
}

assert not ({n for names in _CONTAINERS.values() for n in names} ^ set(_DOMAINS)), (
    "_CONTAINERS must partition _DOMAINS exactly")
assert all(n not in _CONTAINERS for n in _DOMAINS), (
    "a futu tool name shadows a container name — would be unmountable")


def register(mcp, providers, settings) -> None:
    if settings.futu_mount_layout != "grouped":
        return
    from ..providers import futu_bridge

    existing = {t.name for t in mcp._tool_manager.list_tools()}
    for container, names in _CONTAINERS.items():
        table = futu_bridge.extract_futu_tools(names, existing)
        per_tool_timeout = max(settings.request_timeout * 2, 30.0)
        desc = (f"Futu OpenD {container}: {', '.join(names)}. "
                "action: 'list' | 'describe' (tool=...) "
                "| 'call' (tool=..., params={{...}}).")
        fn = _make_container(container, table, per_tool_timeout)
        mcp.add_tool(fn, name=container, description=desc)


def _make_container(container: str, table, timeout: float):
    """table: dict[str, (fn, description)]; check-failure names are excluded."""

    async def futu_container(action: str = "list", tool: str | None = None,
                             params: dict | None = None) -> dict:
        """Futu OpenD domain container; action list/describe/call."""
        if action == "list":
            return {"data": {"container": container,
                             "tools": {n: _DOMAINS.get(n, "") for n in sorted(table)}}}
        if action == "describe":
            entry = table.get(tool) if isinstance(tool, str) else None
            if entry is None:
                return _unknown_tool(tool, table)
            fn, description = entry
            return {"data": {"tool": tool, "container": container,
                             "signature": str(inspect.signature(fn)),
                             "description": description or ""}}
        if action == "call":
            entry = table.get(tool) if isinstance(tool, str) else None
            if entry is None:
                return _unknown_tool(tool, table)
            fn, _ = entry
            if params is None:
                kwargs: dict = {}
            elif isinstance(params, dict):
                kwargs = params
            else:
                return tool_error("params must be an object of keyword arguments",
                                  hint='e.g. params={"code": "HK.00700"}')
            try:
                out = await anyio.to_thread.run_sync(lambda: fn(**kwargs))
            except TypeError as e:
                # skill_runner drops anyhow=..., so fn(**kwargs) TypeErrors are
                # genuine bad-argument errors: surface the signature as the hint.
                return tool_error(f"bad params for {tool}: {e}",
                                  hint=str(inspect.signature(fn)))
            except Exception as e:  # noqa: BLE001 - containers never raise
                return tool_error(f"{tool}: {type(e).__name__}: {str(e)[:200]}",
                                  source="futu")
            return _decode(out)
        return tool_error(
            f"unknown action {action!r}",
            hint="action: list | describe | call "
                 f"(container tools: {sorted(table)})",
        )

    return futu_container


def _unknown_tool(tool, table) -> dict:
    return tool_error(f"unknown tool {tool!r} for this container",
                      hint=f"available: {sorted(table)}")


def _decode(out) -> dict:
    """Skill fns print a JSON payload on stdout; skill_runner returns the
    captured string. Decode it; already-structured results pass through."""
    if isinstance(out, str):
        try:
            out = json.loads(out)
        except json.JSONDecodeError:
            return tool_error("futu skill returned non-JSON output",
                              source="futu")
    if isinstance(out, dict) and out.get("_skill_error"):
        return tool_error(f"futu: {out.get('error')}", source="futu")
    return {"data": out}
