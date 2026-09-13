"""Kimi Datasource meta-source. Auth lives upstream (cliproxy passthrough or a
user-supplied Kimi Code token); this client only sends a Bearer + X-Msh headers.
Protocol reference (re-implemented, NOT copied): AGPL plugin
piexian/astrbot_plugin_kimi_datasource_api + official Kimi Code plugin docs.

Token/base resolution order (controller ruling 2, 2026-09-10 proxy decision;
management-key extension for the cliproxy kimi-tools plugin, 2026-09-11;
allow-list allow-growth R14, 2026-09-13):
  1. settings.kimi_proxy_url non-empty -> base_url = proxy URL. The proxy
     holds/refreshes the upstream bearer. If settings.kimi_access_token is
     ALSO set here, its value is used as the CLIProxyAPI *management* key
     for the proxy endpoint and sent as `Authorization: Bearer <token>`;
     the proxy strips it before talking to Kimi. Leave that empty for an
     unauthenticated proxy.
  2. settings.kimi_access_token (without proxy_url) -> base_url =
     settings.kimi_base_url, Bearer = token, device_id = _generated_device_id()
     (XDG-persisted).
  3. resolve_kimi_auth_file(settings) -> base_url = settings.kimi_base_url,
     creds from the cliproxy auth JSON (_KimiCredentials, incl. the
     self-refresh fallback via auth.kimi.com).
  All three empty -> available() False; _headers() raises AuthError listing
  the three configuration ways.

Source discoverability (R14 — 用户口径 2026-09-13):
  `KNOWN_SOURCES` is a SEED list, not a whitelist. `describe()` and `call()`
  accept any source name the upstream actually knows about, via a probe-on-
  first-sight pattern:
    - hit in `_VERIFIED_SOURCES` -> proceed
    - hit in `_BLOCKED_SOURCES` (recent enough) -> NotFound (fail fast, no quota)
    - otherwise -> probe upstream get_data_source_desc once
        * doc contains "###"   -> add to _VERIFIED_SOURCES, proceed
        * doc is a skeleton    -> add to _BLOCKED_SOURCES (24h TTL), NotFound
        * upstream error        -> propagate (NOT block) so transient failures
                                  don't permanently mask a source; auth /
                  rate_limited errors in particular must NOT block,
                  per the user's R14 ruling ("排除额度不足").
"""
from __future__ import annotations

import base64
import fcntl
import json
import os
import re
import stat
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import anyio

from ..config import DEFAULT_KIMI_BASE_URL, Settings
from ..errors import AuthError, NotFound, ProviderError, UpstreamError, scrub
from ..http import PoliteClient
from .base import Provider

__all__ = [
    "DEFAULT_KIMI_BASE_URL",
    "KNOWN_SOURCES",
    "DISCOURAGED_SOURCES",
    "SOURCE_ALLOWED_API_PREFIXES",
    "KimiProvider",
    "resolve_kimi_auth_file",
]

# DEFAULT_KIMI_BASE_URL is re-exported via the import above (brief import path).
KIMI_DATASOURCE_VERSION = "3.4.0"

# Seed list — the 12 sources live-verified on 2026-09-13. NOT a whitelist:
# any source the upstream accepts is auto-added to `_VERIFIED_SOURCES` on
# first successful describe (see KimiProvider._resolve_source).
KNOWN_SOURCES = [
    "stock_finance_data", "yahoo_finance", "world_bank_open_data", "tianyancha",
    "arxiv", "scholar", "yuandian_law", "wind", "imf", "gildata",
    "sec_edgar", "sp_data",
]

# Sources the R1-R12 evaluation judged "摘" or "保留-仅gap" (2026-09-13).
# Keeping them here (not removing) lets the pass-through serve them when a
# user enables new upstream plugins; the DISCOURAGED tag downgrades them to
# "documented but not recommended" without blocking.
# Mapping to evidence: docs/research/kimi-sources/<source>.verdict.md
DISCOURAGED_SOURCES: dict[str, str] = {
    "yahoo_finance": "R2 摘 — repo providers/yahoo.py 已覆盖",
    "world_bank_open_data": "R3 摘 — 官方 api.worldbank.org 免 key；kimi 路由死代码",
    "arxiv": "R5 摘 — arXiv 官方 API + user ~/paper-search",
    "scholar": "R6 摘 — OpenAlex + google_scholar链",
    "imf": "R9 摘 — IMF DataMapper + api.imf.org SDMX 2.1 免 key",
    "sec_edgar": "R11 摘 — SEC EDGAR 官方 REST 全免 key",
    "stock_finance_data": "R1 摘 — EM/sina/cninfo 免费等质 ≈93%",
    "wind": "R8 保留-仅gap — 36 API 中 58% 免费等质",
    "sp_data": "R12 保留-仅gap — 13 API 中 8 已由 yahoo/fmp/13F 覆盖",
}

# Per-source allowed API prefixes. Empty/absent entry = unrestricted.
# For wind/sp_data (R8/R12 保留-仅gap): only the gap-classes are allowed
# through; everything else is rejected BEFORE the upstream call (zero
# quota cost for the rejected traffic). Exact prefixes below were derived
# from the live describe docs on 2026-09-13 — see the verdict files for the
# API-by-API mapping.
SOURCE_ALLOWED_API_PREFIXES: dict[str, tuple[str, ...]] = {
    # wind (R8 保留-仅gap): keep the 17% that free sources genuinely lack.
    # Live-verified 2026-09-13 against the upstream's own "Available APIs"
    # listing. Free-side 100% equivalents (price/quote basics, fund NAV,
    # announcements, plain financial_data) route to akshare instead.
    "wind": (
        "wind_get_risk_metrics",            # 波动率/Beta/相关性矩阵等——免费弱
        "wind_get_bond_basicinfo",
        "wind_get_bond_issuer_info",
        "wind_get_bond_market_data",
        "wind_get_bond_financial_data",     # 债券个券估值/久期/凸性所在
        "wind_get_stock_technicals",        # MACD/RSI 等更完整
        "wind_get_index_technicals",
        "wind_get_stock_price_indicators",  # PE/PB/PS 全史——免费弱
        "wind_get_fund_price_indicators",
        "wind_get_index_price_indicators",
        "wind_get_fund_holders",            # 份额持有人结构——免费弱
        "wind_get_fund_company_info",
        "wind_get_fund_financials",
        "wind_get_fund_performance",
        "wind_get_index_basicinfo",
        "wind_get_index_fundamentals",
        "wind_search_economic_indicator",   # EDB 长尾宏观
        "wind_query_economic_indicator_data",
    ),
    # sp_data (R12 保留-仅gap): keep transcripts / estimates / competitors /
    # transactions&advisors / relationships — the 5 classes free sources lack.
    "sp_data": (
        "sp_get_estimates",                 # 一致预期历史
        "sp_get_transcripts",               # 业绩电话会议全文
        "sp_get_competitors",               # 竞对列表
        "sp_get_transactions_advisors",     # 交易/并购顾问关系
        "sp_get_transactions_relationships", # 交易关系图谱
    ),
}

_DESC_CACHE: dict[str, tuple[float, str]] = {}
_DESC_TTL = 24 * 3600

# R14 runtime source registry (see module docstring).
_VERIFIED_SOURCES: set[str] = set(KNOWN_SOURCES)
_BLOCKED_SOURCES: dict[str, float] = {}  # source -> block epoch
_BLOCKED_TTL = 24 * 3600

KIMI_OAUTH_TOKEN_URL = "https://auth.kimi.com/api/oauth/token"
KIMI_CLIENT_ID = "17e5f671-d194-4dfb-9706-5516cb48c098"  # Kimi Code CLI public client
_REFRESH_MARGIN = 60  # 距过期不足 60s 视为待刷新

_AUTH_HINT = ("kimi 未配置：设 KIMI_PROXY_URL 指 cliproxy kimi-tools 管理端点"
              "（若该端点要求鉴权，请把 KIMI_ACCESS_TOKEN 设为 cliproxy 管理 key），"
              "或 KIMI_ACCESS_TOKEN 直注，"
              "或 KIMI_AUTH_FILE 指 cliproxy 的 auths/kimi-*.json")


def resolve_kimi_auth_file(settings: Settings) -> Path | None:
    """Exact path or the first glob candidate whose JSON is not disabled.

    glob.glob (not Path().glob) so absolute patterns like
    /mnt/docker/cliproxy/auths/kimi-*.json work on py3.10.
    """
    import glob as _glob

    pat = settings.kimi_auth_file
    if not pat:
        return None
    candidates = sorted(_glob.glob(pat)) if any(c in pat for c in "*?[") else [pat]
    for c in candidates:
        if not Path(c).is_file():  # a glob matching a directory must be skipped
            continue
        try:
            data = json.loads(Path(c).read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and not data.get("disabled"):
            return Path(c)
    return None


class _KimiCredentials:
    """Reads cliproxy's kimi auth JSON (mtime-cached); self-refreshes as fallback."""

    def __init__(self, path: Path):
        self.path, self._mtime, self._data = path, 0.0, {}

    def _reload_if_changed(self) -> dict:
        try:
            mtime = self.path.stat().st_mtime
        except OSError as e:
            raise AuthError(f"kimi auth file unreadable: {self.path}") from e
        if mtime != self._mtime:
            try:
                self._data = json.loads(self.path.read_text())
            except (OSError, UnicodeDecodeError, ValueError) as e:
                # Corrupt auth JSON must become AuthError, never escape as a
                # UnicodeDecodeError/JSONDecodeError (a ValueError) into the
                # call body.
                raise AuthError(f"kimi auth file corrupt: {self.path}") from e
            if not isinstance(self._data, dict):
                # Valid JSON but not an object ([1,2,3], "hi", 42, null):
                # consumers access .get() on it, so degrade to AuthError
                # instead of an AttributeError mid-call.
                raise AuthError(f"kimi auth file corrupt: {self.path}")
            self._mtime = mtime
        return self._data

    @staticmethod
    def _expiry(data: dict) -> float:
        try:
            return datetime.fromisoformat(str(data.get("expired", "")).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return 0.0

    async def token(self, http: PoliteClient) -> tuple[str, str]:
        """-> (access_token, device_id)。过期则先重读（cliproxy auto-refresh 可能已写），
        仍过期则 refresh_token 自刷新并原子写回。"""
        data = self._reload_if_changed()
        if self._expiry(data) - time.time() > _REFRESH_MARGIN and data.get("access_token"):
            return data["access_token"], str(data.get("device_id") or "")
        await anyio.to_thread.run_sync(time.sleep, 1.5)  # 等 cliproxy 一拍
        data = self._reload_if_changed()
        if self._expiry(data) - time.time() > _REFRESH_MARGIN and data.get("access_token"):
            return data["access_token"], str(data.get("device_id") or "")
        if not data.get("refresh_token"):
            raise AuthError("kimi auth file has no refresh_token; 请在 cliproxy 重新登录 kimi")
        refreshed = await self._refresh(http, data["refresh_token"])
        return refreshed["access_token"], str(refreshed.get("device_id") or "")

    async def _refresh(self, http: PoliteClient, refresh_token: str) -> dict:
        body = await http.post_form(
            KIMI_OAUTH_TOKEN_URL,
            {"client_id": KIMI_CLIENT_ID, "grant_type": "refresh_token",
             "refresh_token": refresh_token})
        if not body.get("access_token"):
            raise AuthError(scrub(f"kimi token refresh failed: {str(body)[:120]}",
                                  refresh_token))

        def _write_back():
            # Atomic write-back: tmp file in the same dir + os.replace under
            # flock — a crash mid-write can never leave a truncated auth file.
            tmp_path = self.path.with_name(f".{self.path.name}.tmp")
            with self.path.open("r") as fh:
                fcntl.flock(fh, fcntl.LOCK_EX)
                data = json.load(fh)
                data.update({"access_token": body["access_token"],
                             "refresh_token": body.get("refresh_token", refresh_token),
                             "expired": (datetime.now(timezone.utc) +
                                         timedelta(seconds=int(body.get("expires_in", 900))))
                                        .isoformat().replace("+00:00", "Z"),
                             "last_refresh": datetime.now(timezone.utc).isoformat(),
                             "timestamp": int(time.time())})
                tmp_path.write_text(json.dumps(data))
                os.chmod(tmp_path, stat.S_IMODE(self.path.stat().st_mode))
                os.replace(tmp_path, self.path)
                fcntl.flock(fh, fcntl.LOCK_UN)
            self._mtime = 0.0
            return data

        return await anyio.to_thread.run_sync(_write_back)


def _generated_device_id(settings: Settings) -> str:
    """XDG-persisted device id for standalone-token users (proxy/direct paths)."""
    cfg_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) \
        / "unified-finance-mcp"
    try:
        cfg_dir.mkdir(parents=True, exist_ok=True)
        f = cfg_dir / "kimi_device_id"
        if f.exists():
            device_id = f.read_text().strip()
            if device_id:
                return device_id
        device_id = str(uuid.uuid4())
        f.write_text(device_id)
        return device_id
    except OSError:
        return str(uuid.uuid4())


def _extract_user_text(value: Any) -> str:
    """value[role] == [{"type": "text", "text": ...}, ...] -> joined text
    (user channel first, assistant fallback)."""
    if not isinstance(value, dict):
        return ""
    for role in ("user", "assistant"):
        parts = value.get(role)
        if isinstance(parts, list):
            texts = [p.get("text", "") for p in parts
                     if isinstance(p, dict) and p.get("type") == "text"]
            joined = "\n".join(t for t in texts if t)
            if joined:
                return joined
    return ""


class KimiProvider(Provider):
    name = "kimi"
    markets = frozenset({"CN", "GLOBAL"})

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._http: PoliteClient | None = None
        self._creds: _KimiCredentials | None = None

    def available(self) -> bool:
        return (bool(self.settings.kimi_proxy_url)
                or bool(self.settings.kimi_access_token)
                or resolve_kimi_auth_file(self.settings) is not None)

    def covers(self, market: str) -> bool:
        # GLOBAL = wildcard: the kimi meta-source serves global macro series
        # for any market (macro.py routes with market="US" for alphavantage).
        return "GLOBAL" in self.markets or market in self.markets

    def list_sources(self) -> list[str]:
        """All sources the client has prove-ably reached, alphabetised.
        Seeds from KNOWN_SOURCES; grows at runtime as probes succeed."""
        return sorted(_VERIFIED_SOURCES)

    def _client(self) -> PoliteClient:
        if self._http is None:
            self._http = PoliteClient(timeout=60.0,
                                      max_retries=self.settings.max_retries,
                                      min_host_delay=self.settings.min_host_delay)
        return self._http

    @property
    def _base_url(self) -> str:
        return (self.settings.kimi_proxy_url.rstrip("/")
                if self.settings.kimi_proxy_url
                else self.settings.kimi_base_url.rstrip("/"))

    async def _headers(self) -> dict[str, str]:
        headers = {
            "X-Msh-Platform": "kimi-code-cli",
            "X-Msh-Version": KIMI_DATASOURCE_VERSION,
            "X-Msh-Tool-Call-Id": str(uuid.uuid4()),
            "User-Agent": f"kimi-datasource/{KIMI_DATASOURCE_VERSION}",
        }
        if self.settings.kimi_proxy_url:
            # Proxy holds/refreshes the upstream bearer. If kimi_access_token
            # is ALSO set, its value is used as the CLIProxyAPI management key
            # for the proxy endpoint (the proxy strips it before talking to
            # Kimi, so it never leaves the cliproxy boundary). Leave empty for
            # an unauthenticated proxy.
            if self.settings.kimi_access_token:
                headers["Authorization"] = f"Bearer {self.settings.kimi_access_token}"
            headers["X-Msh-Device-Id"] = _generated_device_id(self.settings)
            return headers
        if self.settings.kimi_access_token:
            headers["Authorization"] = f"Bearer {self.settings.kimi_access_token}"
            headers["X-Msh-Device-Id"] = _generated_device_id(self.settings)
            return headers
        if self._creds is None:
            path = resolve_kimi_auth_file(self.settings)
            if path is None:
                raise AuthError(_AUTH_HINT)
            self._creds = _KimiCredentials(path)
        token, device_id = await self._creds.token(self._client())
        headers["Authorization"] = f"Bearer {token}"
        headers["X-Msh-Device-Id"] = device_id
        return headers

    async def _invoke(self, method: str, params: dict) -> dict:
        http = self._client()
        base = self._base_url
        request = lambda h: http.post_json(base, json_body={"method": method,
                                                            "params": params},
                                           headers=h)
        try:
            body = await request(await self._headers())
        except AuthError:
            # Re-read the credential file once (cliproxy may have refreshed),
            # then retry; the direct-token/proxy paths have nothing to re-read.
            if self.settings.kimi_proxy_url:
                raise AuthError("kimi proxy 已配置但返回 401：检查 proxy 容器的"
                                "凭证/cliproxy 登录状态") from None
            if self.settings.kimi_access_token:
                raise AuthError(_AUTH_HINT) from None
            self._creds = None
            body = await request(await self._headers())
        if isinstance(body, dict) and body.get("is_success") is False:
            # Scrub the in-use bearer (direct token or auth-file creds); the
            # proxy path sends none. scrub() ignores empty secrets.
            bearer = (self.settings.kimi_access_token
                      or (self._creds._data.get("access_token")
                          if self._creds else None))
            raise UpstreamError(scrub(
                _extract_user_text(body.get("error")) or str(body)[:200], bearer))
        return body if isinstance(body, dict) else {"raw": body}

    # ── R14 source-resolution gate ─────────────────────────────────────────

    async def _resolve_source(self, source: str) -> None:
        """Probe-on-first-sight gate (replaces the R13 KNOWN_SOURCES whitelist).

        Fast paths:
          * source in _VERIFIED_SOURCES -> return immediately.
          * source in _BLOCKED_SOURCES and the block is fresh (<_BLOCKED_TTL)
            -> NotFound, fail fast without spending quota.

        Slow path: probe upstream get_data_source_desc once.
          * doc contains "###"  -> add to _VERIFIED_SOURCES.
          * doc is a skeleton     -> block for _BLOCKED_TTL, NotFound.
          * upstream raised       -> propagate; do NOT block. Auth /
            rate_limited / network failures must not permanently mask a
            source (user R14 ruling "排除额度不足" — quota-only rejections
            count as transient, not as a reason to block).
        """
        if source in _VERIFIED_SOURCES:
            return
        blocked_at = _BLOCKED_SOURCES.get(source)
        if blocked_at is not None and time.time() - blocked_at < _BLOCKED_TTL:
            raise NotFound(
                f"kimi: unknown datasource {source!r} "
                f"(probe returned skeleton doc {int(time.time()-blocked_at)}s ago)")
        text = await self._probe_describe(source)  # may raise (auth/net/upstream)
        if "###" in text:
            _VERIFIED_SOURCES.add(source)
            _BLOCKED_SOURCES.pop(source, None)
            return
        _BLOCKED_SOURCES[source] = time.time()
        raise NotFound(
            f"kimi: unknown datasource {source!r}; probe doc has no API headings")

    async def _probe_describe(self, source: str) -> str:
        """Uncached describe probe (may raise UpstreamError on failure).

        Always at most one live call per miss; the verify caller caches the
        successful doc immediately. Skeleton docs return truthy (no leading
        `###`) so the caller can distinguish real docs from empty shells.
        """
        body = await self._invoke("get_data_source_desc", {"name": source})
        text = self._desc_text(body)
        if not text:
            raise UpstreamError(
                f"kimi describe({source}): no usable doc in upstream response")
        return text

    async def describe(self, source: str) -> str:
        """describe with R14 pass-through.

        Verified+described sources hit the 24h _DESC_CACHE; new sources are
        probe-verified first (adds them to _VERIFIED_SOURCES on success).
        """
        cached = _DESC_CACHE.get(source)
        if cached and time.time() - cached[0] < _DESC_TTL:
            return cached[1]
        await self._resolve_source(source)
        # _resolve_source just called upstream; now fetch again so the cache
        # write is local to one method. Two live describe hits on first sight
        # is acceptable — succeeded sources cache for 24h regardless.
        text = await self._probe_describe(source)
        if "###" not in text:
            # Race: probe succeeded but a second describe regressed — treat
            # as transient and refuse to cache skeleton output.
            raise UpstreamError(
                f"kimi describe({source}): doc regressed to skeleton after probe")
        _DESC_CACHE[source] = (time.time(), text)
        return text

    @staticmethod
    def _desc_text(body: Any) -> str:
        """Doc text from either wire shape. Official upstream envelope:
        {"result": {"user"|"assistant": [{"type": "text", ...}]}}. The
        cliproxy kimi-tools proxy instead returns the bare markdown doc as a
        top-level JSON string, which _invoke surfaces as {"raw": <str>}.
        """
        if isinstance(body, dict):
            raw = body.get("raw")
            if isinstance(raw, str):
                return raw
            return _extract_user_text(body.get("result"))
        if isinstance(body, str):
            return body
        return ""

    async def call(self, source: str, api: str, params: dict) -> dict:
        # R14 gate 1: probe-verify source before any quota spend.
        await self._resolve_source(source)
        # R14 gate 2: per-source API prefix whitelist (drop-in, no upstream
        # call for rejected traffic).
        allowed = SOURCE_ALLOWED_API_PREFIXES.get(source)
        if allowed is not None and not api.startswith(allowed):
            raise NotFound(
                f"kimi: {source}/{api} not in allowed api prefixes "
                f"({len(allowed)} prefix(es); see SOURCE_ALLOWED_API_PREFIXES)")
        merged = dict(params or {})
        if not merged.get("file_path"):
            merged["file_path"] = (f"{self.settings.kimi_files_dir}/"
                                   f"{source}_{api}_{uuid.uuid4().hex[:8]}.csv")
        body = await self._invoke("call_data_source_tool", {
            "data_source_name": source, "api_name": api, "params": merged})
        result = body.get("result") if isinstance(body, dict) else None
        text, notice = self._extract_call_result(result)
        files = body.get("files") if isinstance(body, dict) else None
        saved = await self._save_files(files or [])
        if text.lstrip().startswith("# Tianyancha Query OK"):
            # The tabular data landed in the CSV; the assistant text is just
            # the success banner. Prepend the saved-file path so callers can
            # find the payload.
            text = f"saved_files: {saved[0]}\n{text}" if saved else text
        out = {"data_preview": text,
               "saved_files": saved,
               "source": source,
               "api": api}
        if notice:
            out["notice"] = notice
        return out

    @classmethod
    def _extract_call_result(cls, result: Any) -> tuple[str, str | None]:
        """(preview_text, notice) from a call_data_source_tool `result` block.

        Two live-verified shapes (2026-09-13):
          1. official:  {"user":[{"type":"text","text": <csv-or-text>}]}
          2. kimi-sources nest: the assistant text is a stringified JSON dict
             {"data_preview": <csv|null>, "notice": ...} — e.g. stock_finance
             embeds 10k+ row CSVs this way (scholar does NOT nest).
        """
        outer = _extract_user_text(result)
        if not outer:
            return "", None
        stripped = outer.lstrip()
        if not stripped.startswith("{"):
            return outer, None
        try:
            inner = json.loads(outer)
        except (ValueError, TypeError):
            return outer, None
        if not isinstance(inner, dict):
            return outer, None
        preview = inner.get("data_preview")
        preview_s = preview if isinstance(preview, str) else ""
        notice = inner.get("notice")
        notice_s = notice if isinstance(notice, str) and notice else None
        # Nested preview wins; fall back to the outer text when the inner
        # envelope carries no data_preview of its own.
        return (preview_s or outer), notice_s

    async def _save_files(self, files: list) -> list[str]:
        out: list[str] = []
        files_dir = Path(self.settings.kimi_files_dir)
        for item in files:
            if not isinstance(item, dict):
                continue
            name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(str(item.get("name") or "")).name)
            if not name:
                continue
            content = item.get("content")
            if isinstance(content, str):
                try:
                    raw = base64.b64decode("".join(content.split())) \
                        if item.get("encoding") == "base64" else content.encode()
                except (ValueError, UnicodeEncodeError):
                    continue
            else:
                continue
            try:
                files_dir.mkdir(parents=True, exist_ok=True)
                (files_dir / name).write_bytes(raw)
            except OSError:
                continue
            out.append(str(files_dir / name))
        return out

    # ── unified-tool provider faces (R14) ──────────────────────────────────

    # NOTE: the `economic()` face is intentionally REMOVED in R13. R3/R9
    # verdicts showed both kimi macro routes (world_bank_open_data +
    # imf) were dead code paths whose api names never matched the live
    # describe doc, so alphavantage is now the sole macro provider.
    # See tools/macro.py for the new chain.

    async def shareholders(self, company: str) -> dict:
        """CN company-name major-holders fallback (tianyancha shareholders)."""
        from ..tools import kimi as kimi_tools

        return await kimi_tools.get_company_risk_cn(company, aspects=["shareholders"])
