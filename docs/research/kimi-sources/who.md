# who — describe dump（R18 live，2026-09-13）

> `get_data_source_desc {"name":"who"}` → HTTP 200，含 `###`，真源。2 API。

- **Description:** WHO Global Health Observatory (GHO) public health indicators and observations through the official OData API.

## Available APIs

### who_search

**Description:** Search the WHO GHO indicator catalogue by indicator code or name. Omit keyword to list the complete catalogue.

**Optional Parameters:**
- `keyword` (): Optional case-insensitive indicator code or name keyword. Empty text is treated as omitted. (default: <nil>)

---

### who_query

**Description:** Query WHO indicator observations by keyword or exact indicator code. Returns a CSV file plus a preview.

**Required Parameters:**
- `filepath` (string): Output CSV file path. A .csv extension is appended if missing.

**Optional Parameters:**
- `country` (): Optional ISO 3166-1 alpha-3 country code, normalized to uppercase. (default: <nil>)
- `year` (): Optional calendar year. WHO filters records by TimeDimensionBegin in that year. (default: <nil>)
- `top` (integer): Maximum observations returned in the CSV file. One extra row may be requested upstream to determine has_more. (default: 200)
- `keyword` (): Indicator code or name keyword. Either 'keyword' or 'code' must be provided. (default: <nil>)
- `code` (): Exact WHO indicator code, for example WHOSIS_000001. Either 'keyword' or 'code' must be provided. (default: <nil>)
