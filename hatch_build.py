"""Hatch build hook: ensure the dashboard static directory exists.

The Vite-built frontend lives at ``src/prd_tool/dashboard/static/`` and is
gitignored — CI rebuilds it before publishing to PyPI. Installs straight from
git (``uv tool install git+...``) and editable installs in fresh checkouts
don't run that build, so hatchling's ``force-include`` would error out.

This hook just guarantees the directory exists so the build succeeds; it does
not write any placeholder file. ``server.py`` already serves an in-process
fallback page when ``static/index.html`` is missing, so leaving the directory
empty preserves that behavior.
"""

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class StaticBundleStubHook(BuildHookInterface):  # type: ignore[misc]
    PLUGIN_NAME = "prd-static-stub"

    def initialize(self, version: str, build_data: dict) -> None:
        static_dir = Path(self.root) / "src" / "prd_tool" / "dashboard" / "static"
        static_dir.mkdir(parents=True, exist_ok=True)
