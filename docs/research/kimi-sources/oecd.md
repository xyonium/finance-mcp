# oecd

**Description:** OECD Data Explorer datasets and observations through the official SDMX 3.0 REST API.

## Available APIs

### oecd_search

**Description:** Search a small bundled catalogue of verified OECD Data Explorer dataflows. Any official dataflow identity returned here, or obtained elsewhere, can be passed to oecd_query.

**Optional Parameters:**
- `keyword` (): Optional case-insensitive keyword matched against catalogue code, title, description, agency, and dataflow. Empty text is treated as omitted. (default: &lt;nil&gt;)

---

### oecd_query

**Description:** Query OECD observations by keyword or exact dataflow identity. Returns a CSV file plus a preview. If no series key is supplied, a wildcard key is built from the official DSD dimension order.

**Required Parameters:**
- `filepath` (string): Output CSV file path. A .csv extension is appended if missing.

**Optional Parameters:**
- `start` (): Optional inclusive start reporting period, for example 2020, 2020-Q1, or 2020-01. Cannot be combined with last_n_observations. (default: &lt;nil&gt;)
- `end` (): Optional inclusive end reporting period in the same precision as start. Cannot be combined with last_n_observations. (default: &lt;nil&gt;)
- `last_n_observations` (): Optional provider-side maximum observations per matching series, counted backwards from the latest observation. Cannot be combined with start or end. (default: &lt;nil&gt;)
- `top` (integer): Maximum observations returned inline. Parsing stops after one additional row to determine has_more. (default: 50)
- `keyword` (): Keyword to search the bundled OECD catalogue. Either &#39;keyword&#39; or &#39;dataset&#39; must be provided. (default: &lt;nil&gt;)
- `dataset` (): Protocol-native OECD dataflow identity. Either &#39;keyword&#39; or &#39;dataset&#39; must be provided.
- `key` (): Optional SDMX 3.0 key in official DSD dimension order. Use &#39;*&#39; for a wildcard dimension. If omitted, the tool builds an all-wildcard key from the DSD. (default: &lt;nil&gt;)

---

