# imf

**Description:** IMF economic data via indicator-resolution pipeline. Supports IFS (CPI, exchange rates), BOP (balance of payments), DOTS (trade), DIP (direct investment), PIP (portfolio investment), WEO (forecasts), FSI, COFER, QGFS, IRFCL.

## Available APIs

### imf_bop_data

**Description:** Get BOP data: current account, trade balance, financial account.

Common indicators:
- BCA_BP6_USD: Current account balance
- BXG_BP6_USD: Goods exports
- BMG_BP6_USD: Goods imports
- BFA_BP6_USD: Financial account balance


**Required Parameters:**
- `indicator` (string): BOP indicator code (e.g., BCA_BP6_USD, BXG_BP6_USD)
- `country` (string): ISO3 country code
- `filepath` (string): CSV file save path

**Optional Parameters:**
- `start_year` (string): 
- `end_year` (string): 
- `frequency` (string): A (annual) or Q (quarterly) (default: A) (options: A, Q)

---

### imf_weo_data

**Description:** Get IMF WEO (World Economic Outlook) macroeconomic FORECAST data.

WEO is the IMF&#39;s forward-looking economic outlook dataset. It contains:
- Forecast values for current year and future years
- Some historical data, BUT data for current year and beyond are FORECASTS

ONLY call this tool when the user query EXPLICITLY mentions:
- &#34;forecast&#34;, &#34;outlook&#34;, &#34;projection&#34;, &#34;预测&#34;, &#34;展望&#34;
- &#34;IMF outlook&#34; or &#34;World Economic Outlook&#34;
- Future years beyond confirmed historical data (e.g. &#34;2026 GDP forecast&#34;)

DO NOT call this tool for:
- &#34;actual GDP&#34;, &#34;real GDP&#34;, &#34;historical GDP&#34; — these require confirmed historical data
- &#34;GDP of China 2024&#34; without mention of forecast — use World Bank or other sources
- Any query where the user asks for &#34;actual&#34;, &#34;real&#34; (meaning historical), or &#34;confirmed&#34; data

Common subjects:
- NGDP_RPCH: Real GDP growth rate forecast
- NGDP: Nominal GDP forecast
- PCPIPCH: CPI inflation rate forecast
- LUR: Unemployment rate forecast
- BCA: Current account balance forecast
- GGXCNL: General government net lending forecast


**Required Parameters:**
- `subject` (string): WEO subject code (e.g., NGDP_RPCH, PCPIPCH, LUR)
- `country` (string): ISO3 country code(s), comma-separated for multiple
- `filepath` (string): CSV file save path

**Optional Parameters:**
- `end_year` (string): 
- `start_year` (string): 

---

### imf_fsi_data

**Description:** Get FSI banking sector health metrics.

Common indicators:
- FSANL_PT: Non-performing loans to total loans (%)
- FSKRTC_PT: Regulatory capital to risk-weighted assets (%)
- FSLTL_PT: Liquid assets to short-term liabilities (%)


**Required Parameters:**
- `indicator` (string): FSI indicator code
- `country` (string): ISO3 country code
- `filepath` (string): CSV file save path

**Optional Parameters:**
- `frequency` (string): Q (quarterly) or A (annual) (default: Q) (options: Q, A)
- `start_year` (string): 
- `end_year` (string): 

---

### imf_cofer_data

**Description:** Get COFER reserve currency composition data.

COFER shows how central banks allocate FX reserves across currencies.

Country groups (COFER uses special codes, not ISO3):
- WOO or G001: World (all countries)
- G110: Advanced Economies
- G200: Emerging Market and Developing Economies

Indicators:
- AFXRA: Allocated FX Reserves
- TFXRA: Total FX Reserves
- UFXRA: Unallocated FX Reserves

Currencies:
- CI_USD, CI_EUR, CI_JPY, CI_GBP, CI_CNY
- CI_OTHC: Other currencies
- CI_T: Total across currencies

Transformations:
- NV_USD: Nominal value in USD
- SHRO_PT: Share in percent

Example: Get USD share of world reserves
  imf_cofer_data(indicator=&#34;AFXRA&#34;, country=&#34;WOO&#34;, transformation=&#34;SHRO_PT&#34;)


**Required Parameters:**
- `indicator` (string): COFER indicator: AFXRA (allocated), TFXRA (total), UFXRA (unallocated)
- `country` (string): Country group: WOO/G001 (world), G110 (advanced), G200 (emerging)
- `filepath` (string): CSV file save path

**Optional Parameters:**
- `start_year` (string): Start year (e.g., &#39;2020&#39;). Optional: defaults to current year if not specified (returns ~1 year of data)
- `end_year` (string): End year (e.g., &#39;2024&#39;). Optional: defaults to current year if not specified
- `currency` (string): Optional: Filter by currency (CI_USD, CI_EUR, CI_JPY, CI_CNY, CI_OTHC)
- `transformation` (string): NV_USD (nominal value) or SHRO_PT (share percent) (default: NV_USD) (options: NV_USD, SHRO_PT)
- `frequency` (string): Q (quarterly) or A (annual) (default: Q) (options: Q, A)

---

### imf_qgfs_data

**Description:** Get QGFS government fiscal data.

Common indicators:
- GGR: General government revenue
- GGX: General government expenditure
- GGSB: Government balance (surplus/deficit)
- GGXWDG: Government gross debt


**Required Parameters:**
- `indicator` (string): QGFS indicator code (e.g., GGR, GGX, GGSB)
- `country` (string): ISO3 country code
- `filepath` (string): CSV file save path

**Optional Parameters:**
- `start_year` (string): 
- `end_year` (string): 
- `frequency` (string): Q (quarterly) or A (annual) (default: Q) (options: Q, A)

---

### imf_pip_data

**Description:** Get PIP portfolio investment positions data (formerly CPIS).

PIP shows portfolio investment positions between economies:
- Debt securities
- Equity and investment fund shares

Common indicators:
- P_F3_DIC_USD_P_USD: Debt securities in USD
- P_F51_DIC_USD_P_USD: Equity securities in USD

Use imf_search_indicators to find specific indicator codes.


**Required Parameters:**
- `indicator` (string): PIP indicator code (e.g., P_F3_DIC_USD_P_USD)
- `country` (string): Reporter country ISO3 code (e.g., USA)
- `partner` (string): Counterpart country ISO3 code (e.g., CHN, G001 for World)
- `filepath` (string): CSV file save path

**Optional Parameters:**
- `frequency` (string): A (annual) only (default: A) (options: A)
- `start_year` (string): Start year (e.g., &#39;2020&#39;). Optional: defaults to current year if not specified (returns ~1 year of data)
- `end_year` (string): End year (e.g., &#39;2024&#39;). Optional: defaults to current year if not specified

---

### imf_search_indicators

**Description:** Search IMF indicators by keyword. FIRST STEP of the pipeline.

This tool ONLY searches for indicator codes. It does NOT accept time/date parameters.
Time range (start_year, end_year) should be specified in Step 2 when fetching data.

Pipeline usage:
1. imf_search_indicators(query=&#34;CPI inflation&#34;) → returns &#34;PCPI_IX&#34;
2. imf_ifs_data(indicator=&#34;PCPI_IX&#34;, country=&#34;USA&#34;, start_year=&#34;2020&#34;) → returns data

Note: Query should only contain indicator keywords (e.g., &#34;CPI&#34;, &#34;GDP growth&#34;).
Do NOT include country names or time ranges like &#34;2020-2023&#34; in the query.

Common indicator codes by data type:
- IFS (CPI): PCPI_IX, PCPIFE_IX (core), ENDE_XDC_USD_RATE (exchange)
- BOP: BCA_BP6_USD (current account), BXG_BP6_USD (exports)
- DOTS: TXG_FOB_USD (exports), TMG_CIF_USD (imports)
- DIP (direct investment): INWD_D_AG_FL_ALL (inward), OUTWD_D_AG_FL_ALL (outward)
- PIP (portfolio investment): P_F3_DIC_USD_P_USD (debt), P_F51_DIC_USD_P_USD (equity)
- WEO: NGDP_RPCH (GDP growth), PCPIPCH (inflation), LUR (unemployment)
- FSI: FSANL_PT (NPL ratio), FSKRTC_PT (capital ratio)
- COFER: RAXGFX_USD (total reserves), RAX_USD (USD share)
- QGFS: GGR (revenue), GGX (expenditure), GGSB (balance)
- IRFCL: RA_FX (FX reserves), RA_GOLD (gold), RA_TB (total reserves)


**Required Parameters:**
- `query` (string): Search keywords for indicators. Examples: &#39;CPI&#39;, &#39;inflation&#39;, &#39;exchange rate&#39;, &#39;GDP growth&#39;, &#39;unemployment&#39;, &#39;exports&#39;. Note: Do NOT include country names in the query, use the dataflow parameter to narrow down by category if needed.

**Optional Parameters:**
- `dataflow` (string): Optional: limit search to specific dataflow (CPI, BOP, DOTS, DIP, PIP, WEO, FSI, COFER, QGFS, IRFCL)

---

### imf_ifs_data

**Description:** Get IFS data: CPI, exchange rates, interest rates, reserves.

Use after imf_search_indicators to get specific indicator code.
Common indicators:
- PCPI_IX: Consumer Price Index (all items)
- PCPIFE_IX: Core CPI (excl. food &amp; energy)
- ENDE_XDC_USD_RATE: Exchange rate (LCU per USD)
- FILR_PA: Policy interest rate

Example:
  imf_search_indicators(query=&#34;CPI USA&#34;) → PCPI_IX
  imf_ifs_data(indicator=&#34;PCPI_IX&#34;, country=&#34;USA&#34;, filepath=&#34;/tmp/cpi.csv&#34;)


**Required Parameters:**
- `indicator` (string): IFS indicator code from imf_search_indicators (e.g., PCPI_IX, ENDE_XDC_USD_RATE)
- `country` (string): ISO3 country code (e.g., USA, CHN, DEU, JPN)
- `filepath` (string): CSV file save path

**Optional Parameters:**
- `frequency` (string): Data frequency: M (monthly), Q (quarterly), A (annual) (default: M) (options: M, Q, A)
- `start_year` (string): Start year (e.g., &#39;2020&#39;). Optional: defaults to current year if not specified (returns ~1 year of data)
- `end_year` (string): End year (e.g., &#39;2024&#39;). Optional: defaults to current year if not specified

---

### imf_dots_data

**Description:** Get DOTS bilateral trade data: exports/imports between two countries.

Common indicators:
- TXG_FOB_USD: Goods exports (FOB)
- TMG_CIF_USD: Goods imports (CIF)
- TBG_USD: Trade balance

Example: USA exports to China
  imf_dots_data(indicator=&#34;TXG_FOB_USD&#34;, country=&#34;USA&#34;, partner=&#34;CHN&#34;)


**Required Parameters:**
- `indicator` (string): Trade indicator: TXG_FOB_USD (exports), TMG_CIF_USD (imports), TBG_USD (balance)
- `country` (string): Reporter country ISO3 code (e.g., USA)
- `partner` (string): Partner country ISO3 code (e.g., CHN, WOO for World)
- `filepath` (string): CSV file save path

**Optional Parameters:**
- `frequency` (string): A (annual) or M (monthly) (default: A) (options: A, M)
- `start_year` (string): 
- `end_year` (string): 

---

### imf_irfcl_data

**Description:** Get IRFCL international reserves data: foreign exchange, gold, total reserves.

Common indicators:
- RA_FX: Foreign exchange reserves
- RA_GOLD: Gold reserves
- RA_TB: Total reserves
- RA_RES_PF: Reserve position in IMF


**Required Parameters:**
- `indicator` (string): IRFCL indicator code (e.g., RA_FX, RA_GOLD, RA_TB)
- `country` (string): ISO3 country code
- `filepath` (string): CSV file save path

**Optional Parameters:**
- `frequency` (string): M (monthly) or A (annual) (default: M) (options: M, A)
- `start_year` (string): 
- `end_year` (string): 

---

### imf_dip_data

**Description:** Get DIP direct investment positions data (formerly CDIS).

DIP shows direct investment positions between economies:
- Inward investment (foreign investment in reporting country)
- Outward investment (reporting country investment abroad)

Common indicators:
- INWD_D_AG_FL_ALL: Inward direct investment, all industries
- OUTWD_D_AG_FL_ALL: Outward direct investment, all industries

Use imf_search_indicators to find specific indicator codes.


**Required Parameters:**
- `indicator` (string): DIP indicator code (e.g., INWD_D_AG_FL_ALL, OUTWD_D_AG_FL_ALL)
- `country` (string): Reporter country ISO3 code (e.g., USA)
- `partner` (string): Counterpart country ISO3 code (e.g., CHN, G001 for World)
- `filepath` (string): CSV file save path

**Optional Parameters:**
- `frequency` (string): A (annual) only (default: A) (options: A)
- `start_year` (string): Start year (e.g., &#39;2020&#39;). Optional: defaults to current year if not specified (returns ~1 year of data)
- `end_year` (string): End year (e.g., &#39;2024&#39;). Optional: defaults to current year if not specified

---

