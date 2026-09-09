"""T14 R2.5 pinning tests: TA screener slug resolution via the exchange-name
map (EXCHANGE_NAME_TO_TV_MARKET), not the provider's uppercase-keyed
EXCHANGE_TO_TV_SCREENER.

Pre-fix: ``_screener_for("egx")`` returned "egx" (the .get fallthrough of a
map keyed "EGX"), so every scan/egx/single-TF TA path called
``get_multiple_analysis(screener="egx", ...)``. The reference semantic is
``EXCHANGE_SCREENER.get(exchange, "crypto")`` — the exchange-name map.

All tests hermetic (zero network); the getaddrinfo-guard harness runs this
file keyless and keyed.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from unified_finance_mcp.tools import _tv_scanners

# ── _screener_for: exchange-name map (reference get_market_type) ────────────

@pytest.mark.parametrize("exchange,expected", [
    ("egx", "egypt"),
    ("EGX", "egypt"),          # case-insensitive
    ("nasdaq", "america"),
    ("nyse", "america"),
    ("amex", "america"),
    ("hkex", "hongkong"),
    ("sse", "china"),
    ("kucoin", "crypto"),
    ("binance", "crypto"),
    ("bist", "turkey"),
    ("tadawul", "ksa"),
    ("NO_SUCH_VENUE", "crypto"),
])
def test_screener_for_exchange_name_map(exchange, expected):
    assert _tv_scanners._screener_for(exchange) == expected


# ── _resolve_screener_for_symbol: prefix lookup + TA-only layer kept ────────

def test_resolve_screener_for_symbol_stock_and_ta_only():
    # EGX-prefixed symbol -> egypt (exchange-name map, lowercase prefix)
    assert _tv_scanners._resolve_screener_for_symbol("EGX:COMI", "egx") == "egypt"
    # TVC-prefixed (XAUUSD alias target) -> cfd via the kept TA-only layer
    assert _tv_scanners._resolve_screener_for_symbol("TVC:GOLD", "oanda") == "cfd"
    # unprefixed symbol falls back to the exchange argument
    assert _tv_scanners._resolve_screener_for_symbol("COMI", "egx") == "egypt"
    # unknown prefix falls back to crypto
    assert _tv_scanners._resolve_screener_for_symbol("X:Y", "x") == "crypto"


# ── capture: an egx impl passes "egypt" into get_multiple_analysis ──────────

def _analysis_row():
    a = MagicMock()
    a.indicators = {"open": 100.0, "close": 105.0, "SMA20": 100.0,
                    "BB.upper": 106.0, "BB.lower": 96.0, "EMA50": 99.0,
                    "RSI": 55.0, "volume": 1_000_000.0}
    return a


def test_egx_overview_uses_egypt_screener_slug(monkeypatch):
    captured = {}

    def fake_gma(screener, interval, symbols):
        captured["screener"] = screener
        captured["interval"] = interval
        captured["count"] = len(symbols)
        return {s: _analysis_row() for s in symbols}

    # Network layer only: tradingview_ta.get_multiple_analysis. _screener_for
    # and the vendored symbol list are the REAL code path.
    monkeypatch.setattr("tradingview_ta.get_multiple_analysis", fake_gma)
    out = _tv_scanners.egx_overview(timeframe="1D", limit=5)
    assert "error" not in out
    assert out["total_analyzed"] == 253  # full vendored egx universe
    assert captured["screener"] == "egypt"  # NOT "egx"
    assert captured["interval"] == "1D"


# ── guard: ProviderError kind survives the container boundary ───────────────

async def test_container_kind_preserved_for_egx_impl(monkeypatch):
    from unified_finance_mcp.errors import RateLimited
    from unified_finance_mcp.tools import containers as containers_mod

    def boom(timeframe, limit):
        raise RateLimited("tradingview throttle (egx)")

    monkeypatch.setattr("unified_finance_mcp.tools._tv_scanners.egx_overview",
                        boom)
    out = await containers_mod.egx_market("overview")
    assert out["error"].startswith("rate_limited: ")
    assert out["source"] == "tradingview"
