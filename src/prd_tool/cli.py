"""CLI entry point for prd-tool."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from prd_tool.format import format_prd
from prd_tool.root import resolve_ref
from prd_tool.stats import print_stats
from prd_tool.validate import validate


def _resolve_or_exit(ref: str) -> Path:
    try:
        return resolve_ref(ref)
    except FileNotFoundError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="PRD XML validation and formatting tool.")
    sub = parser.add_subparsers(dest="command", required=True)

    val_parser = sub.add_parser("validate", help="Validate PRD XML structure")
    val_parser.add_argument("ref", help="Path or <module>/<feature> ref")

    fmt_parser = sub.add_parser("format", help="Format and normalize PRD XML")
    fmt_parser.add_argument("ref", help="Path or <module>/<feature> ref")
    fmt_parser.add_argument(
        "--check",
        action="store_true",
        help="Check if file is already formatted (exit 1 if not)",
    )

    stats_parser = sub.add_parser(
        "stats",
        help="Print rule/bug/ui counters for a PRD file or PRD index (read-only)",
    )
    stats_parser.add_argument(
        "ref",
        nargs="?",
        default=None,
        help="Path or <module>/<feature> ref; defaults to <prd_dir>/index.xml",
    )

    sub.add_parser("root", help="Print the resolved PRD root (debugging)")

    ls_parser = sub.add_parser("ls", help="List PRD refs under the PRD dir")
    ls_parser.add_argument("module", nargs="?", default=None, help="Optional module filter")

    args = parser.parse_args()

    if args.command == "validate":
        path = _resolve_or_exit(args.ref)
        errors = validate(path)
        if errors:
            print(f"Validation failed with {len(errors)} error(s):\n")
            for i, err in enumerate(errors, 1):
                print(f"  {i}. {err}")
            sys.exit(1)
        print(f"Validation passed: {path}")
        sys.exit(0)

    elif args.command == "format":
        path = _resolve_or_exit(args.ref)
        formatted = format_prd(path)
        if args.check:
            current = path.read_text(encoding="utf-8")
            if current == formatted:
                print(f"Already formatted: {path}")
                sys.exit(0)
            print(f"Not formatted: {path}", file=sys.stderr)
            sys.exit(1)
        path.write_text(formatted, encoding="utf-8")
        errors = validate(path)
        if errors:
            print(f"Formatted but validation found {len(errors)} error(s):")
            for i, err in enumerate(errors, 1):
                print(f"  {i}. {err}")
            sys.exit(1)
        print(f"Formatted and validated: {path}")
        sys.exit(0)

    elif args.command == "stats":
        if args.ref is None:
            from prd_tool.root import find_root

            root = find_root()
            if root is None:
                print(
                    "prd stats: no ref given and no PRD root found from cwd",
                    file=sys.stderr,
                )
                sys.exit(1)
            path = root.prd_dir / "index.xml"
            if not path.is_file():
                print(f"prd stats: {path} does not exist", file=sys.stderr)
                sys.exit(1)
        else:
            path = _resolve_or_exit(args.ref)
        sys.exit(print_stats(path))

    elif args.command == "root":
        from prd_tool.root import find_root

        root = find_root()
        if root is None:
            cwd = Path.cwd().resolve()
            print(
                "prd: not a PRD repo\n"
                f"  searched upward from: {cwd}\n"
                "  looking for:          .prd-tool.toml  (preferred)\n"
                "                        prd/index.xml   (convention)",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"{root.repo_root}\t{root.prd_dir}\t{root.source}")
        sys.exit(0)

    elif args.command == "ls":
        from prd_tool.root import find_root

        root = find_root()
        if root is None:
            print("prd ls: no PRD root found from cwd", file=sys.stderr)
            sys.exit(1)
        base = root.prd_dir if args.module is None else root.prd_dir / args.module
        if not base.is_dir():
            print(f"prd ls: {base} is not a directory", file=sys.stderr)
            sys.exit(1)
        refs: list[str] = []
        for xml in sorted(base.rglob("*.xml")):
            rel = xml.relative_to(root.prd_dir)
            if rel.name == "index.xml":
                continue
            refs.append(str(rel.with_suffix("")))
        print("\n".join(refs))
        sys.exit(0)
