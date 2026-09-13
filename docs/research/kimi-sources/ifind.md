# ifind

**Description:** iFinD is a financial data platform provided by ifind Inc. 
It offers comprehensive financial analysis across global markets (China A-shares, Hong Kong, US markets) 
including stock information, financial statements (balance sheet, income statement, cash flow with ustomizable time range), business segmentation, 
stock prices, announcements (only A-shared companies), holder information, forecasts (only A-shared companies), and intelligent stock screening with multi-dimensional filtering capabilities.

#ticker format
 A-share: XXXXXX.SH/SZ/BJ (6 digits)
 HK-stock: XXXX.HK (4 digits)
 US-stock: XXXX.O/N/A (1-4 letters)
 For the stock codes of unknown or recently listed companies, search for them first to obtain.


## Available APIs

### ifind_get_stock_financial_index

**Description:** Description: Get financial indicators for a given ticker symbol from ifind, supporting six major financial analysis dimensions:
1. capital_structure - Capital structure leverage, asset composition and long-term solvency (Asset-liability ratio, parent company asset-liability ratio, interest-bearing debt ratio, equity multiplier, current/non-current liability structure, long-term debt composition, etc.)
2. liquidity - Short-term liquidity, cash coverage and immediate solvency 
   (Current ratio, quick ratio, cash ratio, operating cash flow to current liabilities, cash flow ratio, monetary capital to short-term debt, etc.)
3. efficiency - Operating efficiency and turnover metrics (Operating cycle, inventory turnover days, receivables/payables turnover days, current/non-current/fixed/intangible asset turnover days, total asset turnover days, working capital turnover days, etc.)
4. profitability - Profitability level, ROE, EPS and EBITDA coverage (ROE/ROA/ROIC, net/gross profit margin, operating expense ratios, EPS basic/BPS, cash flow per share, EBITDA interest coverage, debt-to-EBITDA ratios, etc.)
5. growth - Scale expansion, revenue growth and asset-liability growth (Operating revenue YoY, operating profit/total profit/net profit YoY,  net interest income growth, operating cost/cash flow YoY, net assets/total liabilities/total assets/receivables/currency capital growth, etc.)
6. cash_coverage - Cash flow coverage for debt and interest, long-term security  (Cash flow interest coverage, operating cash flow to interest-bearing debt/non-current liabilities/net debt, non-financing cash flow to total liabilities, long-term debt to working capital ratio, long-term debt proportion, cash turnover, etc.)


**Required Parameters:**
- `ticker` (string): Ticker(s), comma-separated (max 3). e.g. &#39;AAPL.O,0001.HK,600223.SH&#39;
- `financial_parameter` (string): The time parameters for the company&#39;s financial reports are represented by a four-digit year followed by 0331 (Q1), 0630 (semi-annual), 0930 (Q3), or 1231 (annual), e.g. &#39;2021231&#39;, &#39;20240331&#39;, &#39;20230630&#39;. Report date YYYY-MM-DD (normalized internally)
- `category` (string): Financial indicator category, choose 1 from 6: capital_structure (Capital structure &amp; leverage), liquidity (Short-term liquidity), efficiency (Operating efficiency &amp; turnover), profitability (Profitability &amp; earnings quality), growth (Growth capability), cash_coverage (Cash flow coverage &amp; long-term security) (options: capital_structure, liquidity, efficiency, profitability, growth, cash_coverage)
- `file_path` (string): File path to save data in CSV format.

**Optional Parameters:**
- `format` (string): Optional. Set to &#34;json&#34; to request JSON output. (default: json)

---

### ifind_get_price

**Description:** Description: Get historical price data (stock/index/commodity, etc.) from ifind.
**Note**:
To query the most recent/last stock price or if no specific time is specified, query the stock prices for the past 5 days.
When `adjust` is omitted, A-shares use forward-adjusted prices; HK and US stocks use unadjusted prices.
**Limitations**:
- Maximum 3 tickers per query.
- Maximum date range is 3 years.


**Required Parameters:**
- `ticker` (string): Ticker(s), comma-separated (max 3). Stock: &#39;AAPL.O,600223.SH&#39;; Index: &#39;000001.SH,399001.SZ&#39;; Commodity: &#39;AU9999.SHG&#39;
- `start_date` (string): Start date YYYY-MM-DD. Date range (end_date - start_date) must not exceed 3 years.
- `end_date` (string): End date YYYY-MM-DD. Date range (end_date - start_date) must not exceed 3 years.
- `file_path` (string): File path to save data in CSV format.

**Optional Parameters:**
- `interval` (string): Time interval for price data: &#39;D&#39; (daily), &#39;W&#39; (weekly), &#39;M&#39; (monthly), &#39;Q&#39; (quarterly), &#39;Y&#39; (yearly) (default: D)
- `adjust` (string): Price adjustment type. When omitted, A-shares use &#39;forward&#39; (forward adjustment), while HK and US stocks use &#39;none&#39; (no adjustment). An explicit &#39;forward&#39;, &#39;backward&#39;, or &#39;none&#39; value overrides the market default. (options: forward, backward, none)
- `format` (string): Optional. Set to &#34;json&#34; to request JSON output. (default: json)

---

### ifind_get_stock_announcement

**Description:** Description: Query only A-shared company announcements from ifind for a given ticker within a specified date range.
Returns announcement date, publish time, title, PDF URL, and unique sequence number. If no specific
information is mentioned, the default is the most recent month.


**Required Parameters:**
- `ticker` (string): A-share ticker(s), comma-separated. e.g. &#39;600223.SH,000001.SZ&#39;
- `start_date` (string): The start date of the query period, formatted as &#39;YYYY-MM-DD&#39;
- `end_date` (string): The end date of the query period, formatted as &#39;YYYY-MM-DD&#39;
- `file_path` (string): File path to save data in CSV format.

**Optional Parameters:**
- `format` (string): Optional. Set to &#34;json&#34; to request JSON output. (default: json)

---

### ifind_get_holder_info

**Description:** Description: Get detailed shareholder information for a given ticker symbol from ifind, including shareholder
names, shareholding quantities, ratios, types, changes in shareholder count, institutional holdings, and more.


**Required Parameters:**
- `ticker` (string): Ticker(s), comma-separated (max 3). e.g. &#39;AAPL.O,0001.HK,600223.SH&#39;
- `file_path` (string): File path to save data in CSV format.

**Optional Parameters:**
- `request_time` (string): Optional. The date requested by the user (YYYY-MM-DD). Defaults to today. (default: &lt;nil&gt;)
- `format` (string): Optional. Set to &#34;json&#34; to request JSON output. (default: json)

---

### ifind_get_stock_realtime_price

**Description:** Description: Get real-time stock price data from ifind. Supports A-shares (.SH/.SZ/.BJ), HK stocks (.HK), and US stocks (.US). Mixed tickers across markets are supported and will be queried separately then merged.
This API supports:
1. realtime_price: Real-time fundamental data — A-shares, HK &amp; **US stocks** (.US, e.g. AAPL.US); US returns price, change, change%, volume, amount
2. realtime_tech: Real-time technical indicators (MA5/10/20/60, EXPMA12/50, SAR, BOLL(20,2), BBI, RSI6/12/24, KDJ, MACD, DMI(PDI/MDI/ADX/ADXR), BIAS6/12/24, WR6/10, CCI14, ROC/MAROC, LB, ATR14) — **A-shares only (excluding ETFs and STAR Market 688xxx)**; HK codes are silently skipped when mixed; pure HK/ETF/STAR Market will return an error. K-line interval: when query time minutes are a multiple of 5 (e.g. HH:00, HH:05, HH:10…), returns 5-minute bar indicators; otherwise returns 1-minute bar indicators

**Important Notes**:
- Maximum 3 stock codes per query
- Mixed A-share, HK, and US tickers are supported; queries are split automatically and results merged
- US stocks use `.US` suffix (e.g. AAPL.US, NVDA.US, TSLA.US); only `realtime_price` is supported
- realtime_tech is not supported for HK stocks (pure HK will error; mixed will skip HK)
- HK realtime_price: only available during HK trading hours for current day intraday data; data is not retained after market close
- A-share realtime_price: historical intraday minute K-line data is available at any time, not limited to trading hours
- Time format: YYYY-MM-DD HH:MM:SS (seconds must be 00)
- All stock codes must be comma-separated


**Required Parameters:**
- `ticker` (string): Stock code(s), comma-separated, maximum 3. A-shares (.SH/.SZ/.BJ), HK stocks (.HK), and/or US stocks (.US). Mixed markets are supported (auto-split and merged). e.g. &#39;600223.SH&#39;, &#39;000001.SZ,0700.HK&#39;, &#39;AAPL.US&#39;, &#39;AAPL.US,NVDA.US&#39;
- `file_path` (string): File path to save data in CSV format.

**Optional Parameters:**
- `time` (string): Query time in format YYYY-MM-DD HH:MM:SS. Optional, defaults to current time. Automatically snapped to nearest active trading time for each market.
- `type` (string): Query type:
- realtime_price: Real-time fundamental data — A-shares, HK &amp; **US stocks** (.US) (high_frequency endpoint; HK returns high, low, close, avgPrice, volume, amount, change, sellVolume, buyVolume; US returns price, change, change%, volume, amount)
- realtime_tech: Real-time technical indicators — **A-shares only** (locally computed from ifind K-line data; returns MA5/10/20/60, EXPMA12/50, SAR, BOLL(20,2) mid/upper/lower, BBI, RSI6/12/24, KDJ K/D/J, MACD DIF/DEA, DMI PDI/MDI/ADX/ADXR, BIAS6/12/24, WR6/10, CCI14, ROC/MAROC, LB, ATR14). **Not supported for**: HK stocks (.HK), US stocks (.US), ETFs (e.g. 510300.SH), STAR Market stocks (.SH 688xxx). Using realtime_tech with pure unsupported codes will return an error; mixed queries (A-share + HK/US) will silently skip the unsupported portion.
 (default: realtime_price) (options: realtime_price, realtime_tech)
- `format` (string): Optional. Set to &#34;json&#34; to request JSON output. (default: json)

---

### ifind_get_financial_statements

**Description:** Description: Query one or multiple financial statements(balance_sheet, income_statement, cash_flow). Use &#39;all&#39; to get all three statements at once.


**Required Parameters:**
- `ticker` (string): Ticker(s), comma-separated (max 3). e.g. &#39;600223.SH&#39; or &#39;AAPL.O,0001.HK&#39;
- `statement` (string): Specify &#39;all&#39; for all three statements, or one/more of: balance_sheet, income_statement, cash_flow (aliases: bs, is, cf). Can be comma-separated like &#39;bs,is,cf&#39;
- `financial_parameter` (string): The time parameters for the company&#39;s financial reports are represented by a four-digit year followed by 0331 (Q1), 0630 (semi-annual), 0930 (Q3), or 1231 (annual), e.g. &#39;2021231&#39;, &#39;20240331&#39;, &#39;20230630&#39;. Report date YYYY-MM-DD (normalized internally)
- `file_path` (string): File path to save data in CSV format.

**Optional Parameters:**
- `format` (string): Optional. Set to &#34;json&#34; to request JSON output. (default: json)

---

### ifind_get_forecast

**Description:** Description: Get predicted financial data (net profit, operating revenue and their YoY growth) for give only A-shared
ticker symbols. The tool forces request_time to today internally.


**Required Parameters:**
- `ticker` (string): Ticker(s), comma-separated (max 3). e.g. &#39;600223.SH&#39;
- `file_path` (string): File path to save data in CSV format.

**Optional Parameters:**
- `format` (string): Optional. Set to &#34;json&#34; to request JSON output. (default: json)

---

### ifind_get_stock_info

**Description:** Description: Get stock information for one or multiple tickers from iFinD, across multiple markets
(CN A-shares, HK, US, etc.). Include: Stock abbreviation; Registered capital; Controlling shareholder;
Shareholding ratio of controlling shareholder; Actual controller; Shareholding ratio of actual controller;
Type of actual controller; Type of enterprise; Business scope; Name of main products; Main business;
Competing companies; Comparable companies; Company website; Total number of employees; Total share capital;
Shareholder name; Number of shares held by shareholder, and more.


**Required Parameters:**
- `ticker` (string): Ticker(s), comma-separated (max 3). e.g. &#39;600223.SH&#39; or &#39;AAPL.O,0001.HK&#39;
- `file_path` (string): File path to save data in CSV format.

**Optional Parameters:**
- `request_time` (string): Optional. The date requested by the user, e.g. &#39;2025-09-17&#39; (the tool defaults to today). YYYY-MM-DD format. Defaults to today. (default: &lt;nil&gt;)
- `format` (string): Optional. Set to &#34;json&#34; to request JSON output. (default: json)

---

### ifind_get_stock_business_segmentation

**Description:** Description: Get business segmentation data (by industry/product/region, including revenue, cost, gross
profit) for a given ticker symbol from ifind.


**Required Parameters:**
- `ticker` (string): Ticker(s), comma-separated (max 3). e.g. &#39;600223.SH&#39; or &#39;AAPL.O,0001.HK&#39;
- `financial_parameter` (string): The time parameters for the company&#39;s financial reports are represented by a four-digit year followed by 0331 (Q1), 0630 (semi-annual), 0930 (Q3), or 1231 (annual), e.g. &#39;2021231&#39;, &#39;20240331&#39;, &#39;20230630&#39;. Report date YYYY-MM-DD (normalized internally)
- `file_path` (string): File path to save data in CSV format.

**Optional Parameters:**
- `format` (string): Optional. Set to &#34;json&#34; to request JSON output. (default: json)

---

