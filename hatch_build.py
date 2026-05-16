"""Hatch build hook: ensure the dashboard static bundle exists before packaging.

The Vite-built frontend lives at ``src/prd_tool/dashboard/static/`` and is
gitignored — CI rebuilds it before publishing to PyPI. Installs straight from
git (``uv tool install git+...``) and editable installs in fresh checkouts
don't run that build, so ``force-include`` would fail. This hook drops in a
minimal placeholder when the real bundle is missing so the wheel still builds;
the dashboard CLI itself reports the missing bundle at runtime.
"""

from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_PLACEHOLDER_HTML = """<!doctype html>
<meta charset="utf-8">
<title>prd dashboard</title>
<p>Dashboard bundle not built. Run <code>pnpm --dir frontend install &amp;&amp; pnpm --dir frontend build</code>.</p>
"""


class StaticBundleStubHook(BuildHookInterface):  # type: ignore[misc]
    PLUGIN_NAME = "prd-static-stub"

    def initialize(self, version: str, build_data: dict) -> None:
        static_dir = Path(self.root) / "src" / "prd_tool" / "dashboard" / "static"
        if static_dir.exists() and any(static_dir.iterdir()):
            return
        static_dir.mkdir(parents=True, exist_ok=True)
        (static_dir / "index.html").write_text(_PLACEHOLDER_HTML, encoding="utf-8")
