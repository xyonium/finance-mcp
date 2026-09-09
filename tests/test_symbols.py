import pytest

from unified_finance_mcp.symbols import parse_symbol


def test_futu_prefix():
    p = parse_symbol("HK.00700")
    assert p.market == "HK" and p.local == "00700"
    assert p.yahoo() == "0700.HK" and p.futu() == "HK.00700"


def test_yahoo_suffix_cn():
    p = parse_symbol("600519.SS")
    assert p.market == "CN" and p.exchange == "SH" and p.futu() == "SH.600519"


def test_egypt_via_yahoo_suffix():
    p = parse_symbol("COMI.CA")
    assert p.market == "EG" and p.yahoo() == "COMI.CA" and p.tv() == ("EGX", "COMI")
    with pytest.raises(ValueError):
        p.futu()  # futu does not cover EG


def test_tv_prefix():
    p = parse_symbol("EGX:COMI")
    assert p.market == "EG" and p.yahoo() == "COMI.CA"


def test_bare_is_us():
    p = parse_symbol("AAPL")
    assert p.market == "US" and p.yahoo() == "AAPL" and p.av() == "AAPL"
    assert p.futu() == "US.AAPL"


def test_hk_padding():
    assert parse_symbol("700.HK").futu() == "HK.00700"  # HK codes are 5-digit
