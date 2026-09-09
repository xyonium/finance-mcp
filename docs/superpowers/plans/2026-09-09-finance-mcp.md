# unified-finance-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `unified-finance-mcp` — one MCP server unifying Yahoo Finance, TradingView, FMP, Alpha Vantage, marketaux and (via package mount) futu-opend-mcp — with market-aware source routing and rotator-friendly base-URL config.

**Architecture:** FastMCP server (`build_mcp(settings)` factory, reach-mcp style), provider registry with `available()`/`covers(market)` gating, 14 unified cross-source tools + 3 tv containers + 56 futu tools mounted from `futu-opend-mcp`, two L2 self-describing containers (`quant_backtest`, `kimi_datasource`). Key-rotating stays in `api-key-rotator` (env `*_BASE_URL` overrides); Kimi OAuth stays in CLIProxyAPI (we read its credential file, `KIMI_AUTH_FILE`).

**Tech Stack:** Python >=3.10, `mcp[cli]>=1.27` FastMCP, httpx (async), yfinance, tradingview-ta, tradingview-screener, futu-opend-mcp, pandas, uvicorn/starlette (http mode), pytest + respx + ruff.

**Spec:** `docs/superpowers/specs/2026-09-09-finance-mcp-design.md`

## Global Constraints

- Package name `unified-finance-mcp`, import `unified_finance_mcp`, CLI `unified-finance-mcp`; GitHub repo `xyonium/finance-mcp` (public, MIT).
- `requires-python = ">=3.10"`; src-layout + hatchling.
- Server-knob envs prefixed `FINANCE_MCP_*`; vendor creds unprefixed (`FMP_API_KEY`, `ALPHAVANTAGE_API_KEY`, `MARKETAUX_API_TOKEN`, `FUTU_OPEND_*`).
- Every MCP tool returns a `dict` and NEVER raises; failures return `{"error": str, "hint": str, ...}`.
- No API key may appear in any error message or log line (use `errors.scrub`).
- All sync library calls (yfinance, tradingview-*) go through `anyio.to_thread.run_sync`; `pandas` and `tradingview_screener` are eager-imported on the main thread at server start (tradingview-mcp issue #91 deadlock).
- Lint clean under `ruff check .` (line-length 100); tests green under `pytest -q -m "not integration"`.
- Commit after every task; conventional-commit style messages (`feat:`, `test:`, `chore:`).
- Reference port sources (read-only, do NOT modify):
  - tradingview-mcp v0.8.1: `/mnt/docker/mcpserver/uv-cache/archive-v0/DH-4mhgPjnG1yj0BHV4Qv/tradingview_mcp/` (alias `$TV_SRC` below)
  - yahoo-finance-mcp: `/mnt/docker/mcpserver/uv-cache/archive-v0/_DawLE8hv_Mdk63PLxTKn/server.py`
  - futu-opend-mcp: `/home/eli/futu-opend-mcp`

---

### Task 1: Repo scaffold, packaging, config, server skeleton, CI

**Files:**
- Create: `pyproject.toml`, `LICENSE`, `README.md`, `.github/workflows/ci.yml`, `.github/workflows/publish.yml`
- Create: `src/unified_finance_mcp/__init__.py`, `config.py`, `server.py`, `__main__.py`, `tools/__init__.py`, `providers/__init__.py`
- Test: `tests/test_config.py`, `tests/test_server.py`

**Interfaces:**
- Produces: `Settings` dataclass + `get_settings()`; `build_mcp(settings) -> FastMCP`; `build_app(settings) -> Starlette`; `main()` CLI (`--transport {stdio,http} --host --port`); `tools.ALL_MODULES: list[str]` (empty now, appended by later tasks).

- [ ] **Step 1: Write failing tests**

`tests/test_config.py`:
```python
from unified_finance_mcp.config import get_settings

def test_defaults(monkeypatch):
    for v in ("FMP_API_KEY", "FMP_BASE_URL", "FINANCE_MCP_TRANSPORT"):
        monkeypatch.delenv(v, raising=False)
    s = get_settings()
    assert s.transport == "stdio" and s.port == 8000
    assert s.fmp_base_url == "https://financialmodelingprep.com"
    assert s.fmp_api_key == ""

def test_env_override(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "k1")
    monkeypatch.setenv("FMP_BASE_URL", "http://api-key-rotator:8788/fmp")
    monkeypatch.setenv("FINANCE_MCP_PORT", "9000")
    s = get_settings()
    assert s.fmp_api_key == "k1" and s.fmp_base_url.endswith("/fmp") and s.port == 9000
```

`tests/test_server.py`:
```python
from unified_finance_mcp.config import get_settings
from unified_finance_mcp.server import build_mcp

def test_build_mcp():
    mcp = build_mcp(get_settings())
    assert mcp.name == "unified-finance-mcp"
```

- [ ] **Step 2: Run tests, verify FAIL** — `pytest -q` → `ModuleNotFoundError: unified_finance_mcp`

- [ ] **Step 3: Implement**

`pyproject.toml`:
```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "unified-finance-mcp"
version = "0.1.0"
description = "Unified finance & business MCP server: Yahoo, TradingView, FMP, Alpha Vantage, marketaux and Futu OpenD behind one tool surface."
readme = "README.md"
requires-python = ">=3.10"
license = "MIT"
authors = [{ name = "eli" }]
keywords = ["mcp", "finance", "stocks", "yfinance", "tradingview", "fmp", "alpha-vantage", "futu"]
classifiers = [
  "Programming Language :: Python :: 3",
  "License :: OSI Approved :: MIT License",
  "Operating System :: OS Independent",
]
dependencies = [
  "mcp[cli]>=1.27",
  "httpx>=0.27",
  "yfinance>=0.2.40",
  "tradingview-ta>=3.3",
  "tradingview-screener>=3.0",
  "futu-opend-mcp>=0.1.2",
  "pandas>=2",
  "uvicorn[standard]>=0.30",
  "starlette>=0.37",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "ruff>=0.5", "respx>=0.22"]

[project.scripts]
unified-finance-mcp = "unified_finance_mcp.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/unified_finance_mcp"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
markers = ["integration: needs live APIs or a live OpenD gateway"]

[tool.ruff]
line-length = 100
```

`src/unified_finance_mcp/config.py`:
```python
"""Settings from env. Server knobs use FINANCE_MCP_*, vendor creds unprefixed."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


DEFAULT_FMP_BASE_URL = "https://financialmodelingprep.com"
DEFAULT_AV_BASE_URL = "https://www.alphavantage.co"
DEFAULT_MARKETAUX_BASE_URL = "https://api.marketaux.com"


@dataclass(frozen=True)
class Settings:
    transport: str = field(default_factory=lambda: _env("FINANCE_MCP_TRANSPORT", "stdio"))
    host: str = field(default_factory=lambda: _env("FINANCE_MCP_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("FINANCE_MCP_PORT", 8000))
    request_timeout: float = field(default_factory=lambda: _env_float("FINANCE_MCP_REQUEST_TIMEOUT", 20.0))
    max_retries: int = field(default_factory=lambda: _env_int("FINANCE_MCP_MAX_RETRIES", 3))
    min_host_delay: float = field(default_factory=lambda: _env_float("FINANCE_MCP_MIN_HOST_DELAY", 0.5))
    futu_enabled: bool = field(default_factory=lambda: _env_bool("FINANCE_MCP_FUTU", True))
    fmp_api_key: str = field(default_factory=lambda: _env("FMP_API_KEY"))
    fmp_base_url: str = field(default_factory=lambda: _env("FMP_BASE_URL", DEFAULT_FMP_BASE_URL))
    alphavantage_api_key: str = field(default_factory=lambda: _env("ALPHAVANTAGE_API_KEY"))
    alphavantage_base_url: str = field(default_factory=lambda: _env("ALPHAVANTAGE_BASE_URL", DEFAULT_AV_BASE_URL))
    marketaux_api_token: str = field(default_factory=lambda: _env("MARKETAUX_API_TOKEN"))
    marketaux_base_url: str = field(default_factory=lambda: _env("MARKETAUX_BASE_URL", DEFAULT_MARKETAUX_BASE_URL))


def get_settings() -> Settings:
    return Settings()
```

`src/unified_finance_mcp/server.py`:
```python
"""Server assembly: build_mcp(settings) / build_app(settings) / main()."""
from __future__ import annotations

import argparse
import importlib
import logging

# Eager-import on the main thread: tradingview_screener's first Query() lazily
# imports pandas and can deadlock inside an anyio worker (tradingview-mcp#91).
import pandas  # noqa: F401
import tradingview_screener  # noqa: F401

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse

from .config import Settings, get_settings

log = logging.getLogger("unified_finance_mcp")

INSTRUCTIONS = (
    "Unified finance data server. Prefer the unified tools (get_quote, get_history, "
    "get_company_info, get_financial_report, get_news, get_technical_indicators, "
    "run_screener, get_ownership, get_events_calendar, get_economic_data, "
    "search_symbols) — they auto-route across sources by market coverage. Use the "
    "futu_*-style tools (get_snapshot, get_kline, get_option_chain, ...) for "
    "HK/CN/US depth from Futu OpenD. tv_scan/tv_analyze/egx_market/futures_market "
    "are TradingView scanner containers selected by `action`. quant_backtest runs "
    "strategy backtests; call it with action='help' for its full parameter guide. "
    "get_service_status reports which sources are configured."
)


def build_mcp(settings: Settings) -> FastMCP:
    from . import tools
    from .providers import build_providers

    mcp = FastMCP("unified-finance-mcp", instructions=INSTRUCTIONS)
    providers = build_providers(settings)
    for mod_name in tools.ALL_MODULES:
        mod = importlib.import_module(f"{__package__}.tools.{mod_name}")
        mod.register(mcp, providers, settings)
    if settings.futu_enabled:
        from .providers import futu_bridge

        futu_bridge.mount_futu_tools(mcp)
    return mcp


def build_app(settings: Settings):
    mcp = build_mcp(settings)

    @mcp.custom_route("/health", methods=["GET"])
    async def _health(request):
        return JSONResponse({"status": "ok"})

    app = mcp.streamable_http_app()
    app.state.settings = settings
    app.state.mcp = mcp
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="unified-finance-mcp")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()
    settings = get_settings()
    transport = args.transport or settings.transport
    if transport == "stdio":
        build_mcp(settings).run()
        return
    import uvicorn

    uvicorn.run(build_app(settings), host=args.host or settings.host,
                port=args.port or settings.port, log_level="info")


if __name__ == "__main__":
    main()
```

`src/unified_finance_mcp/__main__.py`: `from .server import main; main()` guarded by `if __name__ == "__main__":`.
`src/unified_finance_mcp/tools/__init__.py`: `ALL_MODULES: list[str] = []` (later tasks append module names; `test_tools_*` assert registration).
`src/unified_finance_mcp/providers/__init__.py`: `def build_providers(settings): return {}` placeholder replaced in Task 3.
`LICENSE`: MIT text, copyright `2026 eli`. `README.md`: placeholder with project name + "under construction" (finalized in Task 17).
`.github/workflows/ci.yml` and `publish.yml`: copy verbatim from `/home/eli/futu-opend-mcp/.github/workflows/` (ci: setup-python 3.12, `pip install -e ".[dev]"`, `ruff check .`, `pytest -q -m "not integration"`; publish: `v*` tag → `python -m build` → `pypa/gh-action-pypi-publish@release/v1` with `permissions: { id-token: write }`, comment noting pending-publisher config for `unified-finance-mcp`).

- [ ] **Step 4: Run tests, verify PASS** — `pip install -e ".[dev]" && pytest -q` → 3 passed; `ruff check .` clean.

- [ ] **Step 5: Create GitHub repo and push**

```bash
git add -A && git commit -m "feat: project scaffold (packaging, config, server skeleton, CI)"
gh repo create xyonium/finance-mcp --public --source . --remote origin --push
```

---

### Task 2: Error taxonomy + PoliteClient (shared async HTTP)

**Files:**
- Create: `src/unified_finance_mcp/errors.py`, `src/unified_finance_mcp/http.py`
- Test: `tests/test_http.py`, `tests/test_errors.py`

**Interfaces:**
- Produces: `ProviderError` (+ `RateLimited`, `AuthError`, `NotFound`, `UpstreamError`) with `.kind` / `.retryable`; `tool_error(msg, hint=None, **extra) -> dict`; `scrub(text, *secrets) -> str`; `PoliteClient(timeout, max_retries, min_host_delay)` with `async get_json(url, params=None, headers=None) -> Any` and `aclose()`. Later REST providers (Tasks 6-8) consume these.

- [ ] **Step 1: Write failing tests**

`tests/test_errors.py`:
```python
from unified_finance_mcp.errors import RateLimited, scrub, tool_error

def test_tool_error_shape():
    e = tool_error("boom", hint="try later", market="EG")
    assert e == {"error": "boom", "hint": "try later", "market": "EG"}

def test_scrub_removes_secrets():
    assert scrub("failed key=abc123 at fmp", "abc123") == "failed key=*** at fmp"

def test_kinds():
    assert RateLimited("x").kind == "rate_limited" and RateLimited("x").retryable
```

`tests/test_http.py`:
```python
import httpx
import pytest
import respx

from unified_finance_mcp.errors import AuthError, RateLimited
from unified_finance_mcp.http import PoliteClient


@respx.mock
async def test_retry_after_then_success():
    route = respx.get("https://x.test/data")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"ok": True}),
    ]
    async with PoliteClient(min_host_delay=0) as c:
        assert await c.get_json("https://x.test/data") == {"ok": True}
    assert route.call_count == 2


@respx.mock
async def test_auth_error_fast_fail():
    respx.get("https://x.test/data").respond(401, json={"e": 1})
    async with PoliteClient(min_host_delay=0, max_retries=3) as c:
        with pytest.raises(AuthError):
            await c.get_json("https://x.test/data")
    assert respx.calls.call_count == 1  # no retry on 4xx


@respx.mock
async def test_exhausted_retries_raise_rate_limited():
    respx.get("https://x.test/data").respond(429, headers={"Retry-After": "0"})
    async with PoliteClient(min_host_delay=0, max_retries=1) as c:
        with pytest.raises(RateLimited):
            await c.get_json("https://x.test/data")
```

- [ ] **Step 2: Run tests, verify FAIL** — `pytest tests/test_http.py tests/test_errors.py -q` → import errors.

- [ ] **Step 3: Implement**

`src/unified_finance_mcp/errors.py`:
```python
"""Error taxonomy + never-raise tool error dicts."""
from __future__ import annotations


class ProviderError(Exception):
    kind = "error"
    retryable = False


class RateLimited(ProviderError):
    kind = "rate_limited"
    retryable = True


class AuthError(ProviderError):
    kind = "auth"


class NotFound(ProviderError):
    kind = "not_found"


class UpstreamError(ProviderError):
    kind = "unavailable"
    retryable = True


def tool_error(msg: object, hint: str | None = None, **extra) -> dict:
    out = {"error": str(msg)}
    if hint:
        out["hint"] = hint
    out.update(extra)
    return out


def scrub(text: str, *secrets: str) -> str:
    for s in secrets:
        if s:
            text = text.replace(s, "***")
    return text
```

`src/unified_finance_mcp/http.py`:
```python
"""PoliteClient: shared async HTTP with per-host pacing, Retry-After and backoff.
Ported from reach-mcp's http.py; error translation goes to errors.py taxonomy."""
from __future__ import annotations

import asyncio
import time
from types import TracebackType
from typing import Any
from urllib.parse import urlparse

import httpx

from .errors import AuthError, NotFound, RateLimited, UpstreamError

UA = "unified-finance-mcp/0.1 (+https://github.com/xyonium/finance-mcp)"
_MAX_RETRY_AFTER = 10.0


class PoliteClient:
    def __init__(self, timeout: float = 20.0, max_retries: int = 3,
                 min_host_delay: float = 0.5):
        self._client = httpx.AsyncClient(timeout=timeout, headers={"User-Agent": UA})
        self._max_retries = max_retries
        self._min_gap = min_host_delay
        self._last: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "PoliteClient":
        return self

    async def __aexit__(self, *exc: TracebackType) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _pace(self, host: str) -> None:
        async with self._lock:
            gap = time.monotonic() - self._last.get(host, 0.0)
            if gap < self._min_gap:
                await asyncio.sleep(self._min_gap - gap)
            self._last[host] = time.monotonic()

    @staticmethod
    def _retry_after(resp: httpx.Response, attempt: int) -> float:
        ra = resp.headers.get("Retry-After", "")
        if ra.replace(".", "", 1).isdigit():
            return min(float(ra), _MAX_RETRY_AFTER)
        return 0.5 * (2 ** attempt)

    async def get_json(self, url: str, params: dict | None = None,
                       headers: dict | None = None) -> Any:
        host = urlparse(url).netloc
        last: Exception | None = None
        for attempt in range(self._max_retries + 1):
            await self._pace(host)
            try:
                resp = await self._client.get(url, params=params, headers=headers)
            except httpx.HTTPError as e:
                last = UpstreamError(f"network error from {host}: {e}")
                await asyncio.sleep(0.5 * (2 ** attempt))
                continue
            if resp.status_code in (429, 503):
                last = RateLimited(f"HTTP {resp.status_code} from {host}")
                await asyncio.sleep(self._retry_after(resp, attempt))
                continue
            if resp.status_code in (401, 403):
                raise AuthError(f"HTTP {resp.status_code} from {host}")
            if resp.status_code == 404:
                raise NotFound(f"HTTP 404 from {host}")
            if resp.status_code >= 400:
                raise UpstreamError(f"HTTP {resp.status_code} from {host}")
            return resp.json()
        raise last if last is not None else UpstreamError(f"request to {host} failed")
```

- [ ] **Step 4: Run tests, verify PASS** — `pytest tests/test_http.py tests/test_errors.py -q` → 6 passed. `ruff check .` clean.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: error taxonomy and shared polite HTTP client"`

---

### Task 3: Symbol normalization + provider base/registry

**Files:**
- Create: `src/unified_finance_mcp/symbols.py`, `src/unified_finance_mcp/providers/base.py`
- Modify: `src/unified_finance_mcp/providers/__init__.py` (real `build_providers`)
- Test: `tests/test_symbols.py`, `tests/test_providers_base.py`

**Interfaces:**
- Produces:
  - `parse_symbol(raw: str) -> ParsedSymbol`; `ParsedSymbol(market, local, exchange=None)` with methods `yahoo() -> str`, `futu() -> str`, `tv() -> tuple[str, str]` (exchange, symbol), `fmp() -> str`, `av() -> str` — each raising `ValueError` with a clear message when the form is unsupported for that market.
  - `class Provider` (base): attrs `name: str`, `markets: frozenset[str] | None` (`None` = global), methods `available() -> bool`, `covers(market: str) -> bool`.
  - `build_providers(settings) -> dict[str, Provider]` — returns all six providers keyed by name.

- [ ] **Step 1: Write failing tests**

`tests/test_symbols.py`:
```python
import pytest

from unified_finance_mcp.symbols import parse_symbol


def test_futu_prefix():
    p = parse_symbol("HK.00700")
    assert p.market == "HK" and p.local == "00700"
    assert p.yahoo() == "0700.HK" and p.futu() == "HK.00700"


def test_yahoo_suffix_cn():
    p = parse_symbol("600519.SS")
    assert p.market == "CN" and p.exchange == "SH" and p.futu() == "SH.600519"


def test_egypt_via_yahoo_suffix():
    p = parse_symbol("COMI.CA")
    assert p.market == "EG" and p.yahoo() == "COMI.CA" and p.tv() == ("EGX", "COMI")
    with pytest.raises(ValueError):
        p.futu()  # futu does not cover EG


def test_tv_prefix():
    p = parse_symbol("EGX:COMI")
    assert p.market == "EG" and p.yahoo() == "COMI.CA"


def test_bare_is_us():
    p = parse_symbol("AAPL")
    assert p.market == "US" and p.yahoo() == "AAPL" and p.av() == "AAPL"
    assert p.futu() == "US.AAPL"


def test_hk_padding():
    assert parse_symbol("700.HK").futu() == "HK.00700"  # HK codes are 5-digit
```

`tests/test_providers_base.py`:
```python
from unified_finance_mcp.config import get_settings
from unified_finance_mcp.providers import build_providers


def test_registry_keys():
    ps = build_providers(get_settings())
    assert set(ps) == {"yahoo", "tradingview", "fmp", "alphavantage", "marketaux", "futu"}


def test_keyless_available_and_coverage():
    ps = build_providers(get_settings())
    assert ps["yahoo"].available() and ps["tradingview"].available()
    assert ps["yahoo"].covers("EG")           # global fallback
    assert not ps["futu"].covers("EG")        # futu: no Egypt
    assert ps["futu"].covers("HK")
    assert not ps["alphavantage"].covers("EG")


def test_fmp_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.delenv("FMP_BASE_URL", raising=False)
    ps = build_providers(get_settings())
    assert not ps["fmp"].available()


def test_fmp_available_via_rotator_base_url(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    monkeypatch.setenv("FMP_BASE_URL", "http://api-key-rotator:8788/fmp")
    ps = build_providers(get_settings())
    assert ps["fmp"].available()  # rotator injects the key upstream
```

- [ ] **Step 2: Run tests, verify FAIL** — `pytest tests/test_symbols.py tests/test_providers_base.py -q` → import errors.

- [ ] **Step 3: Implement**

`src/unified_finance_mcp/symbols.py` — tables + parser (keep this exact behavior; tests pin it):
```python
"""Symbol normalization across futu / yahoo / tradingview / fmp / alphavantage forms."""
from __future__ import annotations

from dataclasses import dataclass

# futu prefix -> market
_FUTU = {"HK": "HK", "US": "US", "SH": "CN", "SZ": "CN", "SG": "SG", "MY": "MY", "JP": "JP"}
# yahoo suffix -> (market, exchange or None). NOTE: .CA is Cairo (EGX), NOT Canada.
_SUFFIX = {
    "HK": ("HK", "HKEX"), "SS": ("CN", "SH"), "SZ": ("CN", "SZ"),
    "CA": ("EG", "EGX"), "T": ("JP", "TSE"), "L": ("UK", "LSE"),
    "TO": ("CA", "TSX"), "V": ("CA", "TSXV"), "AX": ("AU", "ASX"),
    "DE": ("DE", "XETR"), "PA": ("FR", "EURONEXT"), "KS": ("KR", "KRX"),
    "TW": ("TW", "TWSE"), "NS": ("IN", "NSE"), "SI": ("SG", "SGX"),
    "KL": ("MY", "MYX"), "IS": ("TR", "BIST"),
}
# tradingview exchange -> market
_TV = {
    "EGX": "EG", "NASDAQ": "US", "NYSE": "US", "AMEX": "US", "HKEX": "HK",
    "SSE": "CN", "SZSE": "CN", "TSE": "JP", "LSE": "UK", "TSX": "CA",
    "ASX": "AU", "XETR": "DE", "EURONEXT": "FR", "KRX": "KR", "TWSE": "TW",
    "TPEX": "TW", "NSE": "IN", "SGX": "SG", "MYX": "MY", "BURSA": "MY",
    "BIST": "TR",
}
# market -> (yahoo suffix, futu prefix or None, tv exchange or None)
_MARKET = {
    "US": ("", "US", "NASDAQ"), "HK": (".HK", "HK", "HKEX"),
    "CN": (None, None, None),  # exchange-dependent, see methods
    "EG": (".CA", None, "EGX"), "JP": (".T", "JP", "TSE"), "UK": (".L", None, "LSE"),
    "CA": (".TO", None, "TSX"), "AU": (".AX", None, "ASX"), "DE": (".DE", None, "XETR"),
    "FR": (".PA", None, "EURONEXT"), "KR": (".KS", None, "KRX"), "TW": (".TW", None, "TWSE"),
    "IN": (".NS", None, "NSE"), "SG": (".SI", "SG", "SGX"), "MY": (".KL", "MY", "MYX"),
    "TR": (".IS", None, "BIST"),
}


@dataclass(frozen=True)
class ParsedSymbol:
    market: str
    local: str
    exchange: str | None = None

    def yahoo(self) -> str:
        if self.market == "CN":
            suffix = ".SZ" if self.exchange == "SZ" else ".SS"
            return f"{self.local}{suffix}"
        entry = _MARKET.get(self.market)
        if entry is None:
            raise ValueError(f"no yahoo form for market {self.market}")
        local = self.local
        if self.market == "HK":
            local = local.zfill(4)  # 700 -> 0700
        return f"{local}{entry[0]}"

    def futu(self) -> str:
        if self.market == "CN":
            prefix = "SZ" if self.exchange == "SZ" else "SH"
            return f"{prefix}.{self.local}"
        entry = _MARKET.get(self.market)
        if entry is None or entry[1] is None:
            raise ValueError(f"futu does not cover market {self.market}")
        local = self.local.zfill(5) if self.market == "HK" else self.local
        return f"{entry[1]}.{local}"

    def tv(self) -> tuple[str, str]:
        if self.market == "CN":
            return ("SZSE" if self.exchange == "SZ" else "SSE", self.local)
        entry = _MARKET.get(self.market)
        if entry is None or entry[2] is None:
            raise ValueError(f"tradingview form unknown for market {self.market}")
        return (entry[2], self.local)

    def fmp(self) -> str:
        return self.yahoo()

    def av(self) -> str:
        if self.market != "US":
            raise ValueError(f"alphavantage equities are US-only, got {self.market}")
        return self.local


def parse_symbol(raw: str) -> ParsedSymbol:
    s = raw.strip().upper()
    if not s:
        raise ValueError("empty symbol")
    if ":" in s:  # tradingview form EGX:COMI
        exch, _, local = s.partition(":")
        return ParsedSymbol(_TV.get(exch, "US"), local, exch)
    if "." in s:
        head, _, tail = s.rpartition(".")
        if head in _FUTU:  # futu form HK.00700
            return ParsedSymbol(_FUTU[head], tail, head if head in ("SH", "SZ") else None)
        if tail in _SUFFIX:  # yahoo form 0700.HK / COMI.CA
            market, exch = _SUFFIX[tail]
            return ParsedSymbol(market, head, exch)
        raise ValueError(f"unrecognized symbol form: {raw!r}")
    if s.isdigit() and len(s) == 6:  # bare A-share code: 6xxxxx -> SH else SZ
        return ParsedSymbol("CN", s, "SH" if s.startswith("6") else "SZ")
    return ParsedSymbol("US", s)
```

`src/unified_finance_mcp/providers/base.py`:
```python
"""Provider registry: availability (env) + market coverage gating."""
from __future__ import annotations

from ..config import Settings


class Provider:
    name: str = "base"
    markets: frozenset[str] | None = None  # None = global fallback

    def __init__(self, settings: Settings):
        self.settings = settings

    def available(self) -> bool:
        return True

    def covers(self, market: str) -> bool:
        return self.markets is None or market in self.markets
```

`src/unified_finance_mcp/providers/__init__.py`:
```python
"""Build the provider dict. Providers are cheap to construct; network use is lazy."""
from __future__ import annotations

from ..config import Settings
from .base import Provider


def build_providers(settings: Settings) -> dict[str, Provider]:
    from . import alphavantage, fmp, futu_bridge, marketaux, tradingview, yahoo

    instances = [
        yahoo.YahooProvider(settings),
        tradingview.TradingViewProvider(settings),
        fmp.FmpProvider(settings),
        alphavantage.AlphaVantageProvider(settings),
        marketaux.MarketauxProvider(settings),
        futu_bridge.FutuProvider(settings),
    ]
    return {p.name: p for p in instances}
```

Create the six provider modules as minimal stubs so the import works (real methods land in Tasks 4-9):
```python
# yahoo.py / tradingview.py: class YahooProvider(Provider): name="yahoo"; markets=None
# fmp.py: class FmpProvider(Provider): name="fmp"; markets=frozenset({"US"})
#         def available(self): return bool(self.settings.fmp_api_key) or \
#             self.settings.fmp_base_url != DEFAULT_FMP_BASE_URL
# alphavantage.py: name="alphavantage"; markets=frozenset({"US","FX","CRYPTO"})
#         available() = bool(settings.alphavantage_api_key) or base_url != default
# marketaux.py: name="marketaux"; markets=None; available() = token or base_url override
# futu_bridge.py: class FutuProvider(Provider): name="futu";
#         markets=frozenset({"US","HK","CN","SG","MY","JP"}); available() -> False for now
#         (Task 9 wires the real OpenD reachability check)
#         plus def mount_futu_tools(mcp) -> list[str]: return []  (Task 9 replaces)
```

- [ ] **Step 4: Run tests, verify PASS** — `pytest tests/test_symbols.py tests/test_providers_base.py -q` → all pass. `ruff check .` clean.

- [ ] **Step 5: Commit** — `git commit -am "feat: symbol normalization and provider registry"`

### Task 4: yahoo provider（yfinance 直依赖，移植 yahoo-finance-mcp 的 9 个能力）

**Files:**
- Modify: `src/unified_finance_mcp/providers/yahoo.py`（替换 T3 stub）
- Test: `tests/test_provider_yahoo.py`

**Interfaces:**
- Consumes: `symbols.ParsedSymbol`（T3）；`errors.ProviderError` 族（T2）。
- Produces（全部为 `async` 方法，返回 dict/list，失败抛 `ProviderError` 子类；统一工具经这些名字调用）:
  - `YahooProvider.quote(parsed: ParsedSymbol) -> dict`
  - `YahooProvider.history(parsed, interval="1d", start=None, end=None) -> list[dict]`
  - `YahooProvider.company_info(parsed) -> dict`
  - `YahooProvider.financial_report(parsed, statement, period) -> list[dict]`
  - `YahooProvider.news(parsed, limit=10) -> list[dict]`
  - `YahooProvider.ownership(parsed, kind) -> list[dict]`（kind: major|institutional|mutualfund|insider_transactions|insider_roster）
  - `YahooProvider.search(query, limit=10) -> list[dict]`

- [ ] **Step 1: Write failing tests**

`tests/test_provider_yahoo.py`（在库边界 mock yfinance；provider 内部用 `anyio.to_thread.run_sync` 调同步库）:
```python
from unittest.mock import MagicMock
import pytest

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.providers.yahoo import YahooProvider
from unified_finance_mcp.symbols import parse_symbol


def make_provider(monkeypatch, ticker_mock):
    import yfinance as yf
    monkeypatch.setattr(yf, "Ticker", lambda s: ticker_mock)
    monkeypatch.setattr(yf, "Search", lambda q, **kw: search_mock)
    return YahooProvider(get_settings())


async def test_quote_maps_fast_info(monkeypatch):
    t = MagicMock()
    t.fast_info = {"lastPrice": 189.5, "marketCap": 2.9e12, "currency": "USD"}
    t.info = {"shortName": "Apple Inc.", "regularMarketPrice": 189.5}
    p = make_provider(monkeypatch, t)
    q = await p.quote(parse_symbol("AAPL"))
    assert q["symbol"] == "AAPL" and q["price"] == 189.5 and q["currency"] == "USD"


async def test_history_rows(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.history.return_value = pd.DataFrame(
        {"Open": [1.0], "High": [2.0], "Low": [0.5], "Close": [1.5], "Volume": [100]},
        index=pd.to_datetime(["2026-01-02"]))
    p = make_provider(monkeypatch, t)
    rows = await p.history(parse_symbol("AAPL"), interval="1d")
    assert rows == [{"date": "2026-01-02", "open": 1.0, "high": 2.0,
                     "low": 0.5, "close": 1.5, "volume": 100}]


async def test_financial_report_columns_to_records(monkeypatch):
    import pandas as pd
    t = MagicMock()
    t.get_income_stmt.return_value = pd.DataFrame(
        {"2025-09-30": {"Total Revenue": 100, "Net Income": 20}})
    p = make_provider(monkeypatch, t)
    rows = await p.financial_report(parse_symbol("AAPL"), "income", "annual")
    assert rows[0]["date"] == "2025-09-30" and rows[0]["Total Revenue"] == 100


async def test_error_wraps_as_provider_error(monkeypatch):
    from unified_finance_mcp.errors import ProviderError
    t = MagicMock()
    t.fast_info = property(lambda s: (_ for _ in ()).throw(RuntimeError("boom")))
    type(t).fast_info = property(lambda s: (_ for _ in ()).throw(RuntimeError("boom")))
    p = make_provider(monkeypatch, t)
    with pytest.raises(ProviderError):
        await p.quote(parse_symbol("AAPL"))
```

- [ ] **Step 2: Run tests, verify FAIL** — methods don't exist on stub.

- [ ] **Step 3: Implement**

`src/unified_finance_mcp/providers/yahoo.py`：
```python
"""Yahoo Finance via yfinance (sync lib -> anyio.to_thread). Keyless, global."""
from __future__ import annotations

import anyio
import yfinance as yf

from ..errors import ProviderError
from ..symbols import ParsedSymbol
from .base import Provider

_STMT = {"income": "get_income_stmt", "balance": "get_balance_sheet",
         "cashflow": "get_cashflow"}
_HOLDER = {"major": "major_holders", "institutional": "institutional_holders",
           "mutualfund": "mutualfund_holders",
           "insider_transactions": "insider_transactions",
           "insider_roster": "insider_roster_holders"}


class YahooProvider(Provider):
    name = "yahoo"
    markets = None  # global fallback

    async def _ticker(self, parsed: ParsedSymbol):
        return yf.Ticker(parsed.yahoo())

    @staticmethod
    async def _run(fn, *args, **kwargs):
        try:
            return await anyio.to_thread.run_sync(lambda: fn(*args, **kwargs))
        except Exception as e:  # noqa: BLE001 - library raises bare Exception
            raise ProviderError(f"yahoo: {e}") from e

    async def quote(self, parsed: ParsedSymbol) -> dict:
        t = await self._ticker(parsed)
        info = dict(await self._run(lambda: t.fast_info))
        return {"symbol": parsed.yahoo(),
                "price": info.get("lastPrice") or info.get("last_price"),
                "currency": info.get("currency"),
                "market_cap": info.get("marketCap") or info.get("market_cap"),
                "source": self.name}

    async def history(self, parsed, interval="1d", start=None, end=None) -> list[dict]:
        t = await self._ticker(parsed)
        df = await self._run(t.history, interval=interval, start=start, end=end)
        if df is None or df.empty:
            return []
        df = df.reset_index()
        df.columns = [str(c).lower() for c in df.columns]
        date_col = "date" if "date" in df.columns else "datetime"
        df[date_col] = df[date_col].astype(str).str[:10]
        keep = [date_col, "open", "high", "low", "close", "volume"]
        out = df[[c for c in keep if c in df.columns]].rename(columns={date_col: "date"})
        return out.to_dict("records")

    async def company_info(self, parsed) -> dict:
        t = await self._ticker(parsed)
        return dict(await self._run(lambda: t.info))

    async def financial_report(self, parsed, statement, period) -> list[dict]:
        t = await self._ticker(parsed)
        fn = getattr(t, _STMT[statement])
        df = await self._run(fn, freq="yearly" if period == "annual" else "quarterly")
        if df is None or df.empty:
            return []
        return [dict({"date": str(c)[:10]}, **{str(k): v for k, v in df[c].dropna().items()})
                for c in df.columns]

    async def news(self, parsed, limit=10) -> list[dict]:
        t = await self._ticker(parsed)
        items = await self._run(lambda: t.news) or []
        return [{"title": i.get("title"), "publisher": i.get("publisher"),
                 "link": i.get("link"), "published": i.get("providerPublishTime"),
                 "source": self.name} for i in items[:limit]]

    async def ownership(self, parsed, kind) -> list[dict]:
        t = await self._ticker(parsed)
        df = await self._run(lambda: getattr(t, _HOLDER[kind]))
        if df is None or (hasattr(df, "empty") and df.empty):
            return []
        return df.reset_index().astype(str).to_dict("records")

    async def search(self, query, limit=10) -> list[dict]:
        s = await self._run(lambda: yf.Search(query, max_results=limit))
        return [{"symbol": q.get("symbol"), "name": q.get("shortname") or q.get("longname"),
                 "exchange": q.get("exchange"), "type": q.get("quoteType"),
                 "source": self.name} for q in (s.quotes or [])]
```

- [ ] **Step 4: Run tests, verify PASS** — `pytest tests/test_provider_yahoo.py -q` → 4 passed（search 用例并入 quote 文件，mock `yf.Search` 同法）。`ruff check .`。

- [ ] **Step 5: Commit** — `git commit -am "feat: yahoo provider"`

---

### Task 5: tradingview provider（TA 评级 + 全市场 screener）

**Files:**
- Modify: `src/unified_finance_mcp/providers/tradingview.py`（替换 stub）
- Test: `tests/test_provider_tradingview.py`

**Interfaces:**
- Consumes: T2/T3。
- Produces:
  - `TradingViewProvider.technicals(parsed, interval="1d") -> dict`（summary + oscillators + moving_averages）
  - `TradingViewProvider.screener(market="US", filters=None, sort="market_cap", order="desc", limit=25) -> list[dict]`
  - market → tradingview-screener 国家 slug 映射表 `MARKET_TO_TV_SCREENER: dict[str, str]`

- [ ] **Step 1: Write failing tests**

```python
from unittest.mock import MagicMock, patch
from unified_finance_mcp.config import get_settings
from unified_finance_mcp.providers.tradingview import TradingViewProvider
from unified_finance_mcp.symbols import parse_symbol


async def test_technicals_summary(monkeypatch):
    analysis = MagicMock()
    analysis.summary = {"RECOMMENDATION": "BUY", "BUY": 12, "SELL": 3, "NEUTRAL": 11}
    analysis.oscillators = {"RECOMMENDATION": "NEUTRAL"}
    analysis.moving_averages = {"RECOMMENDATION": "BUY"}
    analysis.indicators = {"RSI": 55.0, "close": 100.0}
    monkeypatch.setattr(
        "unified_finance_mcp.providers.tradingview._get_analysis",
        lambda exch, sym, interval: analysis)
    p = TradingViewProvider(get_settings())
    out = await p.technicals(parse_symbol("EGX:COMI"))
    assert out["summary"]["RECOMMENDATION"] == "BUY" and out["exchange"] == "EGX"


async def test_screener_egypt_market_slug(monkeypatch):
    captured = {}

    class FakeQuery:
        def set_markets(self, *markets): captured["markets"] = markets; return self
        def select(self, *cols): return self
        def order_by(self, col, asc=True): captured["sort"] = col; return self
        def limit(self, n): return self
        def get_scanner_data(self):
            return 2, MagicMock(to_dict=lambda orient: [
                {"name": "COMI", "close": 80.0, "market_cap_basic": 2.4e11}])

    monkeypatch.setattr("tradingview_screener.Query", FakeQuery)
    p = TradingViewProvider(get_settings())
    rows = await p.screener(market="EG", limit=5)
    assert captured["markets"] == ("egypt",) and rows[0]["name"] == "COMI"


async def test_screener_unsupported_market():
    p = TradingViewProvider(get_settings())
    from unified_finance_mcp.errors import ProviderError
    import pytest
    with pytest.raises(ProviderError):
        await p.screener(market="ANTARCTICA")
```

- [ ] **Step 2: Run tests, verify FAIL** — methods don't exist.

- [ ] **Step 3: Implement**

`src/unified_finance_mcp/providers/tradingview.py`：
```python
"""TradingView TA ratings + screener (sync libs -> anyio.to_thread)."""
from __future__ import annotations

import anyio
from tradingview_ta import TA_Handler, Interval
from tradingview_screener import Query

from ..errors import ProviderError
from ..symbols import ParsedSymbol
from .base import Provider

_INTERVAL = {"1m": Interval.INTERVAL_1_MINUTE, "5m": Interval.INTERVAL_5_MINUTES,
             "15m": Interval.INTERVAL_15_MINUTES, "1h": Interval.INTERVAL_1_HOUR,
             "4h": Interval.INTERVAL_4_HOURS, "1d": Interval.INTERVAL_1_DAY,
             "1wk": Interval.INTERVAL_1_WEEK, "1mo": Interval.INTERVAL_1_MONTH}

# our market code -> tradingview-screener country slug
MARKET_TO_TV_SCREENER = {
    "US": "america", "HK": "hongkong", "CN": "china", "EG": "egypt",
    "JP": "japan", "UK": "uk", "CA": "canada", "AU": "australia",
    "DE": "germany", "FR": "france", "KR": "korea", "TW": "taiwan",
    "IN": "india", "SG": "singapore", "MY": "malaysia", "TR": "turkey",
}

# canonical filter field -> (screener column, fmp fallback handled elsewhere)
FILTER_COLUMNS = {"price": "close", "market_cap": "market_cap_basic",
                  "pe_ratio": "price_earnings_ttm", "change_percent": "change",
                  "volume": "volume", "dividend_yield": "dividend_yield_current",
                  "rsi": "RSI"}
SORT_COLUMNS = {**FILTER_COLUMNS, "name": "name"}


def _get_analysis(exchange: str, symbol: str, interval: str):
    h = TA_Handler(symbol=symbol, exchange=exchange, screener="cfd" if exchange == "EGX"
                   else exchange.lower(), interval=_INTERVAL.get(interval, Interval.INTERVAL_1_DAY))
    return h.get_analysis()


class TradingViewProvider(Provider):
    name = "tradingview"
    markets = None  # global; screener gated by MARKET_TO_TV_SCREENER

    def covers(self, market: str) -> bool:
        return True  # TA works for any tv() form; screener checks slug itself

    async def technicals(self, parsed: ParsedSymbol, interval: str = "1d") -> dict:
        exchange, symbol = parsed.tv()
        try:
            a = await anyio.to_thread.run_sync(_get_analysis, exchange, symbol, interval)
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"tradingview TA: {e}") from e
        return {"symbol": symbol, "exchange": exchange, "interval": interval,
                "summary": a.summary, "oscillators": a.oscillators,
                "moving_averages": a.moving_averages,
                "indicators": {k: v for k, v in a.indicators.items() if v is not None},
                "source": self.name}

    async def screener(self, market="US", filters=None, sort="market_cap",
                       order="desc", limit=25) -> list[dict]:
        slug = MARKET_TO_TV_SCREENER.get(market)
        if slug is None:
            raise ProviderError(f"tradingview screener has no market slug for {market!r}",
                                kind="not_found")
        col = SORT_COLUMNS.get(sort, "market_cap_basic")
        cols = ["name", "description", col, "close", "change", "volume"]

        def _query():
            q = Query().set_markets(slug).select(*cols).order_by(
                col, asc=(order == "asc")).limit(limit)
            for field, rng in (filters or {}).items():
                screener_col = FILTER_COLUMNS.get(field)
                if screener_col is None:
                    continue
                from tradingview_screener import Column
                c = Column(screener_col)
                if "min" in rng:
                    q = q.where(c >= rng["min"])
                if "max" in rng:
                    q = q.where(c <= rng["max"])
            return q.get_scanner_data()

        try:
            _, df = await anyio.to_thread.run_sync(_query)
        except Exception as e:  # noqa: BLE001
            raise ProviderError(f"tradingview screener: {e}") from e
        return df.to_dict("records")
```

- [ ] **Step 4: Run tests, verify PASS** — `pytest tests/test_provider_tradingview.py -q` → 3 passed。注意 TA_Handler 的 `screener=` 参数：实现时对照 `$TV_SRC/core/services/*` 的取值惯例（egypt/cfd 等）核对。

- [ ] **Step 5: Commit** — `git commit -am "feat: tradingview provider"`

---

### Task 6: fmp provider（stable REST + 交易所探测）

**Files:**
- Modify: `src/unified_finance_mcp/providers/fmp.py`（替换 stub）
- Test: `tests/test_provider_fmp.py`

**Interfaces:**
- Consumes: `http.PoliteClient`（T2）、T3。PoliteClient 由 provider 惰性创建并复用（`self._client()` 工厂，进程级单例即可）。
- Produces:
  - `FmpProvider.quote(parsed) -> dict`、`history(parsed, interval, start, end) -> list[dict]`
  - `company_info(parsed) -> dict`、`financial_report(parsed, statement, period) -> list[dict]`
  - `news(parsed, limit) -> list[dict]`、`ownership(parsed, kind) -> list[dict]`（institutional=13F summary, insider=insider-trading/search）
  - `events_calendar(kind, start, end) -> list[dict]`（earnings|dividends|ipo）
  - `search(query, limit) -> list[dict]`
  - `covers(market) -> bool`（静态种子 {"US"} ∪ `probe_exchanges()` 24h 缓存结果）
- Auth 注入：`apikey` query 参数，值 = `settings.fmp_api_key or "rotated-by-upstream"`（rotator 会剥离替换；见 spec §3.3）。

- [ ] **Step 1: Write failing tests**

```python
import pytest
import respx
import httpx

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.providers.fmp import FmpProvider
from unified_finance_mcp.symbols import parse_symbol


def make_provider(monkeypatch, base="https://financialmodelingprep.com"):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setenv("FMP_BASE_URL", base)
    return FmpProvider(get_settings())


@respx.mock
async def test_quote(monkeypatch):
    respx.get("https://financialmodelingprep.com/stable/quote").respond(
        200, json=[{"symbol": "AAPL", "price": 189.5, "marketCap": 2.9e12}])
    p = make_provider(monkeypatch)
    q = await p.quote(parse_symbol("AAPL"))
    assert q["price"] == 189.5 and q["source"] == "fmp"
    assert respx.calls[0].request.url.params["apikey"] == "test-key"


@respx.mock
async def test_quote_non_us_symbol_untouched(monkeypatch):
    route = respx.get("https://financialmodelingprep.com/stable/quote").respond(
        200, json=[{"symbol": "0700.HK", "price": 380.0}])
    p = make_provider(monkeypatch)
    q = await p.quote(parse_symbol("HK.00700"))
    assert route.called and q["price"] == 380.0


@respx.mock
async def test_covers_after_exchange_probe(monkeypatch):
    respx.get("https://financialmodelingprep.com/stable/available-exchanges").respond(
        200, json=[{"exchange": "NASDAQ"}, {"exchange": "HKEX"}, {"exchange": "EGX"}])
    p = make_provider(monkeypatch)
    assert p.covers("US")          # static seed, no network
    await p.probe_exchanges()      # fills cache
    assert p.covers("HK") and p.covers("EG")


@respx.mock
async def test_402_maps_to_rate_limited(monkeypatch):
    from unified_finance_mcp.errors import RateLimited
    respx.get("https://financialmodelingprep.com/stable/quote").respond(402, json={})
    p = make_provider(monkeypatch)
    with pytest.raises(RateLimited):
        await p.quote(parse_symbol("AAPL"))
```

- [ ] **Step 2: Run tests, verify FAIL**

- [ ] **Step 3: Implement** `src/unified_finance_mcp/providers/fmp.py`：
- 类骨架：`name="fmp"`，静态 `markets = frozenset({"US"})`，`_exchanges_cache: tuple[float, set[str]] | None`。
- `available()`：`bool(settings.fmp_api_key) or settings.fmp_base_url != DEFAULT_FMP_BASE_URL`。
- 私有 `_get(path, **params)`：`PoliteClient.get_json(f"{base}/stable/{path}", params={**params, "apikey": key_or_placeholder})`；HTTP 402 → `RateLimited`（FMP 额度耗尽返回 402）；空列表结果 → `NotFound`。
- 方法→端点映射（全部 GET，`symbol`/`symbols` 用 `parsed.fmp()`）:
  - quote: `quote?symbol=`（批量时逗号连接，v1 单票）
  - history: `historical-price-eod-light?symbol=&from=&to=`（日内间隔 v1 不支持，交由 yahoo/av）
  - company_info: `profile?symbol=`
  - financial_report: `{income-statement|balance-sheet-statement|cashflow-statement}?symbol=&period={annual|quarter}`
  - news: `news/stock?symbols=&limit=`
  - ownership institutional: `institutional-ownership/symbol-positions-summary?symbol=&year=&quarter=`（当年当季）；insider: `insider-trading/search?symbol=`
  - events_calendar: `{earnings-calendar|dividends-calendar|ipos-calendar}?from=&to=`
  - search: `search-name?query=&limit=`
- `probe_exchanges()`：GET `available-exchanges` → 交易所名集合 → 经 `EXCHANGE_TO_MARKET` 映射（NASDAQ/NYSE/AMEX→US, HKEX→HK, SSE/SZSE→CN, EGX→EG, TSX→CA, LSE→UK, TSE→JP, XETR→DE, EURONEXT→FR, ASX→AU, SGX→SG, BURSA→MY）并入缓存（`time.monotonic()` 24h TTL，失败沿用旧缓存）。`covers()` = 静态种子 ∪ 缓存。
- 端点路径若与实盘不符（FMP stable 文档可能微调），以 `https://financialmodelingprep.com/developer/docs` 对应词条为准修正；测试已钉住 base+path 拼接方式（`/stable/quote` 前缀结构）。

- [ ] **Step 4: Run tests, verify PASS** — `pytest tests/test_provider_fmp.py -q` → 4 passed。

- [ ] **Step 5: Commit** — `git commit -am "feat: fmp provider with exchange probing"`

---

### Task 7: alphavantage provider（200-body 限流识别）

**Files:**
- Modify: `src/unified_finance_mcp/providers/alphavantage.py`（替换 stub）
- Test: `tests/test_provider_alphavantage.py`

**Interfaces:**
- Produces:
  - `quote(parsed) -> dict`（GLOBAL_QUOTE）
  - `history(parsed, interval, start, end) -> list[dict]`（TIME_SERIES_DAILY；日内 TIME_SERIES_INTRADAY）
  - `company_info(parsed) -> dict`（OVERVIEW）
  - `financial_report(parsed, statement, period) -> list[dict]`（INCOME_STATEMENT|BALANCE_SHEET|CASH_FLOW）
  - `news(parsed, limit) -> list[dict]`（NEWS_SENTIMENT）
  - `economic(indicator) -> list[dict]`（REAL_GDP|CPI|INFLATION|UNEMPLOYMENT|FEDERAL_FUNDS_RATE|TREASURY_YIELD|RETAIL_SALES|NONFARM_PAYROLL）
  - `technicals(parsed, indicator, interval) -> dict`（SMA|EMA|RSI|MACD|BBANDS|STOCH|ADX|CCI|AROON|OBV）
  - `search(query, limit) -> list[dict]`（SYMBOL_SEARCH）
  - 类常量 `ECONOMIC_INDICATORS: dict[str, str]`（规范名→AV function，供 get_economic_data 校验）

- [ ] **Step 1: Write failing tests**

```python
import pytest
import respx

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import NotFound, RateLimited
from unified_finance_mcp.providers.alphavantage import AlphaVantageProvider
from unified_finance_mcp.symbols import parse_symbol

BASE = "https://www.alphavantage.co/query"


def make_provider(monkeypatch):
    monkeypatch.setenv("ALPHAVANTAGE_API_KEY", "k")
    return AlphaVantageProvider(get_settings())


@respx.mock
async def test_quote(monkeypatch):
    respx.get(BASE).respond(200, json={"Global Quote": {"05. price": "189.50",
                                                         "08. previous close": "188.0"}})
    p = make_provider(monkeypatch)
    q = await p.quote(parse_symbol("AAPL"))
    assert q["price"] == 189.5


@respx.mock
async def test_note_body_is_rate_limited(monkeypatch):
    respx.get(BASE).respond(200, json={"Note": "Thank you for using Alpha Vantage! "
                                               "Our standard API rate limit is 25 requests per day."})
    p = make_provider(monkeypatch)
    with pytest.raises(RateLimited):
        await p.quote(parse_symbol("AAPL"))


@respx.mock
async def test_information_body_is_rate_limited(monkeypatch):
    respx.get(BASE).respond(200, json={"Information": "premium endpoint"})
    p = make_provider(monkeypatch)
    with pytest.raises(RateLimited):
        await p.economic("GDP")


@respx.mock
async def test_empty_global_quote_is_not_found(monkeypatch):
    respx.get(BASE).respond(200, json={"Global Quote": {}})
    p = make_provider(monkeypatch)
    with pytest.raises(NotFound):
        await p.quote(parse_symbol("AAPL"))


@respx.mock
async def test_economic_series(monkeypatch):
    respx.get(BASE).respond(200, json={"name": "Real Gross Domestic Product",
                                       "data": [{"date": "2025-01-01", "value": "23000.0"}]})
    p = make_provider(monkeypatch)
    rows = await p.economic("GDP")
    assert rows[0]["date"] == "2025-01-01" and rows[0]["value"] == 23000.0
```

- [ ] **Step 2: Run tests, verify FAIL**

- [ ] **Step 3: Implement** `src/unified_finance_mcp/providers/alphavantage.py`：
- `name="alphavantage"`, `markets=frozenset({"US","FX","CRYPTO"})`；`available()` 同 FMP 规则（key 或 base_url 覆盖，默认 `https://www.alphavantage.co`）。
- 私有 `_get(**params)`：`PoliteClient.get_json(f"{base}/query", params={**params, "apikey": key_or_placeholder})`；返回 dict 含 `"Note"` 或 `"Information"` 键 → `RateLimited`（hint 文本含"日额度耗尽/配置 rotator"）；含 `"Error Message"` → `NotFound`。
- 各方法按上表映射 function 名；数值字段 `float()` 化；US-only 校验走 `parsed.av()`（非 US 抛 ValueError → 包成 `NotFound`）。
- `ECONOMIC_INDICATORS = {"GDP": "REAL_GDP", "CPI": "CPI", "INFLATION": "INFLATION", "UNEMPLOYMENT": "UNEMPLOYMENT", "FEDERAL_FUNDS_RATE": "FEDERAL_FUNDS_RATE", "TREASURY_YIELD_10Y": "TREASURY_YIELD", "RETAIL_SALES": "RETAIL_SALES", "NONFARM_PAYROLL": "NONFARM_PAYROLL"}`；TREASURY_YIELD 附 `maturity=10year`。

- [ ] **Step 4: Run tests, verify PASS** — `pytest tests/test_provider_alphavantage.py -q` → 5 passed。

- [ ] **Step 5: Commit** — `git commit -am "feat: alphavantage provider with 200-body rate-limit detection"`

---

### Task 8: marketaux provider（并入 get_news 的新闻源）

**Files:**
- Modify: `src/unified_finance_mcp/providers/marketaux.py`（替换 stub）
- Test: `tests/test_provider_marketaux.py`

**Interfaces:**
- Produces: `MarketauxProvider.news(parsed: ParsedSymbol | None, limit=10) -> list[dict]`；`search` 不支持（调用方跳过）。

- [ ] **Step 1: Write failing tests**

```python
import respx
from unified_finance_mcp.config import get_settings
from unified_finance_mcp.providers.marketaux import MarketauxProvider
from unified_finance_mcp.symbols import parse_symbol


def make_provider(monkeypatch):
    monkeypatch.setenv("MARKETAUX_API_TOKEN", "tok")
    return MarketauxProvider(get_settings())


@respx.mock
async def test_news_with_symbol(monkeypatch):
    respx.get("https://api.marketaux.com/v1/news/all").respond(200, json={
        "data": [{"title": "Apple beats", "url": "https://x",
                  "published_at": "2026-01-02T10:00:00Z",
                  "entities": [{"symbol": "AAPL"}]}]})
    p = make_provider(monkeypatch)
    items = await p.news(parse_symbol("AAPL"), limit=5)
    assert items[0]["title"] == "Apple beats" and items[0]["source"] == "marketaux"
    params = respx.calls[0].request.url.params
    assert params["symbols"] == "AAPL" and params["api_token"] == "tok"


@respx.mock
async def test_news_general_without_symbol(monkeypatch):
    respx.get("https://api.marketaux.com/v1/news/all").respond(200, json={"data": []})
    p = make_provider(monkeypatch)
    assert await p.news(None, limit=5) == []
    assert "symbols" not in respx.calls[0].request.url.params
```

- [ ] **Step 2: Run tests, verify FAIL**

- [ ] **Step 3: Implement** — `name="marketaux"`, `markets=None`；`available()` = token 或 base_url 覆盖（默认 `https://api.marketaux.com`）；`news()` GET `/v1/news/all?api_token=&language=en&limit=&symbols=`（parsed 非空时带 `parsed.yahoo()`；解析 `data[]` 为 `{"title","url","published","entities","source":"marketaux"}`）。

- [ ] **Step 4: Run tests, verify PASS** — 2 passed。

- [ ] **Step 5: Commit** — `git commit -am "feat: marketaux provider"`

---

### Task 9: futu_bridge（挂载 56 个 futu 工具 + 统一工具内部桥接）

**Files:**
- Modify: `src/unified_finance_mcp/providers/futu_bridge.py`（替换 stub）
- Test: `tests/test_futu_bridge.py`

**Interfaces:**
- Consumes: 已安装包 `futu_opend_mcp`（其 `tools/_base.py` 的 FastMCP 单例与 `skill_fn`）；T3。
- Produces:
  - `mount_futu_tools(mcp) -> list[str]`：把 futu_opend_mcp 全部工具转注册到本 server，返回挂载的工具名；重名跳过并 `log.warning`。
  - `FutuProvider.quote(parsed) -> dict`、`history(parsed, interval, start, end) -> list[dict]`
  - `FutuProvider.available() -> bool`：OpenD TCP 可达性探测（`settings` 读 `FUTU_OPEND_HOST/PORT`，默认 127.0.0.1:11111；5s 缓存避免每次 TCP）。

- [ ] **Step 1: Write failing tests**

```python
import pytest
from mcp.server.fastmcp import FastMCP

import futu_opend_mcp.tools  # noqa: F401 - registration side effect
from unified_finance_mcp.config import get_settings
from unified_finance_mcp.providers import futu_bridge


def test_mount_registers_all_futu_tools():
    mcp = FastMCP("test")
    names = futu_bridge.mount_futu_tools(mcp)
    assert len(names) >= 50 and "get_snapshot" in names and "get_kline" in names


def test_mount_skips_conflicts():
    mcp = FastMCP("test")

    @mcp.tool(name="get_snapshot")
    def mine() -> dict:  # noqa: D103
        return {"mine": True}

    names = futu_bridge.mount_futu_tools(mcp)
    assert "get_snapshot" not in names  # conflict skipped


async def test_quote_via_futu_skill(monkeypatch):
    async def fake_run(skill, **kwargs):
        assert skill == "get_snapshot"
        return {"code": kwargs["code"], "last_price": 380.0}
    monkeypatch.setattr(futu_bridge, "_run_skill", fake_run)
    monkeypatch.setattr(futu_bridge.FutuProvider, "available", lambda self: True)
    p = futu_bridge.FutuProvider(get_settings())
    q = await p.quote(__import__("unified_finance_mcp.symbols", fromlist=["parse_symbol"])
                      .parse_symbol("HK.00700"))
    assert q["last_price"] == 380.0


async def test_unavailable_when_opend_down(monkeypatch):
    monkeypatch.setattr(futu_bridge, "_opend_reachable", lambda host, port: False)
    p = futu_bridge.FutuProvider(get_settings())
    assert p.available() is False
```

- [ ] **Step 2: Run tests, verify FAIL**

- [ ] **Step 3: Implement** `src/unified_finance_mcp/providers/futu_bridge.py`：
```python
"""Mount futu-opend-mcp's tools and bridge unified calls into futu skills."""
from __future__ import annotations

import logging
import os
import socket
import time

from ..errors import ProviderError
from ..symbols import ParsedSymbol
from .base import Provider

log = logging.getLogger(__name__)

_reach_cache: dict[tuple[str, int], tuple[float, bool]] = {}


def _opend_reachable(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def opend_available() -> bool:
    host = os.environ.get("FUTU_OPEND_HOST", "127.0.0.1")
    port = int(os.environ.get("FUTU_OPEND_PORT", "11111") or 11111)
    key = (host, port)
    ts, ok = _reach_cache.get(key, (0.0, False))
    if time.monotonic() - ts > 5:
        ok = _opend_reachable(host, port)
        _reach_cache[key] = (time.monotonic(), ok)
    return ok


def mount_futu_tools(mcp) -> list[str]:
    import futu_opend_mcp.tools  # noqa: F401 - registration side effect
    from futu_opend_mcp.tools import _base as futu_base

    mounted: list[str] = []
    existing = {t.name for t in mcp._tool_manager.list_tools()}
    for t in futu_base.mcp._tool_manager.list_tools():
        if t.name in existing:
            log.warning("futu tool %r conflicts with unified tool, skipped", t.name)
            continue
        mcp.add_tool(t.fn, name=t.name, description=t.description,
                     annotations=t.annotations)
        existing.add(t.name)
        mounted.append(t.name)
    log.info("mounted %d futu-opend-mcp tools", len(mounted))
    return mounted


async def _run_skill(skill: str, **kwargs):
    """Call a futu-opend-mcp skill; returns its dict result (never raises)."""
    from futu_opend_mcp.tools._base import skill_fn

    fn = skill_fn(skill)
    return await fn(**kwargs)


class FutuProvider(Provider):
    name = "futu"
    markets = frozenset({"US", "HK", "CN", "SG", "MY", "JP"})

    def available(self) -> bool:
        return opend_available()

    async def quote(self, parsed: ParsedSymbol) -> dict:
        result = await _run_skill("get_snapshot", code=parsed.futu())
        if isinstance(result, dict) and result.get("error"):
            raise ProviderError(f"futu: {result['error']}")
        return result

    async def history(self, parsed, interval="1d", start=None, end=None) -> list[dict]:
        # futu ktype names: K_DAY/K_WEEK/K_MON/K_60M/...; map common intervals
        ktype = {"1d": "K_DAY", "1wk": "K_WEEK", "1mo": "K_MON",
                 "1h": "K_60M", "30m": "K_30M", "15m": "K_15M",
                 "5m": "K_5M", "1m": "K_1M"}.get(interval, "K_DAY")
        kwargs = {"code": parsed.futu(), "ktype": ktype}
        if start:
            kwargs["start"] = start
        if end:
            kwargs["end"] = end
        result = await _run_skill("get_kline", **kwargs)
        if isinstance(result, dict) and result.get("error"):
            raise ProviderError(f"futu: {result['error']}")
        return result if isinstance(result, list) else result.get("klines", result)
```

注意：`_run_skill` 的参数名（`code=`/`ktype=` 等）以实现时 `~/futu-opend-mcp/src/futu_opend_mcp/tools/quote.py` 与 skills 层的真实签名为准；若 skill_fn 是同步返回 callable 则直接调用，若是 async 则 await（对照 `~/futu-opend-mcp/src/futu_opend_mcp/tools/_base.py`）。`_tool_manager` 为 mcp 内部属性，T16 的不变量测试钉住其存在性。

- [ ] **Step 4: Run tests, verify PASS** — `pytest tests/test_futu_bridge.py -q` → 4 passed（无需真实 OpenD，全部 mock）。

- [ ] **Step 5: Commit** — `git commit -am "feat: futu bridge (mount 56 tools + unified routing)"`

---

### Task 10: 路由助手 + get_quote / get_history

**Files:**
- Create: `src/unified_finance_mcp/tools/_routing.py`
- Create: `src/unified_finance_mcp/tools/quote.py`, `src/unified_finance_mcp/tools/history.py`
- Modify: `src/unified_finance_mcp/tools/__init__.py`（ALL_MODULES += ["quote", "history"]）
- Test: `tests/test_routing.py`, `tests/test_tools_quote.py`

**Interfaces:**
- Consumes: T2 errors、T3 providers/symbols、T4-T9 provider 方法。
- Produces:
  - `route_and_call(*, market, chain, providers, call, explicit_source="auto") -> dict`（永不 raise）
  - 统一工具 `get_quote(codes: list[str], source="auto") -> dict`、`get_history(code, interval="1d", start=None, end=None, source="auto") -> dict`
  - 后续任务复用 `route_and_call` 与各 provider 方法名。

- [ ] **Step 1: Write failing tests**

`tests/test_routing.py`:
```python
from unified_finance_mcp.errors import ProviderError
from unified_finance_mcp.tools._routing import route_and_call


class FakeProvider:
    def __init__(self, name, markets=None, available=True, result=None, exc=None):
        self.name, self.markets, self._av = name, markets, available
        self._result, self._exc = result, exc
        self.called = 0
    def available(self): return self._av
    def covers(self, m): return self.markets is None or m in self.markets


async def call(p):
    p.called += 1
    if p._exc: raise p._exc
    return p._result


async def test_skips_non_covering_without_calling():
    a = FakeProvider("a", markets={"US"}, result={"src": "a"})
    b = FakeProvider("b", result={"src": "b"})
    out = await route_and_call(market="EG", chain=["a", "b"],
                               providers={"a": a, "b": b}, call=call)
    assert out == {"src": "b"} and a.called == 0 and b.called == 1


async def test_no_covering_source_returns_immediate_error():
    a = FakeProvider("a", markets={"US"})
    out = await route_and_call(market="EG", chain=["a"], providers={"a": a}, call=call)
    assert "error" in out and "EG" in out["error"] and a.called == 0
    assert "hint" in out


async def test_fallback_collects_source_errors():
    a = FakeProvider("a", exc=ProviderError("down"))
    b = FakeProvider("b", result={"ok": 1})
    out = await route_and_call(market="US", chain=["a", "b"],
                               providers={"a": a, "b": b}, call=call)
    assert out == {"ok": 1}


async def test_all_fail_reports_each():
    a = FakeProvider("a", exc=ProviderError("x1"))
    b = FakeProvider("b", exc=ValueError("x2"))
    out = await route_and_call(market="US", chain=["a", "b"],
                               providers={"a": a, "b": b}, call=call)
    assert out["source_errors"] == {"a": "error: x1", "b": "error: x2"}


async def test_explicit_source_unconfigured():
    a = FakeProvider("a", available=False)
    out = await route_and_call(market="US", chain=["a"], providers={"a": a},
                               call=call, explicit_source="a")
    assert "not configured" in out["error"]
```

`tests/test_tools_quote.py`（build_mcp 全装配，调工具函数本体）:
```python
from unittest.mock import AsyncMock
from unified_finance_mcp.config import get_settings
from unified_finance_mcp.providers import build_providers
from unified_finance_mcp.tools import quote as quote_mod


async def test_get_quote_routes_yahoo_for_egx(monkeypatch):
    providers = build_providers(get_settings())
    providers["yahoo"].quote = AsyncMock(return_value={"price": 80.0, "source": "yahoo"})
    providers["futu"].quote = AsyncMock(side_effect=AssertionError("must not be called"))
    results = {}

    class FakeMCP:
        def tool(self):
            def deco(fn): results[fn.__name__] = fn; return fn
            return deco

    quote_mod.register(FakeMCP(), providers, get_settings())
    out = await results["get_quote"](["COMI.CA"])
    assert out["data"]["COMI.CA"] == {"price": 80.0, "source": "yahoo"}
    providers["futu"].quote.assert_not_called()


async def test_get_quote_bad_symbol_never_raises(monkeypatch):
    providers = build_providers(get_settings())
    results = {}
    class FakeMCP:
        def tool(self):
            def deco(fn): results[fn.__name__] = fn; return fn
            return deco
    quote_mod.register(FakeMCP(), providers, get_settings())
    out = await results["get_quote"](["???bad"])
    assert "error" in out["data"]["???bad"]
```

- [ ] **Step 2: Run tests, verify FAIL**

- [ ] **Step 3: Implement**

`src/unified_finance_mcp/tools/_routing.py`:
```python
"""Market-aware source routing for unified tools. Never raises."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from ..errors import tool_error
from ..providers.base import Provider


def _classify(e: Exception) -> str:
    return f"{getattr(e, 'kind', 'error')}: {str(e)[:200]}"


async def route_and_call(*, market: str, chain: list[str],
                         providers: dict[str, Provider],
                         call: Callable[[Provider], Awaitable[dict]],
                         explicit_source: str = "auto") -> dict:
    if explicit_source and explicit_source != "auto":
        p = providers.get(explicit_source)
        if p is None:
            return tool_error(f"unknown source {explicit_source!r}",
                              hint=f"known sources: {sorted(providers)}")
        if not p.available():
            return tool_error(f"source {explicit_source} not configured",
                              hint=f"configure its env, or use source='auto'")
        if not p.covers(market):
            return tool_error(f"source {explicit_source} does not cover market {market}",
                              hint="use source='auto' for market-aware routing")
        try:
            return await call(p)
        except Exception as e:  # noqa: BLE001
            return tool_error(_classify(e), source=explicit_source)
    candidates = [providers[n] for n in chain
                  if n in providers and providers[n].available() and providers[n].covers(market)]
    if not candidates:
        covering = [n for n in chain if n in providers and providers[n].covers(market)]
        return tool_error(
            f"no configured source covers market {market}",
            hint=(f"market {market} 可被 {', '.join(covering) or '无'} 覆盖；"
                  "配置对应 env 启用后重试"),
            market=market)
    source_errors: dict[str, str] = {}
    for p in candidates:
        try:
            return await call(p)
        except Exception as e:  # noqa: BLE001
            source_errors[p.name] = _classify(e)
    return tool_error("all candidate sources failed", source_errors=source_errors,
                      market=market)
```

`src/unified_finance_mcp/tools/quote.py`:
```python
"""get_quote: latest price snapshot, auto-routed by market."""
from __future__ import annotations

from ..errors import tool_error
from ..symbols import parse_symbol
from ._routing import route_and_call

CHAIN = ["futu", "yahoo", "fmp", "alphavantage"]


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_quote(codes: list[str], source: str = "auto") -> dict:
        """Get latest price/quote snapshot for one or more symbols.

        Accepts futu (HK.00700), yahoo (0700.HK, COMI.CA) or TradingView
        (EGX:COMI) symbol forms; bare tickers default to US. `source` may be
        auto | futu | yahoo | fmp | alphavantage.
        """
        out: dict[str, dict] = {}
        for code in codes:
            try:
                parsed = parse_symbol(code)
            except ValueError as e:
                out[code] = tool_error(str(e), hint="symbol 写法: HK.00700 / 0700.HK / "
                                                    "COMI.CA / EGX:COMI / AAPL")
                continue
            out[code] = await route_and_call(
                market=parsed.market, chain=CHAIN, providers=providers,
                call=lambda p: p.quote(parsed), explicit_source=source)
        return {"data": out}
```

`src/unified_finance_mcp/tools/history.py` — same shape; `get_history(code, interval="1d", start=None, end=None, source="auto")`，chain 同 quote，`call=lambda p: p.history(parsed, interval, start, end)`；futu 不能解析的非 futu 市场由 `covers()` 自动排除。

- [ ] **Step 4: Run tests, verify PASS** — `pytest tests/test_routing.py tests/test_tools_quote.py -q` → 全过。

- [ ] **Step 5: Commit** — `git commit -am "feat: market-aware routing + get_quote/get_history"`

---

### Task 11: get_company_info / get_financial_report / get_news

**Files:**
- Create: `tools/fundamentals.py`（info+report）、`tools/news.py`
- Modify: `tools/__init__.py`（ALL_MODULES += ["fundamentals", "news"]）
- Test: `tests/test_tools_fundamentals.py`, `tests/test_tools_news.py`

**Interfaces:**
- Consumes: T10 `route_and_call`；provider 方法 `company_info/financial_report/news`（T4-T8）。
- Produces 工具:
  - `get_company_info(symbol, source="auto")`；chain `["yahoo", "fmp", "alphavantage"]`
  - `get_financial_report(symbol, statement="income", period="annual", source="auto")`；statement∈{income,balance,cashflow}，period∈{annual,quarterly}；chain `["fmp", "yahoo", "alphavantage"]`
  - `get_news(symbol=None, limit=10, source="auto")`；chain `["fmp", "alphavantage", "marketaux", "yahoo"]`（symbol=None 时 market="GLOBAL"，仅 marketaux 返回综合新闻，其余源在 symbol 为空时跳过）

- [ ] **Step 1: Write failing tests**（FakeMCP 模式同 T10）
```python
async def test_company_info_chain_order(monkeypatch):
    # yahoo 成功 -> fmp/alphavantage 不被调用
    ...
async def test_financial_report_validates_statement():
    out = await fn("AAPL", statement="bogus")
    assert "error" in out and "income|balance|cashflow" in out["hint"]
async def test_news_without_symbol_uses_marketaux_only(monkeypatch):
    # marketaux.news(None, ...) 被调用；fmp.news 不被调用
    ...
```

- [ ] **Step 2: Run tests, verify FAIL**

- [ ] **Step 3: Implement** — 三工具均按 T10 quote.py 模式：parse_symbol → route_and_call。`get_news` 的 call 闭包：`lambda p: p.news(parsed, limit)`；`symbol is None` 时仅 chain `["marketaux", "fmp"]` 且 `parsed=None`。statement/period 用 `Literal` 类型注解让 schema 自校验，外加手动 guard 返回 hint。错误均走 `tool_error`。

- [ ] **Step 4: Run tests, verify PASS**

- [ ] **Step 5: Commit** — `git commit -am "feat: company info, financial report, news tools"`

---

### Task 12: get_technical_indicators / run_screener

**Files:**
- Create: `tools/technicals.py`, `tools/screener.py`
- Modify: `tools/__init__.py`（+= ["technicals", "screener"]）
- Test: `tests/test_tools_technicals.py`, `tests/test_tools_screener.py`

**Interfaces:**
- Produces:
  - `get_technical_indicators(symbol, indicators="summary", interval="1d", source="auto")`：`indicators="summary"` 或逗号列表（RSI,MACD,SMA,...）。auto：summary/评级 → tradingview；显式指标列表 → tradingview（其 indicators 全量已含）失败再 alphavantage 逐指标。
  - `run_screener(market="US", filters=None, sort="market_cap", order="desc", limit=25, source="auto")`：chain `["tradingview", "fmp"]`；filters 为 `{"field": {"min": x, "max": y}}`，field 取 T5 `FILTER_COLUMNS` 键；fmp 路径用 company-screener 原生参数映射（marketCapMoreThan/LowerThan、priceMoreThan/LowerThan、volumeMoreThan、dividendMoreThan、limit），不可映射字段在 docstring 标注 tv-only。

- [ ] **Step 1: Write failing tests**
```python
async def test_technicals_summary_default_to_tv(monkeypatch): ...
async def test_technicals_explicit_list_falls_back_to_av(monkeypatch): ...
async def test_screener_rejects_unknown_filter_field():
    out = await fn(market="US", filters={"nope": {"min": 1}})
    assert "error" in out and "FILTER" in out["hint"].upper()
```

- [ ] **Step 2: Run tests, verify FAIL**

- [ ] **Step 3: Implement** — 模式同前。`get_technical_indicators` 内：summary → `p.technicals(parsed, interval)`（tv）；列表且 av 可用 → 逐指标 `av.technicals(parsed, ind, interval)` 聚合；否则 tv 全量 indicators 中按键筛选子集返回并注明 `source`。`run_screener` 校验 filters 键 ∈ FILTER_COLUMNS，否则 `tool_error(hint=f"可用字段: {sorted(FILTER_COLUMNS)}")`。

- [ ] **Step 4: Run tests, verify PASS**

- [ ] **Step 5: Commit** — `git commit -am "feat: technical indicators and screener tools"`

---

### Task 13: get_ownership / get_events_calendar / get_economic_data / search_symbols

**Files:**
- Create: `tools/ownership.py`, `tools/calendar.py`, `tools/macro.py`, `tools/search.py`
- Modify: `tools/__init__.py`（+= 4 项）
- Test: `tests/test_tools_misc.py`

**Interfaces:**
- Produces:
  - `get_ownership(symbol, kind="major", source="auto")`；kind∈{major,institutional,mutualfund,insider_transactions,insider_roster}；chain `["yahoo", "fmp"]`（fmp 仅 institutional/insider_transactions，其余 kind 跳过 fmp——在 call 闭包内对不支持的 (provider,kind) 组合抛 `NotFound` 让路由自然回退）
  - `get_events_calendar(type="earnings", start=None, end=None, source="auto")`；type∈{earnings,dividends,ipo}；chain `["fmp", "alphavantage"]`（av 仅 earnings：EARNINGS_CALENDAR 返回 CSV 文本，用 `csv.DictReader(io.StringIO(...))` 解析；起止默认今天±7天）
  - `get_economic_data(indicator, source="auto")`；indicator 规范名 = `alphavantage.ECONOMIC_INDICATORS` 键（GDP/CPI/INFLATION/UNEMPLOYMENT/FEDERAL_FUNDS_RATE/TREASURY_YIELD_10Y/RETAIL_SALES/NONFARM_PAYROLL）；chain v1 仅 `["alphavantage"]`（kimi 宏观链在 T18 追加为链首）
  - `search_symbols(query, limit=10, source="auto")`；chain `["fmp", "alphavantage", "yahoo"]`

- [ ] **Step 1: Write failing tests**（每工具至少：chain 顺序 / 参数校验 hint / 单源失败回退）
```python
async def test_ownership_kind_not_supported_by_fmp_falls_back_to_yahoo(): ...
async def test_events_calendar_av_csv_parsed(monkeypatch): ...
async def test_economic_data_unknown_indicator_hint(): ...
async def test_search_symbols_chain(): ...
```

- [ ] **Step 2: Run tests, verify FAIL**

- [ ] **Step 3: Implement** — 同 T10 模式；`_routing.route_and_call` 复用。

- [ ] **Step 4: Run tests, verify PASS**

- [ ] **Step 5: Commit** — `git commit -am "feat: ownership, calendar, macro, symbol search tools"`

---

### Task 14: TradingView 容器三件套（tv_scan / tv_analyze / egx_market）

**Files:**
- Create: `tools/containers.py`, `tools/_tv_scanners.py`, `data/egx_indices.py`（vendored 成分股表）
- Modify: `tools/__init__.py`（+= ["containers"]）
- Test: `tests/test_containers.py`

**Interfaces:**
- Consumes: T5 tradingview provider 设施（`anyio.to_thread`、TA_Handler、Query）。
- Produces 工具:
  - `tv_scan(action, exchange="US", timeframe="1d", limit=25)`；action∈{top_gainers,top_losers,bollinger_squeeze,rating,consecutive_candles,volume_breakout,smart_volume}
  - `tv_analyze(action, symbol, exchange=None, timeframe="1d")`；action∈{summary,coin,candle_pattern,multi_timeframe,volume_confirmation}
  - `egx_market(action, ...)`；action∈{overview,sector_scan,index,screener,trade_plan,fibonacci}

- [ ] **Step 1: Write failing tests**
```python
async def test_tv_scan_unknown_action_lists_valid():
    out = await tv_scan(action="bogus")
    assert "error" in out and "top_gainers" in out["hint"]
async def test_tv_scan_dispatches(monkeypatch):
    # monkeypatch _tv_scanners.top_gainers -> sentinel; assert routed
async def test_egx_index_constituents_vendored():
    from unified_finance_mcp.data.egx_indices import EGX30
    assert "COMI" in EGX30 and len(EGX30) >= 30
```

- [ ] **Step 2: Run tests, verify FAIL**

- [ ] **Step 3: Implement**
- `_tv_scanners.py`：从 `$TV_SRC/core/services/screener_service.py` 与 `scanner_service.py` 移植 7 个 scan 函数与 5 个 analyze 函数（逐个复制函数体，统一改为返回 dict/list、异常抛 ProviderError、`anyio.to_thread` 包装、去掉原项目的 response envelope——envelope 由容器层统一）。
- `data/egx_indices.py`：vendor `$TV_SRC/core/data/egx_indices.py` 的 EGX30/EGX70/EGX100/SHARIAH33 成分表；**不** vendor `egx_sectors.py` 的硬编码市值快照（spec：实时重算）。
- `containers.py`：三个容器函数，`_ROUTES: dict[str, dict[str, callable]]` 分派（futu-opend-mcp corporate_actions 模式）；未知 action → `tool_error(hint=f"可用 action: {...}")`；docstring 每个 action 一行。egx_market 的 sector_scan/screener 用 T5 的 `Query().set_markets("egypt")` 实时取数。

- [ ] **Step 4: Run tests, verify PASS**

- [ ] **Step 5: Commit** — `git commit -am "feat: tradingview containers (scan/analyze/egx)"`

---

### Task 15: quant_backtest L2 容器

**Files:**
- Create: `tools/_backtest_engine.py`（sync pandas 引擎）、`tools/backtest.py`
- Modify: `tools/__init__.py`（+= ["backtest"]）
- Test: `tests/test_backtest.py`

**Interfaces:**
- Consumes: T4 yahoo history（经 `anyio.to_thread`）。
- Produces 工具: `quant_backtest(action, symbol=None, strategy=None, strategies=None, period="1y", interval="1d", capital=10000.0, commission_pct=0.0, slippage_pct=0.0, folds=4, params=None)`；action∈{help,run,compare,walk_forward}；策略 9 个：ma_cross,rsi,bollinger,macd,ema_cross,supertrend,donchian,rsi_pullback,keltner_breakout,triple_ema（以移植源实际清单为准）。

- [ ] **Step 1: Write failing tests**
```python
async def test_help_lists_all_actions_and_strategies():
    out = await quant_backtest(action="help")
    for a in ("run", "compare", "walk_forward"): assert a in out["actions"]
    assert "rsi" in out["strategies"]

async def test_run_on_synthetic_data(monkeypatch):
    # monkeypatch engine.fetch -> 200 行合成 OHLCV DataFrame
    out = await quant_backtest(action="run", symbol="AAPL", strategy="ma_cross")
    assert {"total_return", "sharpe", "max_drawdown", "trades"} <= set(out["metrics"])
```

- [ ] **Step 2: Run tests, verify FAIL**

- [ ] **Step 3: Implement**
- `_backtest_engine.py`：移植 `$TV_SRC/core/services/backtest_service.py` 的 9 个 `_run_*` 策略与 run_backtest/compare_strategies/walk_forward_backtest；数据获取改为内部 `fetch(symbol, period, interval)`（yfinance，`anyio.to_thread`）；返回统一 metrics dict。
- `backtest.py`：容器函数；`action="help"` 返回 `BACKTEST_HELP = {"actions": {...每 action 参数表...}, "strategies": {...每策略一句话+默认 params...}, "examples": [...]}`；未知 strategy → hint 列全部策略。主工具 description 仅一行 + "action='help'"。

- [ ] **Step 4: Run tests, verify PASS**

- [ ] **Step 5: Commit** — `git commit -am "feat: quant_backtest L2 container (9 strategies)"`

---

### Task 16: get_service_status + server instructions 定稿 + 不变量测试

**Files:**
- Create: `tools/diagnostics.py`
- Modify: `tools/__init__.py`（+= ["diagnostics"]）、`server.py`（INSTRUCTIONS 按最终工具面定稿）
- Test: `tests/test_diagnostics.py`, `tests/test_invariants.py`

- [ ] **Step 1: Write failing tests**

`tests/test_invariants.py`:
```python
from unified_finance_mcp.config import get_settings
from unified_finance_mcp.server import build_mcp

EXPECTED_UNIFIED = {
    "get_quote", "get_history", "get_company_info", "get_financial_report",
    "get_news", "get_technical_indicators", "run_screener", "get_ownership",
    "get_events_calendar", "get_economic_data", "search_symbols",
    "get_company_risk_cn", "quant_backtest", "kimi_datasource",
    "get_service_status", "tv_scan", "tv_analyze", "egx_market",
}


def tool_names(mcp):
    return {t.name for t in mcp._tool_manager.list_tools()}


def test_no_duplicate_tool_names():
    mcp = build_mcp(get_settings())
    names = [t.name for t in mcp._tool_manager.list_tools()]
    assert len(names) == len(set(names))


def test_expected_tool_surface():
    mcp = build_mcp(get_settings())
    assert EXPECTED_UNIFIED <= tool_names(mcp)


def test_futu_tools_mounted():
    mcp = build_mcp(get_settings())
    names = tool_names(mcp)
    assert {"get_snapshot", "get_kline", "get_option_chain"} <= names


def test_every_tool_has_description():
    mcp = build_mcp(get_settings())
    for t in mcp._tool_manager.list_tools():
        assert (t.description or "").strip(), t.name


def test_fastmcp_internal_attr_pinned():
    # 钉住 mcp>=1.27 的内部枚举属性（futu 挂载依赖）
    mcp = build_mcp(get_settings())
    assert hasattr(mcp, "_tool_manager")
```

`tests/test_diagnostics.py`: `get_service_status()` 返回 `{"providers": {name: {"available": bool, "covers": [...]}}, "futu_opend": {"reachable": bool}, "tools": {"unified": int, "futu_mounted": int}}`；mock 各 provider.available 后断言形状。

- [ ] **Step 2: Run tests, verify FAIL**

- [ ] **Step 3: Implement** — `diagnostics.py` 注册 `get_service_status()`（只读、快；FMP 缓存的探测交易所列表一并报告）。`server.py` INSTRUCTIONS 增补：企业风险用 get_company_risk_cn、kimi_datasource 深源直达、tv/egx 容器 action 指引。

- [ ] **Step 4: Run tests, verify PASS** — 全仓 `pytest -q -m "not integration"` 绿。

- [ ] **Step 5: Commit** — `git commit -am "feat: service status diagnostics + tool-surface invariants"`

---

### Task 17: README 定稿 + GitHub 首发就绪

**Files:**
- Modify: `README.md`
- Test: 无（文档任务；以 CI 绿为门槛）

- [ ] **Step 1: README 全量**：badges、特性表（统一工具/容器/futu 挂载/Kimi 数据源）、安装（`uvx unified-finance-mcp` / `pipx`）、配置表（全部 env，含 rotator 与 cliproxy 指向示例：`FMP_BASE_URL=http://api-key-rotator:8788/fmp`、`KIMI_AUTH_FILE=/mnt/docker/cliproxy/auths/kimi-xxx.json`）、客户端配置示例（Claude Code `claude mcp add`、claude_desktop_config.json、streamable http）、mcpo 5-server → 1-server 迁移示例、工具速查表、开发命令（`pytest -q -m "not integration"`、`ruff check .`）、发布流程（打 v* tag → OIDC 推 PyPI）。

- [ ] **Step 2: 全量验证** — `ruff check . && pytest -q -m "not integration"` 绿；`python -m build` 产物包含 LICENSE/README/src。

- [ ] **Step 3: 推送** — `git add -A && git commit -m "docs: full README" && git push`；确认 GitHub Actions CI 绿。

---

### Task 18: kimi provider + kimi_datasource 容器 + get_company_risk_cn

**Files:**
- Modify: `config.py`（+kimi 字段）、`providers/__init__.py`（registry +kimi）
- Create: `providers/kimi.py`、`tools/kimi.py`、`data/__init__.py`（若无）
- Modify: `tools/__init__.py`（+= ["kimi"]）、`tools/macro.py`（get_economic_data 链首加 kimi）、`tools/ownership.py`（CN 非上市回退 kimi）
- Test: `tests/test_provider_kimi.py`, `tests/test_tools_kimi.py`

**Interfaces:**
- Consumes: T2 PoliteClient/errors、T3 base、T10 routing。
- Produces:
  - `KimiProvider`：`name="kimi"`, `markets=frozenset({"CN","GLOBAL"})`（企业数据限中国大陆实体；宏观全球）
  - `available()`：`bool(settings.kimi_access_token)` 或 `resolve_kimi_auth_file(settings)` 命中存在且 `disabled!=true` 的凭证文件
  - `describe(source) -> str`（Markdown 文档，24h 内存缓存）、`call(source, api, params) -> dict`（含 `data_preview` 文本 + `saved_files` 列表）、`list_sources() -> list[str]`
  - 工具 `kimi_datasource(action="list"|"describe"|"call", source=None, api=None, params=None)`、`get_company_risk_cn(company, aspects=None)`
  - config 字段：`kimi_access_token`（`KIMI_ACCESS_TOKEN`，standalone 直注，优先生效）、`kimi_auth_file`（`KIMI_AUTH_FILE`，cliproxy 凭证 JSON 路径或 glob，如 `/mnt/docker/cliproxy/auths/kimi-*.json`）、`kimi_base_url`（`KIMI_BASE_URL`，默认 `https://api.kimi.com/coding/v1/tools`，仅测试/特殊部署覆盖用）、`kimi_files_dir`（`KIMI_FILES_DIR`）
  - `resolve_kimi_auth_file(settings) -> Path | None`：精确路径或 glob 第一个 `disabled!=true` 的候选

- [ ] **Step 1: Write failing tests**

`tests/test_provider_kimi.py`（respx 全 mock）:
```python
import pytest
import respx

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import AuthError, UpstreamError
from unified_finance_mcp.providers.kimi import DEFAULT_KIMI_BASE_URL, KimiProvider


def make_provider(monkeypatch):
    monkeypatch.setenv("KIMI_ACCESS_TOKEN", "tok")
    return KimiProvider(get_settings())


def _ok(user_text="preview csv here", files=None):
    body = {"is_success": True,
            "result": {"user": [{"type": "text", "text": user_text}]}}
    if files:
        body["files"] = files
    return body


@respx.mock
async def test_describe_sends_method_and_headers(monkeypatch):
    respx.post(DEFAULT_KIMI_BASE_URL).respond(200, json=_ok("# tianyancha API doc"))
    p = make_provider(monkeypatch)
    doc = await p.describe("tianyancha")
    assert "tianyancha" in doc
    req = respx.calls[0].request
    import json as j
    assert j.loads(req.content) == {"method": "get_data_source_desc",
                                    "params": {"name": "tianyancha"}}
    assert req.headers["authorization"] == "Bearer tok"
    assert req.headers["x-msh-device-id"]


@respx.mock
async def test_call_returns_preview_and_saves_files(monkeypatch, tmp_path):
    monkeypatch.setenv("KIMI_FILES_DIR", str(tmp_path))
    respx.post(DEFAULT_KIMI_BASE_URL).respond(200, json=_ok(
        "name,industry\nX,tech",
        files=[{"name": "out.csv", "content": "name,industry\nX,tech"}]))
    p = make_provider(monkeypatch)
    out = await p.call("tianyancha", "search_company", {"keyword": "腾讯"})
    assert out["data_preview"] == "name,industry\nX,tech"
    assert out["saved_files"] and (tmp_path / "out.csv").exists()


@respx.mock
async def test_is_success_false_maps_to_upstream_error(monkeypatch):
    respx.post(DEFAULT_KIMI_BASE_URL).respond(200, json={
        "is_success": False, "error": {"user": [{"type": "text", "text": "API_NOT_FOUND"}]}})
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamError):
        await p.call("tianyancha", "nope", {})


@respx.mock
async def test_401_maps_to_auth_error_with_hint(monkeypatch):
    respx.post(DEFAULT_KIMI_BASE_URL).respond(401, json={"error": "unauthorized"})
    p = make_provider(monkeypatch)
    with pytest.raises(AuthError):
        await p.describe("wind")


# ---- cliproxy 凭证文件路径 ----

def _write_auth(path, **kw):
    import json
    data = {"access_token": "at", "refresh_token": "rt", "device_id": "dev-1",
            "expired": "2099-01-01T00:00:00Z", "disabled": False,
            "type": "kimi", "token_type": "Bearer"}
    data.update(kw)
    path.write_text(json.dumps(data))
    return path


def test_available_via_auth_file(monkeypatch, tmp_path):
    monkeypatch.delenv("KIMI_ACCESS_TOKEN", raising=False)
    monkeypatch.setenv("KIMI_AUTH_FILE", str(tmp_path / "kimi-*.json"))
    _write_auth(tmp_path / "kimi-1.json")
    assert KimiProvider(get_settings()).available()
    # disabled 文件不算
    (tmp_path / "kimi-1.json").write_text('{"disabled": true}')
    assert not KimiProvider(get_settings()).available()


@respx.mock
async def test_token_from_auth_file_used_with_same_device_id(monkeypatch, tmp_path):
    monkeypatch.delenv("KIMI_ACCESS_TOKEN", raising=False)
    f = _write_auth(tmp_path / "kimi-1.json")
    monkeypatch.setenv("KIMI_AUTH_FILE", str(f))
    respx.post(DEFAULT_KIMI_BASE_URL).respond(200, json={
        "is_success": True, "result": {"user": [{"type": "text", "text": "ok"}]}})
    p = KimiProvider(get_settings())
    await p.describe("wind")
    req = respx.calls[0].request
    assert req.headers["authorization"] == "Bearer at"
    assert req.headers["x-msh-device-id"] == "dev-1"


@respx.mock
async def test_self_refresh_writes_back_when_expired(monkeypatch, tmp_path):
    import json
    monkeypatch.delenv("KIMI_ACCESS_TOKEN", raising=False)
    f = _write_auth(tmp_path / "kimi-1.json", expired="2020-01-01T00:00:00Z")
    monkeypatch.setenv("KIMI_AUTH_FILE", str(f))
    respx.post("https://auth.kimi.com/api/oauth/token").respond(200, json={
        "access_token": "new-at", "refresh_token": "new-rt", "expires_in": 900,
        "token_type": "Bearer"})
    respx.post(DEFAULT_KIMI_BASE_URL).respond(200, json={
        "is_success": True, "result": {"user": [{"type": "text", "text": "ok"}]}})
    p = KimiProvider(get_settings())
    await p.describe("wind")
    req = respx.calls[-1].request
    assert req.headers["authorization"] == "Bearer new-at"
    saved = json.loads(f.read_text())
    assert saved["access_token"] == "new-at" and saved["refresh_token"] == "new-rt"
    assert saved["device_id"] == "dev-1"  # 其他字段保留
```

`tests/test_tools_kimi.py`:
```python
async def test_datasource_list_actions(): ...
async def test_datasource_unknown_action_hint(): ...
async def test_company_risk_cn_resolves_full_name_first(monkeypatch):
    # mock provider.call: 第一次 search_company 返回全称，其后按 aspects 逐项返回
    # 断言聚合 dict 含 shareholders/judicial 键且 search 用的是用户输入简称
async def test_company_risk_cn_aspects_subset(monkeypatch): ...
async def test_company_risk_cn_kimi_unconfigured(monkeypatch):
    # provider.available() False -> {"error", hint 指向 KIMI_ACCESS_TOKEN / KIMI_BASE_URL}
```

- [ ] **Step 2: Run tests, verify FAIL**

- [ ] **Step 3: Implement**

`config.py` 追加（frozen dataclass 新字段，模式同既有字段）:
```python
DEFAULT_KIMI_BASE_URL = "https://api.kimi.com/coding/v1/tools"
# Settings 内：
kimi_access_token: str = field(default_factory=lambda: _env("KIMI_ACCESS_TOKEN"))
kimi_auth_file: str = field(default_factory=lambda: _env("KIMI_AUTH_FILE"))
kimi_base_url: str = field(default_factory=lambda: _env("KIMI_BASE_URL", DEFAULT_KIMI_BASE_URL))
kimi_files_dir: str = field(default_factory=lambda: _env("KIMI_FILES_DIR", "/tmp/unified_finance_mcp"))
```

`providers/kimi.py` 认证部分（凭证直读 cliproxy auth 文件 + 兜底自刷新；OAuth host/client_id 与 cliproxy 相同——Kimi Code CLI 公开 client）:
```python
KIMI_OAUTH_TOKEN_URL = "https://auth.kimi.com/api/oauth/token"
KIMI_CLIENT_ID = "17e5f671-d194-4dfb-9706-5516cb48c098"  # Kimi Code CLI public client
_REFRESH_MARGIN = 60  # 距过期不足 60s 视为待刷新


def resolve_kimi_auth_file(settings) -> Path | None:
    pat = settings.kimi_auth_file
    if not pat:
        return None
    candidates = sorted(Path().glob(pat)) if any(c in pat for c in "*?[") else [Path(pat)]
    for c in candidates:
        try:
            if not json.loads(c.read_text()).get("disabled"):
                return c
        except (OSError, json.JSONDecodeError):
            continue
    return None


class _KimiCredentials:
    """Reads cliproxy's kimi auth JSON (mtime-cached); self-refreshes as fallback."""
    def __init__(self, path: Path):
        self.path, self._mtime, self._data = path, 0.0, {}

    def _reload_if_changed(self) -> dict:
        mtime = self.path.stat().st_mtime
        if mtime != self._mtime:
            self._data = json.loads(self.path.read_text())
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
            raise AuthError(f"kimi token refresh failed: {str(body)[:120]}")
        def _write_back():
            with self.path.open("r+") as fh:      # flock 降低与 cliproxy 的写冲突
                fcntl.flock(fh, fcntl.LOCK_EX)
                data = json.load(fh)
                data.update({"access_token": body["access_token"],
                             "refresh_token": body.get("refresh_token", refresh_token),
                             "expired": (datetime.now(timezone.utc) +
                                         timedelta(seconds=int(body.get("expires_in", 900))))
                                        .isoformat().replace("+00:00", "Z"),
                             "last_refresh": datetime.now(timezone.utc).isoformat(),
                             "timestamp": int(time.time())})
                fh.seek(0); json.dump(data, fh); fh.truncate()
                fcntl.flock(fh, fcntl.LOCK_UN)
            self._mtime = 0.0
            return data
        return await anyio.to_thread.run_sync(_write_back)
```

provider 类内：`_token_and_device()` = `KIMI_ACCESS_TOKEN` 直注时返回 `(token, generated_device_id)`（generated 同原 `_device_id()` 持久化逻辑）；否则经 `_KimiCredentials`（按 `resolve_kimi_auth_file` 惰性构造）。`_headers()` 使用二者；`available()` 按 Interfaces 定义。401 处理：`_invoke` 捕获 `AuthError` 后强制重读凭证文件重试一次，再失败才抛（hint 指 cliproxy 凭证/`KIMI_ACCESS_TOKEN`）。`post_form` 与 T18 的 `post_json` 一并在本任务为 PoliteClient 增补（先写 respx 用例：form 编码、Retry-After 语义与 get_json 一致）。

`providers/kimi.py`:
```python
"""Kimi Datasource meta-source. Auth lives upstream (cliproxy passthrough or a
user-supplied Kimi Code token); this client only sends a Bearer + X-Msh headers.
Protocol reference (re-implemented, NOT copied): AGPL plugin
piexian/astrbot_plugin_kimi_datasource_api + official Kimi Code plugin docs."""
from __future__ import annotations

import re
import time
import uuid
from pathlib import Path

from ..errors import AuthError, UpstreamError, tool_error
from ..http import PoliteClient
from .base import Provider

DEFAULT_KIMI_BASE_URL = "https://api.kimi.com/coding/v1/tools"
KIMI_DATASOURCE_VERSION = "3.4.0"
KNOWN_SOURCES = [
    "stock_finance_data", "yahoo_finance", "world_bank_open_data", "tianyancha",
    "arxiv", "scholar", "yuandian_law", "wind", "imf", "gildata",
    "sec_edgar", "sp_data",
]
_DESC_CACHE: dict[str, tuple[float, str]] = {}
_DESC_TTL = 24 * 3600


class KimiProvider(Provider):
    name = "kimi"
    markets = frozenset({"CN", "GLOBAL"})

    def __init__(self, settings):
        super().__init__(settings)
        self._http: PoliteClient | None = None
        self._creds: _KimiCredentials | None = None

    def available(self) -> bool:
        return bool(self.settings.kimi_access_token) or \
            resolve_kimi_auth_file(self.settings) is not None

    def _client(self) -> PoliteClient:
        if self._http is None:
            self._http = PoliteClient(timeout=60.0,
                                      max_retries=self.settings.max_retries,
                                      min_host_delay=self.settings.min_host_delay)
        return self._http

    async def _headers(self) -> dict[str, str]:
        if self.settings.kimi_access_token:
            token, device_id = self.settings.kimi_access_token, self._generated_device_id()
        else:
            if self._creds is None:
                path = resolve_kimi_auth_file(self.settings)
                if path is None:
                    raise AuthError("kimi 未配置：设 KIMI_AUTH_FILE 指 cliproxy 凭证，"
                                    "或 KIMI_ACCESS_TOKEN 直注")
                self._creds = _KimiCredentials(path)
            token, device_id = await self._creds.token(self._client())
        return {
            "Authorization": f"Bearer {token}",
            "X-Msh-Platform": "kimi-code-cli",
            "X-Msh-Version": KIMI_DATASOURCE_VERSION,
            "X-Msh-Device-Id": device_id,
            "X-Msh-Tool-Call-Id": str(uuid.uuid4()),
            "User-Agent": f"kimi-datasource/{KIMI_DATASOURCE_VERSION}",
        }

    async def _invoke(self, method: str, params: dict) -> dict:
        body = await self._client().post_json(
            self.settings.kimi_base_url, json_body={"method": method, "params": params},
            headers=await self._headers())
        if isinstance(body, dict) and body.get("is_success") is False:
            raise UpstreamError(_extract_user_text(body.get("error")) or str(body)[:200])
        return body if isinstance(body, dict) else {"raw": body}
```

`_generated_device_id()`：原 XDG 持久化逻辑（`~/.config/unified-finance-mcp/kimi_device_id`，standalone token 用户用）。`_extract_user_text(value)`：`value[role]` 为 `[{"type":"text","text"}...]` 时拼接 text（user 优先，assistant 兜底）。

- `describe(source)`：缓存命中直接返回；否则 `_invoke("get_data_source_desc", {"name": source})` → 抽 `result.user[].text`（无则 assistant 通道兜底）→ 写缓存返回。
- `call(source, api, params)`：若 `params` 无 `file_path`，补 `f"{settings.kimi_files_dir}/{source}_{api}_{uuid4().hex[:8]}.csv"`；`_invoke("call_data_source_tool", {...})` → `{"data_preview": text, "saved_files": [...], "source": source, "api": api}`；`files[]` 落盘（encoding=="base64" 时 b64decode；文件名 `re.sub(r"[^A-Za-z0-9._-]+","_",Path(name).name)`）。
- `list_sources()`：返回 `KNOWN_SOURCES`（describe 失败不致命，容器层把失败的源标注）。

`tools/kimi.py`：
```python
ASPECT_APIS = {  # 首选 api_name 候选（实现时先 describe("tianyancha") 核对，漂移时按候选顺序探测）
    "profile": ["company_profile", "get_company_info", "base_info"],
    "shareholders": ["shareholders", "get_shareholders"],
    "executives": ["executives", "get_executives", "management"],
    "judicial": ["judicial_risk", "get_judicial_risk", "lawsuits"],
    "operation": ["operation_risk", "get_operation_risk", "business_risk"],
    "equity_penetration": ["equity_penetration", "get_equity_structure", "ownership_structure"],
    "related_graph": ["related_graph", "get_related_companies", "related_parties"],
}
```

- `kimi_datasource(action, source=None, api=None, params=None)`：list → `{"sources": KimiProvider.list_sources(), "hint": "action='describe' 查看某源 API 文档"}`；describe → `{"source": source, "doc": await p.describe(source)}`；call → `await p.call(...)`；未知 action / 缺参 → `tool_error` + hint。kimi 未配置时三个 action 统一返回 hint（设 `KIMI_AUTH_FILE` 指 cliproxy 的 `auths/kimi-*.json`，或 `KIMI_ACCESS_TOKEN` 直注）。
- `get_company_risk_cn(company, aspects=None)`：
  1. `p.call("tianyancha", <搜索 api 候选>, {"keyword": company})` 取首个结果全名（search api 候选同法探测：`["search_company", "search"]`）；
  2. 对 aspects（默认全 7 项）逐项 `p.call("tianyancha", api, {"name": full_name})`；单项失败不致命，记入 `aspect_errors`；
  3. 聚合 `{"company": full_name, "aspects": {aspect: data_preview/saved_files}, "aspect_errors": {...}}`。
- api_name 探测顺序：先用 `ASPECT_APIS` 候选逐个尝试，`API_NOT_FOUND` 类错误换下一个，全灭则 `describe("tianyancha")` 拉文档把文档原文附在 error.hint 里让 LLM 自选（自描述兜底，不硬失败）。
- `macro.py`：`get_economic_data` chain 改为 `["kimi", "alphavantage"]`；kimi 分支 call 闭包：World Bank/IMF 指标名映射（GDP→world_bank_open_data 对应 api；映射表以 describe 文档为准，v1 仅当 kimi describe 成功且能找到匹配 api 才调用，否则抛 NotFound 回退 av）。
- `ownership.py`：当 `parse_symbol` 失败且输入像中文公司名（`re.search(r"[一-鿿]", symbol)`）时，`kind="major"` 回退 kimi 天眼查股东查询（复用 get_company_risk_cn 的 shareholders 分支）。

- [ ] **Step 4: Run tests, verify PASS** — 全仓 `pytest -q -m "not integration"` 绿；`ruff check .` 绿。

- [ ] **Step 5: Commit + push** — `git commit -am "feat: kimi datasource provider, L2 container and CN company risk tool" && git push`

---

## Self-Review 记录

- ✅ Spec §5.1 14 个统一工具 ↔ T10-T13 + T18 全覆盖；§5.2 三容器 ↔ T14；§5.3 两 L2 ↔ T15/T18；§5.4 futu 挂载 ↔ T9/T16。
- ✅ 类型一致性：`ParsedSymbol`（T3）方法名被 T4-T18 一致使用；`route_and_call`（T10）签名与 T11-T13/T18 调用一致；`PoliteClient` 在 T18 增补 `post_json`/`post_form`（本任务内先写测试）。
- ✅ T16 `EXPECTED_UNIFIED` 与 T10-T18 注册的工具名逐一核对一致（18 个：14 统一 + 3 tv 容器 + kimi_datasource；quant_backtest 在统一计数内）。
- ⚠️ 留待实现期对照实盘文档的点（均已标注，不属于占位符）：FMP stable 端点路径微调、futu skill_fn 真实签名、tianyancha api_name 候选、TA_Handler screener 参数取值。
