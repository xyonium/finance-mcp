"""Jina Reader helper tests: respx-mocked, zero egress.

The reader is only a transport for hosts that 403 this deployment's egress;
these tests pin the URL shape, the verbatim-body header, the optional key,
and the error translation into the repo taxonomy.
"""
import pytest
import respx

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.errors import AuthError, NotFound, UpstreamError
from unified_finance_mcp.jina import JinaReader

TARGET = "https://api.bls.gov/publicAPI/v1/timeseries/data/LNS14000000"
READER = f"https://r.jina.ai/{TARGET}"


def make_reader(monkeypatch, key=None, base="https://r.jina.ai"):
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    monkeypatch.setenv("JINA_READER_URL", base)
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    if key:
        monkeypatch.setenv("JINA_API_KEY", key)
    return JinaReader(get_settings())


@respx.mock
async def test_read_text_asks_for_verbatim_body(monkeypatch):
    respx.get(READER).respond(200, text='{"status":"REQUEST_SUCCEEDED"}')
    out = await make_reader(monkeypatch).read_text(TARGET)
    assert out == '{"status":"REQUEST_SUCCEEDED"}'
    req = respx.calls[0].request
    assert req.headers["x-return-format"] == "text"
    assert "authorization" not in req.headers


@respx.mock
async def test_key_becomes_bearer(monkeypatch):
    respx.get(READER).respond(200, text="ok")
    await make_reader(monkeypatch, key="jina_test").read_text(TARGET)
    assert respx.calls[0].request.headers["authorization"] == "Bearer jina_test"


async def test_empty_base_disables_the_reader(monkeypatch):
    r = make_reader(monkeypatch, base="")
    with pytest.raises(NotFound, match="disabled"):
        await r.read_text(TARGET)


@respx.mock
async def test_reader_403_maps_to_auth_error_with_key_hint(monkeypatch):
    respx.get(READER).respond(403, text="forbidden")
    with pytest.raises(AuthError) as ei:
        await make_reader(monkeypatch).read_text(TARGET)
    assert "JINA_API_KEY" in str(ei.value)


@respx.mock
async def test_target_failure_surfaces_as_upstream_error(monkeypatch):
    """The reader answers 422 when its own fetch fails (e.g. target 403)."""
    respx.get(READER).respond(422, text='{"data":null}')
    with pytest.raises(UpstreamError):
        await make_reader(monkeypatch).read_text(TARGET)
