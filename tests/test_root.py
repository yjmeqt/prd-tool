"""Tests for prd_tool.root."""

from __future__ import annotations

from pathlib import Path

import pytest

from prd_tool.root import Root, find_root, resolve_ref


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


def test_find_root_finds_convention(tmp_path: Path) -> None:
    _touch(tmp_path / "prd" / "index.xml")

    root = find_root(tmp_path)

    assert root == Root(
        repo_root=tmp_path,
        prd_dir=tmp_path / "prd",
        source="convention",
    )


def test_find_root_toml_beats_convention(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")
    _touch(tmp_path / "prd" / "index.xml")

    root = find_root(tmp_path)

    assert root is not None
    assert root.source == "toml"


def test_find_root_walks_up_to_marker(tmp_path: Path) -> None:
    sub = tmp_path / "nested" / "deeper"
    sub.mkdir(parents=True)
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")

    root = find_root(sub)

    assert root is not None
    assert root.repo_root == tmp_path


def test_find_root_custom_dir(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text('[prd]\ndir = "docs/prd"\n', encoding="utf-8")

    root = find_root(tmp_path)

    assert root is not None
    assert root.prd_dir == (tmp_path / "docs" / "prd").resolve()


def test_find_root_malformed_toml_uses_default_dir(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text("this is = not [ valid toml", encoding="utf-8")

    root = find_root(tmp_path)

    assert root is not None
    assert root.prd_dir == (tmp_path / "prd").resolve()


def test_resolve_ref_passthrough_existing_path(tmp_path: Path) -> None:
    f = tmp_path / "literal.xml"
    f.write_text("<prd name='x'/>", encoding="utf-8")

    resolved = resolve_ref(str(f), start=tmp_path)

    assert resolved == f


def test_resolve_ref_module_feature(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")
    target = tmp_path / "prd" / "comments" / "likes-saves.xml"
    _touch(target)

    resolved = resolve_ref("comments/likes-saves", start=tmp_path)

    assert resolved == target


def test_resolve_ref_tolerates_xml_suffix(tmp_path: Path) -> None:
    (tmp_path / ".prd-tool.toml").write_text("", encoding="utf-8")
    target = tmp_path / "prd" / "comments" / "likes-saves.xml"
    _touch(target)

    resolved = resolve_ref("comments/likes-saves.xml", start=tmp_path)

    assert resolved == target


def test_resolve_ref_no_root_raises(tmp_path: Path) -> None:
    sub = tmp_path / "nowhere"
    sub.mkdir()

    with pytest.raises(FileNotFoundError) as exc:
        resolve_ref("comments/likes-saves", start=sub)

    msg = str(exc.value)
    assert ".prd-tool.toml" in msg
    assert "prd/index.xml" in msg
    assert str(sub) in msg
