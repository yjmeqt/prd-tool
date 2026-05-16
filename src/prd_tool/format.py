"""PRD XML formatting."""

import xml.etree.ElementTree as ET
from pathlib import Path

from prd_tool.constants import ATTR_ORDER, INDENT, PRD_DEPRECATED_ATTRS


def format_prd(path: Path) -> str:
    """Format a PRD XML file. Returns the formatted XML string."""
    tree = ET.parse(path)
    root = tree.getroot()

    for attr in PRD_DEPRECATED_ATTRS:
        if attr in root.attrib:
            del root.attrib[attr]

    lines: list[str] = []
    _format_prd_element(root, lines)
    return "\n".join(lines) + "\n"


def _attrs_str(elem: ET.Element) -> str:
    """Format attributes in canonical order."""
    order: list[str] = ATTR_ORDER.get(elem.tag, [])
    order_map = {k: i for i, k in enumerate(order)}
    sorted_attrs = sorted(
        elem.attrib.items(),
        key=lambda kv: (order_map.get(kv[0], 999), kv[0]),
    )
    parts = [f'{k}="{_escape_attr(v)}"' for k, v in sorted_attrs]
    return " ".join(parts)


def _xhtml_attrs_str(elem: ET.Element) -> str:
    """Attributes for inline XHTML. Insertion order, no canonical reordering."""
    parts = [f'{k}="{_escape_attr(v)}"' for k, v in elem.attrib.items()]
    return " ".join(parts)


def _escape_attr(value: str) -> str:
    """Escape attribute values for XML."""
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _escape_text(text: str) -> str:
    """Escape text content for XML."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _serialize_inner_xhtml(elem: ET.Element, exclude_tags: tuple[str, ...] = ()) -> str:
    """Serialize an element's inner content (text + child elements + tails) as XHTML.

    Excludes children whose tag is in ``exclude_tags`` (their tail is also dropped, so the
    structural child can be re-emitted separately by the caller).
    """
    parts: list[str] = []
    if elem.text:
        parts.append(_escape_text(elem.text))
    for child in elem:
        if child.tag in exclude_tags:
            continue
        parts.append(_serialize_xhtml_element(child))
        if child.tail:
            parts.append(_escape_text(child.tail))
    return "".join(parts)


def _serialize_xhtml_element(elem: ET.Element) -> str:
    """Serialize a single inline XHTML element (used inside rich-text fields)."""
    attrs = _xhtml_attrs_str(elem)
    attr_str = f" {attrs}" if attrs else ""
    if len(elem) == 0 and not (elem.text or ""):
        return f"<{elem.tag}{attr_str}/>"
    inner = _serialize_inner_xhtml(elem)
    return f"<{elem.tag}{attr_str}>{inner}</{elem.tag}>"


def _has_xhtml_children(elem: ET.Element, exclude_tags: tuple[str, ...] = ()) -> bool:
    """True iff elem contains any child element that isn't in exclude_tags."""
    return any(child.tag not in exclude_tags for child in elem)


def _format_prd_element(root: ET.Element, lines: list[str]) -> None:
    """Format the entire <prd> element."""
    attrs = _attrs_str(root)
    lines.append(f"<prd {attrs}>")

    for child in root:
        tag = child.tag
        if tag == "overview":
            _format_text_block(child, lines, depth=0)
        elif tag == "implementation":
            _format_self_closing(child, lines, depth=0)
        elif tag == "requirement":
            _format_requirement(child, lines)
        elif tag == "bug":
            _format_bug(child, lines)
        else:
            _format_generic(child, lines, depth=0)

    lines.append("")
    lines.append("</prd>")


def _format_text_block(elem: ET.Element, lines: list[str], depth: int) -> None:
    """Format <overview>: rich-text-aware. Inner lines at column 0."""
    indent = INDENT * depth
    if _has_xhtml_children(elem):
        inner = _serialize_inner_xhtml(elem).strip()
        if not inner:
            lines.append("")
            lines.append(f"{indent}<{elem.tag}/>")
            return
        lines.append("")
        lines.append(f"{indent}<{elem.tag}>")
        for line in inner.splitlines():
            lines.append(line.rstrip())
        lines.append(f"{indent}</{elem.tag}>")
        return

    text = (elem.text or "").strip()
    if not text:
        lines.append("")
        lines.append(f"{indent}<{elem.tag}/>")
        return

    lines.append("")
    lines.append(f"{indent}<{elem.tag}>")
    for line in text.splitlines():
        lines.append(f"{_escape_text(line.rstrip())}")
    lines.append(f"{indent}</{elem.tag}>")


def _format_self_closing(elem: ET.Element, lines: list[str], depth: int) -> None:
    """Format a self-closing element."""
    indent = INDENT * depth
    attrs = _attrs_str(elem)
    lines.append(f"{indent}<{elem.tag} {attrs} />")


def _format_requirement(req: ET.Element, lines: list[str]) -> None:
    """Format a <requirement> element."""
    attrs = _attrs_str(req)
    lines.append("")
    lines.append(f"<requirement {attrs}>")

    for child in req:
        if child.tag == "description":
            _format_description(child, lines)
        elif child.tag == "rule":
            _format_rule(child, lines)
        elif child.tag == "ui_review":
            _format_ui_review(child, lines)
        else:
            _format_generic(child, lines, depth=1)

    lines.append("</requirement>")


def _format_description(elem: ET.Element, lines: list[str]) -> None:
    """Format a <description> inside a requirement. Rich-text-aware."""
    if _has_xhtml_children(elem):
        inner = _serialize_inner_xhtml(elem).strip()
        if not inner:
            lines.append(f"{INDENT}<description/>")
            return
        lines.append(f"{INDENT}<description>")
        for line in inner.splitlines():
            stripped = line.strip()
            if stripped:
                lines.append(f"{INDENT}{INDENT}{stripped}")
            else:
                lines.append("")
        lines.append(f"{INDENT}</description>")
        return

    text = (elem.text or "").strip()
    lines.append(f"{INDENT}<description>")
    for line in text.splitlines():
        lines.append(f"{INDENT}{INDENT}{_escape_text(line.strip())}")
    lines.append(f"{INDENT}</description>")


def _format_rule(rule: ET.Element, lines: list[str]) -> None:
    """Format a <rule> element, including nested <figma_node> children and inline XHTML."""
    attrs = _attrs_str(rule)
    figma_nodes = rule.findall("figma_node")
    has_xhtml = _has_xhtml_children(rule, exclude_tags=("figma_node",))

    if has_xhtml:
        inner = _serialize_inner_xhtml(rule, exclude_tags=("figma_node",)).strip()
        if not figma_nodes:
            lines.append(f"{INDENT}<rule {attrs}>{inner}</rule>")
        else:
            lines.append(f"{INDENT}<rule {attrs}>{inner}")
            for fn in figma_nodes:
                fn_attrs = _attrs_str(fn)
                lines.append(f"{INDENT}{INDENT}<figma_node {fn_attrs} />")
            lines.append(f"{INDENT}</rule>")
        return

    text = (rule.text or "").strip()
    if not figma_nodes:
        lines.append(f"{INDENT}<rule {attrs}>{_escape_text(text)}</rule>")
    else:
        lines.append(f"{INDENT}<rule {attrs}>{_escape_text(text)}")
        for fn in figma_nodes:
            fn_attrs = _attrs_str(fn)
            lines.append(f"{INDENT}{INDENT}<figma_node {fn_attrs} />")
        lines.append(f"{INDENT}</rule>")


def _format_ui_review(ui_review: ET.Element, lines: list[str]) -> None:
    """Format a <ui_review> element."""
    attrs = _attrs_str(ui_review)
    findings = ui_review.findall("finding")

    if not findings:
        lines.append(f"{INDENT}<ui_review {attrs} />")
    else:
        lines.append(f"{INDENT}<ui_review {attrs}>")
        for finding in findings:
            f_attrs = _attrs_str(finding)
            if _has_xhtml_children(finding):
                inner = _serialize_inner_xhtml(finding).strip()
                lines.append(f"{INDENT}{INDENT}<finding {f_attrs}>{inner}</finding>")
            else:
                text = (finding.text or "").strip()
                lines.append(f"{INDENT}{INDENT}<finding {f_attrs}>{_escape_text(text)}</finding>")
        lines.append(f"{INDENT}</ui_review>")


def _format_bug(bug: ET.Element, lines: list[str]) -> None:
    """Format a <bug> element."""
    attrs = _attrs_str(bug)
    lines.append("")
    lines.append(f"<bug {attrs}>")

    for child_tag in ("current", "expected", "steps"):
        child = bug.find(child_tag)
        if child is None:
            continue
        if _has_xhtml_children(child):
            inner = _serialize_inner_xhtml(child).strip()
            if not inner:
                lines.append(f"{INDENT}<{child_tag}/>")
                continue
            lines.append(f"{INDENT}<{child_tag}>")
            for line in inner.splitlines():
                stripped = line.strip()
                if stripped:
                    lines.append(f"{INDENT}{INDENT}{stripped}")
                else:
                    lines.append("")
            lines.append(f"{INDENT}</{child_tag}>")
        else:
            text = (child.text or "").strip()
            lines.append(f"{INDENT}<{child_tag}>")
            for line in text.splitlines():
                lines.append(f"{INDENT}{INDENT}{_escape_text(line.strip())}")
            lines.append(f"{INDENT}</{child_tag}>")

    lines.append("</bug>")


def _format_generic(elem: ET.Element, lines: list[str], depth: int) -> None:
    """Fallback formatter for unknown elements."""
    indent = INDENT * depth
    attrs = _attrs_str(elem)
    attr_str = f" {attrs}" if attrs else ""
    text = (elem.text or "").strip()

    if len(elem) == 0 and not text:
        lines.append(f"{indent}<{elem.tag}{attr_str} />")
    elif len(elem) == 0:
        lines.append(f"{indent}<{elem.tag}{attr_str}>{_escape_text(text)}</{elem.tag}>")
    else:
        lines.append(f"{indent}<{elem.tag}{attr_str}>")
        if text:
            lines.append(f"{indent}{INDENT}{_escape_text(text)}")
        for child in elem:
            _format_generic(child, lines, depth + 1)
        lines.append(f"{indent}</{elem.tag}>")
