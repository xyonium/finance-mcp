"""T14 R2 pinning tests: the vendored coinlist data plane is reachable.

Pre-R2 the module could not even be imported — ``COINLIST_DIR =
Path(__file__).with_name("")`` raises ``ValueError: Invalid name ''`` at import
time, so every consumer (tv_scan actions, candle_pattern, egx_overview,
egx_screener) would fail with that error on a real call. These tests pin:
(a) import smoke, (b) load_symbols shape + case-insensitivity, (c) set-level
parity with the reference coinlist files, (d) exchanges_listing_symbol
behavior, (e) end-to-end: containers reach the vendored symbols with ONLY the
network layer stubbed (_symbols_for / coinlist are never stubbed). All
hermetic — zero network; the getaddrinfo-guard harness runs this file keyless
and keyed.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from unified_finance_mcp.data import coinlist
from unified_finance_mcp.tools import containers as containers_mod

_REF_COINLIST_DIR = Path(
    "/mnt/docker/mcpserver/uv-cache/archive-v0/DH-4mhgPjnG1yj0BHV4Qv"
    "/tradingview_mcp/coinlist")


# ── (a) import smoke ────────────────────────────────────────────────────────

def test_coinlist_import_smoke():
    assert coinlist.COINLIST_DIR.is_dir()
    assert (coinlist.COINLIST_DIR / "egx.txt").is_file()


# ── (b) load_symbols shape ──────────────────────────────────────────────────

def test_load_symbols_egx_vendored():
    rows = coinlist.load_symbols("egx")
    assert len(rows) >= 100
    assert "EGX:COMI" in rows
    assert all(r.count(":") == 1 for r in rows)  # EXCHANGE:TICKER form
    # case-insensitive lookup
    assert coinlist.load_symbols("EGX") == rows


def test_load_symbols_unknown_exchange_empty():
    assert coinlist.load_symbols("no_such_venue") == []


# ── (c) parity with the reference coinlist files ────────────────────────────

@pytest.mark.parametrize("exchange", ["egx", "nasdaq", "kucoin"])
def test_load_symbols_matches_reference_files(exchange):
    rows = coinlist.load_symbols(exchange)
    assert rows and all(r.count(":") == 1 for r in rows)  # always-on assertions
    ref_file = _REF_COINLIST_DIR / f"{exchange}.txt"
    if not ref_file.is_file():
        pytest.skip(f"reference coinlist not readable at {ref_file}")
    ref_rows = [ln.strip()
                for ln in ref_file.read_text(encoding="utf-8").splitlines()
                if ln.strip()]
    assert set(rows) == set(ref_rows)


# ── (d) exchanges_listing_symbol ────────────────────────────────────────────

def test_exchanges_listing_symbol():
    listed = coinlist.exchanges_listing_symbol("COMI")
    assert any(e.lower() == "egx" for e in listed)
    assert "ALL" not in listed  # returned names are uppercase exchange names
    assert coinlist.exchanges_listing_symbol("ZZZ_NO_SUCH") == []


def test_suggestion_exclude_aggregate_never_surfaces():
    # ONGUSDT is listed in BOTH binance.txt and the all.txt aggregate, so if
    # _SUGGESTION_EXCLUDE were deleted the aggregate would surface as "ALL"
    # (names are uppercased) — killing that mutation (M3). With the exclusion
    # active, only the real venue listing remains.
    agg = coinlist.exchanges_listing_symbol("ONGUSDT")
    assert "ALL" not in agg  # _SUGGESTION_EXCLUDE 聚合表永不浮出
    assert "BINANCE" in agg


# F-2: _symbols_for must raise ProviderError when the vendored list is empty
# (kills the mutation that deletes the raise — M9).

def test_symbols_for_raises_provider_error_on_empty_vendored_list(monkeypatch):
    from unified_finance_mcp.errors import ProviderError
    from unified_finance_mcp.tools import _tv_scanners

    monkeypatch.setattr("unified_finance_mcp.data.coinlist.load_symbols",
                        lambda exchange: [])
    with pytest.raises(ProviderError) as exc:
        _tv_scanners._symbols_for("egx")
    assert "egx" in str(exc.value)  # exchange name carried in the message


# ── (e) end-to-end: vendored symbols reach the network layer ────────────────

def _analysis_row():
    a = MagicMock()
    a.indicators = {"open": 100.0, "close": 105.0, "SMA20": 100.0,
                    "BB.upper": 106.0, "BB.lower": 96.0, "EMA50": 99.0,
                    "RSI": 55.0, "volume": 1_000_000.0}
    return a


async def test_tv_scan_top_gainers_egx_end_to_end(monkeypatch):
    captured = {"symbols": []}

    def fake_gma(screener, interval, symbols):
        captured["screener"] = screener
        captured["interval"] = interval
        captured["symbols"] += list(symbols)
        return {s: _analysis_row() for s in symbols}

    # Network layer only: tradingview_ta.get_multiple_analysis. The vendored
    # symbol lists (coinlist / _symbols_for) are the REAL code path.
    monkeypatch.setattr("tradingview_ta.get_multiple_analysis", fake_gma)
    out = await containers_mod.tv_scan("top_gainers", exchange="egx", limit=10)
    assert "error" not in out
    assert len(out["data"]) == 10
    assert "EGX:COMI" in captured["symbols"]  # vendored symbols flowed in
    assert len(captured["symbols"]) == 253  # full egx.txt universe, batched
    assert all(r["symbol"].startswith("EGX:") for r in out["data"])
    # R2.5: _screener_for now resolves via the exchange-name map; the egx scan
    # must reach get_multiple_analysis with the "egypt" market slug.
    assert captured["screener"] == "egypt"


async def test_tv_scan_defaults_resolve_nasdaq_symbols(monkeypatch):
    """Final-fix: tv_scan's shipped default exchange must resolve symbols.
    The old "US" default hit no vendored coinlist file (dead path)."""
    captured = {"symbols": [], "screener": None}

    def fake_gma(screener, interval, symbols):
        captured["screener"] = screener
        captured["symbols"] += list(symbols)
        return {s: _analysis_row() for s in symbols}

    monkeypatch.setattr("tradingview_ta.get_multiple_analysis", fake_gma)
    out = await containers_mod.tv_scan("top_gainers", limit=5)
    assert "error" not in out
    assert len(out["data"]) == 5
    assert captured["symbols"] and all(
        s.startswith("NASDAQ:") for s in captured["symbols"][:10])
    assert captured["screener"] == "america"


class FakeEndToEndQuery:
    """Captures set_markets/limit and returns a candle-pattern-detectable row."""

    def __init__(self):
        self.markets = None
        self.limit_arg = None

    def set_markets(self, *markets):
        self.markets = markets
        return self

    def select(self, *cols):
        return self

    def where(self, *exprs):
        return self

    def limit(self, n):
        self.limit_arg = n
        return self

    def get_scanner_data(self):
        # Container timeframe "1d" -> code "1D", so the multi-TF main path
        # selects "open|1D"/"close|1D"/... columns. The row is crafted to
        # satisfy compute_candle_pattern_score (detected: body ratio, momentum,
        # volume) so the MAIN path returns results and the TA fallback never
        # runs (hermetic: the fallback would call real tradingview_ta).
        rows = [{"ticker": "EGX:COMI", "open|1D": 100.0, "close|1D": 108.0,
                 "high|1D": 108.5, "low|1D": 99.5, "volume|1D": 60000.0,
                 "RSI": 60.0}]
        return 1, pd.DataFrame(rows)


async def test_tv_analyze_candle_pattern_egx_end_to_end(monkeypatch):
    q = FakeEndToEndQuery()

    class FakeColumn:
        def __init__(self, name):
            self.name = name

        def __eq__(self, other):
            return {"col": self.name, "eq": other}

    # Network layer only: the screener Query. _symbols_for / coinlist are the
    # REAL code path — the multi-TF main path must consume the vendored list.
    monkeypatch.setattr("tradingview_screener.Query", lambda: q)
    monkeypatch.setattr("tradingview_screener.Column", FakeColumn)
    out = await containers_mod.tv_analyze("candle_pattern", symbol="COMI",
                                          exchange="egx")
    assert "error" not in out
    assert q.markets == ("egypt",)  # F3 market map, not the dead "crypto" path
    assert q.limit_arg == 30  # min(limit*2, 100) vendored symbols passed in
    data = out["data"]
    assert data["method"] == "multi-timeframe"  # main path, not the TA fallback
    assert data["total_found"] >= 1
    assert data["data"][0]["symbol"] == "EGX:COMI"
