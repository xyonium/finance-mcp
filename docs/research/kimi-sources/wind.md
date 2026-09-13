# wind

**Description:** Wind is a financial datasource providing China and global market data.
This datasource covers the main Wind capability groups:
stock_data, fund_data, index_data, bond_data, financial_docs,
economic_data, and analytics_data.

Notes:
- Use `wind_search_fields` when you need help mapping common stock fields such as
  PE, PB, ROE, market cap, close, volume, and revenue.
- For stock, fund, and index market snapshots, use the `*_price_indicators` tools.
- For historical daily/weekly/monthly prices, use the `*_price` tools.
- For announcements, news, macro data, and broad analytics retrieval, use the
  dedicated document / economic / analytics tools below.


## Available APIs

### wind_get_fund_quote

**Description:** Get intraday minute quote data for exchange-traded funds (ETF/LOF) from Wind. Open-ended mutual funds do not have intraday minute quotes and will return empty data.

**Required Parameters:**
- `ticker` (string): One or multiple Wind codes, comma-separated.
- `file_path` (string): Absolute CSV file path for saving quote data.

**Optional Parameters:**
- `begin` (string): Optional begin marker. Use &#39;LAST&#39; or YYYYMMDD. (default: LAST)
- `end` (string): Optional end marker. Use &#39;LAST&#39; or YYYYMMDD. (default: LAST)

---

### wind_get_company_announcements

**Description:** Search company announcements, annual reports, interim reports, quarterly reports, prospectuses, and regulatory disclosures.

**Required Parameters:**
- `query` (string): Natural-language search query.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `top_k` (integer): Maximum number of returned records. (default: 10)

---

### wind_get_fund_info

**Description:** Get fund profile data such as archive, manager, benchmark, fee, and style.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_fund_performance

**Description:** Get fund performance, ranking, return, and ETF secondary-market performance data.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_index_fundamentals

**Description:** Get index fundamentals such as PE, PB, PS, revenue, profit, and history percentile style queries.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_fund_price

**Description:** Get fund historical price or NAV series from Wind fund kline queries.

**Required Parameters:**
- `ticker` (string): Wind code(s), comma-separated.
- `file_path` (string): Absolute CSV file path for saving time-series data.
- `start_date` (string): Start date in YYYY-MM-DD format.

**Optional Parameters:**
- `price_adj` (string): Price adjustment mode: F (forward), B (backward), N (none). (default: F) (options: F, B, N)
- `end_date` (string): Optional end date in YYYY-MM-DD format. Defaults to today.
- `fields` (string): Optional field list or preset group. Use &#39;price&#39; by default. (default: price)
- `frequency` (string): Sampling frequency. Common values: D, W, M. (default: D) (options: D, W, M)

---

### wind_get_index_price

**Description:** Get index historical price series from Wind index kline queries.

**Required Parameters:**
- `ticker` (string): Wind code(s), comma-separated.
- `file_path` (string): Absolute CSV file path for saving time-series data.
- `start_date` (string): Start date in YYYY-MM-DD format.

**Optional Parameters:**
- `end_date` (string): Optional end date in YYYY-MM-DD format. Defaults to today.
- `fields` (string): Optional field list or preset group. Use &#39;price&#39; by default. (default: price)
- `frequency` (string): Sampling frequency. Common values: D, W, M. (default: D) (options: D, W, M)
- `price_adj` (string): Price adjustment mode: F (forward), B (backward), N (none). (default: F) (options: F, B, N)

---

### wind_get_stock_technicals

**Description:** Get stock technical indicators such as MACD, RSI, KDJ, BOLL, and related market technicals.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_fund_holdings

**Description:** Get fund holdings data such as top holdings, asset allocation, and industry allocation.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_fund_holders

**Description:** Get fund holder structure, subscription/redemption, and scale-change data.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_fund_company_info

**Description:** Get fund-management company profile and manager-team data.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_index_basicinfo

**Description:** Get index profile data such as publisher, base date, base point, and constituent counts.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_bond_basicinfo

**Description:** Get bond profile data such as issue date, size, coupon, term, and redemption profile.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_index_quote

**Description:** Get index intraday minute quote data from Wind.

**Required Parameters:**
- `ticker` (string): One or multiple Wind codes, comma-separated.
- `file_path` (string): Absolute CSV file path for saving quote data.

**Optional Parameters:**
- `begin` (string): Optional begin marker. Use &#39;LAST&#39; or YYYYMMDD. (default: LAST)
- `end` (string): Optional end marker. Use &#39;LAST&#39; or YYYYMMDD. (default: LAST)

---

### wind_get_stock_info

**Description:** Get stock reference data such as security name, exchange, listing date, market type, and Shenwan industry.

**Required Parameters:**
- `ticker` (string): Wind code(s), comma-separated, e.g. &#39;600519.SH,000001.SZ,0700.HK&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `fields` (string): Optional field list or preset group. Use &#39;stock_info&#39; by default. (default: stock_info)
- `trade_date` (string): Optional trade date for cross-sectional queries, format YYYY-MM-DD.

---

### wind_get_stock_financial_index

**Description:** Get curated or user-specified stock financial indicators such as PE, PB, PS, market cap, revenue, net profit, ROE, and gross margin.

**Required Parameters:**
- `ticker` (string): Wind code(s), comma-separated.
- `indicators` (string): Indicator list or preset group. Use &#39;financial_index&#39; or pass comma-separated Wind field names.
- `file_path` (string): Absolute CSV file path for saving financial indicator data.

**Optional Parameters:**
- `report_date` (string): Optional report date, format YYYY-MM-DD.
- `trade_date` (string): Optional trade date, format YYYY-MM-DD.

---

### wind_get_stock_price_indicators

**Description:** Get stock snapshot indicators such as latest price, change, volume, amount, PE, PB, and market cap.

**Required Parameters:**
- `ticker` (string): One or multiple Wind codes, comma-separated.
- `indexes` (string): Comma-separated Wind snapshot indicator names, e.g. &#39;最新成交价,涨跌幅,成交额&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

---

### wind_get_stock_quote

**Description:** Get stock intraday minute quote data from Wind.

**Required Parameters:**
- `ticker` (string): One or multiple Wind codes, comma-separated.
- `file_path` (string): Absolute CSV file path for saving quote data.

**Optional Parameters:**
- `end` (string): Optional end marker. Use &#39;LAST&#39; or YYYYMMDD. (default: LAST)
- `begin` (string): Optional begin marker. Use &#39;LAST&#39; or YYYYMMDD. (default: LAST)

---

### wind_get_financial_news

**Description:** Search financial news, market reports, policy coverage, and related media articles.

**Required Parameters:**
- `query` (string): Natural-language search query.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `top_k` (integer): Maximum number of returned records. (default: 10)

---

### wind_search_economic_indicator

**Description:** Search Wind EDB macroeconomic or industry indicators by natural language and return indicator metadata (name, code, frequency, unit, source) without time-series values.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_query_economic_indicator_data

**Description:** Query time-series values for Wind EDB macroeconomic or industry indicators by natural language or indicator code. Requires either a date range (beginDate + endDate) or observation count.

**Required Parameters:**
- `question` (string): Natural-language metric query or comma-separated Wind indicator codes, e.g. &#39;中国GDP同比&#39; or &#39;M5567876&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `begin_date` (string): Start date in YYYY-MM-DD format. Must be paired with end_date; mutually exclusive with observation.
- `end_date` (string): End date in YYYY-MM-DD format. Must be paired with begin_date; mutually exclusive with observation.
- `observation` (string): Number of recent observations as a numeric string, e.g. &#39;10&#39;. Mutually exclusive with begin_date/end_date.

---

### wind_get_stock_events

**Description:** Get stock corporate-event data such as IPO, refinancing, M&amp;A, dividends, and special treatment events.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_bond_market_data

**Description:** Get bond market and valuation data such as quote, valuation, spread, duration, and convexity.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_search_stocks

**Description:** Screen A-share, Hong Kong, or US stocks with a natural-language query and return matching securities.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_stock_equity_holders

**Description:** Get stock equity structure, top shareholders, actual controller, and related shareholder data.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_financial_data

**Description:** Use Wind analytics_data as a general structured-data fallback when the dedicated stock/fund/index/bond/docs/economic tools do not cover the requested query.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_price

**Description:** Get stock historical OHLCV price series from Wind stock kline queries.

**Required Parameters:**
- `ticker` (string): Wind code(s), comma-separated, e.g. &#39;600519.SH,0700.HK&#39;.
- `file_path` (string): Absolute CSV file path for saving price history.
- `start_date` (string): Start date in YYYY-MM-DD format.

**Optional Parameters:**
- `end_date` (string): Optional end date in YYYY-MM-DD format. Defaults to today.
- `fields` (string): Optional field list or preset group. Use &#39;price&#39; by default. (default: price)
- `frequency` (string): Sampling frequency. Common values: D, W, M. (default: D) (options: D, W, M)
- `price_adj` (string): Price adjustment mode: F (forward), B (backward), N (none). (default: F) (options: F, B, N)

---

### wind_get_index_technicals

**Description:** Get index technical indicators and momentum / volume / volatility metrics.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_bond_issuer_info

**Description:** Get bond issuer data such as issuer identity, industry, region, ownership, and background.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_search_fields

**Description:** Search the curated local Wind stock field catalog before indicator-heavy stock queries.

**Required Parameters:**
- `query` (string): Field keyword, alias, or Chinese description, e.g. &#39;roe&#39;, &#39;市值&#39;, &#39;close&#39;.
- `file_path` (string): Absolute CSV file path for saving matched fields.

**Optional Parameters:**
- `limit` (integer): Maximum number of matched fields to return. (default: 20)

---

### wind_get_fund_financials

**Description:** Get fund financial data such as NAV, profit, income, expense, and dividend information.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_bond_financial_data

**Description:** Get bond issuer financial data such as revenue, profit, assets, and liabilities.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_index_price_indicators

**Description:** Get index snapshot indicators such as latest value, change, advancing/declining counts, and index-level valuation fields.

**Required Parameters:**
- `ticker` (string): One or multiple Wind codes, comma-separated.
- `indexes` (string): Comma-separated Wind snapshot indicator names, e.g. &#39;最新成交价,涨跌幅,成交额&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

---

### wind_get_risk_metrics

**Description:** Get stock risk metrics such as beta, volatility, Sharpe ratio, Jensen alpha, and VaR.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_search_funds

**Description:** Screen mutual funds, ETFs, and LOFs with a natural-language query.

**Required Parameters:**
- `question` (string): Natural-language query, e.g. &#39;筛选沪深市场市值超500亿且连续5日上涨的股票&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

**Optional Parameters:**
- `lang` (string): Language hint for Wind. Default is 中文. (default: 中文) (options: 中文, English)

---

### wind_get_fund_price_indicators

**Description:** Get fund snapshot indicators such as NAV, accumulated NAV, IOPV, discount/premium, and fund size.

**Required Parameters:**
- `ticker` (string): One or multiple Wind codes, comma-separated.
- `indexes` (string): Comma-separated Wind snapshot indicator names, e.g. &#39;最新成交价,涨跌幅,成交额&#39;.
- `file_path` (string): Absolute CSV file path for saving query results.

---

