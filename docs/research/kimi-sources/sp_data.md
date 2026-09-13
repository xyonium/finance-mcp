# sp_data

**Description:** S&amp;P Capital IQ provides institution-grade company fundamentals for US-listed
equities. It combines issuer reference data, security/trading-item identifiers,
standardized financial statement line items, bank and insurance disclosures,
ratios, valuation metrics, consensus estimates, competitor relationships,
ownership records, executive profiles, corporate events, transcripts,
transaction relationships, and company topic tags.

Distinctive S&amp;P identifiers:
- ticker identifies the listed trading item, e.g. AAPL, MSFT, GOOGL
- company_id identifies the underlying Capital IQ company entity
- data_item_id identifies standardized S&amp;P financial or estimate metrics

This datasource uses the S&amp;P password protected scope. Query parameters may
narrow the available range, but requests beyond the allowed range are clipped
before querying.


## Available APIs

### sp_get_financials

**Description:** Retrieve standardized S&amp;P Capital IQ financial data items for a company.
Use this for statement-line fundamentals and comparable metrics that are
indexed by S&amp;P data_item_id and data_item_name rather than by filing layout.

Modules:
- standard: income statement, balance sheet, cash flow, and supplemental items
- bank / insurance: industry-specific financial statement line items
- ratio: S&amp;P ratio metrics
- key_stats: curated key statistics
- valuation: valuation metrics

Available range: up to 10 years of CIQ Latest Financials data.
Provide either ticker or company_id. Use fiscal_year only for a single
exact fiscal year, fiscal_year_start/fiscal_year_end for an inclusive range,
and data_item_id when the request targets a specific S&amp;P metric such as one
cash-flow line item. Requests outside this range are clipped.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `ticker` (string): US stock ticker symbol, e.g. AAPL.
- `module` (string): Financial module to query. (default: standard) (options: standard, bank, insurance, ratio, key_stats, valuation)
- `period_type` (string): annual or quarterly. quarterly currently supports standard financials. (default: annual) (options: annual, quarterly)
- `fiscal_year` (integer): Optional fiscal year filter, e.g. 2025.
- `limit` (integer): Maximum records to return. Default 200. (default: 200)
- `company_id` (integer): S&amp;P Capital IQ companyid. Takes precedence together with ticker filters when provided.
- `fiscal_year_start` (integer): Optional first fiscal year in an inclusive range, e.g. 2021 for FY2021-FY2025.
- `fiscal_year_end` (integer): Optional last fiscal year in an inclusive range, e.g. 2025 for FY2021-FY2025.
- `fiscal_quarter` (integer): Optional fiscal quarter filter, 1-4.
- `data_item_id` (integer): Optional S&amp;P dataitemid filter for a specific metric.

---

### sp_get_estimates

**Description:** Retrieve current S&amp;P Capital IQ consensus estimate data for a company.
Use this for analyst-consensus measures such as EPS, revenue, EBITDA, and
other forecast items identified by S&amp;P data_item_id and data_item_name.

Available range: 2 years of history plus 2 years of forecast.
Estimate rows include fiscal period metadata plus effective_date and to_date,
which describe the current validity window of the consensus value. Provide
either ticker or company_id, and use period_type, fiscal_year,
fiscal_year_start/fiscal_year_end, fiscal_quarter, or data_item_id to
narrow the result set. Requests outside this range are clipped.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `company_id` (integer): S&amp;P Capital IQ companyid.
- `period_type` (string): annual or quarterly. (default: annual) (options: annual, quarterly)
- `fiscal_year_start` (integer): Optional first fiscal year in an inclusive estimate range, e.g. 2026.
- `fiscal_year_end` (integer): Optional last fiscal year in an inclusive estimate range, e.g. 2028.
- `data_item_id` (integer): Optional S&amp;P estimate dataitemid filter.
- `limit` (integer): Maximum records to return. Default 200. (default: 200)
- `ticker` (string): US stock ticker symbol, e.g. AAPL.
- `fiscal_year` (integer): Optional fiscal year filter, e.g. 2026.
- `fiscal_quarter` (integer): Optional fiscal quarter filter, 1-4.

---

### sp_get_competitors

**Description:** Retrieve S&amp;P Capital IQ competitor relationships for a US-listed company.
Use this when the user asks for peer companies, competitors, comparable
operating companies, or a first-pass peer set anchored on Capital IQ company
relationships rather than market-index membership.

Provide either ticker or company_id. Results identify the queried company
and each competitor company, including company_id, security_id,
trading_item_id, ticker, exchange, competitor_company_id, and
competitor_name. Use exchange only when the user explicitly wants to narrow
the listed universe by exchange.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `ticker` (string): US stock ticker symbol, e.g. AAPL.
- `company_id` (integer): S&amp;P Capital IQ companyid.
- `exchange` (string): Optional exchange symbol or exchange name filter, e.g. NASDAQ or NYSE.
- `limit` (integer): Maximum records to return. Default 100. (default: 100)

---

### sp_get_top_owners

**Description:** Retrieve latest top shareholder holdings from S&amp;P Capital IQ for a US-listed
company. Use this when analyzing ownership concentration, major institutional
holders, recent share changes, or portfolio exposure.

Available range: top 50 holders. Returns holders ranked by shares held, including owner name, holding date,
shares held, percent of shares outstanding, shares changed, percent shares
changed, percent of portfolio, rank, and holding period. Provide either ticker
or company_id.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `ticker` (string): US stock ticker symbol, e.g. AAPL.
- `company_id` (integer): S&amp;P Capital IQ companyid.
- `limit` (integer): Maximum records to return. Default 20. (default: 20)

---

### sp_get_transactions_advisors

**Description:** Retrieve S&amp;P Capital IQ transaction records with advisor companies. Use
this when analyzing M&amp;A, financing, transaction status, advisor roles, or
deal participation for a target company.

Available range: 5 years of transaction history. Results include transaction id/type, target company, announcement and
closing dates, status, round number, transaction size, currency, advisor
company, advisor type, and comments. Provide ticker, company_id, or
company_name.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `ticker` (string): US stock ticker symbol, e.g. AAPL.
- `company_id` (integer): S&amp;P Capital IQ companyid.
- `transaction_type` (string): Optional case-insensitive transaction type keyword filter.
- `start_date` (string): Optional announcement-date lower bound in YYYY-MM-DD format. Requests outside the available range are clipped.
- `company_name` (string): Target company name filter. Use when the user gives a company name rather than ticker or company_id.
- `status` (string): Optional case-insensitive transaction status keyword filter.
- `end_date` (string): Optional announcement-date upper bound in YYYY-MM-DD format. Requests outside the available range are clipped.
- `limit` (integer): Maximum records to return. Default 100. (default: 100)

---

### sp_get_transactions_relationships

**Description:** Retrieve S&amp;P Capital IQ transaction records with related companies. Use
this when the user asks for acquirers, sellers, investors, counterparties,
or other companies connected to a transaction.

Available range: 5 years of transaction history. Results include transaction id/type, target company, announcement and
closing dates, status, round number, transaction size, currency, related
company, relationship type, and comments. Provide ticker, company_id, or
company_name.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `status` (string): Optional case-insensitive transaction status keyword filter.
- `transaction_type` (string): Optional case-insensitive transaction type keyword filter.
- `start_date` (string): Optional announcement-date lower bound in YYYY-MM-DD format. Requests outside the available range are clipped.
- `ticker` (string): US stock ticker symbol, e.g. AAPL.
- `company_id` (integer): S&amp;P Capital IQ companyid.
- `end_date` (string): Optional announcement-date upper bound in YYYY-MM-DD format. Requests outside the available range are clipped.
- `limit` (integer): Maximum records to return. Default 100. (default: 100)
- `company_name` (string): Target company name filter. Use when the user gives a company name rather than ticker or company_id.

---

### sp_get_key_developments

**Description:** Retrieve S&amp;P Capital IQ key development records for a company. Use this
for material corporate events, news-like development history, earnings
announcements, strategic updates, litigation, product events, or management
changes.

Available range: key developments within 2 years. Results include company identity, ticker, announcement date, headline,
situation, most important date, event type, and event category. Provide
either ticker or company_id.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `ticker` (string): US stock ticker symbol, e.g. AAPL.
- `company_id` (integer): S&amp;P Capital IQ companyid.
- `start_date` (string): Optional earliest event date, YYYY-MM-DD.
- `end_date` (string): Optional latest event date, YYYY-MM-DD.
- `event_type` (string): Optional case-insensitive event type keyword filter.
- `category` (string): Optional case-insensitive event category keyword filter.
- `limit` (integer): Maximum records to return. Default 100. (default: 100)

---

### sp_get_transcripts

**Description:** Retrieve S&amp;P Capital IQ transcript components for a company. Use this for
earnings-call transcripts, presentation transcripts, speaker attribution,
and transcript text search.

Available range: Machine Readable Transcripts for fiscal years from
current year - 2 through current year, matching the original
fiscal-year SQL filter. Results include company identity, fiscal year/quarter, event headline,
transcript id, collection type, creation timestamp, component order,
component text, component type, speaker type, transcript person, and speaker
company. Provide either ticker or company_id. Use fiscal_year or
fiscal_year_start/fiscal_year_end to narrow the period, and keyword for
transcript text search.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `ticker` (string): US stock ticker symbol, e.g. AAPL.
- `company_id` (integer): S&amp;P Capital IQ companyid.
- `fiscal_year_start` (integer): Optional first fiscal year in an inclusive range. Requests outside the available range are clipped.
- `fiscal_year_end` (integer): Optional last fiscal year in an inclusive range. Requests outside the available range are clipped.
- `transcript_collection_type_id` (integer): Optional transcript collection type id, e.g. 2 for edited transcripts.
- `keyword` (string): Optional case-insensitive transcript text keyword filter.
- `exchange` (string): Optional exchange symbol filter, e.g. NASDAQ or NYSE.
- `fiscal_year` (integer): Optional fiscal year filter, e.g. 2025. Requests outside the available range are clipped.
- `fiscal_quarter` (integer): Optional fiscal quarter filter, 1-4.
- `limit` (integer): Maximum records to return. Default 200. (default: 200)

---

### sp_get_company_info

**Description:** Retrieve S&amp;P Capital IQ company reference data for US-listed equities.
Use this first when you need to resolve a ticker to a Capital IQ company_id,
confirm the primary security/trading item, identify the listing exchange, or
gather company profile context before querying fundamentals.

Returns company identity, security_id, trading_item_id, ticker, exchange,
industry, business description, headquarters/incorporation countries, website,
phone, and address fields.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `keyword` (string): Company-name keyword or exact ticker keyword.
- `limit` (integer): Maximum records to return. Default 20. (default: 20)
- `ticker` (string): US stock ticker symbol, e.g. AAPL, MSFT, GOOGL. Optional for broad search.
- `company_id` (integer): S&amp;P Capital IQ companyid. Optional when ticker or search filters are provided.
- `exchange` (string): Exchange symbol or exchange name filter, e.g. NASDAQ or NYSE.
- `industry` (string): Case-insensitive industry keyword filter.

---

### sp_get_top_executives

**Description:** Retrieve current top executives from S&amp;P Capital IQ for a US-listed company.
Use this for management-team review, CEO/CFO identification, role history,
executive rank, and biographical context.

Available range: top 15 professionals. Returns executive name, title, birth year, position start/end dates, rank,
and biography. For currently active roles, invalid zero-date placeholders are
normalized to an empty value; because empty date fields are omitted, a missing
position_end_date means the executive is still serving in that role.
Provide either ticker or company_id.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `ticker` (string): US stock ticker symbol, e.g. AAPL.
- `company_id` (integer): S&amp;P Capital IQ companyid.
- `limit` (integer): Maximum records to return. Default 20. (default: 20)

---

### sp_get_topic_tags

**Description:** Retrieve S&amp;P Capital IQ topic tags for a company. Use this when the user
asks what themes, business topics, or classification tags are associated
with a listed company.

Results include company identity, ticker, exchange, topic tag text, rank,
score, and source name. Provide either ticker or company_id.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `limit` (integer): Maximum records to return. Default 100. (default: 100)
- `ticker` (string): US stock ticker symbol, e.g. AAPL.
- `company_id` (integer): S&amp;P Capital IQ companyid.
- `exchange` (string): Optional exchange symbol or exchange name filter, e.g. NASDAQ or NYSE.
- `topic` (string): Optional case-insensitive topic tag keyword filter.
- `source` (string): Optional case-insensitive source-name filter.

---

### sp_get_future_events

**Description:** Retrieve S&amp;P Capital IQ future event records for a company. Use this for
upcoming earnings calls, conferences, presentations, investor events, and
other scheduled corporate events.

Available range: future events within 2 years. Results include company identity, ticker, announcement date, headline,
situation, most important date, event type, and event category. Provide
either ticker or company_id.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `limit` (integer): Maximum records to return. Default 100. (default: 100)
- `ticker` (string): US stock ticker symbol, e.g. AAPL.
- `company_id` (integer): S&amp;P Capital IQ companyid.
- `start_date` (string): Optional earliest event date, YYYY-MM-DD.
- `end_date` (string): Optional latest event date, YYYY-MM-DD.
- `event_type` (string): Optional case-insensitive event type keyword filter.
- `category` (string): Optional case-insensitive event category keyword filter.

---

### sp_get_ownership_sellers

**Description:** Retrieve S&amp;P Capital IQ buyer and seller holder counts for owned companies.
Use this when comparing how many holders increased versus reduced ownership
in a company.

Results include owned ticker, owned company, number of buyers, and number
of sellers. This is a buyer/seller count summary, not the ranked top-owner
list. Provide ticker, company_id, or company_name.


**Required Parameters:**
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `company_name` (string): Owned company name filter. Use when the user gives a company name rather than ticker or company_id.
- `limit` (integer): Maximum records to return. Default 100. (default: 100)
- `ticker` (string): US stock ticker symbol, e.g. AAPL.
- `company_id` (integer): S&amp;P Capital IQ companyid.

---

