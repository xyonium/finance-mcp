"""TradingView symbol lists (vendored from tradingview-mcp/coinlist).

Plain text, one ``EXCHANGE:SYMBOL`` per line (e.g. ``EGX:COMI``). Used by the
tv_scan / tv_analyze / egx_market containers to build the symbol batches fed
to tradingview_ta's get_multiple_analysis. ``all.txt`` is an aggregate of
every exchange and is deliberately excluded from the public symbol loaders
(suggesting it as an exchange would be an invalid value).
"""
from __future__ import annotations

import os
from pathlib import Path

COINLIST_DIR = Path(__file__).with_name("")

_SUGGESTION_EXCLUDE = {"all"}


def _symbol_file(exchange: str) -> Path:
    return COINLIST_DIR / f"{exchange.lower()}.txt"


def load_symbols(exchange: str) -> list[str]:
    """Load the vendored symbol list for *exchange* (case-insensitive).

    Lines ship as "EXCHANGE:TICKER" (e.g. "KUCOIN:HYPEUSDT") and are returned
    verbatim. Returns an empty list for unknown exchanges or unreadable files.
    """
    path = _symbol_file(exchange)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return [line.strip() for line in content.splitlines() if line.strip()]


def exchanges_listing_symbol(symbol: str, max_results: int = 6) -> list[str]:
    """Exchanges (per the vendored coinlists) where *symbol* is listed.

    Zero network cost — reads only the bundled files. Accepts bare tickers
    ("HYPEUSDT") or prefixed ones ("BINANCE:HYPEUSDT"). Returns exchange names
    sorted alphabetically, capped at *max_results*; empty list when the ticker
    appears in no vendored list (likely a typo or an unsupported venue).
    """
    bare = symbol.strip().upper().split(":")[-1]
    if not bare:
        return []
    matches: list[str] = []
    try:
        names = sorted(os.listdir(COINLIST_DIR))
    except OSError:
        return []
    for name in names:
        if not name.endswith(".txt"):
            continue
        exch = name[:-4]
        if exch in _SUGGESTION_EXCLUDE:
            continue
        try:
            lines = (_symbol_file(exch).read_text(encoding="utf-8").splitlines())
        except OSError:
            continue
        if any(bare == line.strip().upper().split(":")[-1] for line in lines if line.strip()):
            matches.append(exch.upper())
    return matches[:max_results]
