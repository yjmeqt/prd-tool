"""Tests for prd_tool.root."""

from __future__ import annotations

from pathlib import Path

import pytest  # noqa: F401  # used in later tasks

from prd_tool.root import Root, find_root


def _touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="utf-8")


def test_find_root_finds_toml_at_cwd(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")

    root = find_root(tmp_path)

    assert root == Root(
        repo_root=tmp_path,
        prd_dir=tmp_path / "prd",
        source="toml",
    )
