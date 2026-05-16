"""PRD XML validation."""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from prd_tool.constants import (
    BUG_REQUIRED_ATTRS,
    BUG_STATUSES,
    FINDING_REQUIRED_ATTRS,
    PRD_CHILD_ORDER,
    PRD_REQUIRED_ATTRS,
    REQ_CHILD_ORDER,
    REQUIREMENT_REQUIRED_ATTRS,
    RULE_REQUIRED_ATTRS,
    RULE_STATUSES,
    UI_REVIEW_REQUIRED_ATTRS,
    UI_REVIEW_STATUSES,
)


def validate(path: Path) -> list[str]:
    """Validate a PRD XML file. Returns a list of error strings."""
    errors: list[str] = []

    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as e:
        errors.append(f"XML parse error: {e}")
        return errors

    root = tree.getroot()
    if root.tag != "prd":
        errors.append(f"Root element must be <prd>, got <{root.tag}>")
        return errors

    for attr in PRD_REQUIRED_ATTRS:
        if attr not in root.attrib:
            errors.append(f"<prd> missing required attribute: {attr}")

    child_tags = [child.tag for child in root]
    _check_ordering(child_tags, PRD_CHILD_ORDER, "<prd>", errors)

    all_rules: dict[str, str] = {}
    req_ids: list[str] = []
    req_prefix = "R"

    for req in root.findall("requirement"):
        req_id = req.get("id", "")
        req_ids.append(req_id)

        for attr in REQUIREMENT_REQUIRED_ATTRS:
            if attr not in req.attrib:
                errors.append(f"<requirement> missing required attribute: {attr}")

        expected_idx = len(req_ids)
        if expected_idx == 1:
            match = re.match(r"^([A-Z]+)(\d+)$", req_id)
            req_prefix = match.group(1) if match else "R"
        if req_id != f"{req_prefix}{expected_idx}":
            errors.append(
                f"Requirement ID out of sequence: got {req_id}, expected {req_prefix}{expected_idx}"
            )

        req_child_tags = [child.tag for child in req]
        _check_ordering(req_child_tags, REQ_CHILD_ORDER, f'<requirement id="{req_id}">', errors)

        rule_ids_in_req: set[str] = set()
        for rule in req.findall("rule"):
            for attr in RULE_REQUIRED_ATTRS:
                if attr not in rule.attrib:
                    errors.append(f"<rule> in {req_id} missing required attribute: {attr}")

            rule_id = rule.get("id", "")
            status = rule.get("status", "")

            if status not in RULE_STATUSES:
                errors.append(
                    f"Rule {req_id}.{rule_id}: invalid status '{status}' "
                    f"(expected one of {RULE_STATUSES})"
                )

            if rule_id in rule_ids_in_req:
                errors.append(f"Duplicate rule ID '{rule_id}' in {req_id}")
            rule_ids_in_req.add(rule_id)

            qualified = f"{req_id}.{rule_id}"
            all_rules[qualified] = req_id

        for ui_review in req.findall("ui_review"):
            for attr in UI_REVIEW_REQUIRED_ATTRS:
                if attr not in ui_review.attrib:
                    errors.append(f"<ui_review> in {req_id} missing required attribute: {attr}")

            ui_status = ui_review.get("status", "")
            if ui_status not in UI_REVIEW_STATUSES:
                errors.append(
                    f"<ui_review> in {req_id}: invalid status '{ui_status}' "
                    f"(expected one of {UI_REVIEW_STATUSES})"
                )

            for finding in ui_review.findall("finding"):
                for attr in FINDING_REQUIRED_ATTRS:
                    if attr not in finding.attrib:
                        errors.append(f"<finding> in {req_id} missing required attribute: {attr}")
                finding_rule = finding.get("rule", "")
                if finding_rule and finding_rule not in all_rules:
                    errors.append(f"<finding> references unknown rule: {finding_rule}")

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
                f"Bug '{bug_id}': invalid status '{status}' (expected one of {BUG_STATUSES})"
            )

        if bug_id in bug_ids:
            errors.append(f"Duplicate bug ID: '{bug_id}'")
        bug_ids.add(bug_id)

        if rule_ref and rule_ref not in all_rules:
            errors.append(f"Bug '{bug_id}' references unknown rule: {rule_ref}")

        for child_tag in ("current", "expected", "steps"):
            if bug.find(child_tag) is None:
                errors.append(f"Bug '{bug_id}' missing <{child_tag}> element")

    return errors


def _check_ordering(tags: list[str], canonical: list[str], context: str, errors: list[str]) -> None:
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
                f"Element ordering violation in {context}: <{tag}> must come before <{last_tag}>"
            )
            break
        last_order = current_order
        last_tag = tag
