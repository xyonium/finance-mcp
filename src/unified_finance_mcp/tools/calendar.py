"""get_events_calendar: earnings/dividends/ipo calendar, fmp first.

Defaults to today ±7 days when start/end are omitted (T13 brief). fmp covers
all three kinds; alphavantage covers earnings only (CSV EARNINGS_CALENDAR,
parsed inside AlphaVantageProvider.events_calendar) and raises ProviderError
for dividends/ipo so route_and_call falls back naturally.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..errors import tool_error
from ._routing import route_and_call

CHAIN = ["fmp", "alphavantage"]

TYPES = ("earnings", "dividends", "ipo")


def _default_window() -> tuple[str, str]:
    today = date.today()  # noqa: DTZ011 - local calendar dates per T13 brief
    return ((today - timedelta(days=7)).isoformat(),
            (today + timedelta(days=7)).isoformat())


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_events_calendar(type: str = "earnings", start: str | None = None,
                                  end: str | None = None, source: str = "auto") -> dict:
        """Upcoming corporate events: earnings | dividends | ipo.

        `start`/`end` are inclusive YYYY-MM-DD strings; omitted means today
        ±7 days. `source` may be auto | fmp | alphavantage (av: earnings only).
        Returns {"data": [event, ...]} on success, or the routing error dict at
        the top level on failure — callers check `"error" in out`.
        """
        if type not in TYPES:
            return tool_error(f"unknown event type {type!r}",
                              hint="type 可用: earnings|dividends|ipo")
        if start is None and end is None:
            start, end = _default_window()
        for name, value in (("start", start), ("end", end)):
            if value is not None:
                try:
                    date.fromisoformat(value)
                except ValueError:
                    return tool_error(f"invalid {name} date {value!r}",
                                      hint="日期用 YYYY-MM-DD")
        rows = await route_and_call(
            market="US", chain=CHAIN, providers=providers,
            call=lambda p: p.events_calendar(type, start, end),
            explicit_source=source)
        return rows if "error" in rows else {"data": rows}
