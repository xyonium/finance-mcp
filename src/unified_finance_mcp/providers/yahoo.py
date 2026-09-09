"""Yahoo Finance provider (yfinance). Keyless global fallback; methods land in Task 4."""
from __future__ import annotations

from .base import Provider


class YahooProvider(Provider):
    name = "yahoo"
    markets = None  # global fallback
