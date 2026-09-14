"""Build the provider dict. Providers are cheap to construct; network use is lazy."""
from __future__ import annotations

from ..config import Settings
from .base import Provider


def build_providers(settings: Settings) -> dict[str, Provider]:
    from . import (
        alphavantage,
        cex,
        eastmoney,
        fmp,
        futu_bridge,
        kimi,
        macro,
        marketaux,
        tradingview,
        yahoo,
    )

    instances = [
        yahoo.YahooProvider(settings),
        tradingview.TradingViewProvider(settings),
        fmp.FmpProvider(settings),
        alphavantage.AlphaVantageProvider(settings),
        marketaux.MarketauxProvider(settings),
        futu_bridge.FutuProvider(settings),
        eastmoney.EastmoneyProvider(settings),
        kimi.KimiProvider(settings),
        macro.MacroProvider(settings),
    ]
    if settings.cex_enabled:
        instances.append(cex.CexProvider(settings))
    return {p.name: p for p in instances}
