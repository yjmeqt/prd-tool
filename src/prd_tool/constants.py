"""Constants used across the prd-tool package."""

from typing import Final

RULE_STATUSES: Final = {"✅", "❌", "⚠️"}
BUG_STATUSES: Final = {"Open", "Fix Pending", "Fixed"}
UI_REVIEW_STATUSES: Final = {"✅", "❌", "⚠️"}

PRD_REQUIRED_ATTRS: Final = {"name"}
PRD_DEPRECATED_ATTRS: Final = {
    "rules_done",
    "rules_total",
    "bugs_open",
    "ui_reviewed",
    "ui_total",
}
REQUIREMENT_REQUIRED_ATTRS: Final = {"id", "name"}
RULE_REQUIRED_ATTRS: Final = {"id", "status"}
BUG_REQUIRED_ATTRS: Final = {"id", "status", "date", "rule"}
UI_REVIEW_REQUIRED_ATTRS: Final = {"status", "date"}
FINDING_REQUIRED_ATTRS: Final = {"rule"}

PRD_CHILD_ORDER: Final = ["overview", "implementation", "requirement", "bug"]
REQ_CHILD_ORDER: Final = ["description", "rule", "ui_review"]

ATTR_ORDER: Final = {
    "prd": ["name"],
    "implementation": ["platform", "spec"],
    "requirement": ["id", "name"],
    "rule": ["id", "status", "context"],
    "figma_node": ["name", "file", "node"],
    "bug": ["id", "status", "date", "rule"],
    "ui_review": ["status", "date"],
    "finding": ["rule"],
}

INDENT: Final = "  "
