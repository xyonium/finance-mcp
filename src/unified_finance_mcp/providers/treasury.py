"""US Treasury provider: par yield curve + Fiscal Data (both keyless).

Two hosts, two shapes — one provider, because the consumer-facing question
("rates and federal fiscal position") is one domain:

- **Par yield curve** — `home.treasury.gov` CSV export,
  `/daily-treasury-rates.csv/all/{YYYYMM}?type=daily_treasury_yield_curve&_format=csv`.
  This is the full 1 Mo .. 30 Yr curve published by Treasury's Daily
  Treasury Yield Curve. The repo previously had **only** 10Y (via FRED), so
  2s10s / inversion questions were unanswerable. The handoff called this an
  "XML task"; the CSV export makes it a ~40-line CSV parse instead.
- **Fiscal Data** — the documented JSON API at
  `api.fiscaldata.treasury.gov/services/api/fiscal_service`: daily federal
  debt (`debt_to_penny`) and the average interest rate on the debt
  (`avg_interest_rates`). No key, no registration.

Nothing here is a yield curve substitute: `avg_interest_rates` is the
*stock* of outstanding debt's average coupon, NOT a term structure. The
tool names keep that distinction visible.

Verified 2026-11-18: both CSV and JSON endpoints 200; `/v1/accounting/od/
monthly_treasury_statement` is **404** (the correct MTS tables live under
`/v1/accounting/mts/mts_table_N`), so monthly statements are not offered.

Anti-hallucination discipline: tenor values and fiscal amounts are exactly
what the upstream returns (missing CSV cells -> None, never interpolated;
fiscal rows keep their upstream field names and string amounts unchanged).
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timezone

from ..config import Settings
from ..errors import NotFound, UpstreamError
from ..http import PoliteClient
from .base import Provider

_PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_US_DATE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_TENOR_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(mo|month|yr|year)s?$", re.IGNORECASE)

# kind -> Fiscal Data dataset path (both /v2/accounting/od/...)
FISCAL_KINDS: dict[str, str] = {
    "debt_to_penny": "/v2/accounting/od/debt_to_penny",
    "avg_interest_rates": "/v2/accounting/od/avg_interest_rates",
}


def _tenor(column: str) -> str:
    """'1 Mo' -> '1M', '1.5 Month' -> '1.5M', '10 Yr' -> '10Y'.

    A label that does not parse (Treasury adds columns over time) is kept
    verbatim rather than dropped.
    """
    label = column.strip()
    m = _TENOR_RE.match(label)
    if not m:
        return label
    unit = "M" if m.group(2).lower().startswith("mo") else "Y"
    return f"{m.group(1)}{unit}"


def _num(raw: str) -> float | None:
    text = (raw or "").strip()
    if text in ("", "-", "N/A", "null", "None"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


class TreasuryProvider(Provider):
    name = "treasury"
    markets = None  # federal fiscal/rates data: never gated on a market

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._client: PoliteClient | None = None

    def available(self) -> bool:
        return True  # keyless, no registration

    def _get_client(self) -> PoliteClient:
        if self._client is None:
            self._client = PoliteClient(timeout=self.settings.request_timeout,
                                        max_retries=self.settings.max_retries,
                                        min_host_delay=self.settings.min_host_delay)
        return self._client

    # ── par yield curve (CSV) ───────────────────────────────────────────────

    @staticmethod
    def default_period() -> str:
        """Current UTC month as YYYY-MM (Treasury publishes same-day rows)."""
        return datetime.now(timezone.utc).strftime("%Y-%m")

    async def yield_curve(self, period: str | None = None) -> dict:
        """Daily par yield curve for one month: [{date, 1M, 2Y, 10Y, 30Y, ...}].

        `period` is YYYY-MM; omitted means the current UTC month. An empty
        body (a future month, or a month Treasury never posted) is NotFound,
        not an empty list.
        """
        ym = (period if period is not None else self.default_period()).strip()
        m = _PERIOD_RE.match(ym)
        if not m or not (1 <= int(m.group(2)) <= 12):
            raise NotFound(f"treasury: period must be YYYY-MM, got {period!r}")
        url = f"{self.settings.treasury_yield_csv_url.rstrip('/')}/{ym.replace('-', '')}"
        try:
            text = await self._get_client().get_text(url, params={
                "type": "daily_treasury_yield_curve", "_format": "csv"})
        except UpstreamError as e:
            raise UpstreamError(f"treasury/yield_curve: {e}") from e
        if not text.strip():
            raise NotFound(f"treasury: no yield-curve rows for {ym}")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or "Date" not in reader.fieldnames:
            raise UpstreamError(f"treasury: unexpected CSV header for {ym}: "
                                f"{reader.fieldnames}")
        labels = {col: _tenor(col) for col in reader.fieldnames if col != "Date"}
        rows = []
        for raw in reader:
            m_date = _US_DATE_RE.match((raw.get("Date") or "").strip())
            if not m_date:
                continue  # a malformed row is skipped, never guessed
            month, day, year = (int(g) for g in m_date.groups())
            if not (1 <= month <= 12 and 1 <= day <= 31):
                continue
            date = f"{year:04d}-{month:02d}-{day:02d}"
            row = {"date": date}
            for col, tenor in labels.items():
                row[tenor] = _num(raw.get(col, ""))
            rows.append(row)
        if not rows:
            raise NotFound(f"treasury: no parsable yield-curve rows for {ym}")
        return {"period": ym, "data": rows}

    # ── Fiscal Data (JSON) ──────────────────────────────────────────────────

    async def fiscal(self, kind: str, date_from: str | None = None,
                     page_size: int = 100) -> dict:
        """One Fiscal Data dataset, newest first, fields passed through.

        `date_from` is YYYY-MM-DD and becomes `filter=record_date:gte:...`.
        `meta.total-count` is surfaced as `total` so a caller knows the
        window's real size without paging.
        """
        path = FISCAL_KINDS.get(kind)
        if path is None:
            raise NotFound(f"treasury: unknown kind {kind!r}; "
                           f"valid: {sorted(FISCAL_KINDS)}")
        if date_from is not None and not _DATE_RE.match(date_from.strip()):
            raise NotFound(f"treasury: date_from must be YYYY-MM-DD, "
                           f"got {date_from!r}")
        n = max(1, min(int(page_size), 1000))
        params: dict = {"page[size]": str(n), "sort": "-record_date"}
        if date_from:
            params["filter"] = f"record_date:gte:{date_from.strip()}"
        url = f"{self.settings.treasury_fiscal_base_url.rstrip('/')}{path}"
        try:
            data = await self._get_client().get_json(url, params=params)
        except UpstreamError as e:
            raise UpstreamError(f"treasury/{kind}: {e}") from e
        if not isinstance(data, dict):
            raise UpstreamError(f"treasury/{kind}: unexpected body")
        rows = data.get("data")
        if not isinstance(rows, list) or not rows:
            raise NotFound(f"treasury/{kind}: no rows"
                           + (f" since {date_from}" if date_from else ""))
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        return {"kind": kind, "total": meta.get("total-count"),
                "count": len(rows), "data": rows}
