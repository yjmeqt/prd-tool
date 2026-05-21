"""Test the JsApi bridge surface without launching pywebview."""

from __future__ import annotations

from pathlib import Path

import pytest

from prd_tool.dashboard.native import JsApi

FIXTURES = Path(__file__).parent / "fixtures"
VALID_MINIMAL = (FIXTURES / "valid_minimal.xml").read_text(encoding="utf-8")


@pytest.fixture
def prd_dir(tmp_path: Path) -> Path:
    d = tmp_path / "prd"
    (d / "alpha").mkdir(parents=True)
    (d / "alpha" / "first.xml").write_text(VALID_MINIMAL, encoding="utf-8")
    (d / "index.xml").write_text("<prd_index></prd_index>", encoding="utf-8")
    return d


def test_index_returns_raw(prd_dir: Path) -> None:
    api = JsApi(prd_dir)
    out = api.index()
    # raw payload, no {ok,data} wrapper
    assert "modules" in out


def test_feature_ok_envelope(prd_dir: Path) -> None:
    api = JsApi(prd_dir)
    out = api.feature("alpha", "first")
    assert out["ok"] is True
    assert out["data"]["module"] == "alpha"


def test_feature_missing_error_envelope(prd_dir: Path) -> None:
    api = JsApi(prd_dir)
    out = api.feature("alpha", "nope")
    assert out["ok"] is False
    assert out["error"]["code"] == "not_found"


def test_set_rule_status_error_envelope(prd_dir: Path) -> None:
    api = JsApi(prd_dir)
    out = api.set_rule_status("alpha", "first", "hello", "bogus")
    assert out["ok"] is False
    assert out["error"]["code"] == "invalid"


def test_set_rule_status_ok(prd_dir: Path) -> None:
    api = JsApi(prd_dir)
    out = api.set_rule_status("alpha", "first", "hello", "❌")
    assert out["ok"] is True


def test_asset_root_is_absolute_prd_dir(prd_dir: Path) -> None:
    api = JsApi(prd_dir)
    assert api.asset_root() == str(prd_dir.resolve())


def test_open_window_without_factory_returns_internal_error(prd_dir: Path) -> None:
    api = JsApi(prd_dir)
    out = api.open_window("alpha/first")
    assert out["ok"] is False
    assert out["error"]["code"] == "internal"


def test_open_window_invokes_factory(prd_dir: Path) -> None:
    api = JsApi(prd_dir)
    calls: list[str | None] = []
    api._open_window = lambda r: calls.append(r)
    out = api.open_window("alpha/first")
    assert out["ok"] is True
    assert calls == ["alpha/first"]
