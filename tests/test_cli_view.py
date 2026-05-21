"""Smoke tests for the `prd view` CLI surface."""

from __future__ import annotations

import subprocess
import sys


def test_view_help_lists_server_flag() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "prd_tool", "view", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--server" in r.stdout
    assert "view" in r.stdout.lower()


def test_dashboard_alias_help_still_works() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "prd_tool", "dashboard", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--host" in r.stdout


def test_top_level_help_does_not_describe_dashboard() -> None:
    r = subprocess.run(
        [sys.executable, "-m", "prd_tool", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "view" in r.stdout
    # argparse still surfaces hidden subcommands in the {choices} usage line,
    # but `help=SUPPRESS` removes the description row. Assert the description
    # section after "subcommands:" contains `view` but not `dashboard`.
    if "subcommands:" in r.stdout:
        tail = r.stdout.split("subcommands:", 1)[1]
        assert "view" in tail
        assert "dashboard" not in tail
