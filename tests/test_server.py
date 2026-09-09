from unified_finance_mcp.config import get_settings
from unified_finance_mcp.server import build_mcp


def test_build_mcp():
    mcp = build_mcp(get_settings())
    assert mcp.name == "unified-finance-mcp"
