# unicef — describe dump（R18 live，2026-09-13）

> `get_data_source_desc {"name":"unicef"}` → HTTP 200，含 `###`，真源。2 API。

- **Description:** UNICEF child-focused indicators and observations through the official SDMX REST and CSV API.

## Available APIs

### unicef_search

**Description:** Search the live UNICEF SDMX dataflow catalogue. A clearly marked bundled partial catalogue is used only when the remote catalogue is unavailable.

**Optional Parameters:**
- `keyword` (): Optional case-insensitive dataflow code or name keyword. Empty text is treated as omitted. (default: <nil>)

---

### unicef_query

**Description:** Query UNICEF SDMX-CSV observations by exact dataflow ID or dataflow keyword. Returns a CSV file plus a preview.

**Required Parameters:**
- `filepath` (string): Output CSV file path. A .csv extension is appended if missing.

**Optional Parameters:**
- `dataflow` (): Exact UNICEF SDMX dataflow ID, for example CME or IMMUNISATION. Either 'dataflow' or 'keyword' must be provided. (default: <nil>)
- `keyword` (): Dataflow code or name keyword. Either 'dataflow' or 'keyword' must be provided. (default: <nil>)
- `country` (string): ISO3 REF_AREA code, or up to 20 plus-separated ISO3 codes. (default: CHN)
- `start` (): Optional SDMX start period: YYYY, YYYY-MM, YYYY-Qn, YYYY-Sn, or YYYY-MM-DD. (default: <nil>)
- `dimensions` (object): Provider-specific DSD dimension selections keyed by dimension ID. Values may contain up to 20 plus-separated SDMX codes. Unknown dimensions are rejected after live DSD resolution. (default: map[])
- `top` (integer): Maximum observations returned in the CSV file. One additional CSV row is parsed only to determine has_more. (default: 50)
- `indicator` (): Optional INDICATOR code or plus-separated codes. (default: <nil>)
- `end` (): Optional inclusive SDMX end period in the same format as start. (default: <nil>)
