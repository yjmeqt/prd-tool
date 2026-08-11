"""Tests for the transport-agnostic DashboardOps layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from prd_tool.dashboard.ops import DashboardOps, OpsError

FIXTURES = Path(__file__).parent / "fixtures"
VALID_MINIMAL = (FIXTURES / "valid_minimal.xml").read_text(encoding="utf-8")


@pytest.fixture
def prd_dir(tmp_path: Path) -> Path:
    d = tmp_path / "prd"
    (d / "alpha").mkdir(parents=True)
    (d / "alpha" / "first.xml").write_text(VALID_MINIMAL, encoding="utf-8")
    (d / "index.xml").write_text("<prd_index></prd_index>", encoding="utf-8")
    return d


def test_index_returns_modules(prd_dir: Path) -> None:
    ops = DashboardOps(prd_dir)
    idx = ops.index()
    names = {m["name"] for m in idx["modules"]}
    assert "alpha" in names


def test_feature_roundtrip(prd_dir: Path) -> None:
    ops = DashboardOps(prd_dir)
    feat = ops.feature("alpha", "first")
    assert feat["module"] == "alpha"
    assert feat["feature"] == "first"


def test_feature_missing_raises_not_found(prd_dir: Path) -> None:
    ops = DashboardOps(prd_dir)
    with pytest.raises(OpsError) as ei:
        ops.feature("alpha", "nope")
    assert ei.value.code == "not_found"


def test_set_rule_status_returns_updated_feature(prd_dir: Path) -> None:
    ops = DashboardOps(prd_dir)
    payload = ops.set_rule_status("alpha", "first", "hello", "❌")
    assert payload["module"] == "alpha"


def test_set_rule_status_invalid_raises(prd_dir: Path) -> None:
    ops = DashboardOps(prd_dir)
    with pytest.raises(OpsError) as ei:
        ops.set_rule_status("alpha", "first", "hello", "bogus")
    assert ei.value.code == "invalid"


def test_asset_path_traversal_blocked(prd_dir: Path) -> None:
    # Create a file outside the module dir we should not be able to read.
    secret = prd_dir.parent / "secret.txt"
    secret.write_text("nope", encoding="utf-8")
    ops = DashboardOps(prd_dir)
    with pytest.raises(OpsError) as ei:
        ops.asset_path("alpha", "first", "../../secret.txt")
    assert ei.value.code == "not_found"


def test_asset_path_missing_module_raises(prd_dir: Path) -> None:
    ops = DashboardOps(prd_dir)
    with pytest.raises(OpsError) as ei:
        ops.asset_path("nope", "first", "anything.png")
    assert ei.value.code == "not_found"


def test_feature_with_status_dir(prd_dir: Path, tmp_path: Path) -> None:
    status_dir = tmp_path / "status"
    status_dir.mkdir()
    (status_dir / "alpha").mkdir()
    (status_dir / "alpha" / "first.toml").write_text(
        '[rules]\n"R1.hello" = "✅"\n', encoding="utf-8"
    )

    ops = DashboardOps(prd_dir, status_dir)
    feat = ops.feature("alpha", "first")

    # Check rule status is joined from progress
    r1 = feat["requirements"][0]
    rule = r1["rules"][0]
    assert rule["id"] == "hello"
    assert rule["status"] == "✅"


def test_index_with_status_dir(prd_dir: Path, tmp_path: Path) -> None:
    status_dir = tmp_path / "status"
    status_dir.mkdir()
    (status_dir / "alpha").mkdir()
    (status_dir / "alpha" / "first.toml").write_text(
        '[rules]\n"R1.hello" = "✅"\n', encoding="utf-8"
    )

    ops = DashboardOps(prd_dir, status_dir)
    idx = ops.index()

    alpha = next(m for m in idx["modules"] if m["name"] == "alpha")
    first = next(f for f in alpha["features"] if f["feature"] == "first")

    assert first["stats"]["rules_done"] == 1
    assert first["stats"]["rules_total"] == 1


def test_set_rule_status_overlay_updates_toml(prd_dir: Path, tmp_path: Path) -> None:
    status_dir = tmp_path / "status"
    ops = DashboardOps(prd_dir, status_dir)

    # Set status
    ops.set_rule_status("alpha", "first", "hello", "❌")

    # TOML should be created
    toml_path = status_dir / "alpha" / "first.toml"
    assert toml_path.exists()
    content = toml_path.read_text(encoding="utf-8")
    assert "[rules]" in content
    assert '"R1.hello" = "❌"' in content

    # XML should remain unchanged
    xml_path = prd_dir / "alpha" / "first.xml"
    xml_content = xml_path.read_text(encoding="utf-8")
    assert xml_content == VALID_MINIMAL


def test_set_rule_status_overlay_preserves_other_sections(prd_dir: Path, tmp_path: Path) -> None:
    status_dir = tmp_path / "status"
    status_dir.mkdir()
    (status_dir / "alpha").mkdir()
    toml_path = status_dir / "alpha" / "first.toml"
    toml_path.write_text(
        '[rules]\n"R1.other" = "❌"\n\n[notes]\n"R1.other" = "test note"\n\n[[platform_rule]]\n'
        'id = "ios"\nstatus = "✅"\n',
        encoding="utf-8",
    )

    ops = DashboardOps(prd_dir, status_dir)
    ops.set_rule_status("alpha", "first", "hello", "✅")

    content = toml_path.read_text(encoding="utf-8")
    # Both rules should be present
    assert '"R1.hello" = "✅"' in content
    assert '"R1.other" = "❌"' in content
    # Notes preserved
    assert '"R1.other" = "test note"' in content
    # Platform rule preserved
    assert 'id = "ios"' in content


def test_set_rule_status_overlay_unknown_rule_raises(prd_dir: Path, tmp_path: Path) -> None:
    status_dir = tmp_path / "status"
    ops = DashboardOps(prd_dir, status_dir)
    with pytest.raises(OpsError) as ei:
        ops.set_rule_status("alpha", "first", "bogus_rule", "✅")
    assert ei.value.code == "not_found"


def test_set_rule_status_overlay_invalid_status(prd_dir: Path, tmp_path: Path) -> None:
    status_dir = tmp_path / "status"
    ops = DashboardOps(prd_dir, status_dir)
    with pytest.raises(OpsError) as ei:
        ops.set_rule_status("alpha", "first", "hello", "bogus")
    assert ei.value.code == "invalid"
