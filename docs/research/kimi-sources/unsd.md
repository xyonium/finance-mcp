# unsd — describe dump（R18 live，2026-09-13）

> `get_data_source_desc {"name":"unsd"}` → HTTP 200，含 `###`，真源。2 API。

- **Description:** UN Statistics Division UNdata catalogue discovery and bounded, validated ZIP/CSV table access through the experimental ExplorerHandler and DownloadHandler endpoints.

## Available APIs

### unsd_search

**Description:** List UNdata DataMarts, or list/search tables within one mart. Results are locally paginated after validating the complete internal ExplorerHandler response.

**Optional Parameters:**
- `mart` (): Optional exact DataMart ID from a mart-level search, for example POP or ENV. (default: <nil>)
- `keyword` (): Optional case-insensitive name, ID, category, or filter keyword. Empty text is treated as omitted. (default: <nil>)
- `offset` (integer): Zero-based offset into the complete, filtered catalogue. (default: 0)
- `limit` (integer): Maximum catalogue entries returned in this page. (default: 100)

---

### unsd_query

**Description:** Query one UNdata table by exact filter, table name, or keyword and return a CSV file plus a preview. Either 'filter', 'table', or 'keyword' must be provided together with 'mart'.

**Required Parameters:**
- `filepath` (string): Output CSV file path. A .csv extension is appended if missing.

**Optional Parameters:**
- `year` (): Optional exact year or period text. Values such as 2020 do not match 2020-Q1. (default: <nil>)
- `country_field` (): Optional exact canonical CSV column to use for country matching. Requires country. (default: <nil>)
- `year_field` (): Optional exact canonical CSV column to use for year matching. Requires year. (default: <nil>)
- `table` (): Exact or case-insensitive partial table name. Ambiguous matches return candidate filters instead of selecting the first result. (default: <nil>)
- `keyword` (): Optional case-insensitive keyword to search tables within mart. Either 'filter', 'table', or 'keyword' must be provided (with 'mart'). (default: <nil>)
- `top` (integer): Maximum matching records returned in the CSV file. The bounded CSV scan still completes to validate the archive and report filtered_total. (default: 50)
- `mart` (): Exact DataMart ID returned by unsd_search. Required when filter, table, or keyword is provided. (default: <nil>)
- `filter` (): Exact provider table filter in key:value form. Legacy percent-encoded colon forms such as tableCode%3a4 are accepted. Takes precedence over table/keyword. (default: <nil>)
- `country` (): Optional exact country/area name or code. Matching is case-insensitive equality across recognized country/name/code columns unless country_field is set. (default: <nil>)
