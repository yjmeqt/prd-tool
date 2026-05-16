"""Tests for prd_tool.validate."""

from pathlib import Path

from prd_tool.validate import validate

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_minimal() -> None:
    errors = validate(FIXTURES / "valid_minimal.xml")
    assert errors == []


def test_valid_full() -> None:
    errors = validate(FIXTURES / "valid_full.xml")
    assert errors == []


def test_invalid_bad_root() -> None:
    errors = validate(FIXTURES / "invalid_bad_root.xml")
    assert any("Root element must be <prd>" in e for e in errors)


def test_invalid_missing_attr() -> None:
    errors = validate(FIXTURES / "invalid_missing_attr.xml")
    assert any("missing required attribute: name" in e for e in errors)


def test_invalid_bad_status() -> None:
    errors = validate(FIXTURES / "invalid_bad_status.xml")
    assert any("invalid status" in e for e in errors)


def test_invalid_duplicate_rule() -> None:
    errors = validate(FIXTURES / "invalid_duplicate_rule.xml")
    assert any("Duplicate rule ID" in e for e in errors)


def test_invalid_ordering() -> None:
    errors = validate(FIXTURES / "invalid_ordering.xml")
    assert any("Element ordering violation" in e for e in errors)


def test_nonexistent_file() -> None:
    errors = validate(Path("/nonexistent/prd.xml"))
    assert any("XML parse error" in e for e in errors)
