"""TradingView provider (tradingview-ta / -screener). Keyless; methods land in Task 5."""
from __future__ import annotations

from .base import Provider


class TradingViewProvider(Provider):
    name = "tradingview"
    markets = None  # global fallback
