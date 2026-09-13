# fao — describe dump（R18 live，2026-09-13）

> `get_data_source_desc {"name":"fao"}` → HTTP 200，含 `###`，真源。2 API。

- **Description:** Seven explicitly curated FAOSTAT normalized bulk datasets with bounded async download and streaming CSV filtering.

## Available APIs

### fao_search

**Description:** Search or list the seven curated FAOSTAT bulk datasets. This is not the complete FAOSTAT catalogue.

**Optional Parameters:**
- `keyword` (): Optional case-insensitive keyword matched against curated code, name, and description. (default: <nil>)

---

### fao_query

**Description:** Query a curated FAOSTAT dataset by keyword or exact dataset code. Returns a CSV file plus a preview.

**Required Parameters:**
- `filepath` (string): Output CSV file path. A .csv extension is appended if missing.

**Optional Parameters:**
- `code` (): Exact curated FAOSTAT dataset code. Either 'keyword' or 'code' must be provided. (default: <nil>) (options: QCL, PP, FS, MK, RF, QP, PE)
- `area` (): Exact Area label; mutually exclusive with area_code. (default: <nil>)
- `year_code` (): Exact provider Year Code; mutually exclusive with year. (default: <nil>)
- `item` (): Exact Item label; mutually exclusive with item_code. (default: <nil>)
- `element` (): Exact Element label; mutually exclusive with element_code. (default: <nil>)
- `element_code` (): Exact provider Element Code; mutually exclusive with element. (default: <nil>)
- `keyword` (): Dataset code or name keyword. Either 'keyword' or 'code' must be provided. (default: <nil>)
- `area_code` (): Exact FAOSTAT Area Code or M49 code; a leading apostrophe in provider M49 values is ignored. (default: <nil>)
- `year` (): Exact Year label. Strings support provider ranges such as 2000-2002; mutually exclusive with year_code. (default: <nil>)
- `item_code` (): Exact provider Item Code; mutually exclusive with item. (default: <nil>)
- `top` (integer): Maximum records returned in the CSV file. Parsing stops after one additional exact match. (default: 50)
