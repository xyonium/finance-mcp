# arxiv

**Description:** Arxiv is a free preprint server for scientific papers providing comprehensive data and tools for researchers, clinicians, and general users.
Supports paper search, download, conversion to markdown, and local storage management with advanced filtering capabilities.


## Available APIs

### search_papers

**Description:** Search for papers on arXiv with advanced filtering. 
Recommended to use absolute path to save the arXiv search results to. 
File content is in csv format. Example: /Path/to/example.csv


**Required Parameters:**
- `query` (string): The search query. Will be enhanced with field specifiers if needed for better results.Do not use more than 6 words or connect them with &#39;OR&#39;.
- `file_path` (string): Absolute path to save the search results. File content is in CSV format. 

**Optional Parameters:**
- `max_results` (integer): Maximum number of results to return (default: 10)
- `date_from` (string): Start date for search range (YYYY-MM-DD format). Defaults to 2023-01-01 if not specified (default: 2023-01-01)
- `date_to` (string): End date for search range (YYYY-MM-DD format). Defaults to current date if not specified when date_from is provided (default: &lt;nil&gt;)
- `categories` (array): arXiv categories to filter by (default: &lt;nil&gt;)

---

### download_paper

**Description:** Download a paper from arXiv and convert it to markdown format with asynchronous conversion support.
Supports status checking for ongoing conversions and provides detailed progress information.


**Required Parameters:**
- `paper_id` (string): The arXiv ID of the paper to download (e.g., &#39;2004.10934&#39; or &#39;cs.AI/0601026&#39;)

**Optional Parameters:**
- `check_status` (boolean): If true, only check conversion status without downloading (default: false)

---

### read_paper

**Description:** Read the full content of a stored paper in markdown format.
Paper must be previously downloaded using the download_paper tool.


**Required Parameters:**
- `paper_id` (string): The arXiv ID of the paper to read

---

### list_papers

**Description:** List all existing papers available as resources.
Shows comprehensive information for all downloaded papers including titles, authors, and abstracts.


**Required Parameters:**
- `file_path` (string): Absolute path to save the paper list. File content is in csv format

---

