"""kimi_datasource L2 container + get_company_risk_cn.

kimi_datasource actions:
  list     — known datasource names (list_sources)
  describe — self-describing API doc for one source (24h cached upstream)
  call     — direct datasource call (auto file_path, files landed on disk)

get_company_risk_cn: resolves the tianyancha FULL company name via
tianyancha_company_search (tianyancha rejects 简称 on the data APIs), then
fans out per aspect through tianyancha_api_call with `{api_call_name,
api_call_params: {keyword: full_name}}` — the source exposes 226 data APIs
behind that single meta-API, so ASPECT_APIS carries api_search keywords
(live-verified names first) rather than guessed endpoint names. A single
failing aspect is recorded in aspect_errors, not fatal.

The container layer never raises: ProviderError kinds (auth / rate_limited /
not_found / ...) are preserved as the error payload (T14 ruling-9 parity).
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..errors import ProviderError, tool_error
from ..providers.kimi import KimiProvider

# api_search keywords per aspect (not endpoint names). The first phrase of
# each entry is also the expected live api_call_name prefix; _probe_aspect
# tries those api_call_name candidates directly and falls back to an
# api_search round-trip so upstream drift self-heals at runtime.
ASPECT_APIS = {
    "profile": ["工商信息-企业基本信息", "企业基本信息"],
    "shareholders": ["工商信息-企业股东", "股东信息"],
    "executives": ["工商信息-主要人员", "主要人员 高管"],
    "judicial": ["司法风险-法律诉讼", "法律诉讼 司法风险"],
    "operation": ["经营风险-行政处罚", "经营风险 行政处罚"],
    # equity_penetration primary is live-verified 2026-09-14 via
    # tianyancha_api_search("股权穿透") + direct api_call (returns the
    # penetration tree for a full company name, param `keyword`).
    "equity_penetration": ["关系发现-股权穿透图", "股权穿透 企业受益所有人"],
    "related_graph": ["工商信息-分支机构", "集团谱系 分支机构 关联企业"],
}

_DEFAULT_ASPECTS = tuple(ASPECT_APIS)

_KIMI_HINT = ("设 KIMI_PROXY_URL 指 cliproxy kimi-tools 管理端点"
              "（若该端点要求鉴权，请把 KIMI_ACCESS_TOKEN 设为 cliproxy 管理 key），"
              "或 KIMI_ACCESS_TOKEN 直注，"
              "或 KIMI_AUTH_FILE 指 cliproxy 的 auths/kimi-*.json")

# R13: KIMI_MACRO_CANDIDATES / KIMI_MACRO_VALUES were REMOVED. R3 (world_bank)
# and R9 (imf) verdicts proved both routes were dead code (`economic()` gated
# on `api in describe_doc` and the probed api names did not exist in the live
# doc, and the legacy CompactData endpoint kimi pre-bound those codes to is
# itself DNS-dead). Macro series now route alphavantage-direct in tools/macro.py.


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
                          hint="如 source='tianyancha' api='tianyancha_company_search' "
                               "params={'search_keyword': '腾讯'}")
    return await _guard("kimi_datasource:call", p.call(source, api, params or {}))


async def _describe_action(p: KimiProvider, source: str) -> dict:
    return {"source": source, "doc": await p.describe(source)}


def _parse_api_search_names(text: str) -> list[str]:
    """api_call_name candidates out of a tianyancha_api_search preview
    (`api_name` column of the results table; names are Chinese like
    `工商信息-企业基本信息（含主要人员）`)."""
    names: list[str] = []
    for line in (text or "").splitlines():
        try:
            # Table row shape: "<idx>  <api_name>  <params>" (idx is a digit).
            parts = line.strip().split(None, 2)
            if not (len(parts) >= 2 and parts[0].isdigit()):
                continue
            cand = parts[1].strip()
        except (ValueError, IndexError):
            continue
        if not cand:
            continue
        if (cand.startswith(("工商信息-", "司法风险-", "经营风险-", "知识产权-",
                             "企业发展-", "上市信息-", "历史信息-", "人员风险-"))
                and cand not in names):
            names.append(cand)
    return names


def _first_csv_name(text: str) -> str | None:
    """First data row's company-name column from a tianyancha search CSV.

    Column priority: explicit `name` company-name column -> a bare one-column
    CSV row containing a company keyword -> the LAST header column whose
    single row is a company full-name. Banner text ("# Tianyancha Query OK",
    "saved_files: ...", prose) never matches any of those shapes.
    """
    try:
        rows = list(csv.DictReader(io.StringIO(text or "")))
    except csv.Error:
        rows = []
    company_re = re.compile(r"公司|集团|企业|厂|店|院|银行|事务所|合作社")
    for row in rows:
        name = (row.get("name") or "").strip()
        if name:
            return name
    if rows and len(rows[0]) == 1:
        # 单列 fallback：仅当行内容像公司名时才返回，避免 banner/prose 被吞。
        val = (next((v for v in rows[0].values() if isinstance(v, str)), "") or "").strip()
        return val if company_re.search(val) else None
    for row in rows:
        # DictReader may put a list under the `None` restkey for wide rows;
        # only string cells can be company names.
        vals = [v.strip() for v in row.values()
                if isinstance(v, str) and v.strip()]
        if len(vals) == 1 and company_re.search(vals[0]):
            return vals[0]
    return None


async def _resolve_full_name(p: KimiProvider, company: str) -> str:
    """tianyancha data APIs require the FULL company name: resolve via
    tianyancha_company_search (first CSV row's company-name column); fall
    back to the input on any failure so the aggregation still runs."""
    try:
        result = await p.call("tianyancha", "tianyancha_company_search",
                              {"search_keyword": company})
    except ProviderError:
        return company
    preview = str(result.get("data_preview") or "")
    name = _first_csv_name(preview)
    if name:
        return name
    # saved_files are local paths, not CSV contents; read the first one from
    # disk only when the preview gave nothing (payload landed on disk). CSVs
    # Kimi lands are small (<1MB), so a plain sync read is acceptable.
    for path in result.get("saved_files") or []:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        name = _first_csv_name(text)
        if name:
            return name
    return company


async def _probe_aspect(p: KimiProvider, aspect: str,
                        full_name: str) -> dict:
    """call tianyancha_api_call for one aspect: live-verified api_call_name
    candidates first, then an api_search fallback round-trip (upstream drift
    self-heals at runtime)."""
    phrasings = ASPECT_APIS[aspect]

    async def _call(api_name: str) -> dict:
        return await p.call("tianyancha", "tianyancha_api_call",
                            {"api_call_name": api_name,
                             "api_call_params": {"keyword": full_name}})

    for cand in phrasings:  # phrasing == expected api_call_name prefix
        try:
            return await _call(cand)
        except ProviderError as e:
            if not _is_api_missing(e):
                raise
            continue
    doc = None  # api_search fallback (self-heal on prefix drift)
    for phrasing in phrasings:
        try:
            search = await p.call("tianyancha", "tianyancha_api_search",
                                  {"query": phrasing})
        except ProviderError:
            continue
        doc = doc or str(search.get("data_preview") or "")
        for name in _parse_api_search_names(str(search.get("data_preview") or ""))[:3]:
            try:
                return await _call(name)
            except ProviderError as e:
                if not _is_api_missing(e):
                    raise
                continue  # stale discovered name -> try the next discovered name
    raise ProviderError(
        f"kimi: no working tianyancha api_call_name for {aspect}"
        + (f"; api_search said: {doc[:1600]}" if doc else ""))


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
                out_aspects[aspect] = await _probe_aspect(p, aspect, full_name)
            except ProviderError as e:
                # No [:200] cut: an api_search fallback embeds the discovered
                # API names here so the caller can self-select the right one.
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
