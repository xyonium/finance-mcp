# uniprot

**Description:** UniProtKB protein sequence and functional-annotation knowledgebase via the official REST API (https://rest.uniprot.org), hosted by the UniProt Consortium. Free, no API key. Covers full entry lookup by accession, search with the UniProt query syntax, and asynchronous cross-database ID Mapping (submit + polled result, up to ~60 s). Search and mapping results are paginated via a synthesized `next_cursor` field.

## Available APIs

### uniprot_idmapping_result

**Description:** Poll a submitted ID Mapping job until it finishes (up to ~60 s) and return the mapping results as `{&#34;results&#34;: [{&#34;from&#34;: ..., &#34;to&#34;: ...}], ...}` (`to` is the mapped ID, or a UniProtKB entry object with `primaryAccession` when mapping into UniProtKB). A synthesized `next_cursor` field (null when there are no more pages) signals truncated pages.

**Required Parameters**

- `job_id` (string): the `jobId` returned by `uniprot_idmapping_submit`.

**Optional Parameters**

- `size` (int): results per page, 1~500 (upstream default applies when omitted).
- `fields` (string): comma-separated field list to shrink payloads, e.g. `accession,id`. Strongly recommended when mapping INTO UniProtKB (`to=UniProtKB`), where each result is a full entry object by default.
- `cursor` (string): pagination cursor — the `next_cursor` value from a previous response.

**Errors**: failed or expired ID Mapping jobs surface as `upstream_error`; all errors are returned as structured errors.

**Required Parameters:**
- `job_id` (string): The `jobId` returned by `uniprot_idmapping_submit`.

**Optional Parameters:**
- `size` (integer): Results per page, 1~500 (upstream default applies when omitted).
- `fields` (string): Comma-separated field list to shrink payloads, e.g. `accession,id`. Strongly recommended when mapping INTO UniProtKB (`to=UniProtKB`), where each result is a full entry object by default.
- `cursor` (string): Pagination cursor — the `next_cursor` value from a previous response.

---

### uniprot_get_entry

**Description:** Fetch one full UniProtKB entry by accession.

**Required Parameters**

- `accession` (string): UniProt accession, e.g. `P04637` (human p53).

Single-entry lookups return the full UniProtKB entry JSON (`primaryAccession`, `proteinDescription`, `genes`, `organism`, `comments`, `features`, `sequence`, ...).

**Errors**: unknown accessions return HTTP 404; all errors are returned as structured errors.

**Required Parameters:**
- `accession` (string): UniProt accession, e.g. `P04637` (human p53).

---

### uniprot_search

**Description:** Search UniProtKB with the UniProt query syntax. Examples: `gene:TP53 AND organism_id:9606`, `accession:P04637`, `protein_name:insulin AND reviewed:true`.

**Required Parameters**

- `query` (string): UniProt query string, e.g. `gene:TP53 AND organism_id:9606`.

**Optional Parameters**

- `size` (int): results per page, 1~500 (upstream default applies when omitted).
- `fields` (string): comma-separated field list to shrink payloads, e.g. `accession,id,gene_names,organism_name,length`.
- `cursor` (string): pagination cursor — the `next_cursor` value from a previous response.

Returns `{&#34;results&#34;: [...]}`. Upstream pagination uses a cursor carried only in the HTTP `Link` header, so the output adds a synthesized `next_cursor` field (null when there are no more pages); pass it back as `cursor` to fetch the next page.

**Errors**: invalid queries return HTTP 400; all errors are returned as structured errors.

**Required Parameters:**
- `query` (string): UniProt query string, e.g. `gene:TP53 AND organism_id:9606`.

**Optional Parameters:**
- `size` (integer): Results per page, 1~500 (upstream default applies when omitted).
- `fields` (string): Comma-separated field list to shrink payloads, e.g. `accession,id,gene_names,organism_name,length`.
- `cursor` (string): Pagination cursor — the `next_cursor` value from a previous response.

---

### uniprot_idmapping_submit

**Description:** Submit an ID Mapping job: convert a batch of IDs between UniProt and an external database. Returns `{&#34;jobId&#34;: ...}`; pass the job id to `uniprot_idmapping_result`.

**Required Parameters**

- `from` (string): source database name, e.g. `Ensembl_Protein`, `UniProtKB_AC-ID`.
- `to` (string): target database name, e.g. `UniProtKB`, `Ensembl`.
- `ids` (string): comma-separated IDs, e.g. `ENSP00000369497` or `P04637,Q9H9S0`.

`from`/`to` must be UniProt ID Mapping database names (closed set, e.g. `UniProtKB`, `UniProtKB_AC-ID`, `UniProtKB-Swiss-Prot`, `Ensembl`, `Ensembl_Protein`, `Ensembl_Transcript`, `GeneID`, `PDB`, `RefSeq_Nucleotide`, `RefSeq_Protein`, ...). Note the exact spellings: it is `Ensembl_Protein`, not `Ensembl_PRO`; `RefSeq_Nucleotide`, not `RefSeq_NT`.

**Errors**: invalid database names return HTTP 400; all errors are returned as structured errors.

**Required Parameters:**
- `from` (string): Source database name, e.g. `Ensembl_Protein`, `UniProtKB_AC-ID`. (options: Allergome, ArachnoServer, Araport, BioCyc, BioGRID, BioMuta, CCDS, CGD, CPTAC, CRC64, ChEMBL, ChiTaRS, ClinPGx, CollecTF, ComplexPortal, ConoServer, DIP, DMDM, DNASU, DisProt, DrugBank, EMBL-GenBank-DDBJ, EMBL-GenBank-DDBJ_CDS, ESTHER, EchoBASE, Ensembl, Ensembl_Genomes, Ensembl_Genomes_Protein, Ensembl_Genomes_Transcript, Ensembl_Protein, Ensembl_Transcript, FlyBase, GI_number, GeneCards, GeneID, GeneReviews, GeneTree, GeneWiki, Gene_Name, GenomeRNAi, GlyConnect, GuidetoPHARMACOLOGY, HGNC, HOGENOM, IDEAL, KEGG, LegioList, Leproma, MEROPS, MGI, MIM, MaizeGDB, OMA, OpenTargets, Orphanet, OrthoDB, PATRIC, PDB, PHI-base, PIR, PeroxiBase, PlantReactome, PomBase, ProteomicsDB, PseudoCAP, REBASE, RGD, Reactome, RefSeq_Nucleotide, RefSeq_Protein, SGD, STRING, SwissLipids, TCDB, TubercuList, UCSC, UniParc, UniPathway, UniProtKB, UniProtKB-Swiss-Prot, UniProtKB_AC-ID, UniRef100, UniRef50, UniRef90, VEuPathDB, VGNC, WBParaSite, WBParaSite_Transcript-Protein, WormBase, WormBase_Protein, WormBase_Transcript, Xenbase, ZFIN, dictyBase, eggNOG, euHCVdb)
- `to` (string): Target database name, e.g. `UniProtKB`, `Ensembl`. (options: Allergome, ArachnoServer, Araport, BioCyc, BioGRID, BioMuta, CCDS, CGD, CPTAC, CRC64, ChEMBL, ChiTaRS, ClinPGx, CollecTF, ComplexPortal, ConoServer, DIP, DMDM, DNASU, DisProt, DrugBank, EMBL-GenBank-DDBJ, EMBL-GenBank-DDBJ_CDS, ESTHER, EchoBASE, Ensembl, Ensembl_Genomes, Ensembl_Genomes_Protein, Ensembl_Genomes_Transcript, Ensembl_Protein, Ensembl_Transcript, FlyBase, GI_number, GeneCards, GeneID, GeneReviews, GeneTree, GeneWiki, Gene_Name, GenomeRNAi, GlyConnect, GuidetoPHARMACOLOGY, HGNC, HOGENOM, IDEAL, KEGG, LegioList, Leproma, MEROPS, MGI, MIM, MaizeGDB, OMA, OpenTargets, Orphanet, OrthoDB, PATRIC, PDB, PHI-base, PIR, PeroxiBase, PlantReactome, PomBase, ProteomicsDB, PseudoCAP, REBASE, RGD, Reactome, RefSeq_Nucleotide, RefSeq_Protein, SGD, STRING, SwissLipids, TCDB, TubercuList, UCSC, UniParc, UniPathway, UniProtKB, UniProtKB-Swiss-Prot, UniProtKB_AC-ID, UniRef100, UniRef50, UniRef90, VEuPathDB, VGNC, WBParaSite, WBParaSite_Transcript-Protein, WormBase, WormBase_Protein, WormBase_Transcript, Xenbase, ZFIN, dictyBase, eggNOG, euHCVdb)
- `ids` (string): Comma-separated IDs, e.g. `ENSP00000369497` or `P04637,Q9H9S0`.

---

