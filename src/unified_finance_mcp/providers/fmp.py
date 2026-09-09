"""Financial Modeling Prep provider. Keyed, US equities; methods land in Task 6."""
from __future__ import annotations

from ..config import DEFAULT_FMP_BASE_URL
from .base import Provider


class FmpProvider(Provider):
    name = "fmp"
    markets = frozenset({"US"})

    def available(self) -> bool:
        # A base-url override means an upstream key rotator injects the key for us.
        return bool(self.settings.fmp_api_key) or self.settings.fmp_base_url != DEFAULT_FMP_BASE_URL
