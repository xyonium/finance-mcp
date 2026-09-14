"""scripts/kimi_enum_diff.py unit tests (hermetic — the fetch is not exercised;
only the parser and the universe derivation)."""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "kimi_enum_diff",
    Path(__file__).parent.parent / "scripts" / "kimi_enum_diff.py")
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)

MJS_SNIPPET = """
const TOOLS = [
  { name: 'call_data_source_tool', inputSchema: {} },
  { name: 'get_data_source_desc', inputSchema: { properties: { name: {
      type: 'string',
      enum: [
        'stock_finance_data',
        'tianyancha',
        'caixin',
      ],
      description: '...',
  } } } },
];
"""


def test_enum_parser_extracts_entries():
    from unittest import mock
    body = MJS_SNIPPET.encode()
    with mock.patch.object(_MOD.urllib.request, "urlopen") as uo:
        uo.return_value.__enter__.return_value.read.return_value = body
        enum = _MOD.fetch_official_enum("https://example.invalid/x.mjs")
    assert enum == ["stock_finance_data", "tianyancha", "caixin"]


def test_enum_parser_raises_on_layout_change():
    from unittest import mock
    with mock.patch.object(_MOD.urllib.request, "urlopen") as uo:
        uo.return_value.__enter__.return_value.read.return_value = b"no enum"
        try:
            _MOD.fetch_official_enum("https://example.invalid/x.mjs")
        except RuntimeError as e:
            assert "enum" in str(e)
        else:
            raise AssertionError("expected RuntimeError")


def test_our_universe_is_the_32_source_truth():
    uni = _MOD.our_universe()
    assert len(uni) == 32, f"universe drifted: {sorted(uni)}"
    # kept four present with their tag; the R18 eight all registered.
    for kept in ("tianyancha", "gildata", "yuandian_law", "caixin"):
        assert uni[kept] == "kept"
    for r18 in ("china_nda", "china_nbs", "china_standards", "who",
                "fao", "unsd", "unicef", "xhcj"):
        assert uni[r18].startswith("discouraged (R18"), r18
