"""Hybrid search over all PRDs: lexical (BM25) + semantic (local embeddings).

The index is a snapshot built on demand (``prd index`` / the viewer's reindex
button) and written to a sidecar JSON file *outside* the PRD dir, so it never
trips the file-watcher that drives live reload.

Both retrieval paths run over the same stored snapshot so their fragments and
anchors stay consistent. Semantic search is best-effort: if fastembed is
unavailable or a model download fails, the index degrades to lexical-only and
search still works.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from prd_tool.dashboard.repo import list_feature_files

INDEX_VERSION = 1
# Multilingual (CJK + Latin) sentence embeddings, ~220 MB, 384-dim.
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# How many candidates each retrieval path contributes to the fusion.
_TOP_N = 50


# ---------------------------------------------------------------------------
# Fragments
# ---------------------------------------------------------------------------


@dataclass
class Fragment:
    ref: str  # module/feature
    module: str
    feature: str
    feature_name: str
    kind: str  # overview | requirement | rule | bug | finding | image
    anchor: str  # DOM id to scroll to ("" → feature top)
    label: str  # human label, e.g. "R10 · Collection Inner Feed"
    text: str  # plain-text body (for images: OCR text + VLM tags/description)
    image: str | None = None  # for kind=image: the authored <img src> (module-relative)
    clip: list[float] | None = None  # for kind=image: CLIP vector (visual search)


def _plain_text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    return " ".join("".join(el.itertext()).split())


def _local_img_srcs(el: ET.Element | None) -> list[str]:
    """Module-relative <img src> values under an element (skips external/data)."""
    if el is None:
        return []
    out: list[str] = []
    for img in el.iter("img"):
        src = img.get("src", "")
        if not src or re.match(r"^(https?:|data:|file:|/)", src, re.I):
            continue
        out.append(src.lstrip("./"))
    return out


def iter_fragments(prd_dir: Path) -> list[Fragment]:
    """Walk every PRD and emit one searchable fragment per content unit."""
    frags: list[Fragment] = []
    for ref, path in list_feature_files(prd_dir):
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        if root.tag != "prd":
            continue
        feature_name = root.get("name") or ref.feature
        ctx = _FeatureCtx(ref.ref, ref.module, ref.feature, feature_name, frags)

        ov = root.find("overview")
        if ov is not None:
            ctx.add("overview", "", feature_name, _plain_text(ov))
            ctx.add_images("", feature_name, _local_img_srcs(ov))

        for req in root.findall("requirement"):
            rid = req.get("id", "")
            rname = req.get("name", "")
            desc_el = req.find("description")
            desc = _plain_text(desc_el)
            ctx.add("requirement", rid, f"{rid} · {rname}".strip(" ·"), f"{rname} {desc}")
            ctx.add_images(rid, f"{rid} · {rname}".strip(" ·"), _local_img_srcs(desc_el))
            for rule in req.findall("rule"):
                ruleid = rule.get("id", "")
                rctx = rule.get("context") or ""
                # figma_node names carry component/state info ("bottom sheet",
                # "error state", "toast") as an attribute, which itertext()
                # misses — fold them into the rule's searchable text.
                fnames = " ".join(fn.get("name", "") for fn in rule.findall("figma_node"))
                body = f"{rctx} {_plain_text(rule)} {fnames}"
                ctx.add("rule", f"{rid}.{ruleid}", f"{rid} · {ruleid}", body)
                ctx.add_images(f"{rid}.{ruleid}", f"{rid} · {ruleid}", _local_img_srcs(rule))
            for ui in req.findall("ui_review"):
                for finding in ui.findall("finding"):
                    ctx.add("finding", rid, f"{rid} · finding", _plain_text(finding))

        for bug in root.findall("bug"):
            bid = bug.get("id", "")
            body = " ".join(_plain_text(bug.find(t)) for t in ("current", "expected", "steps"))
            ctx.add("bug", f"bug.{bid}", f"Bug {bid}", body)

    return frags


@dataclass
class _FeatureCtx:
    """Carries per-feature identity so ``add`` doesn't close over loop vars."""

    ref: str
    module: str
    feature: str
    feature_name: str
    out: list[Fragment]
    seen_images: set[str] = field(default_factory=set)

    def add(self, kind: str, anchor: str, label: str, text: str) -> None:
        text = " ".join(text.split())
        if not text:
            return
        self.out.append(
            Fragment(
                self.ref, self.module, self.feature, self.feature_name, kind, anchor, label, text
            )
        )

    def add_images(self, anchor: str, label: str, srcs: list[str]) -> None:
        # Emitted with empty text; reindex() fills OCR/VLM content and drops
        # any image that yields nothing searchable. Deduped per feature so a
        # screenshot referenced by several rules is OCR'd once.
        for src in srcs:
            if src in self.seen_images:
                continue
            self.seen_images.add(src)
            self.out.append(
                Fragment(
                    self.ref,
                    self.module,
                    self.feature,
                    self.feature_name,
                    "image",
                    anchor,
                    f"{label} · image" if label else "image",
                    "",
                    image=src,
                )
            )


# ---------------------------------------------------------------------------
# Tokenizer (CJK-aware: latin words + CJK bigrams)
# ---------------------------------------------------------------------------

_LATIN_RE = re.compile(r"[a-z0-9]+")
_CJK_RUN_RE = re.compile(r"[㐀-鿿぀-ヿ가-힯]+")


def tokenize(text: str) -> list[str]:
    """Tokenize for BM25. Latin runs become whole tokens; CJK has no word
    boundaries, so emit overlapping bigrams (single chars pass through)."""
    text = text.lower()
    tokens: list[str] = _LATIN_RE.findall(text)
    for run in _CJK_RUN_RE.findall(text):
        if len(run) == 1:
            tokens.append(run)
        else:
            tokens.extend(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


# ---------------------------------------------------------------------------
# Embeddings (fastembed, lazy + best-effort)
# ---------------------------------------------------------------------------

_MODEL: Any = None


def _get_model() -> Any:
    global _MODEL
    if _MODEL is None:
        import warnings

        from fastembed import TextEmbedding  # heavy import; keep it lazy

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            _MODEL = TextEmbedding(MODEL_NAME)
    return _MODEL


def _embed(texts: list[str]) -> list[list[float]]:
    model = _get_model()
    return [[round(float(x), 6) for x in vec] for vec in model.embed(texts)]


# ---------------------------------------------------------------------------
# CLIP image/text embeddings (fastembed, lazy + best-effort) — visual search
# ---------------------------------------------------------------------------

CLIP_VISION = "Qdrant/clip-ViT-B-32-vision"
CLIP_TEXT = "Qdrant/clip-ViT-B-32-text"  # shares CLIP_VISION's embedding space
_CLIP_IMAGE: Any = None
_CLIP_TEXT: Any = None


def _clip_image_vec(path: Path) -> list[float]:
    global _CLIP_IMAGE
    if _CLIP_IMAGE is None:
        from fastembed import ImageEmbedding  # heavy import; keep it lazy

        _CLIP_IMAGE = ImageEmbedding(CLIP_VISION)
    vec = next(iter(_CLIP_IMAGE.embed([str(path)])))
    return [round(float(x), 6) for x in vec]


def _clip_text_vec(text: str) -> list[float]:
    global _CLIP_TEXT
    if _CLIP_TEXT is None:
        from fastembed import TextEmbedding

        _CLIP_TEXT = TextEmbedding(CLIP_TEXT)
    vec = next(iter(_CLIP_TEXT.embed([text])))
    return [round(float(x), 6) for x in vec]


# ---------------------------------------------------------------------------
# Image OCR (rapidocr, lazy + best-effort, content-hash cached)
# ---------------------------------------------------------------------------

_OCR_ENGINE: Any = None


def _get_ocr() -> Any:
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR  # heavy import; keep it lazy

        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def _ocr_image(path: Path) -> str:
    result, _ = _get_ocr()(str(path))
    if not result:
        return ""
    return " ".join(line[1] for line in result if len(line) >= 2 and line[1])


def _file_hash(path: Path) -> str | None:
    try:
        return hashlib.sha1(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _load_json(path: Path) -> dict[str, Any]:
    try:
        loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        return loaded
    except (OSError, json.JSONDecodeError):
        return {}


def _enrich_images(
    prd_dir: Path,
    frags: list[Fragment],
    cache_path: Path,
    *,
    clip: bool = False,
) -> None:
    """Fill image fragments with OCR text and an optional CLIP vector for visual
    search. Results are cached by file content hash, per stage, so no stage
    re-runs on an unchanged screenshot. Every stage is best-effort: a missing
    dependency leaves it empty."""
    image_frags = [f for f in frags if f.kind == "image" and f.image]
    if not image_frags:
        return
    cache = _load_json(cache_path)  # {hash: {"ocr": str, "clip": [...]}}
    changed = False
    # When a dependency is missing, report once and stop retrying it — and don't
    # cache the empty result, so a later run with the dep installed re-runs it.
    ocr_off = clip_off = False
    for f in image_frags:
        assert f.image is not None
        abs_path = prd_dir / f.module / f.image
        h = _file_hash(abs_path)
        if h is None:
            continue
        entry = cache.get(h)
        if not isinstance(entry, dict):  # absent or pre-dict (legacy) format
            entry = {}
        if "ocr" not in entry and not ocr_off:
            try:
                entry["ocr"] = _ocr_image(abs_path)
                changed = True
            except ImportError:
                ocr_off = True
                print(
                    "prd index: OCR skipped — image-text search needs the 'vision' extra. "
                    "Install with: uv tool install --with rapidocr-onnxruntime prd-tool",
                    file=sys.stderr,
                )
            except Exception as e:  # noqa: BLE001 — OCR is best-effort
                entry["ocr"] = ""
                changed = True
                print(f"prd index: OCR failed for {f.image} ({e})", file=sys.stderr)
        if clip and "clip" not in entry and not clip_off:
            try:
                entry["clip"] = _clip_image_vec(abs_path)
                changed = True
            except ImportError:
                clip_off = True
                print("prd index: CLIP skipped — fastembed image support missing.", file=sys.stderr)
            except Exception as e:  # noqa: BLE001 — CLIP is best-effort
                entry["clip"] = None
                changed = True
                print(f"prd index: CLIP failed for {f.image} ({e})", file=sys.stderr)
        cache[h] = entry
        f.clip = entry.get("clip") or None
        f.text = entry.get("ocr", "")
    if changed:
        _atomic_write(cache_path, json.dumps(cache, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Index build / sidecar IO
# ---------------------------------------------------------------------------


def default_index_path(prd_dir: Path) -> Path:
    """Sidecar location, kept outside prd_dir so the file-watcher ignores it."""
    return prd_dir.parent / ".prd-tool-search.json"


def _atomic_write(path: Path, contents: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(contents, encoding="utf-8")
    os.replace(tmp, path)


def reindex(
    prd_dir: Path,
    index_path: Path | None = None,
    *,
    embeddings: bool = True,
    clip: bool = False,
) -> dict[str, Any]:
    """Rebuild the search snapshot and write it to disk. Returns its status."""
    index_path = index_path or default_index_path(prd_dir)
    frags = iter_fragments(prd_dir)

    # Image fragments start textless; OCR / CLIP fill them, then drop any that
    # still carry nothing searchable (no OCR text and no visual vector).
    _enrich_images(prd_dir, frags, index_path.with_name(".prd-tool-ocr-cache.json"), clip=clip)
    frags = [f for f in frags if f.kind != "image" or f.text or f.clip]

    vecs: list[list[float]] | None = None
    has_embeddings = False
    if embeddings and frags:
        try:
            vecs = _embed([f.text for f in frags])
            has_embeddings = True
        except Exception as e:  # noqa: BLE001 — degrade to lexical-only
            print(f"prd index: embeddings unavailable, lexical-only ({e})", file=sys.stderr)

    fragments: list[dict[str, Any]] = []
    for i, f in enumerate(frags):
        d = asdict(f)
        d["vec"] = vecs[i] if vecs is not None else None
        fragments.append(d)

    has_clip = any(f.clip for f in frags)
    image_count = sum(1 for f in frags if f.kind == "image")
    data = {
        "version": INDEX_VERSION,
        "indexed_at": time.time(),
        "model": MODEL_NAME if has_embeddings else None,
        "has_embeddings": has_embeddings,
        "has_clip": has_clip,
        "image_count": image_count,
        "fragments": fragments,
    }
    _atomic_write(index_path, json.dumps(data, ensure_ascii=False))
    _CACHE.pop(str(index_path), None)
    return {
        "exists": True,
        "indexed_at": data["indexed_at"],
        "fragment_count": len(fragments),
        "has_embeddings": has_embeddings,
        "has_clip": has_clip,
        "image_count": image_count,
    }


# ---------------------------------------------------------------------------
# Loaded snapshot (cached, with derived BM25 + embedding matrix)
# ---------------------------------------------------------------------------


class _Snapshot:
    def __init__(self, data: dict[str, Any]) -> None:
        self.indexed_at: float = data.get("indexed_at", 0.0)
        self.fragments: list[dict[str, Any]] = data.get("fragments", [])
        self.has_embeddings: bool = bool(data.get("has_embeddings"))
        self.has_clip: bool = bool(data.get("has_clip"))
        self.image_count: int = int(data.get("image_count", 0))
        self._bm25: Any = None
        self._matrix: Any = None
        self._clip: tuple[list[int], Any] | None = None

    @property
    def bm25(self) -> Any:
        if self._bm25 is None and self.fragments:
            from rank_bm25 import BM25Okapi

            corpus = [tokenize(f["text"] + " " + f["label"]) for f in self.fragments]
            self._bm25 = BM25Okapi(corpus)
        return self._bm25

    @property
    def matrix(self) -> Any:
        if self._matrix is None and self.has_embeddings and self.fragments:
            import numpy as np

            m = np.asarray([f["vec"] for f in self.fragments], dtype="float32")
            norms = np.linalg.norm(m, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self._matrix = m / norms
        return self._matrix

    @property
    def clip(self) -> tuple[list[int], Any]:
        """(fragment indices, normalized CLIP matrix) for images with vectors."""
        if self._clip is None:
            idxs = [i for i, f in enumerate(self.fragments) if f.get("clip")]
            if not idxs:
                self._clip = ([], None)
            else:
                import numpy as np

                m = np.asarray([self.fragments[i]["clip"] for i in idxs], dtype="float32")
                norms = np.linalg.norm(m, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                self._clip = (idxs, m / norms)
        return self._clip


# str(index_path) → (mtime, snapshot)
_CACHE: dict[str, tuple[float, _Snapshot]] = {}


def _load_snapshot(index_path: Path) -> _Snapshot | None:
    if not index_path.is_file():
        return None
    mtime = index_path.stat().st_mtime
    cached = _CACHE.get(str(index_path))
    if cached is not None and cached[0] == mtime:
        return cached[1]
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    snap = _Snapshot(data)
    _CACHE[str(index_path)] = (mtime, snap)
    return snap


# ---------------------------------------------------------------------------
# Fusion + query
# ---------------------------------------------------------------------------


def _rrf(rankings: list[list[int]], k: int = 60) -> list[int]:
    """Reciprocal-rank fusion of several ranked index lists."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda i: scores[i], reverse=True)


def _snippet(text: str, query: str, width: int = 180) -> str:
    low = text.lower()
    pos = -1
    for tok in [query.lower().strip(), *_LATIN_RE.findall(query.lower())]:
        if tok:
            pos = low.find(tok)
            if pos != -1:
                break
    if pos == -1:
        return text[:width] + ("…" if len(text) > width else "")
    start = max(0, pos - width // 3)
    end = min(len(text), start + width)
    snip = text[start:end]
    if start > 0:
        snip = "…" + snip
    if end < len(text):
        snip = snip + "…"
    return snip


def _result(frag: dict[str, Any], query: str) -> dict[str, Any]:
    return {
        "ref": frag["ref"],
        "module": frag["module"],
        "feature": frag["feature"],
        "feature_name": frag["feature_name"],
        "kind": frag["kind"],
        "anchor": frag["anchor"],
        "label": frag["label"],
        "snippet": _snippet(frag["text"], query),
        "image": frag.get("image"),
    }


def _status_dict(snap: _Snapshot | None) -> dict[str, Any]:
    if snap is None:
        return {
            "exists": False,
            "indexed_at": None,
            "fragment_count": 0,
            "has_embeddings": False,
            "has_clip": False,
            "image_count": 0,
        }
    return {
        "exists": True,
        "indexed_at": snap.indexed_at,
        "fragment_count": len(snap.fragments),
        "has_embeddings": snap.has_embeddings,
        "has_clip": snap.has_clip,
        "image_count": snap.image_count,
    }


def search_status(prd_dir: Path, index_path: Path | None = None) -> dict[str, Any]:
    index_path = index_path or default_index_path(prd_dir)
    return _status_dict(_load_snapshot(index_path))


def search(
    prd_dir: Path, query: str, limit: int = 30, index_path: Path | None = None
) -> dict[str, Any]:
    index_path = index_path or default_index_path(prd_dir)
    snap = _load_snapshot(index_path)
    base = _status_dict(snap)
    base["needs_index"] = snap is None
    base["results"] = []
    base["visual"] = []
    if snap is None:
        return base

    q = query.strip()
    if not q:
        return base

    rankings: list[list[int]] = []

    qtokens = tokenize(q)
    bm25 = snap.bm25
    if bm25 is not None and qtokens:
        scores = bm25.get_scores(qtokens)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        rankings.append([i for i in order if scores[i] > 0][:_TOP_N])

    if snap.has_embeddings:
        try:
            import numpy as np

            qv = np.asarray(_embed([q])[0], dtype="float32")
            norm = float(np.linalg.norm(qv)) or 1.0
            sims = snap.matrix @ (qv / norm)
            sem_order = np.argsort(-sims)[:_TOP_N]
            rankings.append([int(i) for i in sem_order])
        except Exception as e:  # noqa: BLE001 — semantic is best-effort
            print(f"prd search: semantic pass skipped ({e})", file=sys.stderr)

    fused = _rrf(rankings)[:limit]
    base["results"] = [_result(snap.fragments[i], q) for i in fused]

    # Visual search: rank images by CLIP text↔image similarity (separate space).
    idxs, cmatrix = snap.clip
    if idxs and cmatrix is not None:
        try:
            import numpy as np

            qv = np.asarray(_clip_text_vec(q), dtype="float32")
            qn = qv / (float(np.linalg.norm(qv)) or 1.0)
            sims = cmatrix @ qn
            ranked = np.argsort(-sims)[:8]
            base["visual"] = [
                _result(snap.fragments[idxs[int(i)]], q)
                for i in ranked
                if float(sims[int(i)]) > 0.18
            ]
        except Exception as e:  # noqa: BLE001 — visual pass is best-effort
            print(f"prd search: visual pass skipped ({e})", file=sys.stderr)

    return base
