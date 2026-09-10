"""Tool modules. Later tasks append their module name here; server.py imports and registers each."""
from __future__ import annotations

ALL_MODULES: list[str] = ["quote", "history", "fundamentals", "news",
                          "technicals", "screener", "ownership", "calendar",
                          "macro", "search", "containers", "backtest", "kimi",
                          "diagnostics"]
