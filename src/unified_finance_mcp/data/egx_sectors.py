"""EGX (Egyptian Exchange) sector classification (vendored from tradingview-mcp).

Vendored: the symbol->sector ``EGX_SECTORS`` map, ``SECTOR_DISPLAY_NAMES``,
``get_sector`` / ``get_symbols_by_sector`` / ``get_all_sectors`` /
``get_currency`` and the USD-listing set. Per the Task 14 spec the
``EGX_SECTOR_META`` market-cap snapshot is NOT vendored — the egx_market
sector_scan/screener actions recompute everything live from TradingView data
(Query().set_markets("egypt") / get_multiple_analysis), no hardcoded results.
"""
from __future__ import annotations

EGX_SECTORS: dict[str, set[str]] = {

    "banks": {
        "CANA",  # Suez Canal Bank
        "EXPA",  # Export Development Bank
        "CIEB",  # Credit Agricole Egypt
        "SAUD",  # Al Baraka Bank
        "UBEE",  # The United Bank
        "EGBE",  # Egyptian Gulf Bank
        "HDBK",  # Housing & Development Bank
        "FAIT",  # Faisal Islamic Bank
        "FAITA", # Faisal Islamic Bank (USD)
        "QNBE",  # QNB Alahli
        "COMI",  # CIB
        "ADIB",  # ADIB Egypt
    },

    "basic_resources": {
        "ATQA",  # Misr National Steel - Ataqa
        "MICH",  # Misr Chemical Industries
        "KZPC",  # Kafr El Zayat Pesticides
        "FERC",  # Ferchem Misr for Fertilizers & Chemicals
        "ASCM",  # ASEC Company For Mining - ASCOM
        "SKPC",  # Sidi Kerir Petrochemicals - SIDPEC
        "ISMQ",  # Iron And Steel for Mines and Quarries
        "EGCH",  # Egyptian Chemical Industries (Kima)
        "EFIC",  # Egyptian Financial & Industrial
        "IRON",  # Egyptian Iron & Steel
        "ALUM",  # Arab Aluminum
        "MFPC",  # Misr Fertilizers Production Company - Mopco
        "EGAL",  # Egypt Aluminum
        "ABUK",  # Abou Kir Fertilizers
    },

    "healthcare_and_pharma": {
        "MIPH",  # Minapharm Pharmaceuticals
        "RMDA",  # Rameda
        "BIOC",  # Glaxo Smith Kline	
        "AXPH",  # Alexandria Pharmaceuticals
        "OCPH",  # October Pharma
        "APPC",  # Arab Pharmaceuticals
        "SIPC",  # Sabaa International Company
        "MCRO",  # Macro Group Pharmaceuticals
        "ISPH",  # Ibnsina Pharma
        "SPMD",  # Speed Medical
        "CPCI",  # Cairo Pharmaceuticals
        "MEDP",  # Medical Packaging Company
        "PRMH",  # Premium HealthCare Group
        "MPCI",  # Memphis Pharmaceuticals
        "NIPH",  # El-Nile Pharmaceuticals
        "NINH",  # Nozha International Hospital
        "AMES",  # Alexandria New Medical Center
        "CLHO",  # Cleopatra Hospital Company
        "PHAR",  # EIPICO
    },

    "industrial_goods_and_services": {
        "ENGC",  # El Arabia Engineering Industries
        "MBEN",  # M.B Engineering
        "SWDY",  # Elsewedy Electric
        "GDWA",  # Gadwa For Industrial Development
        "DTPP",  # Delta Printing & Packaging
        "ELEC",  # Electro Cable Egypt
        "GBCO",  # GB Corp
    },

    "real_estate": {
        "RREI",  # Arab Real Estate Investment CO.-ALICO
        "MAAL",  # Egyptian Gulf Marseilia
        "ELSH",  # El Shams Housing
        "AREH",  # Egyptian Real Estate Group
        "ORHD",  # Orascom Development Egypt
        "GIHD",  # Gharbia Islamic Housing Development
        "MASR",  # Madinet Masr
        "OCDI",  # SODIC
        "EMFD",  # Emaar Misr
        "TMGH",  # Talaat Moustafa Group
        "PHDC",  # Palm Hills
        "HELI",  # Heliopolis Housing
        "ZMID",  # Zahraa Maadi
        "ADRI",  # Arab Developers Holding
        "IDRE",  # Ismailia Development
        "AMER",  # Amer Group
        "OBRI",  # El Obour Real Estate
        "PRDC",  # Pioneers Properties
        "UEGC",  # ElSaeed Contracting
        "ELKA",  # El Kahera Housing
    },

    "travel_and_leisure": {
        "MHOT",  # Misr Hotels
        "MMAT",  # Marsa Marsa Alam For Tourism Development
        "SDTI",  # Sharm Dreams Co. for Tourism Investment
        "ROTO",  # Rowad Tourism (Al Rowad)
        "ELWA",  # El Wadi For International and Investment Development
        "PHTV",  # Pyramisa Hotels
        "EGTS",  # Egyptian for Tourism Resorts
        "TRTO",  # TransOceans Tours
        "RTVC",  # Remco for Touristic Villages Construction
    },

    "utilities": {
        "EGAS", # Natural Gas & Mining Project (Egypt Gas)
        "TAQA", # Taqa Arabia
    },

    "it_media_and_communication": {
        "DGTZ",  # Digitize for Investment And Technology
        "MPRC",  # Egyptian Media Production City
        "EGSA",  # Egyptian Satellites (NileSat) (USD)
        "EFIH",  # E-finance
        "RACC",  # Raya Customer Experience
        "OIH",   # Orascom Investment Holding
        "FWRY",  # Fawry
        "ETEL",  # Telecom Egypt
    },

    "food_beverages_and_tobacco": {
        "ELNA",  # El Nasr For Manufacturing Agricultural Crops
        "KRDI",  # Al Khair River For Development Agricultural Investment & Environmental Services
        "GSSC",  # General Silos & Storage
        "CEFM",  # Middle Egypt Flour Mills
        "SUGR",  # Delta Sugar
        "ADPC",  # The Arab Dairy Products Co. Arab Dairy - Panda
        "LUTS",  # Lotus For Agricultural Investments And Development
        "GGRN",  # Gogreen for Agricultural Investment
        "INFI",  # Ismailia National Food Industries
        "ISMA",  # Ismailia Misr Poultry
        "MPCO",  # Mansourah Poultry
        "POUL",  # Cairo Poultry
        "EPCO",  # Egypt for Poultry
        "EAST",  # Eastern Company
        "ZEOT",  # Extracted Oils
        "MILS",  # North Cairo Mills
        "AFMC",  # Alexandria Flour Mills
        "UEFM",  # Upper Egypt Flour Mills
        "WCDF",  # Middle & West Delta Flour Mills
        "SCFM",  # South Cairo & Giza Mills & Bakeries
        "COSG",  # Cairo Oils & Soap
        "MOSC",  # Misr Oils & Soap
        "AJWA",  # AJWA for Food Industries company Egypt
        "SNFC",  # Sharkia National Food
        "DOMT",  # Arabian Food Industries DOMTY
        "NEDA",  # Northern Upper Egypt Development & Agricultural Production
        "JUFO",  # Juhayna Food Industries
        "EFID",  # Edita Food Industries S.A.E
        "OLFI",  # Obour Land For Food Industries
        "EDFM",  # East Delta Flour Mills
    },

    "energy_and_support_services": {
        "MOIL",  # Maridive & Oil Services
        "AMOC",  # Alexandria Mineral Oils Company
    },

    "trade_and_distributors": {
        "IFAP",  # International Agricultural Products
        "SMFR",  # Samad Misr - EGYFERT
        "ICFC",  # International Company For Fertilizers & Chemicals
        "MFSC",  # Misr Duty Free Shops
        "GMCI",  # GMC Group
        "MTIE",  # MM Group For Industry And International Trade
        "GOUR",  # Gourmet Egypt.Com Foods
    },

    "shipping_and_transportation": {
        "ETRS",  # Egyptian Transport (EGYTRANS)
        "ALCN",  # Alexandria Containers and Goods
        "CSAG",  # Canal Shipping Agencies
    },

    "education_services": {
        "MOED",  # The Egyptian Modern Education Systems
        "SCTS",  # Suez Canal Company For Technology Settling
        "TALM",  # Taaleem Management Services
        "CAED",  # Cairo Educational Services
        "CIRA",  # Cairo For Investment And Real Estate Developments (CIRA Edu)
    },

    "non_bank_financial_services": {
        "ACTF",  # Act Financial
        "AREF",  # Egyptians Real Estate Fund Certificates
        "AIH",   # Arabia Investments Holding
        "NAHO",  # Naeem Holding
        "RAYA",  # Raya Holding For Financial Investments
        "CICH",  # CI Capital Holding
        "BTFH",  # Beltone Holding
        "KWIN",  # El Kahera El Watania Investment
        "AMIA",  # Arab Moltaka Investments
        "OSOL",  # Osool ESB Securities Brokerage
        "OBRI",  # O B Financial Holding
        "AFDI",  # El Ahli Investment and Development
        "VALU",  # U Consumer Finance (ValU)
        "AIDC",  # Arabia for Investment and Development
        "ICLE",  # IncoLEASE
        "EAC",   # Themar Brokerage
        "PRMH",  # Prime Holding
        "ASPI",  # Aspire Capital
        "MOIN",  # Mohandes Insurance
        "HRHO",  # EFG Holding
        "VALM",  # Valmore Holding
        "SEIG",  # Saudi Egyptian Investment & Finance
        "ODIN",  # ODIN Investments
        "ANFI",  # Alexandria National Financial Investment
        "ATLC",  # A.T.LEASE
        "BINV",  # B Investments Holding
        "GRCA",  # Grand Investment Capital
        "CCAP",  # QALA (Citadel Capital)
        "EGX30ETF",  # EGX 30 Index ETF
        "CNFN",  # Contact Financial Holding
        "VLMR",   # Valmore Holding (USD)
        "VLMRA",  # Valmore Holding (EGP)
    },

    "contracting_and_construction": {
        "WKOL",  # Wadi Kom Ombo Land Reclamation
        "AALR",  # General Company For Land Reclamation
        "GGCC",  # Giza General Contracting
        "IEEC",  # Industrial & Engineering Projects
        "NCCW",  # Nasr Company for Civil Works
        "ORAS",  # Orascom Construction PLC
        "GPIM",  # GPI For Urban Growth
        "COPR",  # Copper For Commercial Investment & Real Estate Development
        "EALR",  # El Arabia for Land Reclamation
        "ICON",  # Engineering Industries (ICON)
        "CRST",  # Creast Mark For Contracting
    },

    "textiles_and_durables": {
        "DSCW",  # Dice Sport & Casual Wear
        "APSW",  # Arab Polvara Spinning & Weaving
        "GTWL",  # Golden Textiles & Clothes Wool
        "KABO",  # El Nasr Clothes & Textiles
        "ORWE",  # Oriental Weavers
        "CFGH",  # Concrete Fashion Group
        "SPIN",  # Alexandria Spinning & Weaving (Spinalex)
        "ACGC",  # Arab Cotton Ginning
        "GTEX",  # GTEX For Commercial And Industrial
    },

    "building_materials": {
        "CERA",  # Ceramic & Porcelain
        "RREI",  # Ceramica Remas (verify source naming if needed)
        "MBSC",  # Misr Beni Suef Cement
        "ARCC",  # Arabian Cement Company
        "ARVA",  # Arab Valves Company
        "SVCE",  # South Valley Cement
        "PRCL",  # El Ezz Porcelain (Gemma)
        "LCSW",  # Lecico Egypt
        "SCEM",  # Sinai Cement
        "MCQE",  # Misr Cement (Qena)
        "RUBX",  # Rubex International
    },

    "paper_and_packaging": {
        "RAKT",  # Rakta Paper Manufacturing
        "UNIP",  # Universal For Paper and Packaging Materials (Unipack)
        "EPPK",  # El Ahram Co. For Printing And Packing
        "NAPR",  # National Printing
    },
}

EGX_USD_SYMBOLS: set[str] = {
    "FAITA",  # Faisal Islamic Bank (USD)
    "VLMR",   # Valmore Holding (USD)
    "EGSA",   # Egyptian Satellites - NileSat
    "SAIB",   # Societe Arabe Internationale de Banque
    "MOIL",   # Maridive & Oil Services
    "NAHO",   # Naeem Holding
    "EGBE",   # Egyptian Gulf Bank
    "TRTO",   # TransOceans Tours
    "NDRL",   # National Drilling Company 
    "GPPL",   # Golden Pyramids Plaza
}

def get_currency(symbol: str) -> str:
    """Return 'USD' or 'EGP' for an EGX symbol."""
    clean = symbol.upper().replace("EGX:", "")
    return "USD" if clean in EGX_USD_SYMBOLS else "EGP"

_SYMBOL_TO_SECTOR: dict[str, str] = {}

for _sector, _symbols in EGX_SECTORS.items():
    for _sym in _symbols:
        if _sym not in _SYMBOL_TO_SECTOR:
            _SYMBOL_TO_SECTOR[_sym] = _sector

def get_sector(symbol: str) -> str:
    """Return the sector for an EGX symbol, or 'other' if not classified."""
    clean = symbol.upper().replace("EGX:", "")
    return _SYMBOL_TO_SECTOR.get(clean, "other")

def get_symbols_by_sector(sector: str) -> list[str]:
    """Return list of EGX symbols for a given sector."""
    key = sector.lower().replace(" ", "_")
    symbols = EGX_SECTORS.get(key, set())
    return [f"EGX:{s}" for s in sorted(symbols)]

def get_all_sectors() -> list[str]:
    """Return list of all available EGX sectors."""
    return sorted(EGX_SECTORS.keys())

SECTOR_DISPLAY_NAMES: dict[str, str] = {
    "banks": "Banks",
    "basic_resources": "Basic Resources",
    "healthcare_and_pharma": "Health Care & Pharmaceuticals",
    "industrial_goods_and_services": "Industrial Goods, Services & Automobiles",
    "real_estate": "Real Estate",
    "travel_and_leisure": "Travel & Leisure",
    "utilities": "Utilities",
    "it_media_and_communication": "IT, Media & Communication Services",
    "food_beverages_and_tobacco": "Food, Beverages & Tobacco",
    "energy_and_support_services": "Energy & Support Services",
    "trade_and_distributors": "Trade & Distributors",
    "shipping_and_transportation": "Shipping & Transportation Services",
    "education_services": "Education Services",
    "non_bank_financial_services": "Non-Bank Financial Services",
    "contracting_and_construction": "Contracting & Construction Engineering",
    "textiles_and_durables": "Textile & Durables",
    "building_materials": "Building Materials",
    "paper_and_packaging": "Paper & Packaging",
}
