"""Hatch build hook: build the dashboard static bundle before packaging.

The Vite-built frontend lives at ``src/prd_tool/dashboard/static/`` and is
gitignored. When the wheel is built from a fresh checkout (e.g.
``uv tool install git+...``) the directory is empty, so hatchling's
``force-include`` would either fail or ship an empty bundle and the user
would see a placeholder page or a stale ``index.html`` referencing assets
that no longer exist.

This hook runs ``pnpm install`` (if needed) and ``pnpm build`` in
``frontend/`` so the wheel always contains a matching index.html + assets.
If ``frontend/`` is absent or the build tooling is unavailable, it falls
back to ensuring an empty static directory exists — ``server.py`` then
serves its in-process placeholder page.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class StaticBundleHook(BuildHookInterface):  # type: ignore[misc]
    PLUGIN_NAME = "prd-static-bundle"

    def initialize(self, version: str, build_data: dict) -> None:
        root = Path(self.root)
        static_dir = root / "src" / "prd_tool" / "dashboard" / "static"
        static_dir.mkdir(parents=True, exist_ok=True)

        if os.environ.get("PRD_SKIP_FRONTEND_BUILD"):
            return

        frontend = root / "frontend"
        if not (frontend / "package.json").is_file():
            return

        pnpm = shutil.which("pnpm")
        if not pnpm:
            # No pnpm available — leave static empty; server falls back to
            # the placeholder page.
            return

        # Wipe any stale bundle so we never ship index.html pointing at
        # asset hashes that aren't in the wheel.
        for child in static_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

        if not (frontend / "node_modules").is_dir():
            subprocess.run(
                [pnpm, "install", "--frozen-lockfile"],
                cwd=frontend,
                check=True,
            )
        subprocess.run([pnpm, "build"], cwd=frontend, check=True)
