"""Provider registry: availability (env) + market coverage gating."""
from __future__ import annotations

from ..config import Settings


class Provider:
    name: str = "base"
    markets: frozenset[str] | None = None  # None = global fallback

    def __init__(self, settings: Settings):
        self.settings = settings

    def available(self) -> bool:
        return True

    def covers(self, market: str) -> bool:
        return self.markets is None or market in self.markets
