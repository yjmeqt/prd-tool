"""Tests for the SSE watcher's event classification + endpoint smoke."""

from __future__ import annotations

from pathlib import Path

from watchfiles import Change

from prd_tool.dashboard.server import create_app
from prd_tool.dashboard.sse import classify_event

VALID = """<prd name="A"><overview>x</overview>
<requirement id="R1" name="N"><description>d</description>
<rule id="r" status="✅">y</rule>
</requirement></prd>
"""


def test_classify_index_change(tmp_path: Path) -> None:
    prd_dir = tmp_path / "prd"
    prd_dir.mkdir()
    idx = prd_dir / "index.xml"
    idx.write_text("<prd_index></prd_index>", encoding="utf-8")
    assert classify_event(prd_dir, Change.modified, idx) == {
        "type": "index_changed",
        "path": "index.xml",
    }


def test_classify_feature_change(tmp_path: Path) -> None:
    prd_dir = tmp_path / "prd"
    (prd_dir / "m").mkdir(parents=True)
    p = prd_dir / "m" / "f.xml"
    p.write_text(VALID, encoding="utf-8")
    assert classify_event(prd_dir, Change.modified, p) == {
        "type": "prd_changed",
        "path": "m/f.xml",
    }


def test_classify_invalid_xml(tmp_path: Path) -> None:
    prd_dir = tmp_path / "prd"
    (prd_dir / "m").mkdir(parents=True)
    p = prd_dir / "m" / "f.xml"
    p.write_text("<prd><broken", encoding="utf-8")
    assert classify_event(prd_dir, Change.modified, p) == {
        "type": "invalid",
        "path": "m/f.xml",
    }


def test_classify_deleted_file(tmp_path: Path) -> None:
    prd_dir = tmp_path / "prd"
    (prd_dir / "m").mkdir(parents=True)
    ghost = prd_dir / "m" / "gone.xml"
    assert classify_event(prd_dir, Change.deleted, ghost) == {
        "type": "index_changed",
        "path": "m/gone.xml",
    }


def test_classify_ignores_non_xml(tmp_path: Path) -> None:
    prd_dir = tmp_path / "prd"
    prd_dir.mkdir()
    p = prd_dir / "README.md"
    p.write_text("not xml", encoding="utf-8")
    assert classify_event(prd_dir, Change.modified, p) is None


def test_classify_outside_prd_dir(tmp_path: Path) -> None:
    prd_dir = tmp_path / "prd"
    prd_dir.mkdir()
    elsewhere = tmp_path / "other.xml"
    elsewhere.write_text(VALID, encoding="utf-8")
    assert classify_event(prd_dir, Change.modified, elsewhere) is None


def test_events_endpoint_is_registered(tmp_path: Path) -> None:
    prd_dir = tmp_path / "prd"
    prd_dir.mkdir()
    app = create_app(prd_dir)
    paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
    assert "/api/events" in paths
