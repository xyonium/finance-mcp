"""quant_backtest: strategy backtest container over tools/_backtest_engine.py.

Four actions:
  help         — parameter guide (BACKTEST_HELP)
  run          — one strategy on one symbol (reference run_backtest)
  compare      — all 9 (or a requested subset) strategies ranked by return
  walk_forward — train/test robustness check (rejects rsi_pullback/triple_ema)

The engine (reference backtest_service.py port) is sync and fetches via
yfinance, so every action runs in anyio.to_thread.run_sync. The container
layer never raises: bad input and engine {"error": ...} dicts become
tool_error; ProviderError kinds (rate_limited / not_found / ...) are
preserved as "kind: msg" (ruling 9, T14 parity). metrics carries the
reference's full _calc_metrics keys plus the four brief short-name aliases
(total_return/sharpe/max_drawdown/trades); profit_factor == inf (zero losing
trades) sanitizes to None, consistent with the T12 sanitize semantics.
"""
from __future__ import annotations

from typing import Any

import anyio

from ..errors import ProviderError, tool_error
from . import _backtest_engine as engine
from ._sanitize import sanitize

STRATEGIES = tuple(engine._STRATEGY_MAP)

_STRATEGY_DEFAULTS = {
    "rsi": {"oversold": 40, "overbought": 60, "period": 14},
    "bollinger": {"period": 20, "std_mult": 2.0},
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "ema_cross": {"fast_period": 20, "slow_period": 50},
    "supertrend": {"atr_period": 10, "multiplier": 3.0},
    "donchian": {"period": 20},
    "rsi_pullback": {"rsi_period": 14, "oversold": 40, "overbought": 70,
                     "fast_ma": 50, "slow_ma": 200},
    "keltner_breakout": {"ema_period": 20, "atr_period": 14, "multiplier": 2.0},
    "triple_ema": {"fast_period": 20, "slow_period": 50, "trend_period": 200},
}

_ALL_STRATEGY_PARAM_NAMES = {k for d in _STRATEGY_DEFAULTS.values() for k in d}

_ACTIONS = ("help", "run", "compare", "walk_forward")

_WALK_FORWARD_SEVEN = tuple(s for s in STRATEGIES if s not in engine._SMA200_STRATEGIES)

BACKTEST_HELP = {
    "actions": {
        "help": {"description": "Return this parameter guide."},
        "run": {
            "description": "Backtest one strategy on one symbol.",
            "params": {
                "symbol": "Yahoo Finance symbol (AAPL, BTC-USD, COMI.CA)",
                "strategy": f"One of: {', '.join(STRATEGIES)}",
                "period": f"One of: {', '.join(sorted(engine._VALID_PERIODS))} (default '1y')",
                "interval": "1d | 1h (default '1d')",
                "capital": "Initial capital (default 10000.0)",
                "commission_pct": "Per-trade commission % (default 0.0)",
                "slippage_pct": "Per-trade slippage % (default 0.0)",
                "params": ("Optional dict of strategy parameters and flags: "
                           "include_trade_log / include_equity_curve booleans plus "
                           "per-strategy tuning (see strategies section)"),
            },
        },
        "compare": {
            "description": "Run strategies on one symbol and return a ranked leaderboard.",
            "params": {
                "symbol": "Yahoo Finance symbol",
                "strategies": (f"Optional subset of {', '.join(STRATEGIES)}; "
                               "default: all 9"),
                "period": f"One of: {', '.join(sorted(engine._VALID_PERIODS))} (default '1y')",
                "interval": "1d | 1h (default '1d')",
                "capital": "Initial capital (default 10000.0)",
                "commission_pct": "Per-trade commission % (default 0.0)",
                "slippage_pct": "Per-trade slippage % (default 0.0)",
            },
        },
        "walk_forward": {
            "description": ("Walk-forward backtest to detect overfitting via "
                            "train/test folds; returns a robustness verdict."),
            "params": {
                "symbol": "Yahoo Finance symbol",
                "strategy": f"One of: {', '.join(_WALK_FORWARD_SEVEN)} "
                            "(rsi_pullback/triple_ema need SMA200 warmup and are "
                            "not supported)",
                "period": f"One of: {', '.join(sorted(engine._VALID_PERIODS))} (default '1y')",
                "interval": "1d | 1h (default '1d')",
                "folds": "Number of train/test splits, clamped 2..10 (default 4)",
                "capital": "Initial capital (default 10000.0)",
                "commission_pct": "Per-trade commission % (default 0.0)",
                "slippage_pct": "Per-trade slippage % (default 0.0)",
            },
        },
    },
    "strategies": {
        name: {
            "label": engine._STRATEGY_LABELS[name],
            "description": engine._STRATEGY_LABELS[name],
            "params": _STRATEGY_DEFAULTS[name],
        }
        for name in STRATEGIES
    },
    "examples": [
        'quant_backtest(action="run", symbol="AAPL", strategy="rsi")',
        ("quant_backtest(action=\"run\", symbol=\"AAPL\", strategy=\"bollinger\", "
         "params={\"std_mult\": 2.5})"),
        'quant_backtest(action="compare", symbol="AAPL", period="2y")',
        ("quant_backtest(action=\"compare\", symbol=\"AAPL\", "
         "strategies=[\"rsi\", \"macd\", \"ema_cross\"])"),
        ("quant_backtest(action=\"walk_forward\", symbol=\"AAPL\", strategy=\"macd\", "
         "folds=5)"),
    ],
}


# ─── helpers ──────────────────────────────────────────────────────────────────

def _known_action(action: Any) -> bool:
    """Hash-safe action check: non-str actions are never valid and must not
    make the `action in ...` lookup raise TypeError."""
    return isinstance(action, str) and action in _ACTIONS


def _clamp_folds(folds: Any, default: int = 4) -> int:
    """walk_forward folds → n_splits, clamped 2..10 (ruling 4). Garbage
    falls back to the default."""
    try:
        return max(2, min(int(folds), 10))
    except (TypeError, ValueError):
        return default


def _known_strategy(strategy: Any) -> bool:
    return isinstance(strategy, str) and strategy in STRATEGIES


def _symbol_err(symbol: Any) -> bool:
    return not isinstance(symbol, str) or not symbol.strip()


def _split_params(params: dict) -> tuple[dict, bool, bool]:
    """Partition user params into strategy kwargs and engine flags."""
    params = params or {}
    strat = {k: v for k, v in params.items() if k in _ALL_STRATEGY_PARAM_NAMES}
    flags = {k: bool(v) for k, v in params.items()
             if k in ("include_trade_log", "include_equity_curve") and bool(v)}
    return strat, flags.get("include_trade_log", False), \
        flags.get("include_equity_curve", False)


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def _run_in_thread(action: str, impl):
    """Run a sync engine call in a worker thread; containers never raise."""
    try:
        return await anyio.to_thread.run_sync(impl)
    except ProviderError as e:
        # Preserve the taxonomy kind (rate_limited / not_found / ...) at the
        # container boundary (ruling 9 — T14 parity).
        return tool_error(f"{e.kind}: {str(e)[:200]}", source="backtest")
    except Exception as e:  # noqa: BLE001 - containers never raise
        return tool_error(f"{action}: {type(e).__name__}: {str(e)[:200]}",
                          source="backtest")


def _error_out(err: dict) -> dict:
    """Engine {"error": ...} dict → tool_error, carrying the specific engine
    message in the hint (period/interval/strategy vocab) plus fallback advice."""
    msg = str(err.get("error", "backtest failed"))
    return tool_error(msg,
                      hint=f"{msg} — 数据不足或代码错，换 period/interval/symbol 重试",
                      source="backtest")


def _with_aliases(metrics: dict) -> dict:
    """Reference _calc_metrics keys + brief short-name aliases (ruling 5)."""
    out = dict(metrics)
    out["total_return"] = metrics["total_return_pct"]
    out["sharpe"] = metrics["sharpe_ratio"]
    out["max_drawdown"] = metrics["max_drawdown_pct"]
    out["trades"] = metrics["total_trades"]
    return out


def _restructure_run(result: dict) -> dict:
    """Move the flat metrics fields into a metrics sub-dict (brief contract:
    {"total_return","sharpe","max_drawdown","trades"} <= out["metrics"])."""
    metrics = {k: result.pop(k) for k in list(result)
               if k in engine._calc_metrics([], result.get("initial_capital", 0))}
    result["metrics"] = _with_aliases(metrics)
    return result


def _dedupe(strategies: Any) -> list:
    if not isinstance(strategies, list):
        return []
    out, seen = [], set()
    for s in strategies:
        if isinstance(s, str) and s in STRATEGIES and s not in seen:
            seen.add(s)
            out.append(s)
    return out


# ─── container ────────────────────────────────────────────────────────────────

async def quant_backtest(action: str = "help", symbol: str | None = None,
                         strategy: str | None = None,
                         strategies: list | None = None,
                         period: str = "1y", interval: str = "1d",
                         capital: float = 10000.0, commission_pct: float = 0.0,
                         slippage_pct: float = 0.0, folds: int = 4,
                         params: dict | None = None) -> dict:
    """Run strategy backtests; call with action='help' for the full guide."""
    if not _known_action(action):
        return tool_error(f"unknown action {action!r}",
                          hint=f"可用 action: {sorted(_ACTIONS)}")
    if action == "help":
        return BACKTEST_HELP

    capital = _to_float(capital)
    commission_pct = _to_float(commission_pct)
    slippage_pct = _to_float(slippage_pct)
    if None in (capital, commission_pct, slippage_pct):
        return tool_error("capital/commission_pct/slippage_pct must be numbers",
                          hint="capital: 初始资金 float；commission_pct/slippage_pct: "
                               "每边百分比 0..100")

    if action == "run":
        if _symbol_err(symbol):
            return tool_error("symbol is required for quant_backtest run",
                              hint="pass a Yahoo Finance symbol like AAPL or COMI.CA")
        if not _known_strategy(strategy):
            return tool_error(f"unknown strategy {strategy!r}",
                              hint=f"可用 strategy: {list(STRATEGIES)}")
        if params is not None and not isinstance(params, dict):
            return tool_error("params must be a dict of strategy parameters",
                              hint=f"可用 params: {list(_STRATEGY_DEFAULTS[strategy])} "
                                   "+ include_trade_log / include_equity_curve")
        strat_params, want_log, want_curve = _split_params(params)
        merged = dict(_STRATEGY_DEFAULTS[strategy], **strat_params)
        result = await _run_in_thread(
            f"quant_backtest:run:{strategy}",
            lambda: engine.run_backtest(
                symbol, strategy, period=period, initial_capital=capital,
                commission_pct=commission_pct, slippage_pct=slippage_pct,
                interval=interval, include_trade_log=want_log,
                include_equity_curve=want_curve, strategy_params=merged))
        if "error" in result:
            return _error_out(result)
        return sanitize(_restructure_run(result))

    if action == "compare":
        if _symbol_err(symbol):
            return tool_error("symbol is required for quant_backtest compare",
                              hint="pass a Yahoo Finance symbol like AAPL or COMI.CA")
        subset = _dedupe(strategies) if strategies is not None else None
        result = await _run_in_thread(
            "quant_backtest:compare",
            lambda: engine.compare_strategies(
                symbol, period=period, initial_capital=capital,
                commission_pct=commission_pct, slippage_pct=slippage_pct,
                interval=interval, strategies=subset))
        if "error" in result:
            return _error_out(result)
        return sanitize(result)

    # walk_forward
    if _symbol_err(symbol):
        return tool_error("symbol is required for quant_backtest walk_forward",
                          hint="pass a Yahoo Finance symbol like AAPL or COMI.CA")
    if not _known_strategy(strategy):
        return tool_error(f"unknown strategy {strategy!r}",
                          hint=f"可用 strategy: {list(STRATEGIES)}")
    if strategy in engine._SMA200_STRATEGIES:
        return tool_error(
            f"walk_forward does not support '{strategy}': SMA200 warmup "
            f"(~{engine._SMA200_MIN_BARS} bars) exceeds typical fold sizes",
            hint=f"walk_forward 可用 strategy: {list(_WALK_FORWARD_SEVEN)}；"
                 "或改用 action='run' + period='2y'")
    result = await _run_in_thread(
        f"quant_backtest:walk_forward:{strategy}",
        lambda: engine.walk_forward_backtest(
            symbol, strategy, period=period, initial_capital=capital,
            commission_pct=commission_pct, slippage_pct=slippage_pct,
            n_splits=_clamp_folds(folds), interval=interval))
    if "error" in result:
        return _error_out(result)
    return sanitize(result)


def register(mcp, providers, settings) -> None:
    @mcp.tool(name="quant_backtest")
    async def quant_backtest_tool(action: str = "help",
                                  symbol: str | None = None,
                                  strategy: str | None = None,
                                  strategies: list | None = None,
                                  period: str = "1y", interval: str = "1d",
                                  capital: float = 10000.0,
                                  commission_pct: float = 0.0,
                                  slippage_pct: float = 0.0, folds: int = 4,
                                  params: dict | None = None) -> dict:
        """Backtest trading strategies (run/compare/walk_forward); call with action='help' for the full guide."""
        return await quant_backtest(action, symbol, strategy, strategies,
                                    period, interval, capital, commission_pct,
                                    slippage_pct, folds, params)
