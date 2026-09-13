# scholar

**Description:** Scholar is a freely accessible web search engine that indexes the full text or metadata 
of scholarly literature across an array of publishing formats and disciplines. It provides 
comprehensive academic research capabilities including paper search, author profiles, and citation analysis.


## Available APIs

### scholar_search

**Description:** Scholar academic paper search with comprehensive features including keyword search, 
author filtering, year range filtering, and time-based sorting. This unified tool supports 
all search functionalities for academic research, literature reviews, and citation analysis.
For queries involving consecutive years, do not make separate queries for each individual year; instead, conduct a single query covering all the consecutive years.


**Required Parameters:**
- `query` (string): Search query string can be a single paper title, a single or multiple research topics, technical keywords, etc. Do not exceed 6 independent keywords if there are multiple keywords.Do not connect them with &#39;OR&#39;.
- `file_path` (string): File path to save the data in CSV format. The complete data will be saved to this file.

**Optional Parameters:**
- `author` (string): Author name, used for filtering papers by a specific author
- `num_results` (integer): The number of returned results, defaulting to 5, with a recommended range of 1 to 50.Don&#39;t exceed 50. (default: 5)
- `start` (integer): Result offset by pages of 10. Must be 0, 10, 20, 30, etc. The default value is 0. (default: 0)
- `hl` (string): Search result language. The default is zh-cn (Chinese), and en (English) is also an option. (default: zh-cn)
- `start_year` (integer): Search starting year
- `end_year` (integer): Search end year
- `sort_by` (string): Sorting method: relevance (by relevance, default) or date (by time) (default: relevance)

---

### scholar_author_info

**Description:** Scholar author information lookup. Obtain detailed academic profiles of researchers, providing basic 
author information, academic metrics, research interests, and major published papers. It includes important 
academic evaluation indicators such as h-index, i10-index, and total citations.


**Required Parameters:**
- `author_name` (string): Author name. It can be in the form of full name or abbreviation, etc.
- `file_path` (string): File path to save the data in CSV format. The complete data will be saved to this file.

---

