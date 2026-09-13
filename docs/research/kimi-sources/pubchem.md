# pubchem

**Description:** PubChem computed properties, CID resolution, synonyms, and 2D fingerprint similarity search via the official PUG-REST API (https://pubchem.ncbi.nlm.nih.gov/rest/pug, NIH/NCBI). Free, no API key. PubChem is the largest open chemistry database (100M+ compounds). PUG-REST applies dynamic rate limiting: HTTP 429/503 is retried automatically (bounded, honoring Retry-After).

## Available APIs

### pubchem_similarity

**Description:** Fast 2D fingerprint similarity search (Tanimoto over PubChem subgraph fingerprints): find compounds structurally similar to a query SMILES. Returns the matching CID list, most-similar first.

Required parameters:
- `smiles` (string): query structure as SMILES, e.g. `CC(=O)Oc1ccccc1C(=O)O`. The SMILES is sent to PUG-REST in a POST form body automatically, because the server does not decode percent-encoded `/` or `\` in the URL path; SMILES with special characters (`()=#[]+@/\`), including cis/trans stereochemistry markers like `C/C=C/C`, can be passed verbatim.

Optional parameters:
- `threshold` (int): minimum Tanimoto similarity in percent, 0~100 (upstream default 90). Higher = stricter.
- `max_records` (int): maximum number of CIDs to return, 1~10000 (upstream default applies when omitted).

Errors: unknown structures return HTTP 404 (`PUGREST.NotFound`); invalid parameter values return HTTP 400. Both are surfaced as structured errors. PUG-REST applies dynamic rate limiting: HTTP 429/503 (`PUGREST.ServerBusy`) is retried automatically (up to 2 retries, honoring the `Retry-After` header when present).

**Required Parameters:**
- `smiles` (string): Query structure as SMILES, e.g. `CC(=O)Oc1ccccc1C(=O)O`.

**Optional Parameters:**
- `threshold` (integer): Minimum Tanimoto similarity in percent, 0~100 (upstream default 90). Higher = stricter.
- `max_records` (integer): Maximum number of CIDs to return, 1~10000 (upstream default applies when omitted).

---

### pubchem_get_properties

**Description:** Fetch computed properties for one or more compounds, addressed by CID list, name, SMILES, or InChIKey.

Required parameters:
- `by` (string): how to address the compound(s). One of `cids` (one CID or a comma-separated CID list, e.g. `2244,5291`), `name` (compound name, e.g. `aspirin`), `smiles` (a SMILES string, e.g. `CC(=O)Oc1ccccc1C(=O)O`), `inchikey` (an InChIKey, e.g. `BSYNRYMUTXBXSQ-UHFFFAOYSA-N`).
- `value` (string): the identifier value matching `by`.

Optional parameters:
- `properties` (string): comma-separated PubChem property names. Default: MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,IUPACName,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount. Other valid names include ExactMass, MonoisotopicMass, Charge, HeavyAtomCount, Complexity, Title, ... (unknown names are rejected by the upstream with HTTP 400).

Returns `{&#34;PropertyTable&#34;: {&#34;Properties&#34;: [{CID, ...}]}}`. Note: requesting `CanonicalSMILES` yields a `ConnectivitySMILES` key and `IsomericSMILES` yields a `SMILES` key in the response (PubChem renamed these properties). SMILES inputs (`by=smiles`) are sent to PUG-REST in a POST form body automatically, because the server does not decode percent-encoded `/` or `\` in the URL path; SMILES with special characters (`()=#[]+@/\`), including cis/trans stereochemistry markers like `C/C=C/C`, can be passed verbatim in `value`.

Errors: unknown names / structures return HTTP 404 (`PUGREST.NotFound`); invalid property names return HTTP 400. Both are surfaced as structured errors. PUG-REST applies dynamic rate limiting: HTTP 429/503 (`PUGREST.ServerBusy`) is retried automatically (up to 2 retries, honoring the `Retry-After` header when present).

**Required Parameters:**
- `by` (string): How to address the compound(s): `cids` (one CID or a comma-separated CID list, e.g. `2244,5291`), `name` (compound name, e.g. `aspirin`), `smiles` (a SMILES string, e.g. `CC(=O)Oc1ccccc1C(=O)O`), or `inchikey` (an InChIKey, e.g. `BSYNRYMUTXBXSQ-UHFFFAOYSA-N`). (options: cids, name, smiles, inchikey)
- `value` (string): The identifier value matching `by`.

**Optional Parameters:**
- `properties` (string): Comma-separated PubChem property names. Default: MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,IUPACName,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount. Other valid names include ExactMass, MonoisotopicMass, Charge, HeavyAtomCount, Complexity, Title, ... (unknown names are rejected by the upstream with HTTP 400). (default: MolecularFormula,MolecularWeight,CanonicalSMILES,IsomericSMILES,IUPACName,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,RotatableBondCount)

---

### pubchem_to_cids

**Description:** Resolve a compound name, SMILES, or InChIKey to PubChem CID(s). Use this first when the user has a name or structure and later calls need CIDs.

Required parameters:
- `by` (string): one of `name`, `smiles`, `inchikey`.
- `value` (string): the identifier value matching `by`.

Returns `{&#34;IdentifierList&#34;: {&#34;CID&#34;: [...]}}`. SMILES inputs (`by=smiles`) are sent to PUG-REST in a POST form body automatically, because the server does not decode percent-encoded `/` or `\` in the URL path; SMILES with special characters (`()=#[]+@/\`), including cis/trans stereochemistry markers like `C/C=C/C`, can be passed verbatim in `value`.

Errors: unknown names / structures return HTTP 404 (`PUGREST.NotFound`), surfaced as a structured error. PUG-REST applies dynamic rate limiting: HTTP 429/503 (`PUGREST.ServerBusy`) is retried automatically (up to 2 retries, honoring the `Retry-After` header when present).

**Required Parameters:**
- `by` (string): How to address the compound: `name`, `smiles`, or `inchikey`. (options: name, smiles, inchikey)
- `value` (string): The identifier value matching `by`.

---

### pubchem_get_synonyms

**Description:** List synonyms (common names, CAS registry numbers, IUPAC-like names, brand names) for a compound.

Required parameters:
- `by` (string): one of `cids` (one CID or a comma-separated CID list), `name`.
- `value` (string): the identifier value matching `by`.

Returns `{&#34;InformationList&#34;: {&#34;Information&#34;: [{CID, &#34;Synonym&#34;: [...]}]}}`; the synonym list can be long (common names, CAS numbers, drug brand names, depositor-supplied names).

Errors: unknown names return HTTP 404 (`PUGREST.NotFound`), surfaced as a structured error. PUG-REST applies dynamic rate limiting: HTTP 429/503 (`PUGREST.ServerBusy`) is retried automatically (up to 2 retries, honoring the `Retry-After` header when present).

**Required Parameters:**
- `by` (string): How to address the compound: `cids` (one CID or a comma-separated CID list) or `name`. (options: cids, name)
- `value` (string): The identifier value matching `by`.

---

