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


def test_kimi_defaults(monkeypatch):
    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN", "KIMI_AUTH_FILE",
              "KIMI_BASE_URL", "KIMI_FILES_DIR"):
        monkeypatch.delenv(v, raising=False)
    s = get_settings()
    assert s.kimi_proxy_url == ""
    assert s.kimi_access_token == ""
    assert s.kimi_auth_file == ""
    assert s.kimi_base_url == "https://api.kimi.com/coding/v1/tools"
    assert s.kimi_files_dir == "/tmp/unified_finance_mcp"


def test_kimi_env_override(monkeypatch):
    monkeypatch.setenv("KIMI_PROXY_URL", "http://kimi-proxy:8788/coding/v1/tools")
    monkeypatch.setenv("KIMI_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("KIMI_AUTH_FILE", "/mnt/docker/cliproxy/auths/kimi-*.json")
    monkeypatch.setenv("KIMI_FILES_DIR", "/tmp/kimi-out")
    s = get_settings()
    assert s.kimi_proxy_url.endswith("/coding/v1/tools")
    assert s.kimi_access_token == "tok"
    assert s.kimi_auth_file.endswith("kimi-*.json")
    assert s.kimi_files_dir == "/tmp/kimi-out"
