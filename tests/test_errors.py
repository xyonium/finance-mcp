from unified_finance_mcp.errors import RateLimited, scrub, tool_error


def test_tool_error_shape():
    e = tool_error("boom", hint="try later", market="EG")
    assert e == {"error": "boom", "hint": "try later", "market": "EG"}


def test_scrub_removes_secrets():
    assert scrub("failed key=abc123 at fmp", "abc123") == "failed key=*** at fmp"


def test_kinds():
    assert RateLimited("x").kind == "rate_limited" and RateLimited("x").retryable
