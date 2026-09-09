"""Alpha Vantage provider. Keyed, US equities + FX + crypto; methods land in Task 7."""
from __future__ import annotations

from ..config import DEFAULT_AV_BASE_URL
from .base import Provider


class AlphaVantageProvider(Provider):
    name = "alphavantage"
    markets = frozenset({"US", "FX", "CRYPTO"})

    def available(self) -> bool:
        # A base-url override means an upstream key rotator injects the key for us.
        return (bool(self.settings.alphavantage_api_key)
                or self.settings.alphavantage_base_url != DEFAULT_AV_BASE_URL)
