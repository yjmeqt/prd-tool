"""Tests for the hybrid search index (lexical paths; embeddings stubbed)."""

from __future__ import annotations

from pathlib import Path

import pytest

from prd_tool.dashboard import search
from prd_tool.dashboard.ops import DashboardOps

SAMPLE = """<prd name="Collection Feed">
<overview>Inner feed shows a collection of items.</overview>

<requirement id="R10" name="Collection Inner Feed">
  <description>The inner feed renders collection entries.</description>
  <rule id="renders_items" status="✅">展示收藏内流的条目列表。</rule>
  <rule id="paginates" status="❌">Loads more items when scrolling to the bottom.</rule>
  <rule id="has_shot" status="❌">See <img src="shots/login.png"/> for the layout.</rule>
</requirement>

<bug id="B1" status="Open" date="2026-01-01" rule="R10.paginates">
  <current>Pagination stalls after the second page.</current>
  <expected>It should keep loading.</expected>
</bug>
</prd>
"""


@pytest.fixture
def prd_dir(tmp_path: Path) -> Path:
    d = tmp_path / "prd"
    (d / "feed" / "shots").mkdir(parents=True)
    (d / "feed" / "collection.xml").write_text(SAMPLE, encoding="utf-8")
    # A real (tiny) file so the OCR enrichment can hash it.
    (d / "feed" / "shots" / "login.png").write_bytes(b"\x89PNG\r\n\x1a\n-fake-png-bytes")
    (d / "index.xml").write_text("<prd_index></prd_index>", encoding="utf-8")
    return d


def test_tokenize_latin_and_cjk_bigrams() -> None:
    toks = search.tokenize("Inner Feed 收藏内流")
    assert "inner" in toks
    assert "feed" in toks
    # CJK has no word breaks → overlapping bigrams
    assert "收藏" in toks
    assert "藏内" in toks
    assert "内流" in toks


def test_iter_fragments_kinds_and_anchors(prd_dir: Path) -> None:
    frags = search.iter_fragments(prd_dir)
    by_anchor = {f.anchor: f for f in frags}
    kinds = {f.kind for f in frags}
    assert kinds == {"overview", "requirement", "rule", "bug", "image"}
    # rule anchor matches the DOM id RuleCard renders: "<reqId>.<ruleId>"
    assert "R10.renders_items" in by_anchor
    assert by_anchor["R10.renders_items"].kind == "rule"
    # bug anchor matches BugCard's id "bug.<id>"
    assert "bug.B1" in by_anchor
    # requirement anchor is the bare requirement id
    assert by_anchor["R10"].kind == "requirement"


def test_default_index_path_outside_prd_dir(prd_dir: Path) -> None:
    p = search.default_index_path(prd_dir)
    # Must live outside prd_dir so the file-watcher never sees it.
    assert prd_dir not in p.parents
    assert p == prd_dir.parent / ".prd-tool-search.json"


def test_reindex_lexical_then_search(prd_dir: Path) -> None:
    status = search.reindex(prd_dir, embeddings=False)
    assert status["exists"] is True
    assert status["has_embeddings"] is False
    assert status["fragment_count"] >= 4
    assert search.default_index_path(prd_dir).is_file()

    # Latin lexical match
    res = search.search(prd_dir, "pagination")
    assert res["needs_index"] is False
    assert any("paginat" in r["snippet"].lower() or r["anchor"] == "bug.B1" for r in res["results"])

    # CJK lexical match via bigrams
    cjk = search.search(prd_dir, "收藏内流")
    assert any(r["anchor"] == "R10.renders_items" for r in cjk["results"])


def test_search_without_index_signals_needs_index(prd_dir: Path) -> None:
    res = search.search(prd_dir, "anything")
    assert res["needs_index"] is True
    assert res["results"] == []


def test_search_status_reflects_index(prd_dir: Path) -> None:
    assert search.search_status(prd_dir)["exists"] is False
    search.reindex(prd_dir, embeddings=False)
    st = search.search_status(prd_dir)
    assert st["exists"] is True
    assert st["fragment_count"] >= 4


def test_image_fragment_indexed_with_ocr(prd_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub OCR so the test doesn't need the onnx model.
    monkeypatch.setattr(search, "_ocr_image", lambda p: "Login error banner shown")
    search.reindex(prd_dir, embeddings=False)

    res = search.search(prd_dir, "login error banner")
    img_hits = [r for r in res["results"] if r["kind"] == "image"]
    assert img_hits, "expected an image fragment to match the OCR text"
    hit = img_hits[0]
    assert hit["image"] == "shots/login.png"
    # anchored to the rule that embeds the <img>
    assert hit["anchor"] == "R10.has_shot"


def test_clip_visual_search_returns_image(prd_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Stub OCR (empty) and CLIP so the image is kept only via its visual vector.
    monkeypatch.setattr(search, "_ocr_image", lambda p: "")
    monkeypatch.setattr(search, "_clip_image_vec", lambda p: [1.0, 0.0, 0.0])
    monkeypatch.setattr(search, "_clip_text_vec", lambda q: [1.0, 0.0, 0.0])
    st = search.reindex(prd_dir, embeddings=False, clip=True)
    assert st["has_clip"] is True

    res = search.search(prd_dir, "anything visual")
    assert res["visual"], "expected a CLIP visual hit"
    assert res["visual"][0]["image"] == "shots/login.png"


def test_image_without_ocr_text_is_dropped(prd_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search, "_ocr_image", lambda p: "")
    search.reindex(prd_dir, embeddings=False)
    res = search.search(prd_dir, "login")
    assert all(r["kind"] != "image" for r in res["results"])


def test_ops_reindex_degrades_without_model(prd_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Force the embedding model to be unavailable; reindex must degrade to
    # lexical-only rather than fail.
    def boom() -> object:
        raise RuntimeError("no model in tests")

    monkeypatch.setattr(search, "_get_model", boom)
    ops = DashboardOps(prd_dir)
    status = ops.reindex()
    assert status["exists"] is True
    assert status["has_embeddings"] is False
    hits = ops.search("inner feed")
    assert hits["needs_index"] is False
    assert len(hits["results"]) > 0
