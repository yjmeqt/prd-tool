"""Tests for prd_tool.format."""

from pathlib import Path

from prd_tool.format import format_prd

FIXTURES = Path(__file__).parent / "fixtures"


def test_format_valid_minimal() -> None:
    result = format_prd(FIXTURES / "valid_minimal.xml")
    assert "<prd name=" in result
    assert "</prd>" in result


def test_format_valid_full() -> None:
    result = format_prd(FIXTURES / "valid_full.xml")
    assert "<prd name=" in result
    assert "</prd>" in result
    assert "<implementation platform=" in result


def test_format_idempotent() -> None:
    """Formatting twice should produce the same output."""
    first = format_prd(FIXTURES / "valid_minimal.xml")
    # Write to temp, read back, format again
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(first)
        tmp_path = Path(f.name)
    try:
        second = format_prd(tmp_path)
        assert first == second
    finally:
        tmp_path.unlink()


def test_format_strips_deprecated_attrs() -> None:
    """Format should strip deprecated counter attributes from <prd>."""
    import tempfile
    import xml.etree.ElementTree as ET

    xml = '<prd name="Test" rules_done="3" rules_total="5"><overview>x</overview></prd>'
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(xml)
        tmp_path = Path(f.name)
    try:
        result = format_prd(tmp_path)
        root = ET.fromstring(result)
        assert "rules_done" not in root.attrib
        assert "rules_total" not in root.attrib
    finally:
        tmp_path.unlink()


def test_format_preserves_figma_nodes() -> None:
    result = format_prd(FIXTURES / "valid_full.xml")
    assert "figma_node" in result
    assert 'file="abc123"' in result
