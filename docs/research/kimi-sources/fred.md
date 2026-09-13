# fred

**Description:** Federal Reserve Economic Data series metadata and observations through the official FRED REST JSON API. FRED_API_KEY is read only from server configuration.

## Available APIs

### fred_search

**Description:** Search official FRED series metadata by text. Omit keyword to list the small bundled popular-series catalogue.

**Optional Parameters:**
- `keyword` (): Optional FRED series search text. Empty text is treated as omitted. (default: &lt;nil&gt;)
- `limit` (integer): Maximum series metadata records returned. (default: 20)
- `realtime_start` (): Optional inclusive start of the FRED real-time period for remote search metadata. (default: &lt;nil&gt;)
- `realtime_end` (): Optional inclusive end of the FRED real-time period for remote search metadata. (default: &lt;nil&gt;)

---

### fred_query

**Description:** Query FRED series observations by exact series id or keyword. Returns a CSV file plus a preview. Either &#39;id&#39; or &#39;keyword&#39; must be provided.

**Required Parameters:**
- `filepath` (string): Output CSV file path. A .csv extension is appended if missing.

**Optional Parameters:**
- `start` (): Optional first observation date (observation_start upstream). (default: &lt;nil&gt;)
- `frequency` (): Optional lower aggregation frequency using an official FRED frequency code. (default: &lt;nil&gt;) (options: d, w, bw, m, q, sa, a, wef, weth, wew, wetu, wem, wesu, wesa, bwew, bwem)
- `realtime_start` (): Optional inclusive start of the observation real-time period. Mutually exclusive with vintage_dates. (default: &lt;nil&gt;)
- `realtime_end` (): Optional inclusive end of the observation real-time period. Mutually exclusive with vintage_dates. (default: &lt;nil&gt;)
- `vintage_dates` (): Past dates on which data should be viewed. Sent instead of a real-time period, in provider order. (default: &lt;nil&gt;)
- `output_type` (integer): Official FRED output type: 1 real-time periods; 2 all by vintage; 3 new/revised by vintage; 4 initial releases. (default: 1) (options: )
- `id` (): Exact FRED series identifier, for example GDPC1. Either &#39;id&#39; or &#39;keyword&#39; must be provided. (default: &lt;nil&gt;)
- `end` (): Optional last observation date (observation_end upstream). (default: &lt;nil&gt;)
- `units` (): Optional official FRED value transformation code. (default: &lt;nil&gt;) (options: lin, chg, ch1, pch, pc1, pca, cch, cca, log)
- `aggregation_method` (): Aggregation used with frequency: average, sum, or end of period. Requires frequency. (default: &lt;nil&gt;) (options: avg, sum, eop)
- `limit` (integer): Maximum observations returned in the CSV file. (default: 1000)
- `keyword` (): FRED series search text. Either &#39;id&#39; or &#39;keyword&#39; must be provided. (default: &lt;nil&gt;)

---

