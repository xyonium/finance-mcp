"""get_sec_filing: SEC EDGAR behind one `kind`-routed tool.

Deliberately ONE tool, not two: the filing index and the XBRL facts are two
views of the same object (a registrant) and share the same symbol/CIK
resolution, so a `kind` switch keeps the unified surface smaller — the same
reasoning as get_symbol_intel.

  kind=filings  recent filings (form / dates / accession / primary doc)
  kind=facts    as-reported XBRL concepts for a tag whitelist

No key. SEC's fair-access policy does require a *declared* user agent; set
SEC_EDGAR_USER_AGENT="<tool> <email>". A UA containing github.com is
answered with 403 by SEC (measured), and the provider maps that 403 to an
AuthError carrying this instruction instead of a generic "unavailable".
"""
from __future__ import annotations

import re

from ..errors import tool_error
from ._routing import route_and_call

CHAIN = ["edgar"]
KINDS = ("filings", "facts")
# Common tags. `Revenues` is the pre-2018 revenue tag; newer filers report
# RevenueFromContractWithCustomerExcludingAssessedTax, so both are listed in
# the docstring and a missing tag comes back in `missing_tags` (not an error).
DEFAULT_TAGS = "Revenues,NetIncomeLoss,EarningsPerShareDiluted"
MAX_TAGS = 8
_TAG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_\-\.]{0,127}$")


def _parse_tags(raw: str | None) -> tuple[list[str], str | None]:
    text = (raw or "").strip() or DEFAULT_TAGS
    tags = [t.strip() for t in text.split(",") if t.strip()]
    if not tags:
        return [], "tags 为空"
    if len(tags) > MAX_TAGS:
        return [], f"tags 最多 {MAX_TAGS} 个（收到 {len(tags)}）"
    bad = [t for t in tags if not _TAG_RE.match(t)]
    if bad:
        return [], f"非法 XBRL tag: {bad}"
    return tags, None


def register(mcp, providers, settings) -> None:
    @mcp.tool()
    async def get_sec_filing(symbol_or_cik: str, kind: str = "filings",
                             form_type: str | None = None,
                             tags: str | None = None, limit: int = 20,
                             source: str = "auto") -> dict:
        """SEC EDGAR filings and as-reported XBRL facts (US registrants, no key).

        kind=filings — the registrant's most recent filings from EDGAR's
            `recent` block (latest ~1000): form, filing_date, report_date,
            accession_number, primary_document. `form_type` filters, comma
            separated ("10-K,10-Q,8-K"); a bare form also matches amendments
            ("10-K" includes "10-K/A").
        kind=facts   — XBRL concepts exactly as filed, each row tagged with
            form/filed/accn for citation. `tags` is a comma-separated
            whitelist (max 8, default "Revenues,NetIncomeLoss,
            EarningsPerShareDiluted"). Common alternatives: Assets, Liabilities,
            StockholdersEquity, RevenueFromContractWithCustomerExcludingAssessedTax,
            CashAndCashEquivalentsAtCarryingValue, OperatingIncomeLoss.
            A tag the filer never reported comes back in `missing_tags`.

        `symbol_or_cik` accepts a ticker (AAPL), a CIK ("320193",
        "CIK0000320193") or a 10-digit padded CIK. `limit` caps filings
        (1-100) or rows per tag/unit (1-100). `source` is auto | edgar.

        Requires a declared user agent per SEC policy: set
        SEC_EDGAR_USER_AGENT="unified-finance-mcp your@email". Returns
        {"data": ...} semantics — the provider dict directly — or the routing
        error dict at the top level; callers check `"error" in out`.
        """
        key = kind.strip().lower() if isinstance(kind, str) else ""
        if key not in KINDS:
            return tool_error(f"unknown kind {kind!r}", hint=f"kind: {list(KINDS)}")
        try:
            n = int(limit)
        except (TypeError, ValueError):
            return tool_error(f"limit must be an integer, got {limit!r}")
        if not 1 <= n <= 100:
            return tool_error(f"limit must be 1..100, got {n}")
        value = (symbol_or_cik or "").strip()
        if not value:
            return tool_error("symbol_or_cik 不能为空",
                              hint="ticker (AAPL) 或 CIK (0000320193)")

        if key == "filings":
            out = await route_and_call(
                market="US", chain=CHAIN, providers=providers,
                call=lambda p: p.submissions(value, form_type=form_type, limit=n),
                explicit_source=source)
        else:
            parsed, problem = _parse_tags(tags)
            if problem:
                return tool_error(problem,
                                  hint=f"tags 逗号分隔，最多 {MAX_TAGS} 个，如 "
                                       f"{DEFAULT_TAGS}")
            out = await route_and_call(
                market="US", chain=CHAIN, providers=providers,
                call=lambda p: p.facts(value, parsed, limit=n),
                explicit_source=source)
        return out
