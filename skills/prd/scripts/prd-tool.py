#!/usr/bin/env python3
"""PRD XML validation, formatting, and stats tool.

Usage:
    python3 prd-tool.py validate prd/comments/comments.xml
    python3 prd-tool.py format   prd/comments/comments.xml
    python3 prd-tool.py stats    prd/comments/comments.xml
    python3 prd-tool.py stats    prd/index.xml
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RULE_STATUSES = {"✅", "❌", "⚠️"}
BUG_STATUSES = {"Open", "Fix Pending", "Fixed"}
UI_REVIEW_STATUSES = {"✅", "❌", "⚠️"}

PRD_REQUIRED_ATTRS = {"name"}
# Counter attributes that used to live on <prd>. No longer persisted or
# validated — `format` strips them, `stats` recomputes on demand.
PRD_DEPRECATED_ATTRS = {
    "rules_done",
    "rules_total",
    "bugs_open",
    "ui_reviewed",
    "ui_total",
}
REQUIREMENT_REQUIRED_ATTRS = {"id", "name"}
RULE_REQUIRED_ATTRS = {"id", "status"}
BUG_REQUIRED_ATTRS = {"id", "status", "date", "rule"}
UI_REVIEW_REQUIRED_ATTRS = {"status", "date"}
FINDING_REQUIRED_ATTRS = {"rule"}

# Canonical element order inside <prd>
PRD_CHILD_ORDER = ["overview", "implementation", "requirement", "bug"]

# Canonical element order inside <requirement>
REQ_CHILD_ORDER = ["description", "rule", "ui_review"]

# Attribute order per element (for formatting)
ATTR_ORDER = {
    "prd": ["name"],
    "implementation": ["platform", "spec"],
    "requirement": ["id", "name"],
    "rule": ["id", "status", "context"],
    "figma_node": ["name", "file", "node"],
    "bug": ["id", "status", "date", "rule"],
    "ui_review": ["status", "date"],
    "finding": ["rule"],
}

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate(path: Path) -> list[str]:
    """Validate a PRD XML file. Returns a list of error strings."""
    errors: list[str] = []

    # 1. Well-formed XML
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        errors.append(f"XML parse error: {e}")
        return errors

    root = tree.getroot()
    if root.tag != "prd":
        errors.append(f"Root element must be <prd>, got <{root.tag}>")
        return errors

    # 2. <prd> required attributes
    for attr in PRD_REQUIRED_ATTRS:
        if attr not in root.attrib:
            errors.append(f"<prd> missing required attribute: {attr}")

    # 3. Element ordering inside <prd>
    child_tags = [child.tag for child in root]
    _check_ordering(child_tags, PRD_CHILD_ORDER, "<prd>", errors)

    # 4. Collect all rules and requirements for cross-referencing
    all_rules: dict[str, str] = {}  # qualified_id -> requirement_id
    req_ids: list[str] = []

    _req_prefix = "R"
    for req in root.findall("requirement"):
        req_id = req.get("id", "")
        req_ids.append(req_id)

        # Required attributes
        for attr in REQUIREMENT_REQUIRED_ATTRS:
            if attr not in req.attrib:
                errors.append(f"<requirement> missing required attribute: {attr}")

        # Sequential requirement IDs — detect prefix from first requirement
        expected_idx = len(req_ids)
        if expected_idx == 1:
            # Infer prefix from the first requirement (e.g. "R", "S", "L")
            match = re.match(r"^([A-Z]+)(\d+)$", req_id)
            if match:
                _req_prefix = match.group(1)
            else:
                _req_prefix = "R"
        if req_id != f"{_req_prefix}{expected_idx}":
            errors.append(
                f"Requirement ID out of sequence: got {req_id}, expected {_req_prefix}{expected_idx}"
            )

        # Element ordering inside <requirement>
        req_child_tags = [child.tag for child in req]
        _check_ordering(req_child_tags, REQ_CHILD_ORDER, f"<requirement id=\"{req_id}\">", errors)

        # Rules
        rule_ids_in_req: set[str] = set()
        for rule in req.findall("rule"):
            for attr in RULE_REQUIRED_ATTRS:
                if attr not in rule.attrib:
                    errors.append(
                        f"<rule> in {req_id} missing required attribute: {attr}"
                    )

            rule_id = rule.get("id", "")
            status = rule.get("status", "")

            if status not in RULE_STATUSES:
                errors.append(
                    f"Rule {req_id}.{rule_id}: invalid status '{status}' "
                    f"(expected one of {RULE_STATUSES})"
                )

            if rule_id in rule_ids_in_req:
                errors.append(
                    f"Duplicate rule ID '{rule_id}' in {req_id}"
                )
            rule_ids_in_req.add(rule_id)

            qualified = f"{req_id}.{rule_id}"
            all_rules[qualified] = req_id

        # UI review
        for ui_review in req.findall("ui_review"):
            for attr in UI_REVIEW_REQUIRED_ATTRS:
                if attr not in ui_review.attrib:
                    errors.append(
                        f"<ui_review> in {req_id} missing required attribute: {attr}"
                    )

            ui_status = ui_review.get("status", "")
            if ui_status not in UI_REVIEW_STATUSES:
                errors.append(
                    f"<ui_review> in {req_id}: invalid status '{ui_status}' "
                    f"(expected one of {UI_REVIEW_STATUSES})"
                )

            for finding in ui_review.findall("finding"):
                for attr in FINDING_REQUIRED_ATTRS:
                    if attr not in finding.attrib:
                        errors.append(
                            f"<finding> in {req_id} missing required attribute: {attr}"
                        )
                finding_rule = finding.get("rule", "")
                if finding_rule and finding_rule not in all_rules:
                    errors.append(
                        f"<finding> references unknown rule: {finding_rule}"
                    )

    # 5. Bugs
    bug_ids: set[str] = set()
    for bug in root.findall("bug"):
        for attr in BUG_REQUIRED_ATTRS:
            if attr not in bug.attrib:
                errors.append(f"<bug> missing required attribute: {attr}")

        bug_id = bug.get("id", "")
        status = bug.get("status", "")
        rule_ref = bug.get("rule", "")

        if status not in BUG_STATUSES:
            errors.append(
                f"Bug '{bug_id}': invalid status '{status}' "
                f"(expected one of {BUG_STATUSES})"
            )

        if bug_id in bug_ids:
            errors.append(f"Duplicate bug ID: '{bug_id}'")
        bug_ids.add(bug_id)

        if rule_ref and rule_ref not in all_rules:
            errors.append(
                f"Bug '{bug_id}' references unknown rule: {rule_ref}"
            )

        # Required child elements
        for child_tag in ("current", "expected", "steps"):
            if bug.find(child_tag) is None:
                errors.append(f"Bug '{bug_id}' missing <{child_tag}> element")

    return errors


def _check_ordering(
    tags: list[str], canonical: list[str], context: str, errors: list[str]
):
    """Check that element tags appear in canonical order (each group contiguous)."""
    order_map = {tag: i for i, tag in enumerate(canonical)}
    last_order = -1
    last_tag = ""
    for tag in tags:
        if tag not in order_map:
            continue
        current_order = order_map[tag]
        if current_order < last_order:
            errors.append(
                f"Element ordering violation in {context}: "
                f"<{tag}> must come before <{last_tag}>"
            )
            break
        last_order = current_order
        last_tag = tag


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

INDENT = "  "


def format_prd(path: Path) -> str:
    """Format a PRD XML file. Returns the formatted XML string."""
    tree = ET.parse(path)
    root = tree.getroot()

    # Strip deprecated counter attributes — they are computed on demand by
    # the `stats` subcommand and no longer persisted.
    for attr in PRD_DEPRECATED_ATTRS:
        if attr in root.attrib:
            del root.attrib[attr]

    lines: list[str] = []
    _format_prd_element(root, lines)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def compute_prd_stats(root: ET.Element) -> dict:
    """Compute counters for a single <prd> element."""
    rules_done = 0
    rules_total = 0
    bugs_open = 0
    ui_reviewed = 0
    ui_total = 0

    for req in root.findall("requirement"):
        for rule in req.findall("rule"):
            rules_total += 1
            if rule.get("status") == "✅":
                rules_done += 1
        for ui_review in req.findall("ui_review"):
            ui_total += 1
            if ui_review.get("status") == "✅":
                ui_reviewed += 1

    for bug in root.findall("bug"):
        if bug.get("status") == "Open":
            bugs_open += 1

    return {
        "rules_done": rules_done,
        "rules_total": rules_total,
        "bugs_open": bugs_open,
        "ui_reviewed": ui_reviewed,
        "ui_total": ui_total,
    }


def _format_stats_line(name: str, stats: dict) -> str:
    return (
        f"{name}: "
        f"rules {stats['rules_done']}/{stats['rules_total']}, "
        f"bugs_open {stats['bugs_open']}, "
        f"ui {stats['ui_reviewed']}/{stats['ui_total']}"
    )


def print_stats(path: Path) -> int:
    """Print stats for a PRD file or a PRD index. Returns exit code."""
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        print(f"XML parse error: {e}", file=sys.stderr)
        return 1

    root = tree.getroot()

    if root.tag == "prd":
        name = root.get("name", path.name)
        stats = compute_prd_stats(root)
        print(_format_stats_line(name, stats))
        return 0

    if root.tag == "prd_index":
        base = path.parent
        exit_code = 0
        for module in root.findall("module"):
            module_name = module.get("name", "")
            print(f"[{module_name}]")
            for entry in module.findall("entry"):
                file_attr = entry.get("file", "")
                entry_name = entry.get("name", file_attr)
                target = base / file_attr
                if not target.exists():
                    print(f"  {entry_name}: (file not found: {target})")
                    exit_code = 1
                    continue
                try:
                    sub_root = ET.parse(target).getroot()
                except ET.ParseError as e:
                    print(f"  {entry_name}: (parse error: {e})")
                    exit_code = 1
                    continue
                stats = compute_prd_stats(sub_root)
                print(f"  {_format_stats_line(entry_name, stats)}")
        return exit_code

    print(
        f"Unsupported root element <{root.tag}> (expected <prd> or <prd_index>)",
        file=sys.stderr,
    )
    return 1


def _attrs_str(elem: ET.Element) -> str:
    """Format attributes in canonical order."""
    order = ATTR_ORDER.get(elem.tag, [])
    order_map = {k: i for i, k in enumerate(order)}
    sorted_attrs = sorted(
        elem.attrib.items(),
        key=lambda kv: (order_map.get(kv[0], 999), kv[0]),
    )
    parts = [f'{k}="{_escape_attr(v)}"' for k, v in sorted_attrs]
    return " ".join(parts)


def _escape_attr(value: str) -> str:
    """Escape attribute values for XML."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _escape_text(text: str) -> str:
    """Escape text content for XML."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _format_prd_element(root: ET.Element, lines: list[str]):
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
            # Unknown element — preserve as-is
            _format_generic(child, lines, depth=0)

    lines.append("")
    lines.append("</prd>")


def _format_text_block(elem: ET.Element, lines: list[str], depth: int):
    """Format an element with text content, preserving inner whitespace."""
    indent = INDENT * depth
    text = (elem.text or "").strip()
    if not text:
        lines.append(f"")
        lines.append(f"{indent}<{elem.tag}/>")
        return

    lines.append(f"")
    lines.append(f"{indent}<{elem.tag}>")
    for line in text.splitlines():
        lines.append(f"{_escape_text(line.rstrip())}")
    lines.append(f"{indent}</{elem.tag}>")


def _format_self_closing(elem: ET.Element, lines: list[str], depth: int):
    """Format a self-closing element."""
    indent = INDENT * depth
    attrs = _attrs_str(elem)
    lines.append(f"{indent}<{elem.tag} {attrs} />")


def _format_requirement(req: ET.Element, lines: list[str]):
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


def _format_description(elem: ET.Element, lines: list[str]):
    """Format a <description> inside a requirement."""
    text = (elem.text or "").strip()
    lines.append(f"{INDENT}<description>")
    for line in text.splitlines():
        lines.append(f"{INDENT}{INDENT}{_escape_text(line.strip())}")
    lines.append(f"{INDENT}</description>")


def _format_rule(rule: ET.Element, lines: list[str]):
    """Format a <rule> element, including nested <figma_node> children."""
    attrs = _attrs_str(rule)
    text = (rule.text or "").strip()
    figma_nodes = rule.findall("figma_node")

    if not figma_nodes:
        lines.append(f"{INDENT}<rule {attrs}>{_escape_text(text)}</rule>")
    else:
        lines.append(f"{INDENT}<rule {attrs}>{_escape_text(text)}")
        for fn in figma_nodes:
            fn_attrs = _attrs_str(fn)
            lines.append(f"{INDENT}{INDENT}<figma_node {fn_attrs} />")
        lines.append(f"{INDENT}</rule>")


def _format_ui_review(ui_review: ET.Element, lines: list[str]):
    """Format a <ui_review> element."""
    attrs = _attrs_str(ui_review)
    findings = ui_review.findall("finding")

    if not findings:
        lines.append(f"{INDENT}<ui_review {attrs} />")
    else:
        lines.append(f"{INDENT}<ui_review {attrs}>")
        for finding in findings:
            f_attrs = _attrs_str(finding)
            text = (finding.text or "").strip()
            lines.append(
                f"{INDENT}{INDENT}<finding {f_attrs}>{_escape_text(text)}</finding>"
            )
        lines.append(f"{INDENT}</ui_review>")


def _format_bug(bug: ET.Element, lines: list[str]):
    """Format a <bug> element."""
    attrs = _attrs_str(bug)
    lines.append("")
    lines.append(f"<bug {attrs}>")

    for child_tag in ("current", "expected", "steps"):
        child = bug.find(child_tag)
        if child is not None:
            text = (child.text or "").strip()
            lines.append(f"{INDENT}<{child_tag}>")
            for line in text.splitlines():
                lines.append(f"{INDENT}{INDENT}{_escape_text(line.strip())}")
            lines.append(f"{INDENT}</{child_tag}>")

    lines.append("</bug>")


def _format_generic(elem: ET.Element, lines: list[str], depth: int):
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


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="PRD XML validation and formatting tool."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    val_parser = sub.add_parser("validate", help="Validate PRD XML structure")
    val_parser.add_argument("file", type=Path, help="Path to PRD XML file")

    fmt_parser = sub.add_parser("format", help="Format and normalize PRD XML")
    fmt_parser.add_argument("file", type=Path, help="Path to PRD XML file")
    fmt_parser.add_argument(
        "--check",
        action="store_true",
        help="Check if file is already formatted (exit 1 if not)",
    )

    stats_parser = sub.add_parser(
        "stats",
        help="Print rule/bug/ui counters for a PRD file or PRD index (read-only)",
    )
    stats_parser.add_argument(
        "file",
        type=Path,
        help="Path to a <prd> XML file or a <prd_index> XML file",
    )

    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    if args.command == "validate":
        errors = validate(args.file)
        if errors:
            print(f"Validation failed with {len(errors)} error(s):\n")
            for i, err in enumerate(errors, 1):
                print(f"  {i}. {err}")
            sys.exit(1)
        else:
            print(f"Validation passed: {args.file}")
            sys.exit(0)

    elif args.command == "format":
        formatted = format_prd(args.file)
        if args.check:
            current = args.file.read_text(encoding="utf-8")
            if current == formatted:
                print(f"Already formatted: {args.file}")
                sys.exit(0)
            else:
                print(f"Not formatted: {args.file}", file=sys.stderr)
                sys.exit(1)
        else:
            args.file.write_text(formatted, encoding="utf-8")
            # Validate after formatting
            errors = validate(args.file)
            if errors:
                print(f"Formatted but validation found {len(errors)} error(s):")
                for i, err in enumerate(errors, 1):
                    print(f"  {i}. {err}")
                sys.exit(1)
            else:
                print(f"Formatted and validated: {args.file}")
                sys.exit(0)

    elif args.command == "stats":
        sys.exit(print_stats(args.file))


if __name__ == "__main__":
    main()
