#!/usr/bin/env python3
"""kimi_enum_diff — diff the official kimi-datasource enum against this repo's
adjudicated source universe (R17 coda, task ⑤).

The MoonshotAI/kimi-code plugin `plugins/official/kimi-datasource/bin/
kimi-datasource.mjs` hardcodes the get_data_source_desc `name` enum. That
enum is the AUTHORITATIVE incremental signal for "kimi grew a new source":
the live backend is a superset of the enum (7 of our 32 probed sources —
ifind, dongcai, pubchem, chembl, uniprot, pdb, pubmed — are live but
undocumented), so when the enum gains an entry we have never probed, it is
guaranteed new to us.

This repo's universe is the single-source-of-truth registries in
providers/kimi.py: KNOWN_SOURCES ∪ DISCOURAGED_SOURCES ∪ KEPT_SOURCES
(32 sources as of 2026-09-14).

Exit codes: 0 = enum ⊆ our universe (nothing new to adjudicate);
            1 = enum has unprobed entries (ACTION: probe + verdict);
            2 = fetch/parse failure (no verdict either way).

Usage:  .venv/bin/python scripts/kimi_enum_diff.py [--json] [--mjs-url URL]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request

DEFAULT_MJS_URL = (
    "https://raw.githubusercontent.com/MoonshotAI/kimi-code/main/"
    "plugins/official/kimi-datasource/bin/kimi-datasource.mjs")

# The enum block inside the get_data_source_desc inputSchema:
#     enum: [
#       'stock_finance_data',
#       ...
#     ],
_ENUM_RE = re.compile(r"enum:\s*\[(?P<body>[^\]]*)\]", re.DOTALL)
_ENTRY_RE = re.compile(r"'([^']+)'")


def fetch_official_enum(url: str, timeout: float = 30.0) -> list[str]:
    req = urllib.request.Request(url, headers={"User-Agent":
                                               "finance-mcp-enum-diff"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8")
    m = _ENUM_RE.search(text)
    if not m:
        raise RuntimeError("no `enum: [...]` block found in the mjs — "
                           "the plugin layout changed; update _ENUM_RE")
    entries = _ENTRY_RE.findall(m.group("body"))
    if not entries:
        raise RuntimeError("enum block parsed empty — the mjs shape changed")
    return entries


def our_universe() -> dict[str, str]:
    """source -> adjudication tag ('known'/'kept'/'discouraged: <verdict>')."""
    from unified_finance_mcp.providers.kimi import (
        DISCOURAGED_SOURCES,
        KEPT_SOURCES,
        KNOWN_SOURCES,
    )
    out: dict[str, str] = {s: "known-seed" for s in KNOWN_SOURCES}
    out.update({s: f"discouraged ({v.split('—')[0].strip()})"
                for s, v in DISCOURAGED_SOURCES.items()})
    out.update({s: "kept" for s in KEPT_SOURCES})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="machine-readable out")
    ap.add_argument("--mjs-url", default=DEFAULT_MJS_URL,
                    help="override the plugin mjs URL (pin a tag/commit)")
    args = ap.parse_args()

    try:
        enum = fetch_official_enum(args.mjs_url)
    except Exception as e:  # noqa: BLE001 - CLI boundary: ANY fetch/parse
        # failure (network, TLS, regex drift) means "no verdict" -> exit 2.
        print(f"enum fetch/parse failed: {e}", file=sys.stderr)
        return 2

    ours = our_universe()
    enum_set, our_set = set(enum), set(ours)
    new_upstream = sorted(enum_set - our_set)     # ACTION: probe + verdict
    undocumented = sorted(our_set - enum_set)     # live but not in the enum
    report = {
        "enum_count": len(enum),
        "our_count": len(our_set),
        "new_upstream_unprobed": new_upstream,
        "ours_not_in_enum": undocumented,
        "in_sync": sorted(enum_set & our_set),
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"official enum: {len(enum)} sources; our universe: "
              f"{len(our_set)}")
        if new_upstream:
            print(f"\n!! {len(new_upstream)} NEW upstream source(s) to probe "
                  f"and adjudicate (docs/research/kimi-sources/):")
            for s in new_upstream:
                print(f"   + {s}")
        else:
            print("\nOK: enum ⊆ our universe — nothing new to adjudicate.")
        if undocumented:
            print(f"\n(i) {len(undocumented)} probed source(s) live but NOT "
                  f"in the official enum (backend superset, informational):")
            for s in undocumented:
                print(f"   - {s}  [{ours[s]}]")
    return 1 if new_upstream else 0


if __name__ == "__main__":
    sys.exit(main())
