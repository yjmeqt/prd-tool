"""In-memory model of all PRDs under a discovered PRD root."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prd_tool.stats import compute_prd_stats

# HTML void elements: self-close in JSON output so dangerouslySetInnerHTML
# parses them correctly. Non-void empty elements get an explicit close tag.
_VOID_HTML_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}


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
                "bugs_active": 0,
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


def _escape_html_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _escape_html_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


def _serialize_html_element(elem: ET.Element) -> str:
    """Serialize one element as HTML (void tags self-close; others use full close)."""
    parts = [f'{k}="{_escape_html_attr(v)}"' for k, v in elem.attrib.items()]
    attr_str = (" " + " ".join(parts)) if parts else ""
    if elem.tag in _VOID_HTML_TAGS:
        return f"<{elem.tag}{attr_str}/>"
    inner = _inner_html(elem)
    return f"<{elem.tag}{attr_str}>{inner}</{elem.tag}>"


def _inner_html(elem: ET.Element, exclude_tags: tuple[str, ...] = ()) -> str:
    """Serialize the inner content of a rich-text element as an HTML string.

    Plain text becomes escaped HTML text. Child elements are serialized as HTML
    (void tags self-close). Children in ``exclude_tags`` are skipped along with
    their tail so the caller can handle them separately (e.g. <figma_node>).
    """
    parts: list[str] = []
    if elem.text:
        parts.append(_escape_html_text(elem.text))
    for child in elem:
        if child.tag in exclude_tags:
            continue
        parts.append(_serialize_html_element(child))
        if child.tail:
            parts.append(_escape_html_text(child.tail))
    return "".join(parts).strip()


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
        "text": _inner_html(rule, exclude_tags=("figma_node",)),
        "figma_nodes": figma_nodes,
    }


def _ui_review_to_dict(ui: ET.Element) -> dict[str, Any]:
    findings = [{"rule": f.get("rule", ""), "text": _inner_html(f)} for f in ui.findall("finding")]
    return {
        "status": ui.get("status", ""),
        "date": ui.get("date", ""),
        "findings": findings,
    }


def _requirement_to_dict(req: ET.Element) -> dict[str, Any]:
    desc_el = req.find("description")
    description = _inner_html(desc_el) if desc_el is not None else ""
    return {
        "id": req.get("id", ""),
        "name": req.get("name", ""),
        "description": description,
        "rules": [_rule_to_dict(r) for r in req.findall("rule")],
        "ui_reviews": [_ui_review_to_dict(u) for u in req.findall("ui_review")],
    }


def _bug_to_dict(bug: ET.Element) -> dict[str, Any]:
    def _child_html(tag: str) -> str:
        el = bug.find(tag)
        if el is None:
            return ""
        return _inner_html(el)

    return {
        "id": bug.get("id", ""),
        "status": bug.get("status", ""),
        "date": bug.get("date", ""),
        "rule": bug.get("rule", ""),
        "current": _child_html("current"),
        "expected": _child_html("expected"),
        "steps": _child_html("steps"),
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
    overview = _inner_html(overview_el) if overview_el is not None else ""
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
