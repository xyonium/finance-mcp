# china_nda — describe dump（R18 live，2026-09-13）

> `get_data_source_desc {"name":"china_nda"}` → HTTP 200，含 `###`，真源。4 API。

- **Description:** Search Chinese government public data catalogs from the National Data Administration national registry and selected provincial open-data platforms.

## Available APIs

### china_nda_registry_search

**Description:** Search the National Data Bureau national public data resource registry (sjdj.nda.gov.cn). Results are saved as a CSV file. Each CSV row carries access_code, access_province_code, access_data_type, and access_platform_code columns — pass them through as the parameters of china_nda_registry_access to resolve how to obtain the resource.

**Required Parameters:**
- `filepath` (string): Target file path for the CSV output, e.g. /tmp/china_nda_registry_search.csv.

**Optional Parameters:**
- `industry_code` (string): Industry code. (default: )
- `data_type` (string): Data type: 1=public data resource, 2=product/service, 3=open data. (default: )
- `page` (integer): One-based page number. (default: 1)
- `page_size` (integer): Page size. (default: 10)
- `keyword` (string): Keyword substring for resource name or description. (default: )
- `province_code` (string): Provincial administrative division code, e.g. 130000 for Hebei, 210000 for Liaoning. (default: )

---

### china_nda_registry_access

**Description:** Resolve how to access a registry resource. Use the access_* columns from china_nda_registry_search results as inputs. Returns access guidance (method: open, authorized_operation, or apply), not the raw data.

**Required Parameters:**
- `code` (string): dataRegistCode from registry search results (the access_code CSV column).
- `province_code` (string): Province code from registry search results (the access_province_code CSV column).
- `data_type` (string): Data type from registry search results (the access_data_type CSV column).

**Optional Parameters:**
- `platform_code` (string): Platform code from registry search results (the access_platform_code CSV column); include it when present to route to the correct platform. (default: )

---

### china_nda_province_search

**Description:** Search a provincial open-data or data-bureau catalog by province code. Use china_nda_provinces to get supported codes. Results are saved as a CSV file.

**Required Parameters:**
- `filepath` (string): Target file path for the CSV output, e.g. /tmp/china_nda_province_search.csv.
- `province_code` (string): GB/T 2260 province/region code. Only the codes returned by china_nda_provinces are supported (a limited set of regions); unsupported codes are rejected with PARAMETER_ERROR. For nationwide registry coverage by province, use china_nda_registry_search instead.

**Optional Parameters:**
- `keyword` (string): Keyword for resource name (support varies by province). (default: )
- `page` (integer): One-based page number. (default: 1)
- `page_size` (integer): Page size. (default: 10)

---

### china_nda_provinces

**Description:** List province and region codes supported by china_nda_province_search.
