"""Tests for the dashboard edits pipeline + mutation endpoints."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prd_tool.dashboard.edits import (
    EditError,
    _mutate_and_persist,
    resolve_finding,
    set_bug_status,
    set_rule_status,
)
from prd_tool.dashboard.server import create_app

PRD_WITH_BUG_AND_REVIEW = """<prd name="Rich Feature">
<overview>A PRD that exercises rules, bugs, and ui_review.</overview>

<requirement id="R1" name="Basic">
  <description>Two rules and a finding.</description>
  <rule id="alpha" status="❌">First rule.</rule>
  <rule id="beta" status="✅">Second rule.</rule>
  <ui_review status="❌" date="2026-05-01">
    <finding rule="R1.alpha">Looks wrong.</finding>
    <finding rule="R1.beta">Wrong spacing.</finding>
  </ui_review>
</requirement>

<bug id="example_bug" status="Open" date="2026-05-10" rule="R1.alpha">
  <current>Broken behaviour.</current>
  <expected>Correct behaviour.</expected>
  <steps>1. Do the thing.</steps>
</bug>
</prd>
"""


@pytest.fixture
def feature_path(tmp_path: Path) -> Path:
    prd_dir = tmp_path / "prd"
    (prd_dir / "demo").mkdir(parents=True)
    p = prd_dir / "demo" / "thing.xml"
    p.write_text(PRD_WITH_BUG_AND_REVIEW, encoding="utf-8")
    return p


@pytest.fixture
def prd_dir(feature_path: Path) -> Path:
    return feature_path.parent.parent


def test_set_rule_status_flips_alpha(feature_path: Path) -> None:
    set_rule_status(feature_path, "alpha", "✅")
    text = feature_path.read_text(encoding="utf-8")
    assert 'id="alpha" status="✅"' in text


def test_set_rule_status_unknown_rule_is_not_found(feature_path: Path) -> None:
    with pytest.raises(EditError) as exc:
        set_rule_status(feature_path, "ghost", "✅")
    assert exc.value.code == "not_found"


def test_set_rule_status_rejects_invalid_status(feature_path: Path) -> None:
    with pytest.raises(EditError) as exc:
        set_rule_status(feature_path, "alpha", "DONE")
    assert exc.value.code == "invalid"


def test_set_bug_status_to_fix_pending(feature_path: Path) -> None:
    set_bug_status(feature_path, "example_bug", "Fix Pending")
    text = feature_path.read_text(encoding="utf-8")
    assert 'status="Fix Pending"' in text


def test_resolve_finding_keeps_others(feature_path: Path) -> None:
    resolve_finding(feature_path, "R1.alpha")
    text = feature_path.read_text(encoding="utf-8")
    assert "R1.alpha" not in text or 'rule="R1.alpha">Looks wrong' not in text
    assert 'rule="R1.beta">Wrong spacing' in text
    # ui_review still ❌ because one finding remains
    assert 'ui_review status="❌"' in text


def test_resolve_finding_marks_review_done_when_empty(feature_path: Path) -> None:
    resolve_finding(feature_path, "R1.alpha")
    resolve_finding(feature_path, "R1.beta")
    text = feature_path.read_text(encoding="utf-8")
    assert 'ui_review status="✅"' in text


def test_resolve_finding_unknown_rule_qid(feature_path: Path) -> None:
    with pytest.raises(EditError) as exc:
        resolve_finding(feature_path, "R1.ghost")
    assert exc.value.code == "not_found"


def test_post_rule_status_endpoint(prd_dir: Path) -> None:
    client = TestClient(create_app(prd_dir))
    r = client.post("/api/prd/demo/thing/rule/alpha/status", json={"status": "✅"})
    assert r.status_code == 200, r.text
    rules = {rule["id"]: rule for req in r.json()["requirements"] for rule in req["rules"]}
    assert rules["alpha"]["status"] == "✅"


def test_post_rule_status_invalid_returns_400(prd_dir: Path) -> None:
    client = TestClient(create_app(prd_dir))
    r = client.post("/api/prd/demo/thing/rule/alpha/status", json={"status": "DONE"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid"


def test_post_rule_status_unknown_rule_returns_404(prd_dir: Path) -> None:
    client = TestClient(create_app(prd_dir))
    r = client.post("/api/prd/demo/thing/rule/ghost/status", json={"status": "✅"})
    assert r.status_code == 404


def test_post_bug_status_endpoint(prd_dir: Path) -> None:
    client = TestClient(create_app(prd_dir))
    r = client.post(
        "/api/prd/demo/thing/bug/example_bug/status",
        json={"status": "Fix Pending"},
    )
    assert r.status_code == 200
    assert r.json()["bugs"][0]["status"] == "Fix Pending"


def test_post_finding_resolve_endpoint(prd_dir: Path) -> None:
    client = TestClient(create_app(prd_dir))
    r = client.post("/api/prd/demo/thing/finding/R1.alpha/resolve")
    assert r.status_code == 200
    findings = r.json()["requirements"][0]["ui_reviews"][0]["findings"]
    assert all(f["rule"] != "R1.alpha" for f in findings)


def test_concurrent_disk_change_returns_conflict(feature_path: Path) -> None:
    """Simulate an editor overwriting the file mid-edit; persist must refuse."""

    def _apply(root: ET.Element) -> None:
        rule = root.find("requirement/rule[@id='alpha']")
        assert rule is not None
        rule.set("status", "✅")
        time.sleep(0.01)
        feature_path.write_text(feature_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(EditError) as exc:
        _mutate_and_persist(feature_path, _apply)
    assert exc.value.code == "conflict"
