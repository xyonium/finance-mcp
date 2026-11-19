#!/usr/bin/env python3
"""live_smoke — hit the keyless official sources for real and report PASS/FAIL.

This is the manual counterpart to the hermetic test suite: it is **not**
collected by pytest and never runs in CI (`pytest -m "not integration"` is
the CI gate). Use it before/after touching a provider, or when a user reports
"source X returns nothing":

    .venv/bin/python scripts/live_smoke.py
    .venv/bin/python scripts/live_smoke.py --only edgar,treasury
    .venv/bin/python scripts/live_smoke.py --verbose

Checks only sources that need no account (SEC EDGAR, US Treasury, World Bank,
BLS). FRED is included only when `FRED_API_KEY` is set. Alpha Vantage / FMP
are deliberately excluded: their free tiers are tiny and must stay mocked.

Exit codes: 0 = all selected checks passed; 1 = at least one failed.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import traceback
from collections.abc import Awaitable, Callable

from unified_finance_mcp.config import get_settings
from unified_finance_mcp.providers import build_providers

CHECKS: dict[str, Callable[[dict], Awaitable[str]]] = {}


def check(name: str):
    def deco(fn):
        CHECKS[name] = fn
        return fn
    return deco


class Skip(Exception):
    """A check that cannot run in this environment (missing optional config)."""


def _require_edgar_ua(p: dict) -> None:
    """SEC's www.sec.gov ticker map 403s a bare UA; a contact email is required."""
    ua = (p["edgar"].settings.sec_edgar_user_agent or "").strip()
    if "@" not in ua:
        raise Skip('SEC_EDGAR_USER_AGENT needs a contact email '
                   '(e.g. "unified-finance-mcp you@example.com"); '
                   'the bare default is 403\'d by www.sec.gov')


@check("edgar.filings")
async def edgar_filings(p: dict) -> str:
    _require_edgar_ua(p)
    data = await p["edgar"].submissions("AAPL", form_type="10-K", limit=2)
    rows = ", ".join(f"{f['form']} {f['filing_date']}" for f in data["filings"])
    return f"{data['name']}: {rows}"


@check("edgar.facts")
async def edgar_facts(p: dict) -> str:
    _require_edgar_ua(p)
    data = await p["edgar"].facts("AAPL", ["NetIncomeLoss"], limit=1)
    row = data["facts"]["NetIncomeLoss"]["units"]["USD"][-1]
    return f"NetIncomeLoss {row['val']} (filed {row['filed']}, accn {row['accn']})"


@check("treasury.curve")
async def treasury_curve(p: dict) -> str:
    period = p["treasury"].default_period()
    data = await p["treasury"].yield_curve(period)
    row = data["data"][0]
    return (f"{period} {row['date']}: 1M={row.get('1M')} 2Y={row.get('2Y')} "
            f"10Y={row.get('10Y')} 30Y={row.get('30Y')}")


@check("treasury.debt")
async def treasury_debt(p: dict) -> str:
    data = await p["treasury"].fiscal("debt_to_penny", page_size=1)
    row = data["data"][0]
    return f"{row['record_date']} total={row['tot_pub_debt_out_amt']}"


@check("treasury.mts")
async def treasury_mts(p: dict) -> str:
    data = await p["treasury"].mts_outlays(limit=3)
    top = "; ".join(f"{r['classification_desc']}={r['current_month_gross_outly_amt']}"
                    for r in data["data"])
    return f"{data['record_date']} total={data['total']} truncated={data['truncated']}: {top}"


@check("worldbank")
async def worldbank(p: dict) -> str:
    rows = await p["macro"].world_bank_series("NY.GDP.MKTP.CD", "CHN", 2023, 2024)
    return ", ".join(f"{r['date']}={r['value']}" for r in rows)


@check("bls")
async def bls(p: dict) -> str:
    settings = p["macro"].settings
    if not (settings.bls_proxy_url or settings.jina_api_key):
        raise Skip("needs BLS_PROXY_URL or JINA_API_KEY (direct api.bls.gov is "
                   "403 from this egress)")
    rows = await p["macro"].bls_series("JTS000000000000000JOL")
    return f"JOLTS {rows[0]['date']}={rows[0]['value']} ({len(rows)} months)"


@check("fred")
async def fred(p: dict) -> str:
    if not p["fred"].available():
        raise Skip("FRED_API_KEY not set")
    data = await p["fred"].series_observations("DGS10", limit=1)
    row = data["data"][0]
    return f"DGS10 {row['date']}={row['value']}"


def _selected(only: list[str]) -> list[str]:
    if not only:
        return list(CHECKS)
    picked = [n for n in CHECKS
              if any(n == o or n.startswith(o + ".") for o in only)]
    unknown = [o for o in only if not any(n == o or n.startswith(o + ".") for n in CHECKS)]
    if unknown:
        print(f"unknown check(s): {', '.join(unknown)}; available: "
              f"{', '.join(CHECKS)}", file=sys.stderr)
        raise SystemExit(2)
    return picked


async def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Live smoke for keyless sources")
    ap.add_argument("--only", default="",
                    help="comma-separated names or prefixes (e.g. edgar,treasury)")
    ap.add_argument("--verbose", action="store_true", help="print tracebacks")
    ap.add_argument("--timeout", type=float, default=200.0,
                    help="per-check timeout in seconds (default 200: covers "
                         "the two-request MTS worst case and one curve retry)")
    args = ap.parse_args(argv)
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    providers = build_providers(get_settings())
    passed = skipped = failures = 0
    for name in _selected(only):
        try:
            detail = await asyncio.wait_for(CHECKS[name](providers),
                                            timeout=args.timeout)
        except asyncio.TimeoutError:
            failures += 1
            print(f"FAIL {name:<16} timed out after {args.timeout:.0f}s",
                  flush=True)
        except Skip as exc:
            skipped += 1
            print(f"SKIP {name:<16} {exc}", flush=True)
        except Exception as exc:  # noqa: BLE001 - a smoke runner reports, never raises
            failures += 1
            print(f"FAIL {name:<16} {type(exc).__name__}: {str(exc)[:200]}",
                  flush=True)
            if args.verbose:
                traceback.print_exc()
        else:
            passed += 1
            print(f"PASS {name:<16} {detail}", flush=True)
    print(f"\n{passed} passed, {skipped} skipped, {failures} failed", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
