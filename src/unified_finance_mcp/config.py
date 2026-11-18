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
DEFAULT_KIMI_BASE_URL = "https://api.kimi.com/coding/v1/tools"
# Eastmoney is keyless: one base per face because EM serves them off three
# different public hosts (realtime / kline history / symbol suggest).
DEFAULT_EASTMONEY_QUOTE_BASE_URL = "https://push2.eastmoney.com"
DEFAULT_EASTMONEY_HISTORY_BASE_URL = "https://push2his.eastmoney.com"
DEFAULT_EASTMONEY_SEARCH_BASE_URL = "https://searchapi.eastmoney.com"
# Official macro/fiscal bases. WB/IMF/EDGAR/Treasury are keyless; FRED is
# free-registration-keyed. ECB/OECD/EUROSTAT stay declared for tombstoned SDMX
# follow-ups (see providers/macro.py docstring) so their env override surface
# already exists; EDGAR/Treasury are wired in providers/edgar.py and
# providers/treasury.py.
DEFAULT_WB_BASE_URL = "https://api.worldbank.org/v2"
DEFAULT_IMF_BASE_URL = "https://www.imf.org/external/datamapper/api/v1"
DEFAULT_FRED_BASE_URL = "https://api.stlouisfed.org/fred"
DEFAULT_EDGAR_BASE_URL = "https://data.sec.gov"
DEFAULT_SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
DEFAULT_ECB_BASE_URL = "https://data-api.ecb.europa.eu/service"
DEFAULT_OECD_BASE_URL = "https://sdmx.oecd.org/public/rest"
DEFAULT_EUROSTAT_BASE_URL = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0")
# Treasury: two hosts, two shapes. The par yield curve is a CSV export on
# home.treasury.gov; Fiscal Data is the documented JSON API.
DEFAULT_TREASURY_FISCAL_BASE_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service")
DEFAULT_TREASURY_YIELD_CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center"
    "/interest-rates/daily-treasury-rates.csv/all")
# SEC's fair-access policy wants a declared user agent with a contact email.
# The shared http.UA cannot be reused: it contains github.com, which SEC
# answers with 403 "Undeclared Automated Tool" (live, 2026-11-18).
DEFAULT_SEC_EDGAR_USER_AGENT = "unified-finance-mcp"


@dataclass(frozen=True)
class Settings:
    transport: str = field(default_factory=lambda: _env("FINANCE_MCP_TRANSPORT", "stdio"))
    host: str = field(default_factory=lambda: _env("FINANCE_MCP_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _env_int("FINANCE_MCP_PORT", 8000))
    request_timeout: float = field(default_factory=lambda: _env_float("FINANCE_MCP_REQUEST_TIMEOUT", 20.0))
    max_retries: int = field(default_factory=lambda: _env_int("FINANCE_MCP_MAX_RETRIES", 3))
    min_host_delay: float = field(default_factory=lambda: _env_float("FINANCE_MCP_MIN_HOST_DELAY", 0.5))
    futu_enabled: bool = field(default_factory=lambda: _env_bool("FINANCE_MCP_FUTU", True))
    futu_mount_layout: str = field(
        default_factory=lambda: _env("FINANCE_MCP_FUTU_MOUNT_LAYOUT", "flat")
        .strip().lower() or "flat")
    fmp_api_key: str = field(default_factory=lambda: _env("FMP_API_KEY"))
    fmp_base_url: str = field(default_factory=lambda: _env("FMP_BASE_URL", DEFAULT_FMP_BASE_URL))
    alphavantage_api_key: str = field(default_factory=lambda: _env("ALPHAVANTAGE_API_KEY"))
    alphavantage_base_url: str = field(default_factory=lambda: _env("ALPHAVANTAGE_BASE_URL", DEFAULT_AV_BASE_URL))
    marketaux_api_token: str = field(default_factory=lambda: _env("MARKETAUX_API_TOKEN"))
    marketaux_base_url: str = field(default_factory=lambda: _env("MARKETAUX_BASE_URL", DEFAULT_MARKETAUX_BASE_URL))
    kimi_proxy_url: str = field(default_factory=lambda: _env("KIMI_PROXY_URL"))
    kimi_access_token: str = field(default_factory=lambda: _env("KIMI_ACCESS_TOKEN"))
    kimi_auth_file: str = field(default_factory=lambda: _env("KIMI_AUTH_FILE"))
    kimi_base_url: str = field(default_factory=lambda: _env("KIMI_BASE_URL", DEFAULT_KIMI_BASE_URL))
    kimi_files_dir: str = field(default_factory=lambda: _env("KIMI_FILES_DIR", "/tmp/unified_finance_mcp"))
    # eastmoney: keyless — no api-key field; base overrides exist for testing
    # and for pointing at a mirror/rotator of the public hosts.
    eastmoney_quote_base_url: str = field(
        default_factory=lambda: _env("EASTMONEY_QUOTE_BASE_URL", DEFAULT_EASTMONEY_QUOTE_BASE_URL))
    eastmoney_history_base_url: str = field(
        default_factory=lambda: _env("EASTMONEY_HISTORY_BASE_URL", DEFAULT_EASTMONEY_HISTORY_BASE_URL))
    eastmoney_search_base_url: str = field(
        default_factory=lambda: _env("EASTMONEY_SEARCH_BASE_URL", DEFAULT_EASTMONEY_SEARCH_BASE_URL))
    cex_enabled: bool = field(default_factory=lambda: _env_bool("FINANCE_MCP_CEX", True))
    cex_exchanges: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            e.strip().lower()
            for e in _env("FINANCE_MCP_CEX_EXCHANGES", "bitget,gate,mexc").split(",")
            if e.strip()))
    cex_product: str = field(
        default_factory=lambda: _env("FINANCE_MCP_CEX_PRODUCT", "USDT-FUTURES"))
    cex_tv_screener: str = field(
        default_factory=lambda: _env("FINANCE_MCP_CEX_TV_SCREENER", "crypto"))
    # ── native macro provider (R18): WB/IMF keyless, FRED free-registration ──
    fred_api_key: str = field(default_factory=lambda: _env("FRED_API_KEY"))
    world_bank_base_url: str = field(
        default_factory=lambda: _env("WORLD_BANK_BASE_URL", DEFAULT_WB_BASE_URL))
    imf_base_url: str = field(
        default_factory=lambda: _env("IMF_BASE_URL", DEFAULT_IMF_BASE_URL))
    fred_base_url: str = field(
        default_factory=lambda: _env("FRED_BASE_URL", DEFAULT_FRED_BASE_URL))
    sec_edgar_base_url: str = field(
        default_factory=lambda: _env("SEC_EDGAR_BASE_URL", DEFAULT_EDGAR_BASE_URL))
    sec_edgar_user_agent: str = field(
        default_factory=lambda: _env("SEC_EDGAR_USER_AGENT", DEFAULT_SEC_EDGAR_USER_AGENT))
    sec_edgar_tickers_url: str = field(
        default_factory=lambda: _env("SEC_EDGAR_TICKERS_URL", DEFAULT_SEC_TICKERS_URL))
    treasury_fiscal_base_url: str = field(
        default_factory=lambda: _env("TREASURY_FISCAL_BASE_URL",
                                     DEFAULT_TREASURY_FISCAL_BASE_URL))
    treasury_yield_csv_url: str = field(
        default_factory=lambda: _env("TREASURY_YIELD_CSV_URL",
                                     DEFAULT_TREASURY_YIELD_CSV_URL))
    ecb_base_url: str = field(
        default_factory=lambda: _env("ECB_BASE_URL", DEFAULT_ECB_BASE_URL))
    oecd_base_url: str = field(
        default_factory=lambda: _env("OECD_BASE_URL", DEFAULT_OECD_BASE_URL))
    eurostat_base_url: str = field(
        default_factory=lambda: _env("EUROSTAT_BASE_URL", DEFAULT_EUROSTAT_BASE_URL))


def get_settings() -> Settings:
    return Settings()
