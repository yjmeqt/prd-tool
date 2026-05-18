"""Tests for the static JSON exporter."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
VALID_FULL = (FIXTURES / "valid_full.xml").read_text(encoding="utf-8")


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")
    prd_dir = tmp_path / "prd"
    target = prd_dir / "discovery" / "list.xml"
    target.parent.mkdir(parents=True)
    target.write_text(VALID_FULL, encoding="utf-8")
    # Drop a non-XML asset under the module so we can verify asset copy.
    asset = prd_dir / "discovery" / "screenshots" / "list.png"
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b"\x89PNG\r\n\x1a\n")
    return prd_dir


def test_export_static_writes_index_and_features(tmp_path: Path) -> None:
    from prd_tool.dashboard.export import export_static

    prd_dir = _make_repo(tmp_path)
    out = tmp_path / "out"

    counts = export_static(prd_dir, out)
    assert counts == {"features": 1, "assets": 1}

    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert [m["name"] for m in index["modules"]] == ["discovery"]
    feature_entry = index["modules"][0]["features"][0]
    assert feature_entry["ref"] == "discovery/list"
    assert feature_entry["parse_ok"] is True

    feature = json.loads((out / "prd" / "discovery" / "list.json").read_text(encoding="utf-8"))
    assert feature["ref"] == "discovery/list"
    assert feature["name"] == "Full Feature"
    assert any(r["id"] == "R1" for r in feature["requirements"])

    asset = out / "asset" / "discovery" / "screenshots" / "list.png"
    assert asset.is_file()
    assert asset.read_bytes() == b"\x89PNG\r\n\x1a\n"


def test_export_static_ignores_non_module_dirs(tmp_path: Path) -> None:
    """When the PRD root is the repo root, top-level dirs like .git must
    not be slurped into asset/."""
    from prd_tool.dashboard.export import export_static

    prd_dir = tmp_path / "prd-root"
    feature = prd_dir / "auth" / "login.xml"
    feature.parent.mkdir(parents=True)
    feature.write_text(VALID_FULL, encoding="utf-8")
    (prd_dir / "auth" / "screenshots").mkdir()
    (prd_dir / "auth" / "screenshots" / "login.png").write_bytes(b"\x89PNG")
    # Sibling directories that look like modules but have no PRDs.
    (prd_dir / ".git").mkdir()
    (prd_dir / ".git" / "config").write_text("nope", encoding="utf-8")
    (prd_dir / ".github" / "workflows").mkdir(parents=True)
    (prd_dir / ".github" / "workflows" / "pages.yml").write_text("nope", encoding="utf-8")
    (prd_dir / "scripts").mkdir()
    (prd_dir / "scripts" / "release.sh").write_text("nope", encoding="utf-8")
    # Dotfile inside the real module — should also be skipped.
    (prd_dir / "auth" / ".DS_Store").write_bytes(b"\x00\x00")

    counts = export_static(prd_dir, tmp_path / "out")

    assert counts["features"] == 1
    assert counts["assets"] == 1
    assert (tmp_path / "out" / "asset" / "auth" / "screenshots" / "login.png").is_file()
    assert not (tmp_path / "out" / "asset" / ".git").exists()
    assert not (tmp_path / "out" / "asset" / ".github").exists()
    assert not (tmp_path / "out" / "asset" / "scripts").exists()
    assert not (tmp_path / "out" / "asset" / "auth" / ".DS_Store").exists()


def test_export_static_cli(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    out = tmp_path / "out"

    result = subprocess.run(
        [sys.executable, "-m", "prd_tool", "export-json", str(out)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Exported 1 feature(s) and 1 asset(s)" in result.stdout
    assert (out / "index.json").is_file()
    assert (out / "prd" / "discovery" / "list.json").is_file()
