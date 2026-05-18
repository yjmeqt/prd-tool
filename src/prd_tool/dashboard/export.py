"""Static JSON export of the dashboard payloads.

Writes the same shapes the FastAPI app serves at ``/api/index`` and
``/api/prd/<module>/<feature>``, so a static host (e.g. GitHub Pages) can
serve a read-only dashboard without the Python backend.

Layout under ``out_dir``::

    index.json
    prd/<module>/<feature>.json
    asset/<module>/<asset_path>   (everything under prd_dir/<module> that isn't an .xml)
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from prd_tool.dashboard.repo import FeatureRef, build_index, list_feature_files, load_feature


def export_static(prd_dir: Path, out_dir: Path) -> dict[str, int]:
    """Materialize the dashboard as static JSON + assets under ``out_dir``.

    Returns counts for the human-friendly CLI summary.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    index_payload = build_index(prd_dir)
    (out_dir / "index.json").write_text(
        json.dumps(index_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    prd_out = out_dir / "prd"
    features = 0
    for ref, _ in list_feature_files(prd_dir):
        payload = load_feature(prd_dir, FeatureRef(module=ref.module, feature=ref.feature))
        if payload is None:
            continue
        target = prd_out / ref.module / f"{ref.feature}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        features += 1

    # Only copy assets from modules that actually contain a feature, so that
    # repo roots used as the PRD dir (`.prd-tool.toml` with dir = ".") don't
    # accidentally slurp `.git/`, `.github/`, or any other top-level directory
    # that happens to live next to the PRDs.
    asset_root = out_dir / "asset"
    assets = 0
    modules_with_features = {ref.module for ref, _ in list_feature_files(prd_dir)}
    for module_name in sorted(modules_with_features):
        module_dir = prd_dir / module_name
        if not module_dir.is_dir():
            continue
        for path in module_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() == ".xml":
                continue
            rel = path.relative_to(module_dir)
            # Skip anything inside a hidden directory (e.g. `.git`, `.DS_Store`).
            if any(part.startswith(".") for part in rel.parts):
                continue
            dest = asset_root / module_name / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            assets += 1

    return {"features": features, "assets": assets}
