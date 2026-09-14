"""get_fred_series / search_fred_series: generic FRED passthrough (task ④).

Boundary with tools/macro.py: get_economic_data owns the canonical-8
indicator vocabulary (GDP/CPI/...) with keyless world_bank/imf fallbacks;
these two tools expose the rest of FRED — 800k+ series by raw series_id
(find them with search_fred_series) — for anything the canonical 8 do not
cover. Requires FRED_API_KEY (free, https://fredaccount.stlouisfed.org/apikeys).
"""
from __future__ import annotations

from ._routing import route_and_call

CHAIN = ["fred"]


async def _search_call(p, query: str, limit: int) -> dict:
    """route_and_call's `call` must return a dict; the provider's search
    returns a bare list, so wrap it in the conventional {"data": rows}."""
    return {"data": await p.series_search(query, limit=limit)}


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_fred_series(series_id: str,
                              observation_start: str | None = None,
                              observation_end: str | None = None,
                              limit: int = 120,
                              sort_order: str = "desc") -> dict:
        """Any FRED series by raw series_id (e.g. "CPIAUCSL", "DGS10",
        "DEXJPUS"). For the 8 canonical indicators prefer get_economic_data
        (keyless fallbacks). Returns {"series_id", "units", "data": rows} —
        rows are exactly what FRED returns ("." missing -> None). Find series
        ids with search_fred_series. Requires FRED_API_KEY.
        """
        return await route_and_call(
            market="US", chain=CHAIN, providers=providers,
            call=lambda p: p.series_observations(
                series_id, observation_start=observation_start,
                observation_end=observation_end, limit=limit,
                sort_order=sort_order))

    @mcp.tool()
    async def search_fred_series(query: str, limit: int = 20) -> dict:
        """Full-text search over FRED series metadata ("japan exchange rate",
        "m2 money stock"). Returns {"data": [{id, title, frequency, units,
        popularity, ...}]} — feed an `id` to get_fred_series. Requires
        FRED_API_KEY.
        """
        return await route_and_call(
            market="US", chain=CHAIN, providers=providers,
            call=lambda p: _search_call(p, query, limit))
