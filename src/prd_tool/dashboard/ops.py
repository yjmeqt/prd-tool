"""Transport-agnostic operations for the PRD dashboard.

Both FastAPI (server.py) and the pywebview JS bridge (native.py) call into
this class. There is no HTTP/JSON/SSE here — only Python types and exceptions.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prd_tool.dashboard.edits import (
    EditError,
    resolve_finding,
    set_bug_status,
    set_rule_status,
)
from prd_tool.dashboard.repo import FeatureRef, build_index, load_feature


@dataclass
class OpsError(Exception):
    code: str  # not_found | invalid | validation_failed | parse_error | conflict | internal
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class DashboardOps:
    def __init__(self, prd_dir: Path) -> None:
        self.prd_dir = prd_dir

    def index(self) -> dict[str, Any]:
        return build_index(self.prd_dir)

    def feature(self, module: str, feature: str) -> dict[str, Any]:
        payload = load_feature(self.prd_dir, FeatureRef(module=module, feature=feature))
        if payload is None:
            raise OpsError("not_found", f"PRD not found: {module}/{feature}")
        return payload

    def _resolve_prd_path(self, module: str, feature: str) -> Path:
        path = self.prd_dir / module / f"{feature}.xml"
        if not path.is_file():
            raise OpsError("not_found", f"PRD not found: {module}/{feature}")
        return path

    def _wrap_edit(self, fn: Callable[..., Any], *args: Any) -> None:
        try:
            fn(*args)
        except EditError as e:
            raise OpsError(e.code, e.message) from e

    def set_rule_status(
        self, module: str, feature: str, rule_id: str, status: str
    ) -> dict[str, Any]:
        path = self._resolve_prd_path(module, feature)
        self._wrap_edit(set_rule_status, path, rule_id, status)
        return self.feature(module, feature)

    def set_bug_status(self, module: str, feature: str, bug_id: str, status: str) -> dict[str, Any]:
        path = self._resolve_prd_path(module, feature)
        self._wrap_edit(set_bug_status, path, bug_id, status)
        return self.feature(module, feature)

    def resolve_finding(self, module: str, feature: str, rule_qid: str) -> dict[str, Any]:
        path = self._resolve_prd_path(module, feature)
        self._wrap_edit(resolve_finding, path, rule_qid)
        return self.feature(module, feature)

    def asset_path(self, module: str, feature: str, asset_path: str) -> Path:
        """Resolve an asset path within the module dir, blocking traversal."""
        module_root = (self.prd_dir / module).resolve()
        if not module_root.is_dir():
            raise OpsError("not_found", "module not found")
        target = (module_root / asset_path).resolve()
        try:
            target.relative_to(module_root)
        except ValueError as e:
            raise OpsError("not_found", "asset path escapes module") from e
        if not target.is_file():
            raise OpsError("not_found", "asset not found")
        return target
