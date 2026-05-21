"""Native (pywebview) entry point and JS bridge for the PRD dashboard.

The JsApi exposes DashboardOps to JavaScript. Methods that can fail return a
result envelope ({"ok": True, "data": ...} | {"ok": False, "error": {...}})
because pywebview surfaces Python exceptions as opaque JS errors that are
awkward to handle in the frontend.
"""

from __future__ import annotations

import contextlib
import sys
import threading
from pathlib import Path
from typing import Any

from prd_tool.dashboard.ops import DashboardOps, OpsError


def _ok(data: Any) -> dict[str, Any]:
    return {"ok": True, "data": data}


def _err(code: str, message: str) -> dict[str, Any]:
    return {"ok": False, "error": {"code": code, "message": message}}


class JsApi:
    """Exposed to JS as ``window.pywebview.api.*``.

    Snake_case Python methods become snake_case in JS; the frontend shim
    translates to camelCase. The shim also unwraps the {ok,data}|{ok,error}
    envelope into a return value or an ApiError.
    """

    def __init__(self, prd_dir: Path) -> None:
        self._prd_dir = prd_dir.resolve()
        self._ops = DashboardOps(self._prd_dir)
        # Set by run_native after the webview module is imported so JsApi can
        # ask the window factory to spawn additional windows.
        self._open_window: Any = None

    # ---- read ----

    def index(self) -> dict[str, Any]:
        # Index never raises meaningfully — return the raw dict so the
        # frontend doesn't have to unwrap.
        return self._ops.index()

    def feature(self, module: str, feature: str) -> dict[str, Any]:
        try:
            return _ok(self._ops.feature(module, feature))
        except OpsError as e:
            return _err(e.code, e.message)

    def asset_root(self) -> str:
        """Absolute filesystem path the frontend uses to build file:// URLs."""
        return str(self._prd_dir)

    # ---- write ----

    def set_rule_status(
        self, module: str, feature: str, rule_id: str, status: str
    ) -> dict[str, Any]:
        try:
            return _ok(self._ops.set_rule_status(module, feature, rule_id, status))
        except OpsError as e:
            return _err(e.code, e.message)

    def set_bug_status(self, module: str, feature: str, bug_id: str, status: str) -> dict[str, Any]:
        try:
            return _ok(self._ops.set_bug_status(module, feature, bug_id, status))
        except OpsError as e:
            return _err(e.code, e.message)

    def resolve_finding(self, module: str, feature: str, rule_qid: str) -> dict[str, Any]:
        try:
            return _ok(self._ops.resolve_finding(module, feature, rule_qid))
        except OpsError as e:
            return _err(e.code, e.message)

    # ---- window control ----

    def open_window(self, ref: str | None = None) -> dict[str, Any]:
        """Open a new native window. ``ref`` is "module/feature" or None for the index."""
        if self._open_window is None:
            return _err("internal", "window factory not registered")
        try:
            self._open_window(ref)
            return _ok(None)
        except Exception as e:
            return _err("internal", str(e))


def run_native(prd_dir: Path, refs: list[str]) -> None:
    """Open one pywebview window per ref (or one index window if refs is empty).

    Blocks until the last window closes. ``watchfiles`` runs in a background
    thread and pushes fs events to every open window via ``evaluate_js``.
    """
    # Imported lazily so unit tests don't need a display.
    import webview

    api = JsApi(prd_dir)
    static_dir = Path(__file__).parent / "static"
    src_index = static_dir / "index.html"
    if not src_index.is_file():
        raise FileNotFoundError(
            f"Frontend bundle missing at {src_index}. Build with: pnpm --dir frontend build"
        )

    # The wheel's bundle uses absolute /assets/... paths so FastAPI can serve
    # SPA deep links. Under file:// those resolve to the filesystem root and
    # the page goes blank. Rewrite to relative ./assets/ in a sibling file the
    # native launcher loads instead.
    index_html = static_dir / "index.native.html"
    html = src_index.read_text(encoding="utf-8")
    html = html.replace('src="/assets/', 'src="./assets/').replace(
        'href="/assets/', 'href="./assets/'
    )
    index_html.write_text(html, encoding="utf-8")

    windows: list[Any] = []

    def _ref_to_url(ref: str | None) -> str:
        # The frontend uses HashRouter in native mode (see T8), so deep links
        # like #/p/<module>/<feature> survive file:// loading.
        base = index_html.as_uri()
        if ref is None:
            return base
        return f"{base}#/p/{ref}"

    def _open(ref: str | None) -> None:
        title = f"PRD — {ref}" if ref else "PRD"
        w = webview.create_window(title, url=_ref_to_url(ref), js_api=api, width=1280, height=860)
        windows.append(w)

    api._open_window = _open

    if not refs:
        _open(None)
    else:
        for r in refs:
            _open(r)

    # Background fs watcher; push events to every live window.
    def _on_change() -> None:
        for w in list(windows):
            # Window may have closed between the watch event and this call.
            with contextlib.suppress(Exception):
                w.evaluate_js(
                    "window.__prdOnFsEvent && window.__prdOnFsEvent({type:'prd_changed'})"
                )

    def _watcher() -> None:
        try:
            from watchfiles import watch

            for _changes in watch(prd_dir):
                _on_change()
        except Exception as e:
            print(f"prd view: file watcher stopped: {e}", file=sys.stderr)

    threading.Thread(target=_watcher, daemon=True).start()

    webview.start()
