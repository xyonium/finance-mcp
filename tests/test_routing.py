from unified_finance_mcp.errors import ProviderError, UpstreamDrift
from unified_finance_mcp.tools._routing import route_and_call


class FakeProvider:
    def __init__(self, name, markets=None, available=True, result=None, exc=None):
        self.name, self.markets, self._av = name, markets, available
        self._result, self._exc = result, exc
        self.called = 0
    def available(self): return self._av
    def covers(self, m): return self.markets is None or m in self.markets


async def call(p):
    p.called += 1
    if p._exc: raise p._exc
    return p._result


async def test_skips_non_covering_without_calling():
    a = FakeProvider("a", markets={"US"}, result={"src": "a"})
    b = FakeProvider("b", result={"src": "b"})
    out = await route_and_call(market="EG", chain=["a", "b"],
                               providers={"a": a, "b": b}, call=call)
    assert out == {"src": "b"} and a.called == 0 and b.called == 1


async def test_no_covering_source_returns_immediate_error():
    a = FakeProvider("a", markets={"US"})
    out = await route_and_call(market="EG", chain=["a"], providers={"a": a}, call=call)
    assert "error" in out and "EG" in out["error"] and a.called == 0
    assert "hint" in out


async def test_fallback_collects_source_errors():
    a = FakeProvider("a", exc=ProviderError("down"))
    b = FakeProvider("b", result={"ok": 1})
    out = await route_and_call(market="US", chain=["a", "b"],
                               providers={"a": a, "b": b}, call=call)
    assert out == {"ok": 1}


async def test_all_fail_reports_each():
    a = FakeProvider("a", exc=ProviderError("x1"))
    b = FakeProvider("b", exc=ValueError("x2"))
    out = await route_and_call(market="US", chain=["a", "b"],
                               providers={"a": a, "b": b}, call=call)
    assert out["source_errors"] == {"a": "error: x1", "b": "error: x2"}


async def test_explicit_source_unconfigured():
    a = FakeProvider("a", available=False)
    out = await route_and_call(market="US", chain=["a"], providers={"a": a},
                               call=call, explicit_source="a")
    assert "not configured" in out["error"]


async def test_drift_failure_asks_the_model_to_contact_admin():
    a = FakeProvider("a", exc=UpstreamDrift("html instead of json"))
    b = FakeProvider("b", exc=ProviderError("down"))
    out = await route_and_call(market="US", chain=["a", "b"],
                               providers={"a": a, "b": b}, call=call)
    assert out["action"] == "contact_admin"
    assert out["drifted_sources"] == ["a"]
    assert "联系管理员" in out["hint"]
    assert out["source_errors"]["a"].startswith("upstream_drift:")


async def test_connectivity_failure_has_no_contact_admin_action():
    a = FakeProvider("a", exc=ProviderError("timeout"))
    out = await route_and_call(market="US", chain=["a"],
                               providers={"a": a}, call=call)
    assert "action" not in out and "hint" not in out


async def test_explicit_source_drift_also_carries_the_action():
    a = FakeProvider("a", exc=UpstreamDrift("bad csv header"))
    out = await route_and_call(market="US", chain=["a"],
                               providers={"a": a}, call=call,
                               explicit_source="a")
    assert out["action"] == "contact_admin"
    assert out["drifted_sources"] == ["a"]
