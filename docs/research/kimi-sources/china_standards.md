# china_standards — describe dump（R18 live，2026-09-13）

> `get_data_source_desc {"name":"china_standards"}` → HTTP 200，含 `###`，真源。3 API。

- **Description:** Official Chinese national, industry, local, and association standard discovery, basic metadata, and verified full-text access.

## Available APIs

### china_standards_search

**Description:** Search one official Chinese standards platform by standard number or name. Choose gb, hb, db, or tt explicitly; exact mode normalizes and reranks standard numbers. Each result carries a provider_id field — pass its value as the standard_id parameter of china_standards_detail or china_standards_fetch. Result status is normalized to 现行 (current), 即将实施 (upcoming), 废止 (abolished), or 未知 (unknown); when the provider page lacks explicit status text the status is date-inferred and status_conflict is true.

**Required Parameters:**
- `standard_type` (string): Official standards platform: gb national, hb industry, db local, or tt association standards. (options: gb, hb, db, tt)
- `query` (string): Standard number or name keyword.

**Optional Parameters:**
- `match_mode` (string): keyword keeps provider ordering; exact filters and reranks normalized standard numbers. (default: keyword) (options: keyword, exact)
- `page` (integer): One-based provider page number. (default: 1)
- `page_size` (integer): Requested provider page size. TT is additionally subject to its current 100-record search cap. (default: 10)

---

### china_standards_detail

**Description:** Get official basic metadata for one Chinese standard using the provider id returned by china_standards_search. Status is normalized to 现行/即将实施/废止/未知 and may be date-inferred (status_conflict=true) when the official detail page lacks explicit status text.

**Required Parameters:**
- `standard_type` (string): Official standards platform containing the standard. (options: gb, hb, db, tt)
- `standard_id` (string): Opaque provider id returned by china_standards_search (the provider_id field of each search result).

---

### china_standards_fetch

**Description:** Resolve and verify an officially published PDF for a GB or TT standard. Returns verified access metadata, not clauses or a server-local file path.

**Required Parameters:**
- `standard_type` (string): gb or tt. HB and DB currently expose metadata but no supported official full-text endpoint. (options: gb, hb, db, tt)
- `standard_id` (string): Opaque provider id returned by china_standards_search (the provider_id field of each search result).
