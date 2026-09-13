"""T15 quant_backtest L2 container: run / compare / walk_forward.

Hermetic: every test stubs `_backtest_engine.fetch` (the single data
boundary) with synthetic list[dict] candles of the ruling-2 shape
(date/open/high/low/close/volume). No test reaches real yfinance code or the
network; the T10-C1 getaddrinfo-guard harness runs this file keyless and
keyed in a fresh process.
"""
from __future__ import annotations

import datetime as dt
import math
import random

import pytest

from unified_finance_mcp import tools as tools_pkg

ALL_NINE = ("rsi", "bollinger", "macd", "ema_cross", "supertrend", "donchian",
            "rsi_pullback", "keltner_breakout", "triple_ema")

WALK_FORWARD_SEVEN = ("rsi", "bollinger", "macd", "ema_cross", "supertrend",
                      "donchian", "keltner_breakout")

REFERENCE_METRIC_KEYS = {
    "total_trades", "winning_trades", "losing_trades", "win_rate_pct",
    "final_capital", "total_return_pct", "avg_gain_pct", "avg_loss_pct",
    "max_drawdown_pct", "profit_factor", "sharpe_ratio", "calmar_ratio",
    "expectancy_pct", "best_trade", "worst_trade",
}

BRIEF_ALIASES = {"total_return", "sharpe", "max_drawdown", "trades"}

RANKING_KEYS = {"strategy", "strategy_label", "total_return_pct", "win_rate_pct",
                "total_trades", "profit_factor", "sharpe_ratio", "calmar_ratio",
                "max_drawdown_pct", "expectancy_pct", "rank"}


def _make_candles(n=200, start_price=100.0, seed=7, interval="1d") -> list[dict]:
    """Deterministic synthetic candles: gentle random walk with small noise."""
    rng = random.Random(seed)
    price = start_price
    base = dt.date(2024, 1, 1)
    candles = []
    for i in range(n):
        price = max(1.0, price * (1 + rng.gauss(0.0008, 0.02)))
        o = round(price * (1 + rng.gauss(0, 0.004)), 4)
        c = round(price, 4)
        h = round(max(o, c) * (1 + abs(rng.gauss(0, 0.004))), 4)
        low = round(min(o, c) * (1 - abs(rng.gauss(0, 0.004))), 4)
        day = base + dt.timedelta(days=i)
        date = day.strftime("%Y-%m-%d")
        if interval == "1h":
            date += f" {(i % 6):02d}:{(i % 6) * 10:02d}"
        candles.append({"date": date, "open": o, "high": h, "low": low,
                        "close": c, "volume": rng.randint(1_000, 1_000_000)})
    return candles


def _stub_fetch(monkeypatch, n=200):
    calls = {}

    def fake(symbol, period, interval):
        calls.update(symbol=symbol, period=period, interval=interval)
        return _make_candles(n, interval=interval)

    monkeypatch.setattr("unified_finance_mcp.tools._backtest_engine.fetch", fake)
    return fake, calls


@pytest.fixture
def stub_fetch(monkeypatch):
    return _stub_fetch(monkeypatch)


@pytest.fixture
def stub_fetch_300(monkeypatch):
    return _stub_fetch(monkeypatch, n=300)


def _all_finite(value) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_all_finite(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return all(_all_finite(v) for v in value)
    return True


# ── module surface ─────────────────────────────────────────────────────────

def test_backtest_registered_in_all_modules():
    assert "backtest" in tools_pkg.ALL_MODULES
    assert len(tools_pkg.ALL_MODULES) == 17
    assert len(set(tools_pkg.ALL_MODULES)) == 17  # no duplicates


def test_strategy_map_has_all_nine():
    from unified_finance_mcp.tools import _backtest_engine as engine

    assert set(engine._STRATEGY_MAP) == set(ALL_NINE)


def test_engine_constants_byte_copied():
    from unified_finance_mcp.tools import _backtest_engine as engine

    assert engine._VALID_PERIODS == {"1mo", "3mo", "6mo", "1y", "2y"}
    assert engine._VALID_INTERVALS == {"1d", "1h"}
    assert engine._SMA200_STRATEGIES == {"rsi_pullback", "triple_ema"}
    assert engine._SMA200_MIN_BARS == 220
    assert engine._ANNUALIZATION == {"1d": 252, "1h": 252 * 6}
    assert len(engine._STRATEGY_LABELS) == 9
    assert engine._STRATEGY_LABELS["rsi"] == "RSI Oversold/Overbought"
    assert engine._STRATEGY_LABELS["keltner_breakout"] == \
        "Keltner Channel Breakout (EMA20 + 2·ATR)"


# ── help ───────────────────────────────────────────────────────────────────

async def test_help_lists_all_actions_and_strategies():
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="help")
    for a in ("run", "compare", "walk_forward"):
        assert a in out["actions"]
    for s in ALL_NINE:
        assert s in out["strategies"]
        entry = out["strategies"][s]
        assert entry["description"] and entry["params"] and entry["label"]
    assert out["examples"]


async def test_help_returns_help_constant():
    from unified_finance_mcp.tools import backtest

    assert await backtest.quant_backtest(action="help") == backtest.BACKTEST_HELP


async def test_help_ignores_other_args():
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="help", symbol=5, strategy=["x"],
                                        params=7)
    assert out == backtest.BACKTEST_HELP


# ── run ────────────────────────────────────────────────────────────────────

async def test_run_on_synthetic_data(stub_fetch):
    from unified_finance_mcp.tools import backtest

    _, calls = stub_fetch
    out = await backtest.quant_backtest(action="run", symbol="AAPL", strategy="rsi")
    assert "error" not in out
    assert {"total_return", "sharpe", "max_drawdown", "trades"} <= set(out["metrics"])
    assert out["symbol"] == "AAPL"
    assert out["strategy"] == "rsi"
    assert out["strategy_label"]
    assert out["candles_analyzed"] == 200
    assert out["period"] == "1y" and out["interval"] == "1d"
    assert out["timeframe"] == "Daily (1d)"
    assert isinstance(out["recent_trades"], list)
    assert out["disclaimer"] and out["timestamp"]
    assert "buy_and_hold_return_pct" in out and "vs_buy_and_hold_pct" in out
    assert calls == {"symbol": "AAPL", "period": "1y", "interval": "1d"}


async def test_run_metrics_full_reference_keys_plus_aliases(stub_fetch):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="run", symbol="AAPL", strategy="macd")
    assert REFERENCE_METRIC_KEYS <= set(out["metrics"])
    assert out["metrics"]["total_return"] == out["metrics"]["total_return_pct"]
    assert out["metrics"]["sharpe"] == out["metrics"]["sharpe_ratio"]
    assert out["metrics"]["max_drawdown"] == out["metrics"]["max_drawdown_pct"]
    assert out["metrics"]["trades"] == out["metrics"]["total_trades"]


async def test_run_output_all_finite(stub_fetch):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="run", symbol="AAPL", strategy="rsi")
    assert _all_finite(out)


@pytest.mark.parametrize("strategy", ALL_NINE)
async def test_run_each_strategy_succeeds(stub_fetch_300, strategy):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="run", symbol="AAPL", strategy=strategy)
    assert "error" not in out, strategy
    assert out["strategy"] == strategy
    assert out["candles_analyzed"] == 300
    assert out["metrics"]["trades"] >= 0


async def test_run_hourly_interval(stub_fetch):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="run", symbol="AAPL", strategy="rsi",
                                        interval="1h")
    assert "error" not in out
    assert out["interval"] == "1h" and out["timeframe"] == "Hourly (1h)"


async def test_run_params_enable_trade_log_and_equity_curve(stub_fetch):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(
        action="run", symbol="AAPL", strategy="rsi",
        params={"include_trade_log": True, "include_equity_curve": True})
    assert "error" not in out
    assert "trade_log" in out and "equity_curve" in out
    assert isinstance(out["trade_log"], list)
    assert out["equity_curve"][0]["date"] == "start"
    plain = await backtest.quant_backtest(action="run", symbol="AAPL",
                                          strategy="rsi")
    assert "trade_log" not in plain and "equity_curve" not in plain


async def test_run_strategy_params_flow_to_engine(monkeypatch):
    from unified_finance_mcp.tools import backtest

    captured = {}

    def fake_rb(symbol, strategy, period, initial_capital, commission_pct,
                slippage_pct, interval, include_trade_log=False,
                include_equity_curve=False, strategy_params=None):
        captured.update(symbol=symbol, strategy=strategy, period=period,
                        initial_capital=initial_capital,
                        commission_pct=commission_pct,
                        slippage_pct=slippage_pct, interval=interval,
                        strategy_params=strategy_params)
        return {"symbol": symbol, "strategy": strategy,
                "total_trades": 0, "winning_trades": 0, "losing_trades": 0,
                "win_rate_pct": 0.0, "final_capital": initial_capital,
                "total_return_pct": 0.0, "avg_gain_pct": 0.0,
                "avg_loss_pct": 0.0, "max_drawdown_pct": 0.0,
                "profit_factor": 0.0, "sharpe_ratio": 0.0,
                "calmar_ratio": 0.0, "expectancy_pct": 0.0,
                "best_trade": None, "worst_trade": None,
                "strategy_label": "x", "period": period, "interval": interval,
                "timeframe": "Daily (1d)", "candles_analyzed": 0,
                "date_from": "", "date_to": "",
                "buy_and_hold_return_pct": 0.0, "vs_buy_and_hold_pct": 0.0,
                "recent_trades": [], "data_source": "stub",
                "disclaimer": "", "timestamp": ""}

    monkeypatch.setattr("unified_finance_mcp.tools._backtest_engine.run_backtest",
                        fake_rb)
    out = await backtest.quant_backtest(action="run", symbol="AAPL",
                                        strategy="rsi",
                                        params={"oversold": 30, "period": 10})
    assert "error" not in out
    # defaults merged, then user params override; engine flags are not strategy params
    assert captured["strategy_params"] == {"oversold": 30, "overbought": 60,
                                           "period": 10}
    assert captured["initial_capital"] == 10000.0
    assert out["metrics"]["trades"] == 0


# ── run error paths ────────────────────────────────────────────────────────

async def test_run_unknown_strategy_hints_all_nine(stub_fetch):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="run", symbol="AAPL",
                                        strategy="ma_cross")
    assert "error" in out
    for s in ALL_NINE:
        assert s in out["hint"]


async def test_run_invalid_period_hints_valid_set(stub_fetch):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="run", symbol="AAPL", strategy="rsi",
                                        period="5y")
    assert "error" in out
    for p in ("1mo", "3mo", "6mo", "1y", "2y"):
        assert p in out["hint"]


async def test_run_invalid_interval_hints_valid_set(stub_fetch):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="run", symbol="AAPL", strategy="rsi",
                                        interval="5m")
    assert "error" in out
    assert "1d" in out["hint"] and "1h" in out["hint"]


async def test_run_empty_candles_tool_error(monkeypatch):
    from unified_finance_mcp.tools import backtest

    monkeypatch.setattr("unified_finance_mcp.tools._backtest_engine.fetch",
                        lambda s, p, i: [])
    out = await backtest.quant_backtest(action="run", symbol="NOPE", strategy="rsi")
    assert "error" in out and "hint" in out


async def test_run_sma200_strategy_short_data_tool_error(stub_fetch):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="run", symbol="AAPL",
                                        strategy="triple_ema")
    assert "error" in out and "220" in out["error"]


# ── compare ────────────────────────────────────────────────────────────────

async def test_compare_ranks_all_nine_strategies(stub_fetch):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="compare", symbol="AAPL")
    assert "error" not in out
    assert out["candles_analyzed"] == 200
    ranking = out["ranking"]
    assert len(ranking) == 9
    assert {r["strategy"] for r in ranking} == set(ALL_NINE)
    assert [r["rank"] for r in ranking] == list(range(1, 10))
    returns = [r["total_return_pct"] for r in ranking]
    assert returns == sorted(returns, reverse=True)
    assert out["winner"] == ranking[0]["strategy"]
    assert "buy_and_hold_return_pct" in out
    for r in ranking:
        assert RANKING_KEYS <= set(r)
    # 200 bars < SMA200 warmup → zero-trade strategies flagged
    assert out["warnings"] and "rsi_pullback" in out["warnings"]
    assert "triple_ema" in out["warnings"]


async def test_compare_no_warnings_with_220_plus_bars(stub_fetch_300):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="compare", symbol="AAPL")
    assert "error" not in out
    assert out["warnings"] is None


async def test_compare_strategies_subset(stub_fetch_300):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="compare", symbol="AAPL",
                                        strategies=["rsi", "macd"])
    assert "error" not in out
    assert {r["strategy"] for r in out["ranking"]} == {"rsi", "macd"}
    assert len(out["ranking"]) == 2


async def test_compare_unknown_strategies_filtered(stub_fetch_300):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="compare", symbol="AAPL",
                                        strategies=["rsi", "bogus"])
    assert "error" not in out
    assert [r["strategy"] for r in out["ranking"]] == ["rsi"]


async def test_compare_no_valid_strategies_tool_error(stub_fetch_300):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="compare", symbol="AAPL",
                                        strategies=["bogus", "nope"])
    assert "error" in out and "hint" in out


# ── walk_forward ───────────────────────────────────────────────────────────

async def test_walk_forward_runs_on_synthetic_data(stub_fetch):
    from unified_finance_mcp.tools import backtest

    _, calls = stub_fetch
    out = await backtest.quant_backtest(action="walk_forward", symbol="AAPL",
                                        strategy="rsi")
    assert "error" not in out
    assert out["strategy"] == "rsi"
    assert out["n_splits"] == 4
    assert out["train_ratio"] == 0.7
    assert out["total_candles"] == 200
    assert out["verdict"].startswith(("ROBUST", "MODERATE", "WEAK", "OVERFITTED"))
    assert out["folds"] and len(out["folds"]) <= 4
    for fold in out["folds"]:
        assert "fold_robustness_score" in fold
        assert "train_return_pct" in fold and "test_return_pct" in fold
    assert out["oos_total_trades"] >= 0
    assert "buy_and_hold_return_pct" in out
    assert calls["symbol"] == "AAPL" and calls["interval"] == "1d"


@pytest.mark.parametrize("strategy", ["rsi_pullback", "triple_ema"])
async def test_walk_forward_rejects_sma200_strategies(monkeypatch, strategy):
    from unified_finance_mcp.tools import backtest

    def boom(symbol, period, interval):
        raise AssertionError("fetch must not be called for rejected strategy")

    monkeypatch.setattr("unified_finance_mcp.tools._backtest_engine.fetch", boom)
    out = await backtest.quant_backtest(action="walk_forward", symbol="AAPL",
                                        strategy=strategy)
    assert "error" in out
    assert strategy in out["error"]
    for s in WALK_FORWARD_SEVEN:
        assert s in out["hint"]


@pytest.mark.parametrize("folds,expected", [(1, 2), (99, 10), (4, 4),
                                            ("x", 4), (None, 4)])
async def test_walk_forward_folds_clamped(stub_fetch_300, folds, expected):
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="walk_forward", symbol="AAPL",
                                        strategy="rsi", folds=folds)
    assert "error" not in out
    assert out["n_splits"] == expected


async def test_walk_forward_insufficient_data_tool_error(monkeypatch):
    from unified_finance_mcp.tools import backtest

    monkeypatch.setattr("unified_finance_mcp.tools._backtest_engine.fetch",
                        lambda s, p, i: _make_candles(30))
    out = await backtest.quant_backtest(action="walk_forward", symbol="AAPL",
                                        strategy="rsi")
    assert "error" in out and "hint" in out


# ── container never raises (ruling 6 / T14 parity) ─────────────────────────

async def test_unknown_action_hints_valid_actions():
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="bogus")
    assert "error" in out
    for a in ("help", "run", "compare", "walk_forward"):
        assert a in out["hint"]


_GARBAGE_PROBES = [
    ("non-str action", lambda m: m.quant_backtest(action=5)),
    ("list action", lambda m: m.quant_backtest(action=["run"])),
    ("None action", lambda m: m.quant_backtest(action=None)),
    ("run non-str symbol", lambda m: m.quant_backtest(action="run", symbol=5,
                                                      strategy="rsi")),
    ("run None symbol", lambda m: m.quant_backtest(action="run", symbol=None,
                                                   strategy="rsi")),
    ("run empty symbol", lambda m: m.quant_backtest(action="run", symbol="  ",
                                                    strategy="rsi")),
    ("run non-str strategy", lambda m: m.quant_backtest(action="run",
                                                        symbol="AAPL",
                                                        strategy=5)),
    ("run bad period", lambda m: m.quant_backtest(action="run", symbol="AAPL",
                                                  strategy="rsi", period="5y")),
    ("run non-str period", lambda m: m.quant_backtest(action="run", symbol="AAPL",
                                                      strategy="rsi", period=5)),
    ("run bad interval", lambda m: m.quant_backtest(action="run", symbol="AAPL",
                                                    strategy="rsi",
                                                    interval="5m")),
    ("run bad capital", lambda m: m.quant_backtest(action="run", symbol="AAPL",
                                                   strategy="rsi",
                                                   capital="abc")),
    ("run zero capital", lambda m: m.quant_backtest(action="run", symbol="AAPL",
                                                    strategy="rsi", capital=0)),
    ("run bad commission", lambda m: m.quant_backtest(action="run", symbol="AAPL",
                                                      strategy="rsi",
                                                      commission_pct=-1)),
    ("run non-dict params", lambda m: m.quant_backtest(action="run", symbol="AAPL",
                                                       strategy="rsi", params=7)),
    ("compare non-str symbol", lambda m: m.quant_backtest(action="compare",
                                                          symbol=5)),
    ("compare non-list strategies", lambda m: m.quant_backtest(action="compare",
                                                               symbol="AAPL",
                                                               strategies="rsi")),
    ("walk_forward unknown strategy",
     lambda m: m.quant_backtest(action="walk_forward", symbol="AAPL",
                                strategy="nope")),
    ("walk_forward rsi_pullback",
     lambda m: m.quant_backtest(action="walk_forward", symbol="AAPL",
                                strategy="rsi_pullback")),
]


@pytest.mark.parametrize("label,call", _GARBAGE_PROBES,
                         ids=[p[0] for p in _GARBAGE_PROBES])
async def test_quant_backtest_never_raises(label, call, stub_fetch):
    from unified_finance_mcp.tools import backtest

    out = await call(backtest)
    assert isinstance(out, dict), label
    assert "error" in out, label


# ── ruling 9: ProviderError kind preserved at the container boundary ───────

async def test_container_preserves_rate_limited_kind(monkeypatch):
    from unified_finance_mcp.errors import RateLimited
    from unified_finance_mcp.tools import backtest

    def boom(symbol, period, interval):
        raise RateLimited("yahoo throttle")

    monkeypatch.setattr("unified_finance_mcp.tools._backtest_engine.fetch", boom)
    out = await backtest.quant_backtest(action="run", symbol="AAPL", strategy="rsi")
    assert out["error"].startswith("rate_limited: ")
    assert out.get("source") == "backtest"


async def test_container_preserves_not_found_kind(monkeypatch):
    from unified_finance_mcp.errors import NotFound
    from unified_finance_mcp.tools import backtest

    def boom(symbol, period, interval):
        raise NotFound("no data for NOPE")

    monkeypatch.setattr("unified_finance_mcp.tools._backtest_engine.fetch", boom)
    out = await backtest.quant_backtest(action="run", symbol="NOPE", strategy="rsi")
    assert out["error"].startswith("not_found: ")
    assert out.get("source") == "backtest"


# ── engine / indicators port parity (no network by construction) ───────────

def test_calc_metrics_empty_trades_zeroed():
    from unified_finance_mcp.tools import _backtest_engine as engine

    m = engine._calc_metrics([], 10_000.0)
    assert m["total_trades"] == 0 and m["final_capital"] == 10_000.0
    assert m["profit_factor"] == 0 and m["sharpe_ratio"] == 0
    assert m["best_trade"] is None and m["worst_trade"] is None


def test_profit_factor_inf_sanitizes_to_none():
    from unified_finance_mcp.tools import _backtest_engine as engine
    from unified_finance_mcp.tools._sanitize import sanitize

    trades = [{"entry_date": "2024-01-02", "exit_date": "2024-01-05",
               "return_pct": 5.0},
              {"entry_date": "2024-01-09", "exit_date": "2024-01-12",
               "return_pct": 3.0}]
    m = engine._calc_metrics(trades, 10_000.0)
    assert m["profit_factor"] == float("inf")  # reference: no losses → inf
    assert sanitize(m)["profit_factor"] is None  # T12 sanitize semantics


def test_apply_costs_and_trade_log():
    from unified_finance_mcp.tools import _backtest_engine as engine

    trades = [{"entry_date": "2024-01-02", "exit_date": "2024-01-05",
               "entry_price": 100.0, "exit_price": 105.0, "strategy": "rsi"}]
    costed = engine._apply_costs(trades, 0.1, 0.05)
    assert costed[0]["gross_return_pct"] == pytest.approx(5.0)
    assert costed[0]["return_pct"] == pytest.approx(5.0 - 0.3)  # (0.1+0.05)*2
    log = engine._build_trade_log(costed, 10_000.0)
    assert log[0]["trade_no"] == 1
    assert log[0]["holding_days"] == 3
    assert log[0]["capital_before"] == 10_000.0


def test_buy_and_hold_return():
    from unified_finance_mcp.tools import _backtest_engine as engine

    assert engine._buy_and_hold_return([{"close": 100.0}, {"close": 110.0}]) == 10.0
    assert engine._buy_and_hold_return([]) == 0.0


def test_engine_validate_numeric_inputs():
    from unified_finance_mcp.tools import _backtest_engine as engine

    assert engine._validate_numeric_inputs(0, 0, 0) is not None
    assert engine._validate_numeric_inputs(10_000, -1, 0) is not None
    assert engine._validate_numeric_inputs(10_000, 101, 0) is not None
    assert engine._validate_numeric_inputs(10_000, 0.1, 0.05) is None


def test_engine_walk_forward_validation_order():
    from unified_finance_mcp.tools import _backtest_engine as engine

    out = engine.walk_forward_backtest("AAPL", "nope")
    assert "error" in out and "nope" in out["error"]
    out = engine.walk_forward_backtest("AAPL", "rsi", n_splits=11)
    assert "error" in out and "2 and 10" in out["error"]
    out = engine.walk_forward_backtest("AAPL", "rsi", n_splits=3, train_ratio=0.1)
    assert "error" in out and "train_ratio" in out["error"]
    out = engine.walk_forward_backtest("AAPL", "triple_ema")
    assert "error" in out and "SMA200" in out["error"]


def test_indicators_calc_warmup_none_semantics():
    from unified_finance_mcp.tools import _backtest_indicators as ind

    closes = [100.0 + i for i in range(50)]
    ema = ind.calc_ema(closes, 10)
    assert ema[:9] == [None] * 9
    assert ema[9] == pytest.approx(sum(closes[:10]) / 10)
    rsi = ind.calc_rsi(closes, 14)
    assert rsi[:14] == [None] * 14
    assert rsi[14] == 100.0  # monotonically rising → all gains
    sma = ind.calc_sma(closes, 5)
    assert sma[:4] == [None] * 4
    assert sma[4] == pytest.approx(sum(closes[:5]) / 5)


def test_indicators_calc_bollinger_macd_atr_supertrend_donchian():
    from unified_finance_mcp.tools import _backtest_indicators as ind

    closes = [100.0 + i * 0.5 for i in range(60)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    bb = ind.calc_bollinger(closes, 20)
    assert set(bb) == {"upper", "middle", "lower"}
    assert bb["middle"][19] == pytest.approx(sum(closes[:20]) / 20)
    assert bb["upper"][19] > bb["middle"][19] > bb["lower"][19]
    macd = ind.calc_macd(closes)
    assert set(macd) == {"macd", "signal", "histogram"}
    assert macd["macd"][25] is not None and macd["signal"][25] is None
    atr = ind.calc_atr(highs, lows, closes, 14)
    assert atr[:14] == [None] * 14
    assert atr[14] == pytest.approx(2.0)  # constant range 2
    st = ind.calc_supertrend(highs, lows, closes)
    assert set(st) == {"direction", "upper", "lower"}
    assert st["direction"][15] in (1, -1)
    dc = ind.calc_donchian(highs, lows, 20)
    assert set(dc) == {"upper", "lower", "middle"}
    assert dc["upper"][19] == max(highs[:20])
    assert dc["lower"][19] == min(lows[:20])


# ── R1 (F1): _candles_from_frame volume NaN/None coercion ──────────────────

class _FakeYfFrame:
    """Duck-typed yfinance frame: production only calls
    reset_index().to_dict("records")."""

    def __init__(self, rows):
        self._rows = rows

    def reset_index(self):
        return self

    def to_dict(self, orient=None):
        return list(self._rows)


def test_candles_from_frame_volume_nan_none_coerced_to_zero():
    from unified_finance_mcp.tools import _backtest_engine as engine

    rows = [
        {"Date": dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc), "Open": 100.0, "High": 101.0,
         "Low": 99.0, "Close": 100.5, "Volume": 123_456},
        {"Date": dt.datetime(2024, 1, 2, tzinfo=dt.timezone.utc), "Open": 101.0, "High": 102.0,
         "Low": 100.0, "Close": 101.5, "Volume": None},
        {"Date": dt.datetime(2024, 1, 3, tzinfo=dt.timezone.utc), "Open": 102.0, "High": 103.0,
         "Low": 101.0, "Close": 102.5, "Volume": float("nan")},
        {"Date": dt.datetime(2024, 1, 4, tzinfo=dt.timezone.utc), "Open": float("nan"), "High": 103.0,
         "Low": 101.0, "Close": 103.5, "Volume": 500},
        {"Date": dt.datetime(2024, 1, 5, tzinfo=dt.timezone.utc), "Open": 103.0, "High": 104.0,
         "Low": None, "Close": 104.5, "Volume": 600},
    ]
    out = engine._candles_from_frame(_FakeYfFrame(rows), "1d")
    assert [c["date"] for c in out] == ["2024-01-01", "2024-01-02", "2024-01-03"]
    assert out[0]["volume"] == 123_456
    assert out[1]["volume"] == 0  # sparse volume → 0, row kept (reference `v or 0`)
    assert out[2]["volume"] == 0  # NaN volume → 0, row kept
    assert out[0]["close"] == 100.5
    assert out[1]["close"] == 101.5
    assert out[2]["close"] == 102.5


def test_candles_from_frame_real_pandas_volume_none_coerced():
    """Reviewer repro: pandas coerces None volume to NaN, so the plain
    `is not None` guard never fired and int(NaN) raised ValueError."""
    pd = pytest.importorskip("pandas")

    from unified_finance_mcp.tools import _backtest_engine as engine

    frame = pd.DataFrame(
        {"Open": [100.0, 101.0], "High": [101.0, 102.0],
         "Low": [99.0, 100.0], "Close": [100.5, 101.5],
         "Volume": [123_456, None]},
        index=pd.DatetimeIndex(["2024-01-01", "2024-01-02"], name="Date"),
    )
    out = engine._candles_from_frame(frame, "1d")
    assert [c["date"] for c in out] == ["2024-01-01", "2024-01-02"]
    assert out[0]["volume"] == 123_456
    assert out[1]["volume"] == 0


# ── hermeticity guard (T10-C1, in-process getaddrinfo guard) ───────────────

def _getaddrinfo_fail(*args, **kwargs):
    raise AssertionError(f"network resolution attempted: {args[:2]}")


def test_backtest_module_import_does_not_touch_network(monkeypatch):
    """Import-time surface: backtest + engine must not resolve DNS."""
    import socket

    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo_fail)
    from unified_finance_mcp.tools import _backtest_engine, backtest

    assert len(_backtest_engine._STRATEGY_MAP) == 9
    assert set(backtest.BACKTEST_HELP["strategies"]) == set(ALL_NINE)


async def test_unknown_action_no_network(monkeypatch):
    import socket

    monkeypatch.setattr(socket, "getaddrinfo", _getaddrinfo_fail)
    from unified_finance_mcp.tools import backtest

    out = await backtest.quant_backtest(action="bogus")
    assert "error" in out


# ── registration surface ───────────────────────────────────────────────────

def test_register_mounts_quant_backtest():
    from mcp.server.fastmcp import FastMCP

    from unified_finance_mcp.config import get_settings
    from unified_finance_mcp.tools import backtest as backtest_mod

    mcp = FastMCP("t15-test")
    backtest_mod.register(mcp, None, get_settings())
    names = {t.name for t in mcp._tool_manager.list_tools()}
    assert "quant_backtest" in names
