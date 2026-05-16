"""PRD XML stats computation and printing."""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def compute_prd_stats(root: ET.Element) -> dict[str, int]:
    """Compute counters for a single <prd> element."""
    rules_done = 0
    rules_total = 0
    bugs_open = 0
    ui_reviewed = 0
    ui_total = 0

    for req in root.findall("requirement"):
        for rule in req.findall("rule"):
            rules_total += 1
            if rule.get("status") == "✅":
                rules_done += 1
        for ui_review in req.findall("ui_review"):
            ui_total += 1
            if ui_review.get("status") == "✅":
                ui_reviewed += 1

    for bug in root.findall("bug"):
        if bug.get("status") == "Open":
            bugs_open += 1

    return {
        "rules_done": rules_done,
        "rules_total": rules_total,
        "bugs_open": bugs_open,
        "ui_reviewed": ui_reviewed,
        "ui_total": ui_total,
    }


def print_stats(path: Path) -> int:
    """Print stats for a PRD file or a PRD index. Returns exit code."""
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as e:
        print(f"XML parse error: {e}", file=sys.stderr)
        return 1

    root = tree.getroot()

    if root.tag == "prd":
        name = root.get("name", path.name)
        stats = compute_prd_stats(root)
        print(_format_stats_line(name, stats))
        return 0

    if root.tag == "prd_index":
        base = path.parent
        exit_code = 0
        for module in root.findall("module"):
            module_name = module.get("name", "")
            print(f"[{module_name}]")
            for entry in module.findall("entry"):
                file_attr = entry.get("file", "")
                entry_name = entry.get("name", file_attr)
                target = base / file_attr
                if not target.exists():
                    print(f"  {entry_name}: (file not found: {target})")
                    exit_code = 1
                    continue
                try:
                    sub_root = ET.parse(target).getroot()
                except (ET.ParseError, OSError) as e:
                    print(f"  {entry_name}: (parse error: {e})")
                    exit_code = 1
                    continue
                stats = compute_prd_stats(sub_root)
                print(f"  {_format_stats_line(entry_name, stats)}")
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
