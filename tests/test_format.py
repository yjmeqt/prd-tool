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


def _write_tmp_xml(xml: str) -> Path:
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(xml)
        return Path(f.name)


def test_format_preserves_xhtml_in_rule() -> None:
    xml = (
        '<prd name="X"><overview>o</overview>'
        '<requirement id="R1" name="N"><description>d</description>'
        '<rule id="r1" status="✅">Use <code>POST /login</code> and a <a href="https://x">link</a>.</rule>'
        "</requirement></prd>"
    )
    p = _write_tmp_xml(xml)
    try:
        result = format_prd(p)
        assert "<code>POST /login</code>" in result
        assert '<a href="https://x">link</a>' in result
        # No raw < or > leaking from XHTML content
        assert "&lt;code&gt;" not in result
    finally:
        p.unlink()


def test_format_preserves_xhtml_in_description_block() -> None:
    xml = (
        '<prd name="X"><overview>o</overview>'
        '<requirement id="R1" name="N">'
        "<description>Intro.<ul><li>One</li><li>Two</li></ul></description>"
        '<rule id="r1" status="✅">plain</rule>'
        "</requirement></prd>"
    )
    p = _write_tmp_xml(xml)
    try:
        result = format_prd(p)
        assert "<ul>" in result and "<li>One</li>" in result and "</ul>" in result
    finally:
        p.unlink()


def test_format_preserves_self_closing_void_tags() -> None:
    xml = (
        '<prd name="X"><overview>o</overview>'
        '<requirement id="R1" name="N"><description>d</description>'
        '<rule id="r1" status="✅">See <img src="x.png" alt="ok"/> then break<br/>here.</rule>'
        "</requirement></prd>"
    )
    p = _write_tmp_xml(xml)
    try:
        result = format_prd(p)
        assert '<img src="x.png" alt="ok"/>' in result
        assert "<br/>" in result
    finally:
        p.unlink()


def test_format_rule_with_xhtml_and_figma_node() -> None:
    xml = (
        '<prd name="X"><overview>o</overview>'
        '<requirement id="R1" name="N"><description>d</description>'
        '<rule id="r1" status="✅">Tap <strong>send</strong>.'
        '<figma_node name="S" file="abc" node="1-2"/></rule>'
        "</requirement></prd>"
    )
    p = _write_tmp_xml(xml)
    try:
        result = format_prd(p)
        assert "<strong>send</strong>" in result
        assert '<figma_node name="S" file="abc" node="1-2" />' in result
    finally:
        p.unlink()


def test_format_cdata_normalized_to_xhtml() -> None:
    # CDATA wrapping well-formed XHTML is parsed as text by ElementTree and
    # re-emitted as escaped XHTML on the next format pass.
    xml = (
        '<prd name="X"><overview>o</overview>'
        '<requirement id="R1" name="N"><description>d</description>'
        '<rule id="r1" status="✅"><![CDATA[<b>bold</b>]]></rule>'
        "</requirement></prd>"
    )
    p = _write_tmp_xml(xml)
    try:
        first = format_prd(p)
        # ElementTree treats CDATA contents as plain text, so <b> becomes &lt;b&gt;.
        assert "&lt;b&gt;bold&lt;/b&gt;" in first
        # Idempotent on second pass.
        p.write_text(first, encoding="utf-8")
        second = format_prd(p)
        assert first == second
    finally:
        p.unlink()


def test_format_idempotent_with_rich_content() -> None:
    xml = (
        '<prd name="X"><overview>o</overview>'
        '<requirement id="R1" name="N">'
        "<description>Hello <em>world</em><ul><li>a</li><li>b</li></ul></description>"
        '<rule id="r1" status="✅">Use <code>x</code>.</rule>'
        "</requirement></prd>"
    )
    p = _write_tmp_xml(xml)
    try:
        first = format_prd(p)
        p.write_text(first, encoding="utf-8")
        second = format_prd(p)
        assert first == second
    finally:
        p.unlink()
