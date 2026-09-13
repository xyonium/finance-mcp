# world_bank_open_data

**Description:** A free global development data platform provided by the World Bank. It provides access to all countries in the world and 29,000+ indicators covering economic, social, and environmental metrics including GDP,GNP, population, poverty rates, unemployment, trade, inflation, education, health, and environmental data with time series data from 1960 to present.All national-level data are applicable.

## Available APIs

### world_bank_open_data

**Description:** A free global development data platform provided by the World Bank. Query actual data for 29,000+ indicators covering economic, social, and environmental metrics including GDP,GNP, population, poverty rates, unemployment, trade, inflation, education, health, and environmental data. 

This tool is for PRECISE DATA QUERIES using exact indicator codes.
If you need to find indicator codes, use &#39;world_bank_search_indicators&#39; tool first.

IMPORTANT: For complex derived indicators that require calculation from multiple components (e.g., Trade Balance = Exports - Imports, Current Account Balance = Trade Balance + Net Income + Net Transfers), the World Bank does not provide direct indicators. You need to query the component indicators separately and perform calculations yourself.

Supports individual country queries (CHN, USA), global comparisons (all), and comprehensive country/indicator lists, with time series data from 1960 to present.


**Required Parameters:**
- `country` (string): Single or multiple ISO three-letter codes for a country or multiple countries, separated by commas, such as:CHN, USA; If you need global countries, enter &#39;all&#39; (global);If you need to obtain the list of countries, enter &#39;list&#39;
- `indicator` (string): A single or multiple indicator codes from the World Development Indicators database of the World Bank. Multiple codes should be separated by commas. If you need global countries, input &#39;all&#39; (global). Input &#39;list&#39; to obtain a list of all indicators. The code adopts a multi-segment dot-separated structure, which is &#39;[Main Topic Category].[Subtopic/Indicator Category].[Specific Indicator].[Dimension (optional)].[Unit (optional)].[Frequency/Type/Subdivision and Other Modifiers (optional)]&#39;. Each segment consists of two to three capital letters. The main category is the subject area, for example： AG	Agriculture BG	Balance of payments:gross BM	Balance of payments:imports, payments (credit) BN	Balance of payments:net BX	Balance of payments:exports, receipts (debit) CM	Capital markets DC	Debt:aid flows from DAC DT	Debt:external EA	Environment:agriculture EE	Environment:emissions EG	Environment:energy EN	Environment:general EP	Environment:prices ER	Environment:resources FA	Financial:monetary authorities FB	Financial:bank (miscellaneous) FD	Financial:deposit money banks FI	Financial:international liquidity FM	Financial:monetary survey etc. Sub-topic/indicator category is, for example ACS	Access ADJ	Adjusted savings ADM	Admission ADO	Adolescent ADT	Adult AGR	Agriculture AID	Aid AIR	Air transport ALC	Alcohol AMA	Principal adjustments AMD	Principal due AMN	Principal due on new debt AMP	Amphibian AMR	Principal due on arrears/restructurings per DDSR AMT	Amortization ANM	Anemia (or animal) ANN	Annual ARA	Principal arrears reductions/prepayments ASC	Asset period change etc. Dimensions, for example: AG27	Age 27 AG28	Age 28 AG29	Age 29 AGEF	Age of final grade ADVN	Advanced (education) AGES	Ages AGGD	Aggregate direct AGRF	Crops and forest products AGRI	Agricultural FWIN	Freshwater:industry FWTL	Freshwater:total FXAI	Other factor payments etc. Units, for example: K1	Kilometers K2	Square kilometers K3	Cubic kilometers K6	Million kilometers KD	Constant US$ KG	Kilograms KH	Kilowatt hours KM	Kilometers KN	Constant local currency units KO	Kilogram of oil equivalent KT	Kiloton etc 
- `filepath` (string): CSV file save path (required). Data will be saved to this file path with a data preview (up to 50 rows).

**Optional Parameters:**
- `date_range` (string): If the user requires a specific time range, the format should be:YYYY:YYYY. For example:2019:2024. If left blank, all available years will be retrieved.
- `most_recent` (integer): If the user mentions the last n years, then retrieve the data for the last N years. For example, 5 indicates the last 5 years. This option is mutually exclusive with the &#39;date_range&#39; parameter.
- `language` (string): Return language, supported:en (English), zh (Chinese). Default:zh (default: zh)

---

### world_bank_search_indicators

**Description:** Search and browse World Bank Open Data indicators to find the right indicator codes for data queries. 

IMPORTANT USAGE NOTES:
- DO NOT include country names in search queries. For example, if you want to search for &#39;Rural land area&#39;, don&#39;t include &#39;China&#39; in the search query.
- Use MULTIPLE keywords in one search for efficiency 
- Use this tool BEFORE querying actual data to find the correct indicator codes

Examples: &#39;GDP&#39;, &#39;GDP,population,unemployment&#39;, &#39;trade,export,import&#39;, &#39;education,health,poverty&#39;


**Required Parameters:**
- `query` (string): Search query for economic/social indicators ONLY (no country names). Use multiple keywords separated by commas for efficiency. Examples: &#39;GDP,population,inflation&#39;, &#39;trade,export,import&#39;, &#39;education,health,unemployment&#39;. Each keyword returns up to 4 most relevant indicators.

---

