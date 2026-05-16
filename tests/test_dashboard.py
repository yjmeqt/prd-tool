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


# Rich-content (XHTML) JSON serialization tests


_RICH_PRD = (
    '<prd name="Rich Demo">\n'
    "<overview>\n"
    "Use <code>POST /login</code> for sign-in.<br/>\n"
    "Returns <strong>200</strong> on success.\n"
    "</overview>\n"
    "\n"
    '<requirement id="R1" name="Rich rules">\n'
    "  <description>Intro with <em>emphasis</em>."
    "<ul><li>One</li><li>Two</li></ul></description>\n"
    '  <rule id="r1" status="✅">Tap '
    '<a href="prd:dashboard/viewer#R1">the dashboard launch rules</a>.</rule>\n'
    '  <rule id="r2" status="❌">Shows '
    '<img src="screenshots/err.png" alt="Error toast"/> when failing.</rule>\n'
    '  <rule id="r3" status="✅">Plain text rule with no markup at all.</rule>\n'
    "</requirement>\n"
    "\n"
    '<bug id="b1" status="Open" date="2026-05-16" rule="R1.r1">\n'
    "  <current>Login throws <strong>500</strong>.</current>\n"
    "  <expected>Login returns <code>200</code>.</expected>\n"
    "  <steps>1. Open <em>login</em>. 2. Submit.</steps>\n"
    "</bug>\n"
    "\n"
    "</prd>\n"
)


@pytest.fixture
def rich_prd_dir(tmp_path: Path) -> Path:
    d = tmp_path / "prd"
    (d / "content").mkdir(parents=True)
    (d / "content" / "rich.xml").write_text(_RICH_PRD, encoding="utf-8")
    return d


def test_rich_overview_is_html_string(rich_prd_dir: Path) -> None:
    payload = load_feature(rich_prd_dir, FeatureRef("content", "rich"))
    assert payload is not None
    assert "<code>POST /login</code>" in payload["overview"]
    assert "<br/>" in payload["overview"]
    assert "<strong>200</strong>" in payload["overview"]


def test_rich_description_serializes_children(rich_prd_dir: Path) -> None:
    payload = load_feature(rich_prd_dir, FeatureRef("content", "rich"))
    assert payload is not None
    desc = payload["requirements"][0]["description"]
    assert "<em>emphasis</em>" in desc
    assert "<ul>" in desc and "<li>One</li>" in desc


def test_rich_rule_text_serializes_links(rich_prd_dir: Path) -> None:
    payload = load_feature(rich_prd_dir, FeatureRef("content", "rich"))
    assert payload is not None
    r1 = payload["requirements"][0]["rules"][0]
    assert '<a href="prd:dashboard/viewer#R1">' in r1["text"]


def test_void_tags_self_close_in_json(rich_prd_dir: Path) -> None:
    payload = load_feature(rich_prd_dir, FeatureRef("content", "rich"))
    assert payload is not None
    r2 = payload["requirements"][0]["rules"][1]
    assert '<img src="screenshots/err.png" alt="Error toast"/>' in r2["text"]


def test_plain_text_rule_unchanged(rich_prd_dir: Path) -> None:
    payload = load_feature(rich_prd_dir, FeatureRef("content", "rich"))
    assert payload is not None
    r3 = payload["requirements"][0]["rules"][2]
    assert r3["text"] == "Plain text rule with no markup at all."


def test_rich_bug_fields_are_html(rich_prd_dir: Path) -> None:
    payload = load_feature(rich_prd_dir, FeatureRef("content", "rich"))
    assert payload is not None
    bug = payload["bugs"][0]
    assert "<strong>500</strong>" in bug["current"]
    assert "<code>200</code>" in bug["expected"]
    assert "<em>login</em>" in bug["steps"]


# Asset endpoint


def test_asset_endpoint_serves_local_file(rich_prd_dir: Path) -> None:
    asset = rich_prd_dir / "content" / "screenshots" / "err.png"
    asset.parent.mkdir(parents=True, exist_ok=True)
    asset.write_bytes(b"PNGDATA")
    client = TestClient(create_app(rich_prd_dir))
    r = client.get("/api/prd-asset/content/rich/screenshots/err.png")
    assert r.status_code == 200
    assert r.content == b"PNGDATA"


def test_asset_endpoint_rejects_traversal(rich_prd_dir: Path) -> None:
    secret = rich_prd_dir.parent / "secret.txt"
    secret.write_text("classified", encoding="utf-8")
    client = TestClient(create_app(rich_prd_dir))
    r = client.get("/api/prd-asset/content/rich/../../secret.txt")
    assert r.status_code == 404


def test_asset_endpoint_missing_file_is_404(rich_prd_dir: Path) -> None:
    client = TestClient(create_app(rich_prd_dir))
    r = client.get("/api/prd-asset/content/rich/nope.png")
    assert r.status_code == 404


def test_asset_endpoint_missing_module_is_404(rich_prd_dir: Path) -> None:
    client = TestClient(create_app(rich_prd_dir))
    r = client.get("/api/prd-asset/ghost/feat/x.png")
    assert r.status_code == 404
