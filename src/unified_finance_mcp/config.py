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
    kimi_proxy_url: str = field(default_factory=lambda: _env("KIMI_PROXY_URL"))
    kimi_access_token: str = field(default_factory=lambda: _env("KIMI_ACCESS_TOKEN"))
    kimi_auth_file: str = field(default_factory=lambda: _env("KIMI_AUTH_FILE"))
    kimi_base_url: str = field(default_factory=lambda: _env("KIMI_BASE_URL", DEFAULT_KIMI_BASE_URL))
    kimi_files_dir: str = field(default_factory=lambda: _env("KIMI_FILES_DIR", "/tmp/unified_finance_mcp"))


def get_settings() -> Settings:
    return Settings()
