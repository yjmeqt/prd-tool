"""Extract rule statuses from XML into TOML."""

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET

from prd_tool.dashboard.edits import EditError, _mutate_and_persist
from prd_tool.dashboard.repo import list_feature_files
from prd_tool.overlay import Progress, load_progress, overlay_path, save_progress
from prd_tool.root import detect_status_layout, find_root


def migrate_status(dry_run: bool = False, platform: str | None = None) -> int:
    root = find_root()
    if root is None:
        print("prd migrate-status: not a PRD repo", file=sys.stderr)
        return 1

    status_dir = root.status_dir if root.status_dir is not None else root.repo_root / "prd-status"

    selected = (platform or "").strip() or None
    if selected is None:
        env = os.environ.get("PRD_PLATFORM", "").strip()
        selected = env or root.platform

    if status_dir.is_dir():
        layout = detect_status_layout(status_dir)
    else:
        # Creating fresh: namespaced only when an explicit platform is chosen.
        layout = "namespaced" if selected else "flat"

    effective_platform: str | None
    if layout == "namespaced":
        if not selected:
            print(
                "prd migrate-status: namespaced status overlay requires a platform.\n"
                "  select via: --platform <name> (suggested: ios for historical extraction),\n"
                "              env PRD_PLATFORM, or [prd].platform in .prd-tool.toml",
                file=sys.stderr,
            )
            return 1
        effective_platform = selected
    else:
        effective_platform = None

    files_migrated = 0
    rules_extracted = 0
    failed = False

    for feature_ref, path in list_feature_files(root.prd_dir):
        try:
            tree = ET.parse(path)
        except Exception as e:
            print(f"Error parsing {path}: {e}", file=sys.stderr)
            failed = True
            continue

        xml_root = tree.getroot()
        extracted: dict[str, str] = {}
        for req in xml_root.findall("requirement"):
            req_id = req.get("id", "")
            for rule in req.findall("rule"):
                status = rule.get("status")
                if status:
                    qid = f"{req_id}.{rule.get('id', '')}"
                    extracted[qid] = status

        op = overlay_path(status_dir, feature_ref.module, feature_ref.feature, effective_platform)
        existing_progress = None
        if op.exists():
            try:
                existing_progress = load_progress(op)
            except Exception as e:
                print(f"Error loading existing progress for {path}: {e}", file=sys.stderr)
                failed = True
                continue

        # If XML has zero rule statuses left to extract AND TOML already exists with rules
        # treat as already migrated / idempotent no-op for that file
        if not extracted and existing_progress is not None and existing_progress.rules:
            continue

        # Merge
        merged_rules = dict(existing_progress.rules) if existing_progress else {}
        merged_rules.update(extracted)
        notes = dict(existing_progress.notes) if existing_progress else {}
        platform_rules = existing_progress.platform_rules if existing_progress else ()

        new_progress = Progress(rules=merged_rules, notes=notes, platform_rules=platform_rules)

        if not dry_run:
            if extracted or (existing_progress is None and new_progress.rules):
                try:
                    save_progress(op, new_progress)
                except Exception as e:
                    print(f"Error saving progress for {path}: {e}", file=sys.stderr)
                    failed = True
                    continue

            if extracted:

                def _apply(r: ET.Element) -> None:
                    for req in r.findall("requirement"):
                        for rule in req.findall("rule"):
                            if "status" in rule.attrib:
                                del rule.attrib["status"]

                try:
                    _mutate_and_persist(path, _apply, require_rule_status=False)
                except EditError as e:
                    print(f"Error mutating {path}: {e}", file=sys.stderr)
                    failed = True
                    continue

        if extracted:
            files_migrated += 1
            rules_extracted += len(extracted)

    if dry_run:
        print(f"[dry-run] Would migrate {files_migrated} file(s) and {rules_extracted} rule(s).")
    else:
        print(f"Migrated {files_migrated} file(s) and {rules_extracted} rule(s).")

    return 1 if failed else 0
