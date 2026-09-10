from unified_finance_mcp.config import get_settings
from unified_finance_mcp.providers import build_providers


def test_registry_keys():
    ps = build_providers(get_settings())
    assert set(ps) == {"yahoo", "tradingview", "fmp", "alphavantage", "marketaux",
                       "futu", "kimi"}


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
