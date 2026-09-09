"""Futu OpenD bridge provider. Real OpenD reachability + tool mount land in Task 9."""
from __future__ import annotations

from .base import Provider


class FutuProvider(Provider):
    name = "futu"
    markets = frozenset({"US", "HK", "CN", "SG", "MY", "JP"})

    def available(self) -> bool:
        # Task 9 wires the real OpenD reachability check.
        return False


def mount_futu_tools(mcp) -> list[str]:
    """Mount the futu_* tool surface onto `mcp`; returns mounted tool names (Task 9)."""
    return []
