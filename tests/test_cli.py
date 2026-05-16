"""End-to-end CLI tests via subprocess."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"

VALID_MINIMAL = (FIXTURES / "valid_minimal.xml").read_text(encoding="utf-8")


def _run(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "prd_tool", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_validate_accepts_ref(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")
    target = tmp_path / "prd" / "comments" / "likes-saves.xml"
    target.parent.mkdir(parents=True)
    target.write_text(VALID_MINIMAL, encoding="utf-8")

    result = _run(["validate", "comments/likes-saves"], cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "Validation passed" in result.stdout


def test_validate_passthrough_explicit_path(tmp_path: Path) -> None:
    f = tmp_path / "anywhere.xml"
    f.write_text(VALID_MINIMAL, encoding="utf-8")

    result = _run(["validate", str(f)], cwd=tmp_path)

    assert result.returncode == 0, result.stderr


def test_validate_unknown_ref_error_message(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")

    result = _run(["validate", "no/such-feature"], cwd=tmp_path)

    assert result.returncode == 1
    assert ".prd-tool.toml" in result.stderr
    assert "prd/index.xml" in result.stderr


def test_prd_root_prints_resolved_root(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")

    result = _run(["root"], cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    fields = result.stdout.strip().split("\t")
    assert len(fields) == 3
    assert Path(fields[0]).resolve() == tmp_path.resolve()
    assert Path(fields[1]).resolve() == (tmp_path / "prd").resolve()
    assert fields[2] == "toml"


def test_prd_root_exit_1_when_missing(tmp_path: Path) -> None:
    result = _run(["root"], cwd=tmp_path)

    assert result.returncode == 1
    assert ".prd-tool.toml" in result.stderr
