"""Transport-agnostic operations for the PRD dashboard.

Both FastAPI (server.py) and the pywebview JS bridge (native.py) call into
this class. There is no HTTP/JSON/SSE here — only Python types and exceptions.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prd_tool.constants import RULE_STATUSES
from prd_tool.dashboard.edits import (
    EditError,
    resolve_finding,
    set_bug_status,
    set_rule_status,
)
from prd_tool.dashboard.repo import FeatureRef, build_index, load_feature
from prd_tool.overlay import Progress, load_progress, overlay_path, save_progress


@dataclass
class OpsError(Exception):
    code: str  # not_found | invalid | validation_failed | parse_error | conflict | internal
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class DashboardOps:
    def __init__(
        self,
        prd_dir: Path,
        status_dir: Path | None = None,
        platform: str | None = None,
    ) -> None:
        self.prd_dir = prd_dir
        self.status_dir = status_dir
        self.platform = platform

    def index(self) -> dict[str, Any]:
        return build_index(self.prd_dir, self.status_dir, self.platform)

    def feature(self, module: str, feature: str) -> dict[str, Any]:
        payload = load_feature(
            self.prd_dir,
            FeatureRef(module=module, feature=feature),
            self.status_dir,
            self.platform,
        )
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

        if self.status_dir is not None:
            if status not in RULE_STATUSES:
                raise OpsError("invalid", f"status must be one of {sorted(RULE_STATUSES)}")

            try:
                tree = ET.parse(path)
            except (ET.ParseError, OSError) as e:
                raise OpsError("parse_error", str(e)) from e

            root = tree.getroot()
            target_qid = None
            for req in root.findall("requirement"):
                req_id = req.get("id")
                if not req_id:
                    continue
                for rule in req.findall("rule"):
                    if rule.get("id") == rule_id:
                        target_qid = f"{req_id}.{rule_id}"
                        break
                if target_qid:
                    break

            if not target_qid:
                raise OpsError("not_found", f"rule '{rule_id}' not found")

            toml_path = overlay_path(self.status_dir, module, feature, self.platform)
            try:
                stat_before = toml_path.stat()
            except OSError:
                stat_before = None

            from prd_tool.overlay import OverlayError

            try:
                progress = load_progress(toml_path)
            except OverlayError as e:
                raise OpsError("internal", f"failed to load progress: {e}") from e

            new_rules = dict(progress.rules)
            new_rules[target_qid] = status
            new_progress = Progress(
                rules=new_rules, notes=progress.notes, platform_rules=progress.platform_rules
            )

            try:
                stat_now = toml_path.stat()
            except OSError:
                stat_now = None

            if stat_before is not None and stat_now is not None:
                if (
                    stat_now.st_mtime_ns != stat_before.st_mtime_ns
                    or stat_now.st_size != stat_before.st_size
                    or stat_now.st_ino != stat_before.st_ino
                ):
                    raise OpsError(
                        "conflict", "file changed on disk between read and write; refresh and retry"
                    )
            elif stat_before is None and stat_now is not None:
                raise OpsError(
                    "conflict", "file created on disk between read and write; refresh and retry"
                )

            try:
                save_progress(toml_path, new_progress)
            except Exception as e:
                raise OpsError("internal", f"failed to write progress: {e}") from e

            return self.feature(module, feature)

        self._wrap_edit(set_rule_status, path, rule_id, status)
        return self.feature(module, feature)

    def set_bug_status(self, module: str, feature: str, bug_id: str, status: str) -> dict[str, Any]:
        path = self._resolve_prd_path(module, feature)
        self._wrap_edit(set_bug_status, path, bug_id, status, self.status_dir is None)
        return self.feature(module, feature)

    def resolve_finding(self, module: str, feature: str, rule_qid: str) -> dict[str, Any]:
        path = self._resolve_prd_path(module, feature)
        self._wrap_edit(resolve_finding, path, rule_qid, self.status_dir is None)
        return self.feature(module, feature)

    # ---- search ----

    def search(self, query: str, limit: int = 30) -> dict[str, Any]:
        from prd_tool.dashboard import search as search_mod

        return search_mod.search(self.prd_dir, query, limit)

    def search_status(self) -> dict[str, Any]:
        from prd_tool.dashboard import search as search_mod

        return search_mod.search_status(self.prd_dir)

    def reindex(self, clip: bool = False) -> dict[str, Any]:
        from prd_tool.dashboard import search as search_mod

        try:
            return search_mod.reindex(self.prd_dir, clip=clip)
        except OSError as e:
            raise OpsError("internal", f"failed to write search index: {e}") from e

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
