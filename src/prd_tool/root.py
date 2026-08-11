"""PRD root discovery."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Source = Literal["toml", "convention"]
StatusLayout = Literal["flat", "namespaced"]

# Well-known platform directory names under a namespaced status_dir.
KNOWN_PLATFORMS = frozenset({"ios", "android"})


@dataclass(frozen=True)
class Root:
    repo_root: Path
    prd_dir: Path
    source: Source
    status_dir: Path | None = None
    platform: str | None = None  # from [prd].platform in .prd-tool.toml
    status_layout: StatusLayout | None = None  # None when no status_dir


class PlatformError(Exception):
    """Raised when a namespaced overlay needs an explicit platform selection."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


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
            try:
                data = tomllib.loads(toml.read_text(encoding="utf-8"))
            except tomllib.TOMLDecodeError:
                data = {}

            prd_dir_rel = _read_prd_dir(data)
            status_dir = _resolve_status_dir(ancestor, data)
            layout = detect_status_layout(status_dir) if status_dir is not None else None
            return Root(
                repo_root=ancestor,
                prd_dir=(ancestor / prd_dir_rel).resolve(),
                source="toml",
                status_dir=status_dir,
                platform=_read_platform(data),
                status_layout=layout,
            )

        index = ancestor / "prd" / "index.xml"
        if index.is_file():
            status_dir = _resolve_status_dir(ancestor, None)
            layout = detect_status_layout(status_dir) if status_dir is not None else None
            return Root(
                repo_root=ancestor,
                prd_dir=ancestor / "prd",
                source="convention",
                status_dir=status_dir,
                platform=None,
                status_layout=layout,
            )

    return None


def _read_prd_dir(toml_data: dict[str, Any]) -> str:
    section = toml_data.get("prd")
    if isinstance(section, dict):
        value = section.get("dir")
        if isinstance(value, str) and value:
            return value
    return "prd"


def _read_platform(toml_data: dict[str, Any]) -> str | None:
    section = toml_data.get("prd")
    if isinstance(section, dict):
        value = section.get("platform")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_status_dir(repo_root: Path, toml_data: dict[str, Any] | None) -> Path | None:
    if toml_data is not None:
        section = toml_data.get("prd")
        if isinstance(section, dict):
            value = section.get("status_dir")
            if isinstance(value, str) and value:
                candidate = (repo_root / value).resolve()
                if candidate.is_dir():
                    return candidate

    fallback = (repo_root / "prd-status").resolve()
    if fallback.is_dir():
        return fallback

    return None


def _is_module_feature_layout(directory: Path) -> bool:
    """True if `directory` looks like <module>/<feature>.toml."""
    for child in directory.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if any(child.glob("*.toml")):
            return True
    return False


def detect_status_layout(status_dir: Path) -> StatusLayout:
    """Detect flat vs namespaced progress overlay layout under ``status_dir``.

    Namespaced when any immediate child is a known platform name, or is a
    directory that itself contains a module/feature.toml layout.
    Otherwise treat as legacy flat ``<module>/<feature>.toml``.
    """
    if not status_dir.is_dir():
        return "flat"

    for child in status_dir.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name in KNOWN_PLATFORMS:
            return "namespaced"
        if _is_module_feature_layout(child):
            return "namespaced"

    return "flat"


def list_status_platforms(status_dir: Path) -> list[str]:
    """Platform directory names under a namespaced ``status_dir`` (sorted)."""
    if not status_dir.is_dir():
        return []
    names: list[str] = []
    for child in status_dir.iterdir():
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name in KNOWN_PLATFORMS or _is_module_feature_layout(child):
            names.append(child.name)
    return sorted(names)


def resolve_platform(
    root: Root,
    *,
    cli_platform: str | None = None,
    all_platforms: bool = False,
) -> str | None:
    """Resolve the platform segment for overlay paths.

    Precedence: ``cli_platform`` → ``PRD_PLATFORM`` → ``[prd].platform``.

    Returns ``None`` for flat/legacy layout (no platform segment), or when
    ``all_platforms`` is set (caller iterates platforms).

    Raises :class:`PlatformError` if layout is namespaced and no platform
    is selected.
    """
    if root.status_dir is None:
        return None

    layout = root.status_layout or detect_status_layout(root.status_dir)
    if layout == "flat":
        return None

    if all_platforms:
        return None

    selected = (cli_platform or "").strip() or None
    if selected is None:
        env = os.environ.get("PRD_PLATFORM", "").strip()
        selected = env or None
    if selected is None:
        selected = root.platform

    if selected:
        return selected

    platforms = list_status_platforms(root.status_dir)
    available = ", ".join(platforms) if platforms else "(none found)"
    raise PlatformError(
        "prd: namespaced status overlay requires a platform selection.\n"
        f"  status_dir: {root.status_dir}\n"
        f"  available:  {available}\n"
        "  select via: --platform <name>, env PRD_PLATFORM, "
        "or [prd].platform in .prd-tool.toml"
    )


def resolve_ref(ref: str, *, start: Path | None = None) -> Path:
    """Resolve a CLI ref to a concrete file path.

    Order:
      1. If `ref` exists on disk as-is, return it.
      2. Else, find the PRD root from `start` (cwd by default) and try
         `<prd_dir>/<ref>.xml`, then `<prd_dir>/<ref>` (in case the user
         typed `.xml` themselves).
      3. Else, raise FileNotFoundError with an actionable message.
    """
    literal = Path(ref)
    if literal.exists():
        return literal

    root = find_root(start)
    if root is not None:
        candidates = [
            root.prd_dir / f"{ref}.xml",
            root.prd_dir / ref,
        ]
        for c in candidates:
            if c.is_file():
                return c

    searched_from = (start or Path.cwd()).resolve()
    raise FileNotFoundError(
        "prd: not a PRD repo or unknown ref\n"
        f"  searched upward from: {searched_from}\n"
        "  looking for:          .prd-tool.toml  (preferred)\n"
        "                        prd/index.xml   (convention)\n"
        f"  ref tried:            {ref!r}\n"
        "  fix: cd into a PRD repo, create one of the markers above, "
        "or pass an existing path"
    )
