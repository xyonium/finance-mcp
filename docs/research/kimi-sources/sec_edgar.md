# sec_edgar

**Description:** SEC EDGAR provides comprehensive US public company regulatory filings and financial data.
Covers 8,000+ US-listed companies with filings dating back to 2009 (XBRL era).
Includes financial statements (10-K/10-Q), XBRL standardized metrics, insider trades (Form 4),
institutional holdings (13F), company events (8-K), and filing document search.

Data routing:
- all APIs are served from internal DB (alpha-longdata)

#ticker format
US-stock: AAPL, MSFT, GOOGL (standard ticker symbols, no suffix needed)
Also accepts CIK numbers: 0000320193 (Apple&#39;s CIK)


## Available APIs

### sec_edgar_get_insider_trades

**Description:** Get insider trading activity (SEC Form 3/4/5) for a US-listed company.
Shows executive and director stock transactions: buys, sells, option exercises.
Provide either ticker or cik. If both are provided, cik takes precedence.
Use summary=true (default) for one row per filing; summary=false for full transaction detail.


**Required Parameters:**
- `file_path` (string): Absolute path to save. CSV format.

**Optional Parameters:**
- `ticker` (string): US stock ticker symbol
- `cik` (integer): SEC CIK number. Takes precedence over ticker when provided.
- `limit` (integer): Max filings to process. Default 10. (default: 10)
- `summary` (boolean): If true (default), return one summary row per filing. If false, return every transaction detail. (default: true)

---

### sec_edgar_get_institutional_holdings

**Description:** Get institutional investor holdings from SEC 13F filings.
Note: ticker should be the INSTITUTION&#39;s ticker (e.g. &#39;BRK-B&#39; for Berkshire), not the stock being held.
Provide either ticker or cik. For institutional filers, cik is often more reliable and takes precedence.
Use compare=true to see quarter-over-quarter position changes.


**Required Parameters:**
- `file_path` (string): Absolute path to save. CSV format.

**Optional Parameters:**
- `ticker` (string): Institutional investor&#39;s ticker symbol (e.g. &#39;BRK-B&#39; for Berkshire Hathaway)
- `cik` (integer): Institutional filer&#39;s SEC CIK number. Takes precedence over ticker when provided.
- `compare` (boolean): If true, compare current vs previous quarter and show position changes. Default false. (default: false)

---

### sec_edgar_get_company_events

**Description:** Get material corporate events from SEC 8-K filings.
Covers: earnings releases, acquisitions, executive changes, etc.
Provide either ticker or cik. If both are provided, cik takes precedence.
Use start_date/end_date to filter by date range (strongly recommended).


**Required Parameters:**
- `file_path` (string): Absolute path to save. CSV format.

**Optional Parameters:**
- `cik` (integer): SEC CIK number. Takes precedence over ticker when provided.
- `start_date` (string): Start date YYYY-MM-DD. Only return events after this date.
- `end_date` (string): End date YYYY-MM-DD. Only return events before this date.
- `limit` (integer): Max events. Default 20. (default: 20)
- `ticker` (string): US stock ticker symbol

---

### sec_edgar_get_company_info

**Description:** Get SEC-registered company information for a given ticker or CIK number.
Includes: Company name, CIK, SIC industry code, state of incorporation,
fiscal year end, stock exchange, shares outstanding, public float, category, and contact info.


**Required Parameters:**
- `ticker` (string): US stock ticker symbol (e.g. &#39;AAPL&#39;, &#39;MSFT&#39;) or CIK number (e.g. &#39;0000320193&#39;)
- `file_path` (string): Absolute path to save the company info. CSV format.

---

### sec_edgar_get_financial_statements

**Description:** Get full structured financial statements (income statement, balance sheet, cash flow)
for a US-listed company, parsed directly from SEC filing XBRL packages.

## When to use this tool vs sec_get_xbrl_facts
- Use THIS tool when you need the COMPLETE statement structure: all line items,
  subtotals, segment breakdowns, and presentation hierarchy — as it appears in the
  actual SEC filing. Best for: detailed financial analysis, financial modeling,
  reproducing the full balance sheet or income statement.
- Use sec_get_xbrl_facts when you need a SINGLE METRIC across multiple years
  (e.g. revenue trend 2019–2024, net income history). xbrl_facts is faster for
  time-series of one concept.

## Multi-year coverage in one call
The latest 10-K already includes 3 fiscal years side by side (income statement,
cash flow) and 2 years (balance sheet). Do NOT call this tool multiple times to
get recent years — one call without financial_parameter returns the latest filing
with multi-year comparatives already included.

## Locating a specific filing
Use financial_parameter with fiscal period notation: &#39;FY2023&#39; for annual,
&#39;Q2FY2026&#39; for quarterly. The tool resolves the correct filing automatically
regardless of the company&#39;s fiscal year end. If unsure which periods are available,
call sec_get_filings first to see the full list with fiscal labels.

## View levels
&#39;summary&#39; (~15 rows), &#39;standard&#39; (~25 rows, default), &#39;detailed&#39; (~50+ rows with
segment breakdowns).


**Required Parameters:**
- `ticker` (string): US stock ticker symbol (e.g. &#39;AAPL&#39;, &#39;MSFT&#39;)
- `statement` (string): &#39;income_statement&#39;, &#39;balance_sheet&#39;, &#39;cash_flow&#39;, or &#39;all&#39;. Aliases: &#39;is&#39;, &#39;bs&#39;, &#39;cf&#39;. (options: income_statement, balance_sheet, cash_flow, is, bs, cf, all)
- `file_path` (string): Absolute path to save. CSV format.

**Optional Parameters:**
- `view` (string): Detail level: &#39;summary&#39; (~15 rows), &#39;standard&#39; (default ~25 rows), &#39;detailed&#39; (~50+ rows with segment breakdowns). (default: standard) (options: summary, standard, detailed)
- `report_type` (string): &#39;annual&#39; (10-K, default) or &#39;quarterly&#39; (10-Q). Ignored when financial_parameter
is provided in fiscal notation (e.g. &#39;Q2FY2026&#39; already implies quarterly).
 (default: annual) (options: annual, quarterly)
- `financial_parameter` (string): Fiscal period to retrieve. Use fiscal notation (preferred):
  &#39;FY{YYYY}&#39;   — annual 10-K,  e.g. &#39;FY2023&#39;
  &#39;Q{N}FY{YYYY}&#39; — quarterly 10-Q, e.g. &#39;Q2FY2026&#39;, &#39;Q1FY2024&#39;
The tool maps the fiscal label to the correct filing automatically,
regardless of the company&#39;s fiscal year end (e.g. AAPL ends in September,
so FY2023 maps to the filing with period_of_report=2023-09-30).
Raw report date in YYYYMMDD format is also accepted as fallback.
If omitted, returns the latest available filing (which already includes
2–3 years of comparative data).


---

### sec_edgar_get_xbrl_facts

**Description:** Get structured XBRL financial facts for a company across time.

## When to use this tool vs sec_get_financial_statements
- Use THIS tool when you need a SINGLE METRIC over multiple years (e.g. revenue
  trend 2019–2024, net income history, 5-year capex). Returns a flat time-series
  DataFrame — fast, one request covers all years.
- Use sec_get_financial_statements when you need the COMPLETE statement structure
  (all line items, subtotals, hierarchy) for a specific filing period.

## Three query modes (mutually exclusive — provide exactly one):
1. keyword (recommended for most queries): map a plain-language term to standard
   XBRL concepts via a predefined table. Near-synonyms accepted.
   Example: keyword=&#39;salary&#39; → fetches LaborAndRelatedExpense, SalariesAndWages, etc.
2. concept: exact XBRL concept name for precise time-series lookup.
   Use when you know the exact us-gaap tag. Note: companies switch concepts over
   time (e.g. AAPL moved from &#39;Revenues&#39; to
   &#39;RevenueFromContractWithCustomerExcludingAssessedTax&#39; after FY2018).
   When unsure, prefer keyword mode.
3. metric: convenience shortcut returning the single latest annual + quarterly
   value. No year/period filtering needed.

## Filtering
Use &#39;year&#39; to restrict results (e.g. &#39;2019-2023&#39;). Filtering is based on the
period end date of each data point, not the fiscal year of the filing.


**Required Parameters:**
- `ticker` (string): US stock ticker symbol
- `file_path` (string): Absolute path to save. CSV format.

**Optional Parameters:**
- `metric` (string): Quick metric name for a single latest value: returns most recent annual + quarterly. No year filter needed. Options: &#39;revenue&#39;, &#39;net_income&#39;, &#39;total_assets&#39;, &#39;operating_income&#39;, &#39;free_cash_flow&#39;, &#39;stockholders_equity&#39;, &#39;operating_cash_flow&#39;, &#39;total_liabilities&#39;, &#39;current_assets&#39;, &#39;current_liabilities&#39;, &#39;capital_expenditures&#39;. (options: revenue, net_income, total_assets, operating_income, free_cash_flow, stockholders_equity, operating_cash_flow, total_liabilities, current_assets, current_liabilities, capital_expenditures)
- `year` (string): Filter by period end year. Single: &#39;2023&#39;. Range: &#39;2019-2023&#39;. Filtering uses the data point&#39;s period end date, not the filing&#39;s fiscal year. Strongly recommended to avoid oversized results.
- `period` (string): Filter by fiscal period: &#39;FY&#39; (annual), &#39;Q1&#39;, &#39;Q2&#39;, &#39;Q3&#39;, &#39;Q4&#39;. (options: FY, Q1, Q2, Q3, Q4)
- `concept` (string): Exact XBRL concept name (e.g. &#39;NetIncomeLoss&#39;, &#39;Assets&#39;). Returns a time series
for that concept. Prefer keyword mode if you are not certain of the exact concept
name — wrong concepts return empty results silently.

- `keyword` (string): Predefined keyword to search XBRL concepts. Supported keywords: revenue, revenues, sales, netsales, netincome, income, profit, grossprofit, operatingincome, ebit, assets, totalassets, currentassets, noncurrentassets, liabilities, totalliabilities, currentliabilities, noncurrentliabilities, equity, stockholdersequity, cash, cashandequivalents, operatingcashflow, freecashflow, debt, longtermdebt, shorttermdebt, borrowings, salary, salaries, compensation, labor, employee, payroll, wage, wages, sharebasedcompensation, stockbasedcompensation, cost, cogs, costofrevenue, costofgoodssold, operatingexpense, operatingexpenses, capex, capitalexpenditure, capitalexpenditures, depreciation, amortization, depreciationandamortization, inventory, receivables, accountsreceivable, payables, accountspayable, goodwill, intangibles, intangibleassets, ppe, propertyplantequipment, marketablesecurities, investments, eps, earningspershare, basiceps, dilutedeps, shares, sharesoutstanding, dividends, tax, incometax, interest, interestexpense, rd, research, researchanddevelopment, randd. Near-synonyms are accepted (e.g. &#39;wages&#39; matches salary concepts).


---

### sec_edgar_get_filings

**Description:** List SEC filings for a company with fiscal period labels.
Returns metadata for each filing: form type, report date, fiscal_year, fiscal_period,
filing date, and accession number.

## Primary use case: look up fiscal period labels before calling other tools
Each row includes fiscal_year and fiscal_period columns (e.g. fiscal_year=2024,
fiscal_period=Q2), so you can identify which filing corresponds to &#39;Q2 FY2024&#39;
and pass the correct financial_parameter to sec_get_financial_statements.

Supports all form types: 10-K (annual), 10-Q (quarterly), 8-K, S-1, DEF 14A,
13F-HR, Form 4, etc.


**Required Parameters:**
- `ticker` (string): US stock ticker symbol
- `file_path` (string): Absolute path to save. CSV format.

**Optional Parameters:**
- `form_type` (string): SEC form type filter: &#39;10-K&#39;, &#39;10-Q&#39;, &#39;8-K&#39;, &#39;4&#39;, &#39;13F-HR&#39;. Omit for all types.
- `limit` (integer): Max filings to return. Default 20. (default: 20)

---

