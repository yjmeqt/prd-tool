"""Persisted mutations to PRD XML files made through the dashboard."""

from __future__ import annotations

import contextlib
import os
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from prd_tool.constants import BUG_STATUSES, RULE_STATUSES
from prd_tool.format import format_prd
from prd_tool.validate import validate


@dataclass(frozen=True)
class EditError(Exception):
    code: str  # "not_found" | "invalid" | "validation_failed" | "parse_error"
    message: str

    def __str__(self) -> str:
        return self.message


def _atomic_write(path: Path, contents: str) -> None:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(contents)
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _mutate_and_persist(path: Path, mutate: Callable[[ET.Element], None]) -> None:
    # Capture the file's identity at read time so we can detect concurrent
    # writes (an editor saving the file, a second POST racing this one) and
    # refuse to clobber.
    try:
        stat_before = path.stat()
    except OSError as e:
        raise EditError(code="parse_error", message=str(e)) from e

    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as e:
        raise EditError(code="parse_error", message=str(e)) from e
    root = tree.getroot()
    if root.tag != "prd":
        raise EditError(code="parse_error", message=f"root is <{root.tag}>, expected <prd>")

    mutate(root)

    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, staging = tempfile.mkstemp(prefix=f".{path.name}.staging.", suffix=".xml", dir=parent)
    staging_path = Path(staging)
    try:
        with os.fdopen(fd, "wb") as f:
            tree.write(f, encoding="utf-8")
        try:
            formatted = format_prd(staging_path)
        except ET.ParseError as e:
            raise EditError(code="invalid", message=f"format failed: {e}") from e
        staging_path.write_text(formatted, encoding="utf-8")
        errors = validate(staging_path)
        if errors:
            raise EditError(code="validation_failed", message="; ".join(errors))

        # Re-check that the target hasn't changed under us. If it has, refuse
        # the write — the client should refetch and retry.
        try:
            stat_now = path.stat()
        except OSError as e:
            raise EditError(code="parse_error", message=str(e)) from e
        if (
            stat_now.st_mtime_ns != stat_before.st_mtime_ns
            or stat_now.st_size != stat_before.st_size
            or stat_now.st_ino != stat_before.st_ino
        ):
            raise EditError(
                code="conflict",
                message="file changed on disk between read and write; refresh and retry",
            )
        _atomic_write(path, formatted)
    finally:
        with contextlib.suppress(OSError):
            staging_path.unlink()


def set_rule_status(path: Path, rule_id: str, status: str) -> None:
    if status not in RULE_STATUSES:
        raise EditError(
            code="invalid",
            message=f"status must be one of {sorted(RULE_STATUSES)}",
        )

    def _apply(root: ET.Element) -> None:
        for req in root.findall("requirement"):
            for rule in req.findall("rule"):
                if rule.get("id") == rule_id:
                    rule.set("status", status)
                    return
        raise EditError(code="not_found", message=f"rule '{rule_id}' not found")

    _mutate_and_persist(path, _apply)


def set_bug_status(path: Path, bug_id: str, status: str) -> None:
    if status not in BUG_STATUSES:
        raise EditError(
            code="invalid",
            message=f"status must be one of {sorted(BUG_STATUSES)}",
        )

    def _apply(root: ET.Element) -> None:
        for bug in root.findall("bug"):
            if bug.get("id") == bug_id:
                bug.set("status", status)
                return
        raise EditError(code="not_found", message=f"bug '{bug_id}' not found")

    _mutate_and_persist(path, _apply)


def resolve_finding(path: Path, rule_qid: str) -> None:
    """Remove the <finding rule=rule_qid>; if the parent <ui_review> has no
    findings left, set its status to ✅."""

    def _apply(root: ET.Element) -> None:
        target_req_id, _, _rule_local = rule_qid.partition(".")
        for req in root.findall("requirement"):
            if req.get("id") != target_req_id:
                continue
            for ui in req.findall("ui_review"):
                matches = [f for f in ui.findall("finding") if f.get("rule") == rule_qid]
                if not matches:
                    continue
                for f in matches:
                    ui.remove(f)
                if not ui.findall("finding"):
                    ui.set("status", "✅")
                return
        raise EditError(code="not_found", message=f"finding for rule '{rule_qid}' not found")

    _mutate_and_persist(path, _apply)
