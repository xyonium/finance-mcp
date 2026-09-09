"""Shared JSON-safety sanitizer for provider payloads.

The tradingview provider's rows can carry numpy scalar types (transitive via
tvdatafeed). numpy is NOT declared in pyproject.toml, so production code must
never import it: numpy scalars are duck-typed via .item() (also unboxes plain
0-d numpy arrays), and float NaN/Inf (which json.dumps serializes as invalid
NaN/Infinity tokens) becomes None. Recursive over dict/list/tuple; other
values pass through untouched.
"""
from __future__ import annotations

import math
from typing import Any


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return sanitize(value.item())
        except (ValueError, TypeError):
            return None
    return value
