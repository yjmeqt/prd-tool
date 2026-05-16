"""PRD root discovery."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Source = Literal["toml", "convention"]


@dataclass(frozen=True)
class Root:
    repo_root: Path
    prd_dir: Path
    source: Source


def find_root(start: Path | None = None) -> Root | None:
    """Walk up from `start` (default: cwd) looking for a PRD root.

    `.prd-tool.toml` takes precedence over the `prd/index.xml` convention
    when both exist in the same ancestor directory. Returns None if no
    marker is found before reaching the filesystem root.
    """
    here = (start or Path.cwd()).resolve()

    for ancestor in [here, *here.parents]:
        toml = ancestor / ".prd-tool.toml"
        if toml.is_file():
            prd_dir_rel = _read_prd_dir(toml)
            return Root(
                repo_root=ancestor,
                prd_dir=(ancestor / prd_dir_rel).resolve(),
                source="toml",
            )

        index = ancestor / "prd" / "index.xml"
        if index.is_file():
            return Root(
                repo_root=ancestor,
                prd_dir=ancestor / "prd",
                source="convention",
            )

    return None


def _read_prd_dir(toml_path: Path) -> str:
    try:
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError:
        return "prd"
    section = data.get("prd")
    if isinstance(section, dict):
        value = section.get("dir")
        if isinstance(value, str) and value:
            return value
    return "prd"
