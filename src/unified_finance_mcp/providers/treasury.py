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

Timeouts: the yield-curve CSV on home.treasury.gov has a ~19-20 s TTFB from
some egresses, so that one request uses a 45 s per-request timeout with a
single retry. Fiscal Data (and MTS) keep the global timeout/retry defaults.

Verified 2026-11-18: both CSV and JSON endpoints 200; `/v1/accounting/od/
monthly_treasury_statement` is **404** — the correct MTS tables live under
`/v1/accounting/mts/mts_table_N`. `mts_table_5` (outlays of the U.S.
government, hierarchical agency/function lines) is exposed as
`TREASURY_MTS_OUTLAYS`; tables 1/9 are not exposed.

Anti-hallucination discipline: tenor values and fiscal amounts are exactly
what the upstream returns (missing CSV cells -> None, never interpolated;
fiscal rows keep their upstream field names and string amounts unchanged).
"""
from __future__ import annotations

import calendar
import csv
import io
import re
from datetime import date, datetime, timezone

from ..config import Settings
from ..errors import NotFound, UpstreamDrift, UpstreamError
from ..http import PoliteClient
from .base import Provider

# home.treasury.gov answers the yield-curve CSV with ~19-20 s TTFB from some
# egresses (measured 3/3 from the London host), which raced the 20 s default
# and timed out in the measured deployment. Scope the longer timeout to this
# one request, with a single retry: two attempts cap the failure path at
# ~91 s instead of 4x45 s, and Fiscal Data keeps the global defaults.
_YIELD_CSV_TIMEOUT = 45.0
_YIELD_CSV_RETRIES = 1

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
            self._client = PoliteClient(
                timeout=self.settings.request_timeout,
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
            text = await self._get_client().get_text(
                url, params={"type": "daily_treasury_yield_curve",
                             "_format": "csv"},
                timeout=_YIELD_CSV_TIMEOUT, max_retries=_YIELD_CSV_RETRIES)
        except UpstreamError as e:
            raise UpstreamError(f"treasury/yield_curve: {e}") from e
        if not text.strip():
            raise NotFound(f"treasury: no yield-curve rows for {ym}")
        reader = csv.DictReader(io.StringIO(text))
        if not reader.fieldnames or "Date" not in reader.fieldnames:
            raise UpstreamDrift(f"treasury: unexpected CSV header for {ym}: "
                                f"{reader.fieldnames}")
        labels = {col: _tenor(col) for col in reader.fieldnames if col != "Date"}
        rows = []
        for raw in reader:
            m_date = _US_DATE_RE.match((raw.get("Date") or "").strip())
            if not m_date:
                continue  # a malformed row is skipped, never guessed
            month, day, year = (int(g) for g in m_date.groups())
            try:
                # real calendar check: 02/31 is not a date, so the row is
                # skipped like any other malformed row (never invented).
                stamp = date(year, month, day).isoformat()
            except ValueError:
                continue
            row = {"date": stamp}
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
        if date_from is not None:
            raw_from = date_from.strip()
            try:
                if not _DATE_RE.match(raw_from):
                    raise ValueError
                date.fromisoformat(raw_from)
            except ValueError:
                raise NotFound(f"treasury: date_from must be a real "
                               f"YYYY-MM-DD date, got {date_from!r}") from None
        n = max(1, min(int(page_size), 1000))
        params: dict = {"page[size]": str(n), "sort": "-record_date"}
        if date_from:
            params["filter"] = f"record_date:gte:{date_from.strip()}"
        url = f"{self.settings.treasury_fiscal_base_url.rstrip('/')}{path}"
        try:
            data = await self._get_client().get_json(url, params=params)
        except UpstreamError as e:
            raise UpstreamError(f"treasury/{kind}: {e}") from e
        except ValueError as e:
            # 200 with a non-JSON body must not escape as a raw ValueError;
            # the provider contract is the errors.py taxonomy.
            raise UpstreamError(f"treasury/{kind}: non-JSON body") from e
        if not isinstance(data, dict):
            raise UpstreamDrift(f"treasury/{kind}: unexpected body")
        rows = data.get("data")
        if not isinstance(rows, list) or not rows:
            raise NotFound(f"treasury/{kind}: no rows"
                           + (f" since {date_from}" if date_from else ""))
        meta = data.get("meta") if isinstance(data.get("meta"), dict) else {}
        return {"kind": kind, "total": meta.get("total-count"),
                "count": len(rows), "data": rows}

    # ── MTS: outlays by agency/function (table 5) ───────────────────────────

    _MTS_OUTLAYS = "/v1/accounting/mts/mts_table_5"

    async def _mts_get(self, params: dict) -> dict:
        url = (f"{self.settings.treasury_fiscal_base_url.rstrip('/')}"
               f"{self._MTS_OUTLAYS}")
        try:
            data = await self._get_client().get_json(url, params=params)
        except UpstreamError as e:
            raise UpstreamError(f"treasury/mts: {e}") from e
        except ValueError as e:
            raise UpstreamError("treasury/mts: non-JSON body") from e
        if not isinstance(data, dict):
            raise UpstreamDrift("treasury/mts: unexpected body")
        return data

    async def mts_outlays(self, period: str | None = None,
                          limit: int = 50) -> dict:
        """Monthly Treasury Statement table 5: outlays by agency/function.

        Report lines are **hierarchical**: the payload contains total and
        subtotal lines (e.g. "Total Outlays", "Total--Department of ...")
        next to agency lines, so summing them double-counts. Amounts are kept
        as the upstream USD strings (nulls stay None); `truncated` says
        whether `total` exceeds the returned `count`.

        `period` is YYYY-MM (month-end record date); omitted means the newest
        published month. One page of up to 1000 rows is fetched, sorted by
        current-month gross outlays descending (nulls last), then capped.
        """
        n = max(1, min(int(limit), 200))
        if period is not None:
            m = _PERIOD_RE.match(period.strip())
            if not m or not 1 <= int(m.group(2)) <= 12:
                raise NotFound(f"treasury/mts: period must be YYYY-MM, "
                               f"got {period!r}")
            year, month = int(m.group(1)), int(m.group(2))
            record_date = (f"{year:04d}-{month:02d}-"
                           f"{calendar.monthrange(year, month)[1]:02d}")
        else:
            latest = await self._mts_get({"sort": "-record_date",
                                          "page[size]": "1"})
            latest_rows = latest.get("data")
            if not isinstance(latest_rows, list) or not latest_rows:
                raise NotFound("treasury/mts: no months published")
            first = latest_rows[0]
            if not isinstance(first, dict):
                raise UpstreamDrift("treasury/mts: malformed latest-month row")
            record_date = str(first.get("record_date") or "")
            if not _DATE_RE.match(record_date):
                raise UpstreamDrift("treasury/mts: unexpected latest "
                                    f"record_date {record_date!r}")
        data = await self._mts_get({"filter": f"record_date:eq:{record_date}",
                                    "page[size]": "1000"})
        rows = data.get("data")
        if not isinstance(rows, list) or not rows:
            raise NotFound(f"treasury/mts: no outlay rows for {record_date}")
        meta = data.get("meta")
        total = meta.get("total-count") if isinstance(meta, dict) else None
        if not isinstance(total, int):
            raise UpstreamDrift("treasury/mts: meta.total-count is not an integer")
        out = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(
                    row.get("classification_desc"), str):
                raise UpstreamDrift("treasury/mts: malformed report row")
            out.append({
                "record_date": row.get("record_date"),
                "classification_id": row.get("classification_id"),
                "parent_id": row.get("parent_id"),
                "line_code_nbr": row.get("line_code_nbr"),
                "classification_desc": row["classification_desc"],
                "current_month_gross_outly_amt":
                    row.get("current_month_gross_outly_amt"),
                "current_fytd_gross_outly_amt":
                    row.get("current_fytd_gross_outly_amt"),
            })

        def _amount(r: dict) -> float:
            raw = r["current_month_gross_outly_amt"]
            try:
                return float(str(raw).replace(",", ""))
            except (TypeError, ValueError):
                return float("-inf")  # null/blank lines sort last

        out.sort(key=_amount, reverse=True)
        kept = out[:n]
        return {"period": record_date[:7], "record_date": record_date,
                "limit": n, "total": total, "count": len(kept),
                "truncated": total > len(kept), "data": kept}
