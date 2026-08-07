import contextlib
import os
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from prd_tool.constants import RULE_STATUSES


@dataclass(frozen=True)
class PlatformRule:
    id: str
    status: str
    description: str = ""


@dataclass(frozen=True)
class Progress:
    rules: dict[str, str]
    notes: dict[str, str]
    platform_rules: tuple[PlatformRule, ...] = ()


@dataclass(frozen=True)
class OverlayError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def overlay_path(status_dir: Path, module: str, feature: str) -> Path:
    return status_dir / module / f"{feature}.toml"


def load_progress(path: Path) -> Progress:
    if not path.is_file():
        return Progress(rules={}, notes={}, platform_rules=())

    try:
        content = path.read_text(encoding="utf-8")
        data = tomllib.loads(content)
    except Exception as e:
        raise OverlayError(f"Failed to read or parse TOML: {e}") from e

    rules = data.get("rules", {})
    if not isinstance(rules, dict):
        raise OverlayError("[rules] must be a table")

    for qid, status in rules.items():
        if status not in RULE_STATUSES:
            raise OverlayError(f"Invalid status {status!r} for rule {qid!r}")

    notes = data.get("notes", {})
    if not isinstance(notes, dict):
        raise OverlayError("[notes] must be a table")

    platform_rules_data = data.get("platform_rule", [])
    if not isinstance(platform_rules_data, list):
        raise OverlayError("[[platform_rule]] must be an array of tables")

    android_rules_data = data.get("android_rule", [])
    if not isinstance(android_rules_data, list):
        raise OverlayError("[[android_rule]] must be an array of tables")

    all_platform_rules = []
    for pr in platform_rules_data + android_rules_data:
        if not isinstance(pr, dict):
            raise OverlayError("Platform rule must be a table")
        pr_id = pr.get("id")
        pr_status = pr.get("status")
        pr_desc = pr.get("description", "")

        if not pr_id or not isinstance(pr_id, str):
            raise OverlayError("Platform rule must have a string id")
        if not pr_status or not isinstance(pr_status, str):
            raise OverlayError("Platform rule must have a string status")
        if pr_status not in RULE_STATUSES:
            raise OverlayError(f"Invalid status {pr_status!r} for platform rule {pr_id!r}")

        all_platform_rules.append(PlatformRule(id=pr_id, status=pr_status, description=pr_desc))

    return Progress(
        rules=dict(rules),
        notes=dict(notes),
        platform_rules=tuple(all_platform_rules),
    )


def rule_status(progress: Progress, qualified_id: str) -> str:
    return progress.rules.get(qualified_id, "❌")

def _escape_toml_string(s: str) -> str:
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
    return f'"{s}"'


def save_progress(path: Path, progress: Progress) -> None:
    lines = []
    
    if progress.rules:
        lines.append("[rules]")
        for qid in sorted(progress.rules.keys()):
            status = progress.rules[qid]
            lines.append(f"{_escape_toml_string(qid)} = {_escape_toml_string(status)}")
        lines.append("")
        
    if progress.notes:
        lines.append("[notes]")
        for qid in sorted(progress.notes.keys()):
            note = progress.notes[qid]
            lines.append(f"{_escape_toml_string(qid)} = {_escape_toml_string(note)}")
        lines.append("")

    for pr in progress.platform_rules:
        lines.append("[[platform_rule]]")
        lines.append(f"id = {_escape_toml_string(pr.id)}")
        lines.append(f"status = {_escape_toml_string(pr.status)}")
        if pr.description:
            lines.append(f"description = {_escape_toml_string(pr.description)}")
        lines.append("")

    content = "\n".join(lines)
    if content and not content.endswith("\n"):
        content += "\n"
    elif not content:
        content = "\n"

    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
