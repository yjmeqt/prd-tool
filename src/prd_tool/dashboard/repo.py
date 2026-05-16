"""In-memory model of all PRDs under a discovered PRD root."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prd_tool.stats import compute_prd_stats


@dataclass(frozen=True)
class FeatureRef:
    module: str
    feature: str

    @property
    def ref(self) -> str:
        return f"{self.module}/{self.feature}"


def list_feature_files(prd_dir: Path) -> list[tuple[FeatureRef, Path]]:
    """Every <module>/<feature>.xml under prd_dir, excluding index.xml."""
    out: list[tuple[FeatureRef, Path]] = []
    for xml in sorted(prd_dir.rglob("*.xml")):
        rel = xml.relative_to(prd_dir)
        if rel.name == "index.xml":
            continue
        if len(rel.parts) < 2:
            continue
        module = rel.parts[0]
        feature = rel.with_suffix("").parts[-1]
        out.append((FeatureRef(module=module, feature=feature), xml))
    return out


def _feature_name_from_xml(path: Path) -> str | None:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None
    if root.tag != "prd":
        return None
    return root.get("name")


def build_index(prd_dir: Path) -> dict[str, Any]:
    """Return the index payload: modules and per-feature stats."""
    modules: dict[str, list[dict[str, Any]]] = {}
    for ref, path in list_feature_files(prd_dir):
        try:
            root = ET.parse(path).getroot()
            stats = compute_prd_stats(root)
            name = root.get("name") or ref.feature
            parse_ok = True
        except (ET.ParseError, OSError):
            stats = {
                "rules_done": 0,
                "rules_total": 0,
                "bugs_open": 0,
                "ui_reviewed": 0,
                "ui_total": 0,
            }
            name = ref.feature
            parse_ok = False
        modules.setdefault(ref.module, []).append(
            {
                "ref": ref.ref,
                "module": ref.module,
                "feature": ref.feature,
                "name": name,
                "stats": stats,
                "parse_ok": parse_ok,
            }
        )
    return {
        "modules": [
            {"name": name, "features": features} for name, features in sorted(modules.items())
        ]
    }


def _rule_to_dict(rule: ET.Element) -> dict[str, Any]:
    figma_nodes = []
    for fn in rule.findall("figma_node"):
        figma_nodes.append(
            {
                "name": fn.get("name", ""),
                "file": fn.get("file", ""),
                "node": fn.get("node", ""),
            }
        )
    return {
        "id": rule.get("id", ""),
        "status": rule.get("status", ""),
        "context": rule.get("context"),
        "text": (rule.text or "").strip(),
        "figma_nodes": figma_nodes,
    }


def _ui_review_to_dict(ui: ET.Element) -> dict[str, Any]:
    findings = [
        {"rule": f.get("rule", ""), "text": (f.text or "").strip()} for f in ui.findall("finding")
    ]
    return {
        "status": ui.get("status", ""),
        "date": ui.get("date", ""),
        "findings": findings,
    }


def _requirement_to_dict(req: ET.Element) -> dict[str, Any]:
    desc_el = req.find("description")
    description = (desc_el.text or "").strip() if desc_el is not None else ""
    return {
        "id": req.get("id", ""),
        "name": req.get("name", ""),
        "description": description,
        "rules": [_rule_to_dict(r) for r in req.findall("rule")],
        "ui_reviews": [_ui_review_to_dict(u) for u in req.findall("ui_review")],
    }


def _bug_to_dict(bug: ET.Element) -> dict[str, Any]:
    def _child_text(tag: str) -> str:
        el = bug.find(tag)
        if el is None or el.text is None:
            return ""
        return el.text.strip()

    return {
        "id": bug.get("id", ""),
        "status": bug.get("status", ""),
        "date": bug.get("date", ""),
        "rule": bug.get("rule", ""),
        "current": _child_text("current"),
        "expected": _child_text("expected"),
        "steps": _child_text("steps"),
    }


def load_feature(prd_dir: Path, ref: FeatureRef) -> dict[str, Any] | None:
    path = prd_dir / ref.module / f"{ref.feature}.xml"
    if not path.is_file():
        return None
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as e:
        return {"ref": ref.ref, "parse_error": str(e)}
    if root.tag != "prd":
        return {"ref": ref.ref, "parse_error": f"root is <{root.tag}>, expected <prd>"}
    overview_el = root.find("overview")
    overview = (overview_el.text or "").strip() if overview_el is not None else ""
    implementations = [
        {
            "platform": impl.get("platform", ""),
            "spec": impl.get("spec", ""),
        }
        for impl in root.findall("implementation")
    ]
    requirements = [_requirement_to_dict(r) for r in root.findall("requirement")]
    bugs = [_bug_to_dict(b) for b in root.findall("bug")]
    stats = compute_prd_stats(root)
    return {
        "ref": ref.ref,
        "module": ref.module,
        "feature": ref.feature,
        "name": root.get("name") or ref.feature,
        "overview": overview,
        "implementations": implementations,
        "requirements": requirements,
        "bugs": bugs,
        "stats": stats,
    }
