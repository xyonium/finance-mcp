"""marketaux news provider. Keyed but global coverage; methods land in Task 8."""
from __future__ import annotations

from ..config import DEFAULT_MARKETAUX_BASE_URL
from .base import Provider


class MarketauxProvider(Provider):
    name = "marketaux"
    markets = None  # global coverage

    def available(self) -> bool:
        # A base-url override means an upstream key rotator injects the token for us.
        return (bool(self.settings.marketaux_api_token)
                or self.settings.marketaux_base_url != DEFAULT_MARKETAUX_BASE_URL)
