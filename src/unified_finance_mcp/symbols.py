"""Symbol normalization across futu / yahoo / tradingview / fmp / alphavantage forms."""
from __future__ import annotations

from dataclasses import dataclass

# futu prefix -> market
_FUTU = {"HK": "HK", "US": "US", "SH": "CN", "SZ": "CN", "SG": "SG", "MY": "MY", "JP": "JP"}
# yahoo suffix -> (market, exchange or None). NOTE: .CA is Cairo (EGX), NOT Canada.
_SUFFIX = {
    "HK": ("HK", "HKEX"), "SS": ("CN", "SH"), "SZ": ("CN", "SZ"),
    "CA": ("EG", "EGX"), "T": ("JP", "TSE"), "L": ("UK", "LSE"),
    "TO": ("CA", "TSX"), "V": ("CA", "TSXV"), "AX": ("AU", "ASX"),
    "DE": ("DE", "XETR"), "PA": ("FR", "EURONEXT"), "KS": ("KR", "KRX"),
    "TW": ("TW", "TWSE"), "NS": ("IN", "NSE"), "SI": ("SG", "SGX"),
    "KL": ("MY", "MYX"), "IS": ("TR", "BIST"),
}
# tradingview exchange -> market
_TV = {
    "EGX": "EG", "NASDAQ": "US", "NYSE": "US", "AMEX": "US", "HKEX": "HK",
    "SSE": "CN", "SZSE": "CN", "TSE": "JP", "LSE": "UK", "TSX": "CA",
    "ASX": "AU", "XETR": "DE", "EURONEXT": "FR", "KRX": "KR", "TWSE": "TW",
    "TPEX": "TW", "NSE": "IN", "SGX": "SG", "MYX": "MY", "BURSA": "MY",
    "BIST": "TR",
}
# market -> (yahoo suffix, futu prefix or None, tv exchange or None)
_MARKET = {
    "US": ("", "US", "NASDAQ"), "HK": (".HK", "HK", "HKEX"),
    "CN": (None, None, None),  # exchange-dependent, see methods
    "EG": (".CA", None, "EGX"), "JP": (".T", "JP", "TSE"), "UK": (".L", None, "LSE"),
    "CA": (".TO", None, "TSX"), "AU": (".AX", None, "ASX"), "DE": (".DE", None, "XETR"),
    "FR": (".PA", None, "EURONEXT"), "KR": (".KS", None, "KRX"), "TW": (".TW", None, "TWSE"),
    "IN": (".NS", None, "NSE"), "SG": (".SI", "SG", "SGX"), "MY": (".KL", "MY", "MYX"),
    "TR": (".IS", None, "BIST"),
}


@dataclass(frozen=True)
class ParsedSymbol:
    market: str
    local: str
    exchange: str | None = None

    def yahoo(self) -> str:
        if self.market == "CN":
            suffix = ".SZ" if self.exchange == "SZ" else ".SS"
            return f"{self.local}{suffix}"
        entry = _MARKET.get(self.market)
        if entry is None:
            raise ValueError(f"no yahoo form for market {self.market}")
        local = self.local
        if self.market == "HK":
            # yahoo HK codes are 4-digit; strip futu's 5-digit padding first (00700 -> 0700).
            local = local.lstrip("0").zfill(4)  # 700 -> 0700
        return f"{local}{entry[0]}"

    def futu(self) -> str:
        if self.market == "CN":
            prefix = "SZ" if self.exchange == "SZ" else "SH"
            return f"{prefix}.{self.local}"
        entry = _MARKET.get(self.market)
        if entry is None or entry[1] is None:
            raise ValueError(f"futu does not cover market {self.market}")
        local = self.local.zfill(5) if self.market == "HK" else self.local
        return f"{entry[1]}.{local}"

    def tv(self) -> tuple[str, str]:
        if self.market == "CN":
            return ("SZSE" if self.exchange == "SZ" else "SSE", self.local)
        entry = _MARKET.get(self.market)
        if entry is None or entry[2] is None:
            raise ValueError(f"tradingview form unknown for market {self.market}")
        return (entry[2], self.local)

    def fmp(self) -> str:
        return self.yahoo()

    def av(self) -> str:
        if self.market != "US":
            raise ValueError(f"alphavantage equities are US-only, got {self.market}")
        return self.local


def parse_symbol(raw: str) -> ParsedSymbol:
    s = raw.strip().upper()
    if not s:
        raise ValueError("empty symbol")
    if ":" in s:  # tradingview form EGX:COMI
        exch, _, local = s.partition(":")
        return ParsedSymbol(_TV.get(exch, "US"), local, exch)
    if "." in s:
        head, _, tail = s.rpartition(".")
        if head in _FUTU:  # futu form HK.00700
            return ParsedSymbol(_FUTU[head], tail, head if head in ("SH", "SZ") else None)
        if tail in _SUFFIX:  # yahoo form 0700.HK / COMI.CA
            market, exch = _SUFFIX[tail]
            return ParsedSymbol(market, head, exch)
        raise ValueError(f"unrecognized symbol form: {raw!r}")
    if s.isdigit() and len(s) == 6:  # bare A-share code: 6xxxxx -> SH else SZ
        return ParsedSymbol("CN", s, "SH" if s.startswith("6") else "SZ")
    return ParsedSymbol("US", s)
