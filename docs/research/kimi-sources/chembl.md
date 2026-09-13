# chembl

**Description:** ChEMBL curated bioactivity database through the official EMBL-EBI REST API (https://www.ebi.ac.uk/chembl/api/data): bioactive molecules with drug-like properties, their biological targets, the assays that measured them, compound-vs-target potency data (IC50/Ki/EC50, pChEMBL), and curated mechanisms of action. Free public API, no key required; keep request rates moderate.

## Available APIs

### chembl_search

**Description:** Full-text search over one ChEMBL resource by name/synonym/description. Required parameters: resource (one of molecule, target, assay) and q (free-text query, e.g. imatinib, ABL1, kinase). Optional parameters: limit (results per page, 1~1000; upstream default applies when omitted) and offset (0-based pagination offset). Returns {&#34;&lt;objects&gt;&#34;: [...], &#34;page_meta&#34;: {...}}; each hit carries the resource&#39;s *_chembl_id plus fields like pref_name, and for targets also target_type and organism. When page_meta.next is not null, more pages exist; raise offset by limit to fetch the next page. Malformed parameters return HTTP 400, surfaced as a structured error.

**Required Parameters:**
- `resource` (string): ChEMBL resource to search: one of molecule, target, assay. (options: molecule, target, assay)
- `q` (string): Free-text query, e.g. imatinib, ABL1, kinase.

**Optional Parameters:**
- `limit` (integer): Results per page, 1~1000 (upstream default applies when omitted).
- `offset` (integer): 0-based pagination offset.

---

### chembl_get

**Description:** Fetch one full record by ChEMBL ID: a molecule (structures, synonyms, properties, max_phase, ...), a target, or an assay. Required parameters: resource (one of molecule, target, assay) and chembl_id (e.g. CHEMBL25 for aspirin, CHEMBL1862 for human ABL1, CHEMBL846551 for an assay). Returns the single object JSON. Molecule records include molecule_structures (canonical_smiles, standard_inchi, standard_inchi_key), molecule_synonyms, molecule_properties, and max_phase (highest clinical phase reached, 4 = approved). Note: molecule, target and assay IDs are different namespaces — CHEMBL25 (a molecule) and CHEMBL1862 (a target) are unrelated objects; always pass an ID to the matching resource. An unknown ChEMBL ID returns HTTP 404, surfaced as a structured error.

**Required Parameters:**
- `resource` (string): ChEMBL resource of the record: one of molecule, target, assay. (options: molecule, target, assay)
- `chembl_id` (string): ChEMBL ID of the record, e.g. CHEMBL25.

---

### chembl_activities

**Description:** List bioactivity measurements for one molecule or one target — the compound-vs-target potency table. Required parameters: exactly one of molecule_chembl_id (activities measured for this compound) or target_chembl_id (activities measured against this target). Optional parameters: limit (results per page, 1~1000) and offset (0-based pagination offset). Returns {&#34;activities&#34;: [...], &#34;page_meta&#34;: {...}}. Each record links molecule_chembl_id + target_chembl_id + assay_chembl_id and carries assay_description, standard_type (IC50 / EC50 / Ki / Kd / ...), standard_value + standard_units (normalized, usually nM), and pchembl_value — the pChEMBL value, defined as -log10 of the molar potency (e.g. IC50 40 nM -&gt; pchembl 7.40); +1 means 10x more potent. Malformed parameters return HTTP 400, surfaced as a structured error.

**Optional Parameters:**
- `molecule_chembl_id` (string): Activities measured for this compound, e.g. CHEMBL941.
- `target_chembl_id` (string): Activities measured against this target, e.g. CHEMBL1862.
- `limit` (integer): Results per page, 1~1000.
- `offset` (integer): 0-based pagination offset.

---

### chembl_mechanisms

**Description:** List curated mechanisms of action for one molecule or one target (drug-level efficacy annotations, e.g. approved-drug MoA). Required parameters: exactly one of molecule_chembl_id or target_chembl_id. Optional parameters: limit (results per page, 1~1000) and offset (0-based pagination offset). Returns {&#34;mechanisms&#34;: [...], &#34;page_meta&#34;: {...}}; each record carries mechanism_of_action (e.g. &#34;Tyrosine-protein kinase ABL inhibitor&#34;) and action_type (e.g. INHIBITOR). Note: only a subset of molecules/targets has curated mechanisms — an empty list is a normal answer, not an error. Malformed parameters return HTTP 400, surfaced as a structured error.

**Optional Parameters:**
- `limit` (integer): Results per page, 1~1000.
- `offset` (integer): 0-based pagination offset.
- `molecule_chembl_id` (string): Mechanisms curated for this compound, e.g. CHEMBL941.
- `target_chembl_id` (string): Mechanisms curated for this target, e.g. CHEMBL1862.

---

