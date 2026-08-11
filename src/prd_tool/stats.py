"""PRD XML stats computation and printing."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prd_tool.overlay import Progress


def _rule_glyph(req_id: str, rule: ET.Element, progress: "Progress | None") -> str:
    if progress is None:
        return rule.get("status", "")
    from prd_tool.overlay import rule_status

    return rule_status(progress, f"{req_id}.{rule.get('id', '')}")


def has_unfinished_work(root: ET.Element, progress: "Progress | None" = None) -> bool:
    """True iff the PRD has at least one rule not ✅ or at least one bug not Fixed."""
    for req in root.findall("requirement"):
        req_id = req.get("id", "")
        for rule in req.findall("rule"):
            if _rule_glyph(req_id, rule, progress) != "✅":
                return True
    if progress is not None and any(pr.status != "✅" for pr in progress.platform_rules):
        return True
    return any(bug.get("status") != "Fixed" for bug in root.findall("bug"))


def compute_prd_stats(root: ET.Element, progress: "Progress | None" = None) -> dict[str, int]:
    """Compute counters for a single <prd> element."""
    rules_done = 0
    rules_total = 0
    bugs_open = 0
    bugs_active = 0
    ui_reviewed = 0
    ui_total = 0

    for req in root.findall("requirement"):
        req_id = req.get("id", "")
        for rule in req.findall("rule"):
            rules_total += 1
            if _rule_glyph(req_id, rule, progress) == "✅":
                rules_done += 1
        for ui_review in req.findall("ui_review"):
            ui_total += 1
            if ui_review.get("status") == "✅":
                ui_reviewed += 1

    if progress is not None:
        for pr in progress.platform_rules:
            rules_total += 1
            if pr.status == "✅":
                rules_done += 1

    for bug in root.findall("bug"):
        status = bug.get("status")
        if status == "Open":
            bugs_open += 1
        if status in ("Open", "Fix Pending"):
            bugs_active += 1

    return {
        "rules_done": rules_done,
        "rules_total": rules_total,
        "bugs_open": bugs_open,
        "bugs_active": bugs_active,
        "ui_reviewed": ui_reviewed,
        "ui_total": ui_total,
    }


def _load_overlay_progress(
    status_dir: Path | None,
    prd_dir: Path | None,
    target: Path,
    platform: str | None,
) -> "Progress | None":
    if status_dir is None or prd_dir is None:
        return None
    from prd_tool.overlay import OverlayError, load_progress, overlay_path

    try:
        rel_path = target.relative_to(prd_dir)
    except ValueError:
        return None
    feature = rel_path.with_suffix("").name
    mod = rel_path.parent.name
    try:
        return load_progress(overlay_path(status_dir, mod, feature, platform))
    except OverlayError as e:
        print(f"Overlay error for {rel_path}: {e}", file=sys.stderr)
        raise


def print_stats(
    path: Path,
    unfinished_only: bool = False,
    progress: "Progress | None" = None,
    *,
    status_dir: Path | None = None,
    prd_dir: Path | None = None,
    platform: str | None = None,
    platforms: list[str] | None = None,
) -> int:
    """Print stats for a PRD file or a PRD index. Returns exit code.

    When ``platforms`` is provided (``--all-platforms``), print a section per
    platform using the namespaced overlay layout.
    """
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as e:
        print(f"XML parse error: {e}", file=sys.stderr)
        return 1

    root = tree.getroot()

    if platforms:
        exit_code = 0
        for plat in platforms:
            print(f"=== platform: {plat} ===")
            code = print_stats(
                path,
                unfinished_only=unfinished_only,
                progress=None,
                status_dir=status_dir,
                prd_dir=prd_dir,
                platform=plat,
            )
            if code != 0:
                exit_code = code
        return exit_code

    if root.tag == "prd":
        name = root.get("name", path.name)
        sub_progress = progress
        if sub_progress is None and status_dir is not None:
            try:
                sub_progress = _load_overlay_progress(status_dir, prd_dir, path, platform)
            except Exception:
                return 1
        if unfinished_only and not has_unfinished_work(root, sub_progress):
            return 0
        stats = compute_prd_stats(root, sub_progress)
        print(_format_stats_line(name, stats))
        return 0

    if root.tag == "prd_index":
        base = path.parent
        exit_code = 0
        effective_prd_dir = prd_dir or base

        for module in root.findall("module"):
            module_name = module.get("name", "")
            module_rows: list[str] = []
            for entry in module.findall("entry"):
                file_attr = entry.get("file", "")
                entry_name = entry.get("name", file_attr)
                target = base / file_attr
                if not target.exists():
                    module_rows.append(f"  {entry_name}: (file not found: {target})")
                    exit_code = 1
                    continue
                try:
                    sub_root = ET.parse(target).getroot()
                except (ET.ParseError, OSError) as e:
                    module_rows.append(f"  {entry_name}: (parse error: {e})")
                    exit_code = 1
                    continue

                sub_progress = None
                if status_dir is not None:
                    try:
                        sub_progress = _load_overlay_progress(
                            status_dir, effective_prd_dir, target, platform
                        )
                    except Exception:
                        exit_code = 1
                        continue

                if unfinished_only and not has_unfinished_work(sub_root, sub_progress):
                    continue
                stats = compute_prd_stats(sub_root, sub_progress)
                module_rows.append(f"  {_format_stats_line(entry_name, stats)}")
            if module_rows:
                print(f"[{module_name}]")
                for row in module_rows:
                    print(row)
        return exit_code

    print(
        f"Unsupported root element <{root.tag}> (expected <prd> or <prd_index>)",
        file=sys.stderr,
    )
    return 1


def _format_stats_line(name: str, stats: dict[str, int]) -> str:
    return (
        f"{name}: "
        f"rules {stats['rules_done']}/{stats['rules_total']}, "
        f"bugs_open {stats['bugs_open']}, "
        f"ui {stats['ui_reviewed']}/{stats['ui_total']}"
    )
