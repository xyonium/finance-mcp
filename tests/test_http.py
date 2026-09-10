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


@respx.mock
async def test_get_text_returns_raw_body():
    respx.get("https://x.test/data").respond(200, text="symbol,name\r\nAAPL,Apple\r\n")
    async with PoliteClient(min_host_delay=0) as c:
        text = await c.get_text("https://x.test/data", params={"fn": "CAL"})
    assert text.startswith("symbol,name")
    assert respx.calls[0].request.url.params["fn"] == "CAL"


@respx.mock
async def test_get_text_retry_after_then_success():
    route = respx.get("https://x.test/data")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, text="ok"),
    ]
    async with PoliteClient(min_host_delay=0) as c:
        assert await c.get_text("https://x.test/data") == "ok"
    assert route.call_count == 2


@respx.mock
async def test_get_text_auth_error_fast_fail():
    respx.get("https://x.test/data").respond(401, text="denied")
    async with PoliteClient(min_host_delay=0) as c:
        with pytest.raises(AuthError):
            await c.get_text("https://x.test/data")
    assert respx.calls.call_count == 1


# ── post_json / post_form (T18: kimi datasource + oauth refresh) ────────────


@respx.mock
async def test_post_json_sends_body_and_headers():
    respx.post("https://x.test/tools").respond(200, json={"is_success": True})
    async with PoliteClient(min_host_delay=0) as c:
        body = await c.post_json("https://x.test/tools",
                                 json_body={"method": "get_data_source_desc",
                                            "params": {"name": "t"}},
                                 headers={"Authorization": "Bearer k"})
    assert body == {"is_success": True}
    req = respx.calls[0].request
    assert req.headers["authorization"] == "Bearer k"
    assert req.headers["content-type"] == "application/json"
    import json as j
    assert j.loads(req.content)["params"] == {"name": "t"}


@respx.mock
async def test_post_json_retry_after_then_success():
    route = respx.post("https://x.test/tools")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"ok": True}),
    ]
    async with PoliteClient(min_host_delay=0) as c:
        assert await c.post_json("https://x.test/tools", json_body={"m": 1}) == \
            {"ok": True}
    assert route.call_count == 2


@respx.mock
async def test_post_json_auth_error_fast_fail():
    respx.post("https://x.test/tools").respond(401, json={"error": "unauthorized"})
    async with PoliteClient(min_host_delay=0, max_retries=3) as c:
        with pytest.raises(AuthError):
            await c.post_json("https://x.test/tools", json_body={"m": 1})
    assert respx.calls.call_count == 1  # no retry on 4xx


@respx.mock
async def test_post_form_urlencodes_fields():
    respx.post("https://auth.x.test/token").respond(200, json={"access_token": "a"})
    async with PoliteClient(min_host_delay=0) as c:
        body = await c.post_form(
            "https://auth.x.test/token",
            {"client_id": "17e5f671", "grant_type": "refresh_token",
             "refresh_token": "rt"})
    assert body == {"access_token": "a"}
    req = respx.calls[0].request
    assert req.headers["content-type"] == "application/x-www-form-urlencoded"
    assert req.content == b"client_id=17e5f671&grant_type=refresh_token&refresh_token=rt"


@respx.mock
async def test_post_form_retry_after_then_success():
    route = respx.post("https://auth.x.test/token")
    route.side_effect = [
        httpx.Response(503, headers={"Retry-After": "0"}),
        httpx.Response(200, json={"access_token": "new"}),
    ]
    async with PoliteClient(min_host_delay=0) as c:
        assert await c.post_form("https://auth.x.test/token",
                                 {"grant_type": "refresh_token",
                                  "refresh_token": "r"}) == {"access_token": "new"}
    assert route.call_count == 2
