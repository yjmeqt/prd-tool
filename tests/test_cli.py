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


def test_prd_ls_lists_refs(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")
    (tmp_path / "prd").mkdir()
    (tmp_path / "prd" / "index.xml").write_text("", encoding="utf-8")
    (tmp_path / "prd" / "comments").mkdir()
    (tmp_path / "prd" / "comments" / "likes-saves.xml").write_text("", encoding="utf-8")
    (tmp_path / "prd" / "comments" / "mentions.xml").write_text("", encoding="utf-8")
    (tmp_path / "prd" / "auth").mkdir()
    (tmp_path / "prd" / "auth" / "login.xml").write_text("", encoding="utf-8")

    result = _run(["ls"], cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    lines = sorted(result.stdout.strip().splitlines())
    assert lines == ["auth/login", "comments/likes-saves", "comments/mentions"]


def test_prd_ls_filters_by_module(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")
    (tmp_path / "prd" / "comments").mkdir(parents=True)
    (tmp_path / "prd" / "comments" / "likes-saves.xml").write_text("", encoding="utf-8")
    (tmp_path / "prd" / "auth").mkdir()
    (tmp_path / "prd" / "auth" / "login.xml").write_text("", encoding="utf-8")

    result = _run(["ls", "comments"], cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip().splitlines() == ["comments/likes-saves"]


def test_dashboard_refuses_without_tty(tmp_path: Path) -> None:
    """Subprocess stdin is a pipe (not a TTY); the dashboard must refuse."""
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")
    (tmp_path / "prd").mkdir()

    result = _run(["dashboard", "--no-open", "--port", "8766"], cwd=tmp_path)

    assert result.returncode == 1
    assert "interactive terminal" in result.stderr
    assert "TTY" in result.stderr


def test_dashboard_no_tty_env_override_attempts_boot(tmp_path: Path) -> None:
    """With the env override set, the TTY guard must let the run proceed past
    the check. We catch it at the port-bind step by giving it a port that's
    already in use, which should fail with the friendly port message rather
    than the TTY message."""
    import socket

    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")
    (tmp_path / "prd").mkdir()

    holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        holder.bind(("127.0.0.1", 0))
        port = holder.getsockname()[1]
        env = {**__import__("os").environ, "PRD_DASHBOARD_ALLOW_NO_TTY": "1"}
        result = subprocess.run(
            [sys.executable, "-m", "prd_tool", "dashboard", "--no-open", "--port", str(port)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )
    finally:
        holder.close()

    assert result.returncode == 1
    assert "interactive terminal" not in result.stderr
    assert "cannot bind" in result.stderr


def test_ls_unfinished_filters_done_refs(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")
    prd = tmp_path / "prd"
    done = (
        '<prd name="Done">'
        '<requirement id="R1" name="x"><description>d</description>'
        '<rule id="r" status="✅">all good</rule>'
        "</requirement></prd>"
    )
    wip = (
        '<prd name="Wip">'
        '<requirement id="R1" name="x"><description>d</description>'
        '<rule id="r" status="❌">todo</rule>'
        "</requirement></prd>"
    )
    (prd / "alpha").mkdir(parents=True)
    (prd / "beta").mkdir(parents=True)
    (prd / "alpha" / "done.xml").write_text(done, encoding="utf-8")
    (prd / "beta" / "wip.xml").write_text(wip, encoding="utf-8")

    result = _run(["ls", "-u"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    refs = [ln for ln in result.stdout.splitlines() if ln]
    assert refs == ["beta/wip"]


def test_ls_without_unfinished_lists_all(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")
    prd = tmp_path / "prd"
    (prd / "m").mkdir(parents=True)
    (prd / "m" / "a.xml").write_text(VALID_MINIMAL, encoding="utf-8")
    (prd / "m" / "b.xml").write_text(VALID_MINIMAL, encoding="utf-8")

    result = _run(["ls"], cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    refs = sorted(ln for ln in result.stdout.splitlines() if ln)
    assert refs == ["m/a", "m/b"]
