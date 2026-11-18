"""Build the provider dict. Providers are cheap to construct; network use is lazy."""
from __future__ import annotations

from ..config import Settings
from .base import Provider


def build_providers(settings: Settings) -> dict[str, Provider]:
    from . import (
        alphavantage,
        cex,
        eastmoney,
        edgar,
        fmp,
        fred,
        futu_bridge,
        kimi,
        macro,
        marketaux,
        tradingview,
        treasury,
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
        fred.FredProvider(settings),
        edgar.EdgarProvider(settings),
        treasury.TreasuryProvider(settings),
    ]
    if settings.cex_enabled:
        instances.append(cex.CexProvider(settings))
    return {p.name: p for p in instances}
