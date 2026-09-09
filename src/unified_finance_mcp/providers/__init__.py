"""Build the provider dict. Providers are cheap to construct; network use is lazy."""
from __future__ import annotations

from ..config import Settings
from .base import Provider


def build_providers(settings: Settings) -> dict[str, Provider]:
    from . import alphavantage, fmp, futu_bridge, marketaux, tradingview, yahoo

    instances = [
        yahoo.YahooProvider(settings),
        tradingview.TradingViewProvider(settings),
        fmp.FmpProvider(settings),
        alphavantage.AlphaVantageProvider(settings),
        marketaux.MarketauxProvider(settings),
        futu_bridge.FutuProvider(settings),
    ]
    return {p.name: p for p in instances}
