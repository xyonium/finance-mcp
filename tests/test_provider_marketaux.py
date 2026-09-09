"""Marketaux provider tests: all respx-mocked, zero live Marketaux calls.

The two brief tests are verbatim; `make_provider` additionally pins
MARKETAUX_BASE_URL (so the request target can never drift to a live host) and
FINANCE_MCP_MIN_HOST_DELAY=0 (PoliteClient's per-host pacing would otherwise
make every test take ~0.5s), matching the alphavantage suite's conventions.
"""
import httpx
import pytest
import respx

from unified_finance_mcp.config import DEFAULT_MARKETAUX_BASE_URL, get_settings
from unified_finance_mcp.errors import AuthError, RateLimited, UpstreamError
from unified_finance_mcp.providers.marketaux import MarketauxProvider
from unified_finance_mcp.symbols import parse_symbol

BASE = "https://api.marketaux.com/v1/news/all"


def make_provider(monkeypatch, base=DEFAULT_MARKETAUX_BASE_URL):
    monkeypatch.setenv("MARKETAUX_API_TOKEN", "tok")
    monkeypatch.setenv("MARKETAUX_BASE_URL", base)
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    monkeypatch.setenv("FINANCE_MCP_MAX_RETRIES", "0")  # keep failure tests instant
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


@respx.mock
async def test_news_with_symbol_empty_data_is_empty_list(monkeypatch):
    """A quiet symbol is an empty result, not an error (get_news falls through)."""
    respx.get(BASE).respond(200, json={"data": []})
    p = make_provider(monkeypatch)
    assert await p.news(parse_symbol("AAPL"), limit=5) == []


@respx.mock
async def test_news_maps_item_fields(monkeypatch):
    respx.get(BASE).respond(200, json={"data": [
        {"title": "Apple beats", "url": "https://x", "description": "d",
         "published_at": "2026-01-02T10:00:00Z", "source": "Reuters",
         "entities": [{"symbol": "AAPL", "name": "Apple Inc"}],
         "similar": [], "matched": 1}]})
    p = make_provider(monkeypatch)
    item = (await p.news(parse_symbol("AAPL"), limit=5))[0]
    assert item["url"] == "https://x" and item["published"] == "2026-01-02T10:00:00Z"
    assert item["entities"] == [{"symbol": "AAPL", "name": "Apple Inc"}]
    assert item["source"] == "marketaux"          # provider wins over upstream "source"
    assert item["source_name"] == "Reuters"       # upstream outlet preserved
    assert "similar" not in item and "matched" not in item


@respx.mock
async def test_news_non_us_symbol_uses_yahoo_form(monkeypatch):
    """Global coverage: HK/JP tickers pass through in yahoo form, no ValueError."""
    respx.get(BASE).respond(200, json={"data": [{"title": "Tencent up", "url": "u"}]})
    p = make_provider(monkeypatch)
    items = await p.news(parse_symbol("HK.00700"), limit=3)
    assert items[0]["title"] == "Tencent up"
    assert respx.calls[0].request.url.params["symbols"] == "0700.HK"


@respx.mock
async def test_news_params_language_and_limit(monkeypatch):
    respx.get(BASE).respond(200, json={"data": []})
    p = make_provider(monkeypatch)
    await p.news(None, limit=7)
    params = respx.calls[0].request.url.params
    assert params["language"] == "en" and params["limit"] == "7"


@respx.mock
async def test_news_auth_error_propagates(monkeypatch):
    """Marketaux signals a bad token with HTTP 401/403 -> AuthError from PoliteClient."""
    respx.get(BASE).respond(401, json={"error": {"message": "invalid api token"}})
    p = make_provider(monkeypatch)
    with pytest.raises(AuthError):
        await p.news(parse_symbol("AAPL"))
    respx.get(BASE).respond(403, json={"error": {"message": "forbidden"}})
    with pytest.raises(AuthError):
        await p.news(parse_symbol("AAPL"))


@respx.mock
async def test_news_rate_limited_propagates(monkeypatch):
    """HTTP 429 -> RateLimited; Retry-After: 0 keeps the retry chain instant."""
    respx.get(BASE).respond(429, headers={"Retry-After": "0"},
                            json={"error": {"message": "rate limit exceeded"}})
    p = make_provider(monkeypatch)
    with pytest.raises(RateLimited):
        await p.news(parse_symbol("AAPL"))


@respx.mock
async def test_news_server_error_is_upstream(monkeypatch):
    respx.get(BASE).respond(500, json={"error": {"message": "boom"}})
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamError):
        await p.news(parse_symbol("AAPL"))


@respx.mock
async def test_news_unexpected_body_is_upstream(monkeypatch):
    respx.get(BASE).respond(200, json={"data": "unexpected"})
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamError):
        await p.news(None)
    respx.get(BASE).respond(200, text="not json")
    with pytest.raises(UpstreamError):
        await p.news(None)


@respx.mock
async def test_error_messages_never_leak_the_token(monkeypatch):
    """PoliteClient does not scrub: the provider must. Token travels in params only."""
    respx.get(BASE).mock(side_effect=httpx.ConnectError(
        "failed to connect to https://api.marketaux.com/v1/news/all?api_token=tok"))
    p = make_provider(monkeypatch)
    with pytest.raises(UpstreamError) as ei:
        await p.news(parse_symbol("AAPL"))
    assert "tok" not in str(ei.value)
    assert "***" in str(ei.value)
    assert "tok" not in respx.calls[0].request.url.path


@respx.mock
async def test_placeholder_token_when_unset(monkeypatch):
    monkeypatch.delenv("MARKETAUX_API_TOKEN", raising=False)
    monkeypatch.setenv("MARKETAUX_BASE_URL", "http://api-key-rotator:8788/marketaux")
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    monkeypatch.setenv("FINANCE_MCP_MAX_RETRIES", "0")
    respx.get("http://api-key-rotator:8788/marketaux/v1/news/all").respond(
        200, json={"data": [{"title": "t", "url": "u"}]})
    p = MarketauxProvider(get_settings())
    items = await p.news(None, limit=3)
    assert items[0]["title"] == "t"
    assert respx.calls[0].request.url.params["api_token"] == "rotated-by-upstream"


async def test_no_search_method(monkeypatch):
    """Unimplemented methods must stay absent so the tools layer can skip this provider."""
    p = make_provider(monkeypatch)
    assert not hasattr(p, "search")
    assert not hasattr(p, "quote")


async def test_available(monkeypatch):
    monkeypatch.delenv("MARKETAUX_API_TOKEN", raising=False)
    monkeypatch.delenv("MARKETAUX_BASE_URL", raising=False)
    assert not MarketauxProvider(get_settings()).available()
    monkeypatch.setenv("MARKETAUX_API_TOKEN", "tok")
    assert MarketauxProvider(get_settings()).available()
    monkeypatch.delenv("MARKETAUX_API_TOKEN", raising=False)
    monkeypatch.setenv("MARKETAUX_BASE_URL", "http://api-key-rotator:8788/marketaux")
    assert MarketauxProvider(get_settings()).available()  # rotator injects the token


def test_markets_is_global(monkeypatch):
    p = make_provider(monkeypatch)
    assert p.markets is None
    assert p.covers("EG") and p.covers("HK") and p.covers("US")
