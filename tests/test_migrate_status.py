import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from prd_tool.migrate_status import migrate_status
from prd_tool.overlay import load_progress, overlay_path


def setup_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".prd-tool.toml").write_text('prd_dir = "prd"', encoding="utf-8")

    prd_dir = repo / "prd"
    prd_dir.mkdir()

    xml = """<?xml version="1.0" encoding="utf-8"?>
<prd name="Test">
  <requirement id="R1" name="Req 1">
    <rule id="foo" status="✅">Done rule</rule>
    <rule id="bar" status="❌">Not done rule</rule>
  </requirement>
</prd>
"""
    feat_dir = prd_dir / "mod1"
    feat_dir.mkdir()
    (feat_dir / "feat1.xml").write_text(xml, encoding="utf-8")
    return repo


def test_migrate_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = setup_repo(tmp_path)
    monkeypatch.chdir(repo)

    assert migrate_status(dry_run=False) == 0

    status_dir = repo / "prd-status"
    op = overlay_path(status_dir, "mod1", "feat1")
    assert op.exists()

    prog = load_progress(op)
    assert prog.rules == {"R1.foo": "✅", "R1.bar": "❌"}

    # Check XML has no status
    xml_path = repo / "prd" / "mod1" / "feat1.xml"
    tree = ET.parse(xml_path)
    root = tree.getroot()
    req = root.find("requirement")
    assert req is not None
    rules = req.findall("rule")
    assert len(rules) == 2
    for r in rules:
        assert "status" not in r.attrib

    from prd_tool.validate import validate

    errors = validate(xml_path, require_rule_status=False)
    assert not errors


def test_migrate_status_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = setup_repo(tmp_path)
    monkeypatch.chdir(repo)

    assert migrate_status(dry_run=True) == 0

    status_dir = repo / "prd-status"
    assert not status_dir.exists()

    xml_path = repo / "prd" / "mod1" / "feat1.xml"
    tree = ET.parse(xml_path)
    root = tree.getroot()
    req = root.find("requirement")
    assert req is not None
    assert req.findall("rule")[0].get("status") == "✅"


def test_migrate_status_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = setup_repo(tmp_path)
    monkeypatch.chdir(repo)

    assert migrate_status(dry_run=False) == 0

    # Second run
    assert migrate_status(dry_run=False) == 0

    status_dir = repo / "prd-status"
    op = overlay_path(status_dir, "mod1", "feat1")
    prog = load_progress(op)
    assert prog.rules == {"R1.foo": "✅", "R1.bar": "❌"}


def test_migrate_status_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = setup_repo(tmp_path)
    monkeypatch.chdir(repo)

    status_dir = repo / "prd-status"
    op = overlay_path(status_dir, "mod1", "feat1")
    op.parent.mkdir(parents=True, exist_ok=True)

    # Pre-existing TOML
    toml_content = """[rules]
"R1.bar" = "✅"
"R1.baz" = "❌"

[notes]
"R1.foo" = "Some note"

[[platform_rule]]
id = "PR1"
status = "✅"
"""
    op.write_text(toml_content, encoding="utf-8")

    assert migrate_status(dry_run=False) == 0

    prog = load_progress(op)
    # XML overrides bar to ❌, foo is added, baz is kept
    assert prog.rules == {"R1.foo": "✅", "R1.bar": "❌", "R1.baz": "❌"}
    assert prog.notes == {"R1.foo": "Some note"}
    assert len(prog.platform_rules) == 1
    assert prog.platform_rules[0].id == "PR1"


def test_migrate_status_namespaced_requires_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = setup_repo(tmp_path)
    (repo / "prd-status" / "ios").mkdir(parents=True)
    monkeypatch.chdir(repo)

    assert migrate_status(dry_run=False) == 1


def test_migrate_status_namespaced_writes_under_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = setup_repo(tmp_path)
    (repo / "prd-status" / "ios").mkdir(parents=True)
    monkeypatch.chdir(repo)

    assert migrate_status(dry_run=False, platform="ios") == 0

    op = overlay_path(repo / "prd-status", "mod1", "feat1", "ios")
    assert op.exists()
    prog = load_progress(op)
    assert prog.rules == {"R1.foo": "✅", "R1.bar": "❌"}
    assert not (repo / "prd-status" / "mod1" / "feat1.toml").exists()
