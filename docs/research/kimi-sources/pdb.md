# pdb

**Description:** RCSB Protein Data Bank (https://www.rcsb.org): experimentally determined 3D structures of proteins, nucleic acids, and their complexes. Free public API, no key required. Two upstream services: the Data API (https://data.rcsb.org/rest/v1/core — entry/entity JSON by ID) and the Search API (https://search.rcsb.org/rcsbsearch/v2/query — POST JSON queries). Entity ids are 1-based numbers within an entry and are NOT chain ids; discover valid entity ids via pdb_get_entry&#39;s rcsb_entry_container_identifiers before calling the entity endpoints.

## Available APIs

### pdb_get_entry

**Description:** Fetch one entry&#39;s core JSON from the RCSB PDB Data API: title (`struct.title`), experimental method (`exptl[].method`), resolution (`rcsb_entry_info.resolution_combined`), authors (`audit_author`), release dates (`rcsb_accession_info`), cell, citation, and container identifiers. The returned `rcsb_entry_container_identifiers` lists the entry&#39;s `polymer_entity_ids` / `non_polymer_entity_ids` — use them to discover valid entity ids before calling pdb_get_polymer_entity / pdb_get_ligand. A PDB ID is 4 characters and starts with a digit (`1TUP`, `4HHB`); case is normalized to upper-case. Errors: an unknown PDB ID returns HTTP 404, surfaced as a structured error.

**Required Parameters:**
- `pdb_id` (string): 4-character PDB ID starting with a digit, e.g. `1TUP` (p53-DNA complex); case is normalized to upper-case.

---

### pdb_get_polymer_entity

**Description:** Fetch one polymer entity of a PDB entry from the RCSB PDB Data API: molecule type (`entity_poly.type`), one-letter sequence (`entity_poly.pdbx_seq_one_letter_code`), chains (`entity_poly.pdbx_strand_id`), description (`rcsb_polymer_entity.pdbx_description`), source organism (`rcsb_entity_source_organism`), and UniProt cross-references when present. `entity_id` is the 1-based polymer entity number, NOT a chain id — one polymer entity may map to several chains (1TUP entity 3 is the p53 protein, chains A/B/C; entities 1/2 are the DNA chains). Discover valid entity ids via pdb_get_entry&#39;s `rcsb_entry_container_identifiers.polymer_entity_ids`. Errors: an unknown PDB ID or entity id returns HTTP 404, surfaced as a structured error.

**Required Parameters:**
- `pdb_id` (string): 4-character PDB ID starting with a digit, e.g. `1TUP`.
- `entity_id` (integer): 1-based polymer entity number, e.g. `3` (1TUP&#39;s p53 protein; entities 1/2 are the DNA chains). NOT a chain id.

---

### pdb_get_ligand

**Description:** Fetch one non-polymer entity (ligand / ion) of a PDB entry from the RCSB PDB Data API: component id (`pdbx_entity_nonpoly.comp_id`), name (`pdbx_entity_nonpoly.name`), chemical component details (`chem_comp`), and description. Example: 1STP entity 2 is biotin (BTN). `entity_id` is the 1-based non-polymer entity number — polymer and non-polymer entities of the same entry are numbered independently. Discover valid entity ids via pdb_get_entry&#39;s `rcsb_entry_container_identifiers.non_polymer_entity_ids`. Errors: an unknown PDB ID or entity id returns HTTP 404, surfaced as a structured error.

**Required Parameters:**
- `pdb_id` (string): 4-character PDB ID starting with a digit, e.g. `1STP`.
- `entity_id` (integer): 1-based non-polymer entity number, e.g. `2` (1STP&#39;s biotin).

---

### pdb_search

**Description:** Text search over RCSB PDB entries (POST to the Search API). Returns entry identifiers matching one attribute condition as `{&#34;total_count&#34;: N, &#34;result_set&#34;: [{&#34;identifier&#34;: &#34;&lt;PDB ID&gt;&#34;, &#34;score&#34;: ...}]}` (up to `size` rows; `total_count` is the full match count); feed the identifiers into pdb_get_entry for details. `operator` is a closed set: exact_match, contains_words, contains_phrase, greater, less, exists — every operator except `exists` requires `value`. Verified attributes: `struct.title` (entry title), `rcsb_entity_source_organism.scientific_name` (source organism), `exptl.method` (experimental method), `rcsb_accession_info.initial_release_date` (release date, use an ISO date string like `2024-01-01`), `rcsb_entry_info.resolution_combined` (resolution in Angstrom, use a number). Errors: an invalid search attribute returns HTTP 400, surfaced as a structured error.

**Required Parameters:**
- `attribute` (string): Entry attribute to match. Verified examples: `struct.title` (entry title), `rcsb_entity_source_organism.scientific_name` (source organism), `exptl.method` (experimental method), `rcsb_accession_info.initial_release_date` (release date), `rcsb_entry_info.resolution_combined` (resolution in Angstrom).
- `operator` (string): One of the closed operator set; every operator except `exists` requires `value`. (options: exact_match, contains_words, contains_phrase, greater, less, exists)

**Optional Parameters:**
- `value` (): Value to compare against (string or number); required for every operator except `exists`. Use a number for numeric attributes (`rcsb_entry_info.resolution_combined`) and an ISO date string like `2024-01-01` for dates.
- `size` (integer): Rows to return, 1~100 (default 10). (default: 10)

---

