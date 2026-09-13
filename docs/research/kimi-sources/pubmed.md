# pubmed

**Description:** PubMed is a free biomedical literature database provided by the National Center for Biotechnology Information (NCBI). It provides comprehensive article metadata, abstracts, full-text links and PDF downloads for researchers and clinicians.

## Available APIs

### pubmed_search

**Description:** Search PubMed and fetch normalized article records. Supports free query, title/author/journal filters, date/year ranges, pagination and sorting. At least one of query, title, author, journal, start_date/end_date, or start_year/end_year is required; calling with no search condition is rejected. Abstracts are omitted from results unless include_abstract=true.

**Optional Parameters:**
- `query` (string): Free PubMed query expression
- `title` (string): Filter by article title
- `journal` (string): Filter by journal name
- `end_date` (string): End publication date (YYYY/MM/DD), must be paired with start_date
- `page_size` (integer): Results per page (1-100) (default: 20)
- `start_year` (integer): Legacy inclusive start year; do not combine with start_date/end_date
- `end_year` (integer): Legacy inclusive end year; do not combine with start_date/end_date
- `pmc_only` (boolean): Require the PubMed PMC filter (default: false)
- `author` (string): Filter by author name
- `start_date` (string): Start publication date (YYYY/MM/DD), must be paired with end_date
- `page` (integer): One-based result page (default: 1)
- `sort` (string): Result sort order (default: relevance) (options: relevance, pub_date, first_author, journal)
- `include_abstract` (boolean): Include full abstract text in results; defaults to false to keep the response compact (abstracts are large and may push the preview past the size limit) (default: false)
- `file_path` (string): Optional safe basename saved under /tmp/data_source/pubmed (for example pubmed_search.json)

---

### pubmed_get_article_metadata

**Description:** Resolve a PubMed article by PMID, PMCID, or DOI and retrieve normalized metadata, abstract, identifiers, and links to PubMed/PMC/DOI. Use the returned URLs with a web_fetch tool to retrieve full text or PDF content, or set include_download to check whether the article has already been downloaded to local storage.

**Required Parameters:**
- `id` (string): PMID, PMCID, or DOI of the article

**Optional Parameters:**
- `metadata_file_path` (string): Optional safe basename saved under /tmp/data_source/pubmed (for example pubmed_article.json)
- `include_resources` (boolean): Return OA resource links: HTTPS S3 URLs for pdf/xml/txt (usable directly with a web_fetch tool) plus the raw OA API links (default: false)
- `include_download` (boolean): Return the current local download record (status and files) if the article has a PMCID (default: false)

---

### pubmed_download_article

**Description:** Download open-access resources for a PubMed article by PMID, PMCID, or DOI. Downloads run asynchronously: while status is pending/processing, poll again with check_status=true until a terminal state (success, partial, unavailable, or error). Status unknown means no download has been started (or the previous record expired); call again without check_status to start one. Completed downloads return resource URIs (file://, oss://, or signed HTTPS) that can be read with a web_fetch tool.

**Required Parameters:**
- `id` (string): PMID, PMCID, or DOI of the article

**Optional Parameters:**
- `check_status` (boolean): If true, return the current download status without starting a new download (default: false)
- `content_types` (array): OA resource formats to download. Defaults to [&#34;pdf&#34;] (default: [pdf])

---

