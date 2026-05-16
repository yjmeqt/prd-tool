"""CLI entry point for prd-tool."""

import argparse
import sys
from pathlib import Path

from prd_tool.format import format_prd
from prd_tool.stats import print_stats
from prd_tool.validate import validate


def main() -> None:
    parser = argparse.ArgumentParser(description="PRD XML validation and formatting tool.")
    sub = parser.add_subparsers(dest="command", required=True)

    val_parser = sub.add_parser("validate", help="Validate PRD XML structure")
    val_parser.add_argument("file", type=Path, help="Path to PRD XML file")

    fmt_parser = sub.add_parser("format", help="Format and normalize PRD XML")
    fmt_parser.add_argument("file", type=Path, help="Path to PRD XML file")
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
        "file",
        type=Path,
        help="Path to a <prd> XML file or a <prd_index> XML file",
    )

    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    if args.command == "validate":
        errors = validate(args.file)
        if errors:
            print(f"Validation failed with {len(errors)} error(s):\n")
            for i, err in enumerate(errors, 1):
                print(f"  {i}. {err}")
            sys.exit(1)
        else:
            print(f"Validation passed: {args.file}")
            sys.exit(0)

    elif args.command == "format":
        formatted = format_prd(args.file)
        if args.check:
            current = args.file.read_text(encoding="utf-8")
            if current == formatted:
                print(f"Already formatted: {args.file}")
                sys.exit(0)
            else:
                print(f"Not formatted: {args.file}", file=sys.stderr)
                sys.exit(1)
        else:
            args.file.write_text(formatted, encoding="utf-8")
            errors = validate(args.file)
            if errors:
                print(f"Formatted but validation found {len(errors)} error(s):")
                for i, err in enumerate(errors, 1):
                    print(f"  {i}. {err}")
                sys.exit(1)
            else:
                print(f"Formatted and validated: {args.file}")
                sys.exit(0)

    elif args.command == "stats":
        sys.exit(print_stats(args.file))
