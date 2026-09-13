# china_nbs — describe dump（R18 live，2026-09-13）

> `get_data_source_desc {"name":"china_nbs"}` → HTTP 200，含 `###`，真源。2 API。

- **Description:** Query National Bureau of Statistics macro indicators and time series data for national, provincial, and major-city scopes.

## Available APIs

### china_nbs_query

**Description:** Query National Bureau of Statistics data using human-readable parameters. Supports curated indicators (GDP, CPI, PPI, etc.) and any indicator returned by china_nbs_indicators across national, provincial, and major-city scopes. Results are saved as a CSV file.

**Required Parameters:**
- `filepath` (string): Target file path for the CSV output, e.g. /tmp/china_nbs_gdp.csv.
- `indicator` (string): Indicator name such as GDP, CPI, 国内生产总值, 居民消费价格指数.

**Optional Parameters:**
- `region` (string): Region name: 全国/国家/中国 (national), a provincial name (e.g. 云南 or 云南省), or one of the 36 major cities. Unrecognized regions are rejected with PARAMETER_ERROR. (default: 全国)
- `year` (string): Year or range such as 2025, 2021-2025. Empty means latest available: the last 10 years for annual, the latest single period for monthly. Most monthly indicators support historical years; price indices (CPI, PPI) are split into year segments and the correct segment is chosen automatically. Quarterly data currently only returns the latest available quarters; older quarter ranges may return empty or partial results. (default: )
- `frequency` (string): Data frequency: annual, quarterly, monthly. Defaults by indicator (GDP=annual, CPI=monthly). (options: annual, quarterly, monthly)

---

### china_nbs_indicators

**Description:** List or search indicators supported by china_nbs_query. Use keyword to filter by indicator name, category, or catalog path. Results are paginated; use page and page_size to browse. Use this before query to discover available indicators.

**Optional Parameters:**
- `keyword` (string): Optional filter by indicator name, category, or catalog path. (default: )
- `frequency` (string): Optional filter by frequency: annual, quarterly, monthly. (default: ) (options: annual, quarterly, monthly)
- `scope` (string): Optional filter by scope: national, province, city. (default: ) (options: national, province, city)
- `page` (integer): Page number, starting from 1. (default: 1)
- `page_size` (integer): Number of indicators per page, max 200. (default: 50)
