"""EGX (Egyptian Exchange) index constituents (vendored from tradingview-mcp).

Vendored constants: ``EGX30_CONSTITUENTS``, ``EGX70_CONSTITUENTS``,
``SHARIAH33_CONSTITUENTS``, ``EGX35LV_CONSTITUENTS``, ``TAMAYUZ_CONSTITUENTS``,
plus the ``EGX:``-prefixed accessor functions and ``EGX_INDICES`` metadata used
by the egx_market index action.

NOTE: the reference source documents an EGX100 EWI index (EGX30 + EGX70
combined) but ships NO ``EGX100_CONSTITUENTS`` table — only the composite
``get_egx100_symbols()`` accessor. This package therefore has no EGX100
constituent table; the egx_market container answers ``index="EGX100"`` with a
tool error listing the available indices.

Symbols are bare EGX tickers (e.g. "COMI"); pass through the ``EGX:``-prefixed
accessors when feeding tradingview_ta / the scanner.
"""
from __future__ import annotations

# EGX30 Price Index - Top 30 blue-chip stocks (weighted by free-float market cap)
EGX30_CONSTITUENTS: list[str] = [
    "ISPH",   # Ibnsina Pharma
    "ABUK",   # Abu Qir Fertilizers
    "EMFD",   # Emaar Misr Development
    "AMOC",   # Alexandria Mineral Oils Company
    "COMI",   # Commercial International Bank (CIB)
    "EAST",   # Eastern Company
    "EGCH",   # KIMA (El Nasr Chemicals)
    "RMDA",   # Rameda
    "ARCC",   # Arabian Cement
    "CCAP",   # Qalaa Holdings
    "ETEL",   # Telecom Egypt
    "ORWE",   # Oriental Weavers
    "ORAS",   # Orascom Construction
    "OIH",    # Orascom Investment Holding
    "ORHD",   # Orascom Development Egypt
    "EFIH",   # e-finance Investment Group
    "EFID",   # Edita Food Industries
    "PHDC",   # Palm Hills Development
    "BTFH",   # Beltone Holding
    "JUFO",   # Juhayna Food Industries
    "GBCO",   # GB Corp
    "RAYA",   # Raya Holding
    "VLMR",   # Valmore Holding (USD)
    "VLMRA",  # Valmore Holding (EGP)
    "FWRY",   # Fawry
    "HRHO",   # EFG Holding
    "TMGH",   # Talaat Moustafa Group
    "HELI",   # Heliopolis Housing
    "MCQE",   # Misr Cement Qena
    "EGAL",   # Egypt Aluminium
    "ADIB",   # Abu Dhabi Islamic Bank Egypt
]

# EGX70 EWI - Next 70 stocks by liquidity (equal-weighted)
EGX70_CONSTITUENTS: list[str] = [
    "AMER",   # Amer Group
    "ATLC",   # AT Lease
    "TALM",   # Taaleem Management Services
    "AIHC",   # Arabia Investments Holding
    "AIDC",   # Arabia Investment & Development
    "ASPI",   # Aspire Capital Holding
    "SCEM",   # Sinai Cement
    "ASCM",   # ASCOM Mining
    "ACTF",   # Act Financial
    "ALCN",   # Alexandria Container & Cargo Handling
    "IDRE",   # Ismailia New Development
    "ISMA",   # Ismailia Misr Poultry
    "AFDI",   # Al Ahly Development & Investment
    "EXPA",   # Export Development Bank of Egypt
    "DAPH",   # Development & Engineering Consultants
    "ISMQ",   # Iron & Steel for Mines & Quarries
    "ICFC",   # International Fertilizers & Chemicals
    "IFAP",   # International Agricultural Products
    "ZEOT",   # Extracted Oils & Derivatives
    "OCDI",   # SODIC
    "SWDY",   # Elsewedy Electric
    "ELSH",   # El Shams Housing
    "UEGC",   # Upper Egypt Contracting
    "ENGC",   # Engineering Industries (ICON)
    "PRCL",   # General Ceramics & Porcelain
    "MEPA",   # Medical Packaging
    "OBRI",   # Obour Land Real Estate Investment
    "ECAP",   # El Ezz Ceramics & Porcelain (Gemma)
    "POUL",   # Cairo Poultry
    "COSG",   # Cairo Oils & Soap
    "CSAG",   # Canal Shipping Agencies
    "IEEC",   # Industrial & Engineering Projects
    "PHAR",   # EIPICO
    "ETRS",   # Egytrans
    "EGTS",   # Egyptian Resorts Company
    "MOED",   # Modern Education Systems
    "MPRC",   # Egyptian Media Production City
    "EHDR",   # Egyptian Housing Development
    "ARAB",   # Arab Developers Holding
    "AMIA",   # Al Moatamad Investments
    "MPCO",   # Mansoura Poultry
    "KABO",   # Kabo Textiles
    "NIPH",   # Nile Pharmaceuticals
    "MTIE",   # MM Group
    "OFH",    # OB Financial Holding
    "HDBK",   # Housing & Development Bank
    "CIEB",   # Credit Agricole Egypt
    "TANM",   # Tanmeya Real Estate Investment
    "BIOC",   # GlaxoSmithKline Egypt
    "SVCE",   # South Valley Cement
    "GPIM",   # GB for Urban Development
    "DSCW",   # Dice Sport & Casual Wear
    "RACC",   # Raya Contact Center
    "ZMID",   # Zahraa Maadi Investment
    "SIPC",   # Saba International Pharma
    "SKPC",   # SIDPEC
    "SDTI",   # Sharm Dreams
    "NCCW",   # Nasr Civil Works
    "TAQA",   # TAQA Arabia
    "CNFN",   # Contact Financial Holding
    "LCSW",   # Lecico Egypt
    "MCRO",   # Macro Group
    "MASR",   # Madinet Masr
    "ATQA",   # Attaka Steel
    "MFPC",   # Mopco
    "AFMC",   # Alexandria Mills
    "MPCI",   # Memphis Pharma
    "KRDI",   # Nile Agriculture Development
    "VALU",   # valU Consumer Finance
    "UNIP",   # Unipack
]


# SHARIAH33 - Shariah-compliant index (34 stocks)
SHARIAH33_CONSTITUENTS: list[str] = [
    "ISPH",   # Ibn Sina Pharma
    "AMOC",   # Alexandria Mineral Oils Company
    "ICFC",   # International Fertilizers Company
    "IFAP",   # International Crops
    "OCDI",   # Sixth of October Development & Investment - SODIC
    "RMDA",   # 10th of Ramadan for Pharmaceutical Industries - RAMEDA
    "ACGC",   # Arab Cotton Ginning Company
    "ARCC",   # Arab Cement Company
    "CIRA",   # Cairo Investment & Development - SERA Education
    "ETRS",   # Egyptian Transport Services - Egytrans
    "ETEL",   # Telecom Egypt
    "MPCO",   # Mansoura Poultry
    "ORWE",   # Oriental Weavers
    "MTIE",   # M.M. Group for Industry & Global Trade
    "ORAS",   # Orascom Construction PLC
    "ORHD",   # Orascom Development Egypt
    "EFIH",   # EFG Hermes Financial & Digital Investments
    "EFID",   # Edita Food Industries
    "PHDC",   # Palm Hills Developments
    "SAUD",   # Bank of Baraka Egypt
    "FAITA",  # Faisal Islamic Bank of Egypt - USD
    "FAIT",   # Faisal Islamic Bank of Egypt - EGP
    "JUFO",   # Juhayna Food Industries
    "RACC",   # Raya Contact Centers
    "SKPC",   # Sidi Kerir Petrochemicals - SIDPEC
    "OLFI",   # Obour Land for Food Industries
    "EGAS",   # Egypt Gas
    "LCSW",   # LESECO Egypt
    "TMGH",   # Talaat Moustafa Group Holding
    "MASR",   # Madinat Misr for Housing & Development
    "ATQA",   # Egypt National Steel - Ataka
    "MCQE",   # Misr Cement - Qena
    "EGAL",   # Egyptalum
    "ADIB",   # Abu Dhabi Islamic Bank Egypt
]

# EGX35-LV - Low Volatility index (35 stocks)
EGX35LV_CONSTITUENTS: list[str] = [
    "ABUK",   # Abu Qir Fertilizers & Chemicals
    "EMFD",   # Emaar Misr for Development
    "ACTF",   # ACT Financial Consulting
    "ALCN",   # Alexandria Container & Cargo Handling
    "AMOC",   # Alexandria Mineral Oils Company
    "AFDI",   # Al Ahly for Development & Investment
    "COMI",   # Commercial International Bank (CIB)
    "EXPA",   # Export Development Bank of Egypt
    "EAST",   # Eastern Company
    "ELSH",   # El Shams for Housing & Development
    "ENGC",   # Engineering Architectural Industries for Construction & Development - ICON
    "RMDA",   # 10th of Ramadan for Pharmaceutical Industries - RAMEDA
    "PHAR",   # Egyptian International Pharmaceutical Industries - EIPICO
    "ETEL",   # Telecom Egypt
    "EHDR",   # Egyptians for Housing & Development
    "ORWE",   # Oriental Weavers
    "ORAS",   # Orascom Construction PLC
    "EFIH",   # EFG Hermes Financial & Digital Investments
    "EFID",   # Edita Food Industries
    "PHDC",   # Palm Hills Developments
    "HDBK",   # Housing & Development Bank
    "CIEB",   # Credit Agricole Egypt
    "JUFO",   # Juhayna Food Industries
    "SKPC",   # Sidi Kerir Petrochemicals - SIDPEC
    "TAQA",   # Arabia Energy
    "VLMRA",  # ValMora Holding for Investments - EGP
    "FWRY",   # Fawry for Banking Technology & Electronic Payments
    "LCSW",   # LESECO Egypt
    "HRHO",   # EFG Holding Group
    "TMGH",   # Talaat Moustafa Group Holding
    "MASR",   # Madinat Misr for Housing & Development
    "HELI",   # Heliopolis Housing & Development
    "MFPC",   # Misr Fertilizers Production Company - MOPCO
    "ADIB",   # Abu Dhabi Islamic Bank Egypt
    "KRDI",   # Nahr El-Kheir for Agricultural Development & Environmental Services
]

# TAMAYUZ - Small/micro-cap emerging companies index (5 stocks)
TAMAYUZ_CONSTITUENTS: list[str] = [
    "INEG",   # Integrated Engineering Group
    "IBCT",   # International Business Corporation for Trade & Agencies
    "VERT",   # Vertica for Industry & Trade
    "HBCO",   # HIBCO for Commercial Investments & Real Estate Development
    "UTOP",   # Utopia for Real Estate & Tourism Investment
]


def get_egx30_symbols() -> list[str]:
    """Return EGX30 constituent symbols with EGX: prefix."""
    return [f"EGX:{s}" for s in EGX30_CONSTITUENTS]


def get_egx70_symbols() -> list[str]:
    """Return EGX70 constituent symbols with EGX: prefix."""
    return [f"EGX:{s}" for s in EGX70_CONSTITUENTS]


def get_egx100_symbols() -> list[str]:
    """Return EGX100 (EGX30 + EGX70) constituent symbols with EGX: prefix."""
    return get_egx30_symbols() + get_egx70_symbols()


def get_shariah33_symbols() -> list[str]:
    """Return SHARIAH33 constituent symbols with EGX: prefix."""
    return [f"EGX:{s}" for s in SHARIAH33_CONSTITUENTS]


def get_egx35lv_symbols() -> list[str]:
    """Return EGX35-LV constituent symbols with EGX: prefix."""
    return [f"EGX:{s}" for s in EGX35LV_CONSTITUENTS]


def get_tamayuz_symbols() -> list[str]:
    """Return TAMAYUZ constituent symbols with EGX: prefix."""
    return [f"EGX:{s}" for s in TAMAYUZ_CONSTITUENTS]


# Index metadata. NOTE: EGX100 is deliberately absent — the reference source
# ships no EGX100_CONSTITUENTS table; the container rejects index="EGX100".
EGX_INDICES: dict[str, dict] = {
    "EGX30": {
        "name": "EGX 30 Price Index",
        "description": "Top 30 most liquid blue-chip stocks, weighted by free-float market cap",
        "constituents_count": len(EGX30_CONSTITUENTS),
        "get_symbols": get_egx30_symbols,
    },
    "EGX70": {
        "name": "EGX 70 EWI (Equal Weight Index)",
        "description": "Next 70 stocks by liquidity, equal-weighted mid/small cap index",
        "constituents_count": len(EGX70_CONSTITUENTS),
        "get_symbols": get_egx70_symbols,
    },
    "SHARIAH33": {
        "name": "S&P/EGX ESG/Shariah Index",
        "description": "Shariah-compliant index of 34 stocks screened for Islamic finance compatibility",
        "constituents_count": len(SHARIAH33_CONSTITUENTS),
        "get_symbols": get_shariah33_symbols,
    },
    "EGX35LV": {
        "name": "EGX 35 Low Volatility Index",
        "description": "35 stocks selected for low volatility characteristics, defensive/stable portfolio",
        "constituents_count": len(EGX35LV_CONSTITUENTS),
        "get_symbols": get_egx35lv_symbols,
    },
    "TAMAYUZ": {
        "name": "TAMAYUZ Index",
        "description": "Small/micro-cap emerging companies index for high-growth potential stocks",
        "constituents_count": len(TAMAYUZ_CONSTITUENTS),
        "get_symbols": get_tamayuz_symbols,
    },
}


def get_index_names() -> list[str]:
    """Return list of available EGX index names."""
    return list(EGX_INDICES.keys())


def is_egx30_stock(symbol: str) -> bool:
    """Check if a symbol is in the EGX30 index."""
    clean = symbol.upper().replace("EGX:", "")
    return clean in EGX30_CONSTITUENTS


def is_egx70_stock(symbol: str) -> bool:
    """Check if a symbol is in the EGX70 index."""
    clean = symbol.upper().replace("EGX:", "")
    return clean in EGX70_CONSTITUENTS
