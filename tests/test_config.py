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
