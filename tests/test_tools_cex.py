"""cex_market container: action routing + never-raise + hallucination hints.

The container wraps providers["cex"] (fake here — the provider itself is
covered in test_provider_cex.py). Contract: every failure shape comes back as
{"error", "hint"?, "source": "cex"}; the layer must never raise.
"""
import pytest

from unified_finance_mcp.tools import cex as cex_tool


class FakeCex:
    async def quote(self, exchange, logical):
        return {"symbol": logical, "exchange": exchange, "price": 95.6, "source": "cex"}

    async def kline(self, exchange, logical, interval="1d", limit=200):
        return [{"date": "2026-09-11", "open": "97", "high": "97.5",
                 "low": "95.2", "close": "95.5", "volume": "201097"}]

    async def summary(self, exchange, logical, interval="1d"):
        return {"summary": {"RECOMMENDATION": "BUY"}, "source": "cex"}

    async def funding(self, exchange, logical):
        return {"symbol": logical, "funding_rate": "-0.0004", "source": "cex"}

    async def open_interest(self, exchange, logical):
        return {"symbol": logical, "open_interest": "525629", "source": "cex"}


@pytest.fixture
def providers():
    return {"cex": FakeCex()}


async def test_quote_action(providers):
    out = await cex_tool.cex_market("quote", "CL", "bitget", providers=providers)
    assert out["data"]["price"] == 95.6


async def test_unknown_action_lists(providers):
    out = await cex_tool.cex_market("nope", "CL", "bitget", providers=providers)
    assert "error" in out and "quote" in out["hint"]


async def test_bad_exchange(providers):
    out = await cex_tool.cex_market("quote", "CL", "kraken", providers=providers)
    assert "error" in out  # kraken 不在白名单


async def test_bad_symbol_hint(providers):
    # UKOIL(Brent)是被拒绝的幻觉资产;USOIL 现在是 mexc 的 WTI 合约→CL,合法。
    out = await cex_tool.cex_market("quote", "UKOIL", "bitget", providers=providers)
    assert "error" in out and "symbols" in out["hint"]


async def test_never_raises(providers):
    class Boom:
        async def quote(self, *a):
            raise RuntimeError("x")
    out = await cex_tool.cex_market("quote", "CL", "bitget",
                                    providers={"cex": Boom()})
    assert "error" in out and out["source"] == "cex"
