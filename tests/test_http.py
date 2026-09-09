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
