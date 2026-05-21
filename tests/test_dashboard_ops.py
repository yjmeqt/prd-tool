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
