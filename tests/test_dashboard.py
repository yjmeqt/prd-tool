"""Tests for the dashboard backend (server + repo parser)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from prd_tool.dashboard.repo import FeatureRef, build_index, load_feature
from prd_tool.dashboard.server import create_app

FIXTURES = Path(__file__).parent / "fixtures"
VALID_MINIMAL = (FIXTURES / "valid_minimal.xml").read_text(encoding="utf-8")


@pytest.fixture
def prd_dir(tmp_path: Path) -> Path:
    d = tmp_path / "prd"
    (d / "alpha").mkdir(parents=True)
    (d / "alpha" / "first.xml").write_text(VALID_MINIMAL, encoding="utf-8")
    (d / "beta").mkdir()
    (d / "beta" / "second.xml").write_text(VALID_MINIMAL, encoding="utf-8")
    (d / "index.xml").write_text("<prd_index></prd_index>", encoding="utf-8")
    return d


def test_build_index_groups_by_module(prd_dir: Path) -> None:
    payload = build_index(prd_dir)
    modules = {m["name"]: m for m in payload["modules"]}
    assert set(modules) == {"alpha", "beta"}
    alpha = modules["alpha"]["features"]
    assert len(alpha) == 1
    assert alpha[0]["ref"] == "alpha/first"
    assert alpha[0]["name"] == "Minimal Feature"
    assert alpha[0]["stats"]["rules_total"] == 1
    assert alpha[0]["stats"]["rules_done"] == 1


def test_load_feature_returns_requirements(prd_dir: Path) -> None:
    payload = load_feature(prd_dir, FeatureRef("alpha", "first"))
    assert payload is not None
    assert payload["name"] == "Minimal Feature"
    assert payload["overview"] == "A minimal valid PRD for testing."
    assert len(payload["requirements"]) == 1
    req = payload["requirements"][0]
    assert req["id"] == "R1"
    assert req["rules"][0]["id"] == "hello"
    assert req["rules"][0]["status"] == "✅"


def test_load_feature_missing_returns_none(prd_dir: Path) -> None:
    assert load_feature(prd_dir, FeatureRef("alpha", "ghost")) is None


def test_load_feature_invalid_xml_returns_parse_error(prd_dir: Path) -> None:
    (prd_dir / "alpha" / "broken.xml").write_text("<prd><not closed", encoding="utf-8")
    payload = load_feature(prd_dir, FeatureRef("alpha", "broken"))
    assert payload is not None
    assert "parse_error" in payload


def test_api_index_endpoint(prd_dir: Path) -> None:
    client = TestClient(create_app(prd_dir))
    r = client.get("/api/index")
    assert r.status_code == 200
    modules = {m["name"]: m for m in r.json()["modules"]}
    assert "alpha" in modules
    assert modules["alpha"]["features"][0]["ref"] == "alpha/first"


def test_api_prd_endpoint(prd_dir: Path) -> None:
    client = TestClient(create_app(prd_dir))
    r = client.get("/api/prd/alpha/first")
    assert r.status_code == 200
    assert r.json()["name"] == "Minimal Feature"


def test_api_prd_missing_is_404(prd_dir: Path) -> None:
    client = TestClient(create_app(prd_dir))
    r = client.get("/api/prd/alpha/ghost")
    assert r.status_code == 404


def test_api_health(prd_dir: Path) -> None:
    client = TestClient(create_app(prd_dir))
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["prd_dir"] == str(prd_dir)
    assert "figma_token" not in body


def test_no_figma_endpoints(prd_dir: Path) -> None:
    app = create_app(prd_dir)
    paths = {r.path for r in app.routes}  # type: ignore[attr-defined]
    assert not any(p.startswith("/api/figma") for p in paths)


def test_root_serves_placeholder_when_no_static(prd_dir: Path) -> None:
    client = TestClient(create_app(prd_dir))
    r = client.get("/")
    assert r.status_code == 200
    assert "PRD Dashboard" in r.text
