"""T18 KimiProvider tests: respx-mocked, zero live api.kimi.com / auth.kimi.com
or kimi-datasource-proxy calls. Credential-file fixtures are built in tmp_path
(_write_auth) — the real cliproxy auths dir must never be read. make_provider
pins every KIMI_* env (and XDG_CONFIG_HOME) so results are identical keyless
or keyed, per the T10-C1 hermeticity hardening (provider-level stubs only;
respx routes are bound to the pinned constants).
"""
from __future__ import annotations

import json
import os
import socket
import tempfile
import time

import httpx
import pytest
import respx

from unified_finance_mcp.config import DEFAULT_KIMI_BASE_URL, get_settings
from unified_finance_mcp.errors import AuthError, UpstreamError
from unified_finance_mcp.providers.kimi import KimiProvider

PROXY_URL = "http://kimi-proxy:8788/coding/v1/tools"


def make_provider(monkeypatch):
    for v in ("KIMI_PROXY_URL", "KIMI_AUTH_FILE", "KIMI_BASE_URL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("KIMI_ACCESS_TOKEN", "tok")
    monkeypatch.setenv("FINANCE_MCP_MIN_HOST_DELAY", "0")
    monkeypatch.setenv("XDG_CONFIG_HOME",
                       os.path.join(tempfile.gettempdir(), "ufm-kimi-tests"))
    return KimiProvider(get_settings())


@pytest.fixture(autouse=True)
def _clear_desc_cache():
    from unified_finance_mcp.providers import kimi

    kimi._DESC_CACHE.clear()
    yield
    kimi._DESC_CACHE.clear()


def _ok(user_text="preview csv here", files=None):
    body = {"is_success": True,
            "result": {"user": [{"type": "text", "text": user_text}]}}
    if files:
        body["files"] = files
    return body


# ── direct-token path (brief verbatim) ──────────────────────────────────────

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
async def test_describe_cached_within_ttl(monkeypatch):
    respx.post(DEFAULT_KIMI_BASE_URL).respond(200, json=_ok("# arxiv doc"))
    p = make_provider(monkeypatch)
    assert await p.describe("arxiv") == "# arxiv doc"
    assert await p.describe("arxiv") == "# arxiv doc"
    assert respx.calls.call_count == 1


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
    # wire shape: call_data_source_tool + auto-generated file_path
    body = json.loads(respx.calls[0].request.content)
    assert body["method"] == "call_data_source_tool"
    assert body["params"]["data_source_name"] == "tianyancha"
    assert body["params"]["api_name"] == "search_company"
    assert body["params"]["params"]["keyword"] == "腾讯"
    assert body["params"]["params"]["file_path"].endswith(".csv")


@respx.mock
async def test_call_data_source_tool_wire_key_set_exact(monkeypatch):
    """F1 probe: the call params carry exactly the protocol keys."""
    respx.post(DEFAULT_KIMI_BASE_URL).respond(200, json=_ok("ok"))
    p = make_provider(monkeypatch)
    await p.call("tianyancha", "search_company", {"keyword": "腾讯"})
    body = json.loads(respx.calls[0].request.content)
    assert set(body["params"]) == {"data_source_name", "api_name", "params"}


@respx.mock
async def test_self_refresh_write_back_is_atomic(monkeypatch, tmp_path):
    """F2: write-back goes through tmp + os.replace under flock."""
    import os
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    f = _write_auth(tmp_path / "kimi-1.json", expired="2020-01-01T00:00:00Z")
    monkeypatch.setenv("KIMI_AUTH_FILE", str(f))
    replaced = {}
    real_replace = os.replace

    def spy(src, dst):
        replaced["src"], replaced["dst"] = str(src), str(dst)
        return real_replace(src, dst)

    monkeypatch.setattr("unified_finance_mcp.providers.kimi.os.replace", spy)
    respx.post("https://auth.kimi.com/api/oauth/token").respond(200, json={
        "access_token": "new-at", "refresh_token": "new-rt", "expires_in": 900})
    respx.post(DEFAULT_KIMI_BASE_URL).respond(200, json=_ok("ok"))
    p = KimiProvider(get_settings())
    await p.describe("wind")
    assert replaced["dst"] == str(f)
    assert replaced["src"].endswith(".kimi-1.json.tmp")
    assert not (tmp_path / ".kimi-1.json.tmp").exists()  # no half-written file left
    saved = json.loads(f.read_text())  # valid JSON after write-back
    assert saved["access_token"] == "new-at"
    assert saved["device_id"] == "dev-1"  # other fields preserved


@respx.mock
async def test_call_files_base64_wrapped_and_newline_decode(monkeypatch, tmp_path):
    """F3: standard base64 (76-col wrap / trailing newline) must land on disk."""
    import base64
    monkeypatch.setenv("KIMI_FILES_DIR", str(tmp_path))
    raw = b"line1,line2\n" * 40
    b64 = base64.b64encode(raw).decode()
    wrapped = "\n".join(b64[i:i + 76] for i in range(0, len(b64), 76))
    respx.post(DEFAULT_KIMI_BASE_URL).respond(200, json=_ok(
        "ok", files=[
            {"name": "wrapped.bin", "content": wrapped, "encoding": "base64"},
            {"name": "trailing.bin", "content": b64 + "\n", "encoding": "base64"}]))
    p = make_provider(monkeypatch)
    out = await p.call("tianyancha", "x", {"keyword": "k"})
    assert (tmp_path / "wrapped.bin").read_bytes() == raw
    assert (tmp_path / "trailing.bin").read_bytes() == raw
    assert len(out["saved_files"]) == 2


@respx.mock
async def test_proxy_401_hint_points_at_proxy(monkeypatch):
    """F4: with KIMI_PROXY_URL set, a 401 blames the proxy, not 'unconfigured'."""
    for v in ("KIMI_ACCESS_TOKEN", "KIMI_AUTH_FILE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("KIMI_PROXY_URL", PROXY_URL)
    respx.post(PROXY_URL).respond(401, json={"error": "unauthorized"})
    p = KimiProvider(get_settings())
    with pytest.raises(AuthError) as exc:
        await p.describe("wind")
    msg = str(exc.value)
    assert "未配置" not in msg
    assert "proxy" in msg
    assert respx.calls.call_count == 1  # proxy path: no re-read retry


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
    with pytest.raises(AuthError) as exc:
        await p.describe("wind")
    assert respx.calls.call_count == 1  # direct-token path: no pointless retry
    for env in ("KIMI_ACCESS_TOKEN", "KIMI_AUTH_FILE", "KIMI_PROXY_URL"):
        assert env in str(exc.value)


@respx.mock
async def test_401_rereads_auth_file_and_retries_once(monkeypatch, tmp_path):
    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    f = _write_auth(tmp_path / "kimi-1.json")
    monkeypatch.setenv("KIMI_AUTH_FILE", str(f))
    route = respx.post(DEFAULT_KIMI_BASE_URL)
    route.side_effect = [
        httpx.Response(401, json={"error": "unauthorized"}),
        httpx.Response(200, json=_ok("recovered")),
    ]
    p = KimiProvider(get_settings())
    assert await p.describe("wind") == "recovered"
    assert route.call_count == 2


# ── cliproxy credential-file path (brief verbatim) ──────────────────────────

def _write_auth(path, **kw):
    import json
    data = {"access_token": "at", "refresh_token": "rt", "device_id": "dev-1",
            "expired": "2099-01-01T00:00:00Z", "disabled": False,
            "type": "kimi", "token_type": "Bearer"}
    data.update(kw)
    path.write_text(json.dumps(data))
    return path


def test_available_via_auth_file(monkeypatch, tmp_path):
    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN", "KIMI_AUTH_FILE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("KIMI_AUTH_FILE", str(tmp_path / "kimi-*.json"))
    _write_auth(tmp_path / "kimi-1.json")
    assert KimiProvider(get_settings()).available()
    # disabled file does not count
    (tmp_path / "kimi-1.json").write_text('{"disabled": true}')
    assert not KimiProvider(get_settings()).available()


# ── F1 regressions: corrupt auth files must never raise out of available() ──

def test_available_binary_auth_file_returns_false(monkeypatch, tmp_path):
    """A corrupt (binary) auth file must not raise UnicodeDecodeError."""
    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    f = tmp_path / "kimi-1.json"
    f.write_bytes(b"\xff\xfe\x00\x01")
    monkeypatch.setenv("KIMI_AUTH_FILE", str(f))
    assert KimiProvider(get_settings()).available() is False  # no raise


def test_available_glob_matching_directory_returns_false(monkeypatch, tmp_path):
    """A glob candidate that is a directory must be skipped, not read."""
    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    (tmp_path / "kimi-dir").mkdir()
    monkeypatch.setenv("KIMI_AUTH_FILE", str(tmp_path / "kimi-*"))
    assert KimiProvider(get_settings()).available() is False  # no raise


async def test_route_and_call_through_kimi_never_raises_on_corrupt_auth(
        monkeypatch, tmp_path):
    """The candidate filter calls available() unguarded: a corrupt auth file
    must degrade to 'not available', not propagate a decode error."""
    from unified_finance_mcp.tools._routing import route_and_call

    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("KIMI_AUTH_FILE", str(tmp_path / "kimi-*.json"))
    (tmp_path / "kimi-1.json").write_bytes(b"\x00\xffbinary")
    providers = {"kimi": KimiProvider(get_settings())}
    out = await route_and_call(market="US", chain=["kimi"], providers=providers,
                               call=lambda p: p.economic("GDP"))
    assert isinstance(out, dict) and "error" in out  # tool_error, no raise


@respx.mock
async def test_corrupt_auth_file_after_resolution_is_auth_error(monkeypatch,
                                                                tmp_path):
    """_reload_if_changed on a file that turns corrupt after resolution must
    raise AuthError (kind auth), never UnicodeDecodeError/JSONDecodeError."""
    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    f = _write_auth(tmp_path / "kimi-1.json")
    monkeypatch.setenv("KIMI_AUTH_FILE", str(f))
    p = KimiProvider(get_settings())
    assert p.available()  # resolves fine now
    # Pre-create the credentials object so _headers() skips re-resolution
    # and _reload_if_changed() is the code path that hits the corrupt file.
    from unified_finance_mcp.providers.kimi import _KimiCredentials

    p._creds = _KimiCredentials(f)
    f.write_bytes(b"\xff\xfe\x00")  # corrupted before the first read
    with pytest.raises(AuthError) as exc:
        await p._headers()
    assert exc.value.kind == "auth"
    assert "corrupt" in str(exc.value)
    # The full invoke path (with its one re-read retry) must also surface
    # only AuthError — never a raw UnicodeDecodeError/JSONDecodeError.
    with pytest.raises(AuthError) as exc2:
        await p.describe("wind")
    assert exc2.value.kind == "auth"


@respx.mock
async def test_token_from_auth_file_used_with_same_device_id(monkeypatch, tmp_path):
    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN"):
        monkeypatch.delenv(v, raising=False)
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
    monkeypatch.setattr(time, "sleep", lambda _s: None)  # skip the cliproxy beat
    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN"):
        monkeypatch.delenv(v, raising=False)
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
    assert saved["device_id"] == "dev-1"  # other fields preserved


@respx.mock
async def test_write_back_preserves_file_mode(monkeypatch, tmp_path):
    """F3 fix: atomic write-back must keep the original file mode (0600) —
    a live-token credential file must never be widened to umask-default."""
    import os
    import stat
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    f = _write_auth(tmp_path / "kimi-1.json", expired="2020-01-01T00:00:00Z")
    os.chmod(f, 0o600)
    monkeypatch.setenv("KIMI_AUTH_FILE", str(f))
    respx.post("https://auth.kimi.com/api/oauth/token").respond(200, json={
        "access_token": "new-at", "refresh_token": "new-rt", "expires_in": 900})
    respx.post(DEFAULT_KIMI_BASE_URL).respond(200, json=_ok("ok"))
    p = KimiProvider(get_settings())
    await p.describe("wind")
    assert stat.S_IMODE(f.stat().st_mode) == 0o600


@respx.mock
async def test_is_success_false_error_scrubs_bearer(monkeypatch):
    """F2 fix: a 200-body error echoing the bearer must not leak the token."""
    for v in ("KIMI_PROXY_URL", "KIMI_AUTH_FILE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("KIMI_ACCESS_TOKEN", "tok-super-secret")
    respx.post(DEFAULT_KIMI_BASE_URL).respond(200, json={
        "is_success": False,
        "error": {"user": [{"type": "text",
                            "text": "bad token tok-super-secret"}]}})
    p = KimiProvider(get_settings())
    with pytest.raises(UpstreamError) as exc:
        await p.call("tianyancha", "nope", {})
    msg = str(exc.value)
    assert "tok-super-secret" not in msg
    assert "***" in msg  # the scrub actually replaced something


@respx.mock
async def test_refresh_failure_scrubs_refresh_token(monkeypatch, tmp_path):
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    f = _write_auth(tmp_path / "kimi-1.json", expired="2020-01-01T00:00:00Z",
                    refresh_token="rt-super-secret")
    monkeypatch.setenv("KIMI_AUTH_FILE", str(f))
    respx.post("https://auth.kimi.com/api/oauth/token").respond(
        200, json={"error": "invalid rt-super-secret"})
    p = KimiProvider(get_settings())
    with pytest.raises(AuthError) as exc:
        await p.describe("wind")
    assert "rt-super-secret" not in str(exc.value)


# ── proxy-container path (controller ruling 3) ──────────────────────────────

@respx.mock
async def test_proxy_url_available_and_no_auth_header(monkeypatch):
    for v in ("KIMI_ACCESS_TOKEN", "KIMI_AUTH_FILE"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("KIMI_PROXY_URL", PROXY_URL)
    respx.post(PROXY_URL).respond(200, json=_ok("# sp_data doc"))
    p = KimiProvider(get_settings())
    assert p.available()
    doc = await p.describe("sp_data")
    assert "sp_data" in doc
    req = respx.calls[0].request
    assert req.url == PROXY_URL
    assert "authorization" not in req.headers  # proxy injects credentials
    assert req.headers["x-msh-device-id"]


@respx.mock
async def test_proxy_url_beats_direct_token(monkeypatch):
    monkeypatch.setenv("KIMI_PROXY_URL", PROXY_URL)
    monkeypatch.setenv("KIMI_ACCESS_TOKEN", "tok")
    respx.post(PROXY_URL).respond(200, json=_ok("via proxy"))
    respx.post(DEFAULT_KIMI_BASE_URL).respond(200, json=_ok("via direct"))
    p = KimiProvider(get_settings())
    assert await p.describe("imf") == "via proxy"
    assert respx.calls[0].request.url.host == "kimi-proxy"
    assert "authorization" not in respx.calls[0].request.headers


# ── unconfigured ────────────────────────────────────────────────────────────

async def test_unconfigured_headers_raise_auth_error_listing_three_ways(monkeypatch):
    for v in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN", "KIMI_AUTH_FILE"):
        monkeypatch.delenv(v, raising=False)
    p = KimiProvider(get_settings())
    assert not p.available()
    with pytest.raises(AuthError) as exc:
        await p._headers()
    for env in ("KIMI_PROXY_URL", "KIMI_ACCESS_TOKEN", "KIMI_AUTH_FILE"):
        assert env in str(exc.value)


# ── hermeticity guard (T10-C1, in-process getaddrinfo guard) ────────────────

def _getaddrinfo_fail(*args, **kwargs):
    raise AssertionError(f"network resolution attempted: {args[:2]}")


def test_provider_module_import_does_not_touch_network(monkeypatch):
    """Import-time surface: the kimi provider must not resolve DNS.

    This module is already imported by earlier tests, so this is a re-import
    over an installed getaddrinfo guard; the fresh-process harness below
    exercises the same path in a clean interpreter.
    """
    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo_fail)
    from unified_finance_mcp.providers import kimi

    assert kimi.KIMI_OAUTH_TOKEN_URL.startswith("https://")
    assert "tianyancha" in kimi.KNOWN_SOURCES
    assert "world_bank_open_data" in kimi.KNOWN_SOURCES
    assert KimiProvider(get_settings()).list_sources() == kimi.KNOWN_SOURCES
