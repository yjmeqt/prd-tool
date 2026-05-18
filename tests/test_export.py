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
