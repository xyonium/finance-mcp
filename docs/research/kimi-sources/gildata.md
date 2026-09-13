# gildata

**Description:** Gildata is a financial datasource backed by the HSGT Juyuan / Gildata MCP tool server.
The current internal rollout wraps the standard tool-set edition through Moonshot datasource
infrastructure, so client plugins call agent-gw while the upstream Gildata MCP credential stays
on the datasource backend.

Server-side config:
- Preferred full endpoint variable: GILDATA_MCP_URL
- Or compose from GILDATA_MCP_BASE_URL + GILDATA_MCP_TOKEN
- Optional timeout variable: GILDATA_MCP_TIMEOUT_SEC

Notes:
- This datasource intentionally mirrors the currently validated 8-tool MCP bundle.
- Every tool accepts natural-language financial questions and returns normalized rows with
  vendor, tool_name, query, score, and retrieved_at evidence fields.
- For richer workflow packaging, keep the client plugin on agent-gw; do not expose the upstream
  Gildata token on the client side.


## Available APIs

### gildata_macro_industry_data

**Description:** Query macroeconomic or industry time-series indicators with natural language.

**Required Parameters:**
- `query` (string): Natural-language financial request, for example &#39;筛选净利润增速超过30%且ROE大于15%的消费股&#39;.
- `file_path` (string): Absolute CSV file path for saving normalized result rows.

---

### gildata_financial_research_report

**Description:** Retrieve broker research-report fragments, viewpoints, and report snippets with natural language.

**Required Parameters:**
- `query` (string): Natural-language financial request, for example &#39;筛选净利润增速超过30%且ROE大于15%的消费股&#39;.
- `file_path` (string): Absolute CSV file path for saving normalized result rows.

---

### gildata_announcement_data

**Description:** Retrieve A-share announcement excerpts and disclosure snippets with natural language.

**Required Parameters:**
- `query` (string): Natural-language financial request, for example &#39;筛选净利润增速超过30%且ROE大于15%的消费股&#39;.
- `file_path` (string): Absolute CSV file path for saving normalized result rows.

---

### gildata_news_data_query

**Description:** Retrieve recent news and public-opinion snippets from the Gildata news corpus with natural language.

**Required Parameters:**
- `query` (string): Natural-language financial request, for example &#39;筛选净利润增速超过30%且ROE大于15%的消费股&#39;.
- `file_path` (string): Absolute CSV file path for saving normalized result rows.

---

### gildata_smart_stock_selection

**Description:** Screen stocks with natural-language multi-factor conditions and return structured candidate rows.

**Required Parameters:**
- `query` (string): Natural-language financial request, for example &#39;筛选净利润增速超过30%且ROE大于15%的消费股&#39;.
- `file_path` (string): Absolute CSV file path for saving normalized result rows.

---

### gildata_smart_fund_selection

**Description:** Screen funds with natural-language conditions covering performance, risk, holdings, managers, or companies.

**Required Parameters:**
- `query` (string): Natural-language financial request, for example &#39;筛选净利润增速超过30%且ROE大于15%的消费股&#39;.
- `file_path` (string): Absolute CSV file path for saving normalized result rows.

---

### gildata_smart_fund_manager_selection

**Description:** Screen fund managers with natural-language conditions across scale, performance, and risk-control traits.

**Required Parameters:**
- `query` (string): Natural-language financial request, for example &#39;筛选净利润增速超过30%且ROE大于15%的消费股&#39;.
- `file_path` (string): Absolute CSV file path for saving normalized result rows.

---

### gildata_fin_query

**Description:** Query structured financial, market, fund, bond, index, industry, or industrial-and-commercial data with natural language.

**Required Parameters:**
- `query` (string): Natural-language financial request, for example &#39;筛选净利润增速超过30%且ROE大于15%的消费股&#39;.
- `file_path` (string): Absolute CSV file path for saving normalized result rows.

---

