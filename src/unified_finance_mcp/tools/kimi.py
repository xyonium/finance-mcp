"""kimi_datasource L2 container + get_company_risk_cn.

kimi_datasource actions:
  list     — known datasource names (list_sources)
  describe — self-describing API doc for one source (24h cached upstream)
  call     — direct datasource call (auto file_path, files landed on disk)

get_company_risk_cn: resolves the tianyancha FULL company name via search
first (tianyancha requires it), then aggregates the requested aspects; a
single failing aspect is recorded in aspect_errors, not fatal. api_names are
probed in candidate order (drift-tolerant) with a describe() doc fallback in
the hint (self-description instead of hard failure).

The container layer never raises: ProviderError kinds (auth / rate_limited /
not_found / ...) are preserved as "kind: msg" (T14 ruling-9 parity).
"""
from __future__ import annotations

from typing import Any

from ..config import get_settings
from ..errors import ProviderError, tool_error
from ..providers.kimi import KimiProvider

ASPECT_APIS = {  # 首选 api_name 候选（实现时先 describe("tianyancha") 核对，漂移时按候选顺序探测）
    "profile": ["company_profile", "get_company_info", "base_info"],
    "shareholders": ["shareholders", "get_shareholders"],
    "executives": ["executives", "get_executives", "management"],
    "judicial": ["judicial_risk", "get_judicial_risk", "lawsuits"],
    "operation": ["operation_risk", "get_operation_risk", "business_risk"],
    "equity_penetration": ["equity_penetration", "get_equity_structure", "ownership_structure"],
    "related_graph": ["related_graph", "get_related_companies", "related_parties"],
}

_DEFAULT_ASPECTS = tuple(ASPECT_APIS)
_SEARCH_APIS = ["search_company", "search"]

_KIMI_HINT = ("设 KIMI_PROXY_URL 指 kimi-datasource-proxy 容器，"
              "或 KIMI_ACCESS_TOKEN 直注，"
              "或 KIMI_AUTH_FILE 指 cliproxy 的 auths/kimi-*.json")

# World Bank / IMF indicator mapping (v1: the api_name candidates are probed
# against the live describe() doc — a miss falls back to alphavantage).
KIMI_MACRO_CANDIDATES = [
    ("world_bank_open_data", "get_world_bank_series", "series"),
    ("world_bank_open_data", "get_indicator_data", "indicator"),
    ("imf", "get_imf_series", "series"),
]
KIMI_MACRO_VALUES = {
    "GDP": "NY.GDP.MKTP.CD",
    "CPI": "FP.CPI.TOTL",
    "INFLATION": "FP.CPI.TOTL.ZG",
    "UNEMPLOYMENT": "SL.UEM.TOTL.ZS",
    "FEDERAL_FUNDS_RATE": "FEDFUNDS",
    "TREASURY_YIELD_10Y": "DGS10",
    "RETAIL_SALES": "RSXFS",
    "NONFARM_PAYROLL": "PAYEMS",
}


def _is_api_missing(e: Exception) -> bool:
    if getattr(e, "kind", None) == "not_found":
        return True
    return "API_NOT_FOUND" in str(e)


def _guard(action: str, coro):
    async def _run():
        try:
            return await coro
        except ProviderError as e:
            return tool_error(f"{e.kind}: {str(e)[:200]}", source="kimi")
        except Exception as e:  # noqa: BLE001 - containers never raise
            return tool_error(f"{action}: {type(e).__name__}: {str(e)[:200]}",
                              source="kimi")
    return _run()


def _provider_of(settings, _provider=None) -> KimiProvider:
    return _provider if _provider is not None else KimiProvider(settings)


async def kimi_datasource(action: str = "list", source: str | None = None,
                          api: str | None = None, params: dict | None = None,
                          _provider: Any = None) -> dict:
    """Kimi datasource meta-source access by `action`.

    Actions: list (known sources) | describe (API doc of one source) |
    call (direct datasource call, files saved under KIMI_FILES_DIR).
    """
    settings = get_settings()
    p = _provider_of(settings, _provider)
    if not p.available():
        return tool_error("kimi datasource not configured", hint=_KIMI_HINT)
    if not isinstance(action, str) or action not in ("list", "describe", "call"):
        return tool_error(f"unknown action {action!r}",
                          hint="action 可用: list | describe | call")
    if action == "list":
        return {"sources": p.list_sources(),
                "hint": "action='describe' 查看某源 API 文档"}
    if action == "describe":
        if not source:
            return tool_error("describe needs source",
                              hint="source 如 " + ", ".join(p.list_sources()))
        return await _guard("kimi_datasource:describe",
                            _describe_action(p, source))
    if not source or not api:
        return tool_error("call needs source and api",
                          hint="如 source='tianyancha' api='search_company' "
                               "params={'keyword': '腾讯'}")
    return await _guard("kimi_datasource:call", p.call(source, api, params or {}))


async def _describe_action(p: KimiProvider, source: str) -> dict:
    return {"source": source, "doc": await p.describe(source)}


async def _probe_api(p: KimiProvider, source: str, candidates: list[str],
                     params: dict, aspect: str) -> dict:
    """Try api_name candidates in order; API_NOT_FOUND moves to the next.

    Non-missing failures (auth/rate/unavailable) abort probing. All candidates
    missing -> describe() doc in the error hint (self-description fallback).
    """
    for api in candidates:
        try:
            return await p.call(source, api, params)
        except ProviderError as e:
            if not _is_api_missing(e):
                raise
            continue
    doc = await p.describe(source)
    raise ProviderError(f"kimi: no working {source} api for {aspect} among "
                        f"{candidates}; doc: {str(doc)[:2000]}")


def _is_error_text(text: str) -> bool:
    low = text.lower()
    return low.startswith("error") or "not_found" in low


async def _resolve_full_name(p: KimiProvider, company: str) -> str:
    """tianyancha requires the company FULL name: search first, take the
    first result line; fall back to the input on an empty/error preview."""
    result = await _probe_api(p, "tianyancha", _SEARCH_APIS,
                              {"keyword": company}, "search")
    text = str(result.get("data_preview") or "")
    first = next((line.strip() for line in text.splitlines() if line.strip()), None)
    if first and not _is_error_text(first):
        return first
    return company


async def get_company_risk_cn(company: str, aspects: list | None = None,
                              _provider: Any = None) -> dict:
    """CN company risk profile from tianyancha (kimi datasource).

    `aspects` defaults to all 7 (profile | shareholders | executives |
    judicial | operation | equity_penetration | related_graph). Per-aspect
    failures are recorded in aspect_errors, not fatal.
    """
    settings = get_settings()
    p = _provider_of(settings, _provider)
    if not p.available():
        return tool_error("kimi datasource not configured", hint=_KIMI_HINT)
    if not isinstance(company, str) or not company.strip():
        return tool_error("company is required",
                          hint="pass the Chinese company name (简称即可)")
    wanted = list(_DEFAULT_ASPECTS if aspects is None else aspects)
    bad = [a for a in wanted if a not in ASPECT_APIS]
    if bad:
        return tool_error(f"unknown aspects {bad!r}",
                          hint="aspects 可用: " + ", ".join(_DEFAULT_ASPECTS))
    try:
        full_name = await _resolve_full_name(p, company.strip())
        out_aspects: dict[str, dict] = {}
        aspect_errors: dict[str, str] = {}
        for aspect in wanted:
            try:
                out_aspects[aspect] = await _probe_api(
                    p, "tianyancha", ASPECT_APIS[aspect],
                    {"name": full_name}, aspect)
            except ProviderError as e:
                # No [:200] cut: a describe() fallback embeds the source doc
                # here so the caller can self-select the right api_name.
                aspect_errors[aspect] = f"{e.kind}: {e!s}"
            except Exception as e:  # noqa: BLE001
                aspect_errors[aspect] = f"{type(e).__name__}: {str(e)[:200]}"
        return {"company": full_name, "aspects": out_aspects,
                "aspect_errors": aspect_errors}
    except ProviderError as e:
        return tool_error(f"{e.kind}: {str(e)[:200]}", source="kimi")
    except Exception as e:  # noqa: BLE001 - containers never raise
        return tool_error(f"get_company_risk_cn: {type(e).__name__}: "
                          f"{str(e)[:200]}", source="kimi")


def register(mcp, providers, settings) -> None:
    @mcp.tool(name="kimi_datasource")
    async def kimi_datasource_tool(action: str = "list",
                                   source: str | None = None,
                                   api: str | None = None,
                                   params: dict | None = None) -> dict:
        """Kimi datasource meta-source by action (see kimi_datasource docstring)."""
        return await kimi_datasource(action, source, api, params)

    @mcp.tool(name="get_company_risk_cn")
    async def get_company_risk_cn_tool(company: str,
                                       aspects: list | None = None) -> dict:
        """CN company risk profile from tianyancha (see get_company_risk_cn)."""
        return await get_company_risk_cn(company, aspects)
