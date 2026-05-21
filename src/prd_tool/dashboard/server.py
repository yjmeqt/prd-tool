"""FastAPI app factory for the PRD dashboard (server mode)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from prd_tool.dashboard.ops import DashboardOps, OpsError
from prd_tool.dashboard.sse import sse_stream

_PLACEHOLDER_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>PRD Dashboard</title></head>
<body style="font-family: system-ui; padding: 2rem; max-width: 48rem; margin: 0 auto">
  <h1>PRD Dashboard</h1>
  <p>The frontend bundle is not built yet. Use the JSON API while it's in development:</p>
  <ul>
    <li><a href="/api/index">/api/index</a></li>
    <li><code>/api/prd/&lt;module&gt;/&lt;feature&gt;</code></li>
  </ul>
</body></html>
"""


def _ops_error_to_http(err: OpsError) -> HTTPException:
    status = {
        "not_found": 404,
        "invalid": 400,
        "validation_failed": 422,
        "parse_error": 422,
        "conflict": 409,
    }.get(err.code, 500)
    return HTTPException(status_code=status, detail={"code": err.code, "message": err.message})


def create_app(prd_dir: Path) -> FastAPI:
    app = FastAPI(title="prd-tool dashboard")
    ops = DashboardOps(prd_dir)

    @app.get("/api/index")
    def get_index() -> dict[str, Any]:
        return ops.index()

    @app.get("/api/prd/{module}/{feature}")
    def get_prd(module: str, feature: str) -> dict[str, Any]:
        try:
            return ops.feature(module, feature)
        except OpsError as e:
            raise _ops_error_to_http(e) from e

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "prd_dir": str(prd_dir)}

    @app.get("/api/prd-asset/{module}/{feature}/{asset_path:path}")
    def get_prd_asset(module: str, feature: str, asset_path: str) -> FileResponse:
        try:
            target = ops.asset_path(module, feature, asset_path)
        except OpsError as e:
            raise _ops_error_to_http(e) from e
        return FileResponse(target)

    @app.post("/api/prd/{module}/{feature}/rule/{rule_id}/status")
    def post_rule_status(
        module: str,
        feature: str,
        rule_id: str,
        body: Annotated[dict[str, str], Body()],
    ) -> dict[str, Any]:
        try:
            return ops.set_rule_status(module, feature, rule_id, body.get("status", ""))
        except OpsError as e:
            raise _ops_error_to_http(e) from e

    @app.post("/api/prd/{module}/{feature}/bug/{bug_id}/status")
    def post_bug_status(
        module: str,
        feature: str,
        bug_id: str,
        body: Annotated[dict[str, str], Body()],
    ) -> dict[str, Any]:
        try:
            return ops.set_bug_status(module, feature, bug_id, body.get("status", ""))
        except OpsError as e:
            raise _ops_error_to_http(e) from e

    @app.post("/api/prd/{module}/{feature}/finding/{rule_qid}/resolve")
    def post_finding_resolve(module: str, feature: str, rule_qid: str) -> dict[str, Any]:
        try:
            return ops.resolve_finding(module, feature, rule_qid)
        except OpsError as e:
            raise _ops_error_to_http(e) from e

    @app.get("/api/events")
    def events() -> StreamingResponse:
        return StreamingResponse(
            sse_stream(prd_dir),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    static_dir = Path(__file__).parent / "static"
    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", response_class=HTMLResponse)
    def root() -> str:
        static_index = static_dir / "index.html"
        if static_index.is_file():
            return static_index.read_text(encoding="utf-8")
        return _PLACEHOLDER_HTML

    # Catch-all so React Router deep links (e.g. /p/<module>/<feature>) work.
    @app.get("/{path:path}", response_class=HTMLResponse)
    def spa_fallback(path: str) -> str:
        if path.startswith("api/") or path.startswith("assets/"):
            raise HTTPException(status_code=404)
        static_index = static_dir / "index.html"
        if static_index.is_file():
            return static_index.read_text(encoding="utf-8")
        return _PLACEHOLDER_HTML

    return app
