"""CLI entry point for prd-tool."""

from __future__ import annotations

import argparse
import sys
import time
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
    stats_parser.add_argument(
        "-u",
        "--unfinished",
        action="store_true",
        help="Restrict per-feature rows to features with unfinished rules or non-Fixed bugs",
    )

    sub.add_parser("root", help="Print the resolved PRD root (debugging)")

    ls_parser = sub.add_parser("ls", help="List PRD refs under the PRD dir")
    ls_parser.add_argument("module", nargs="?", default=None, help="Optional module filter")
    ls_parser.add_argument(
        "-u",
        "--unfinished",
        action="store_true",
        help="List only refs with unfinished work (rules not ✅, or bugs not Fixed)",
    )

    export_parser = sub.add_parser(
        "export-json",
        help="Write a static JSON snapshot of the dashboard (for read-only hosting)",
    )
    export_parser.add_argument(
        "out",
        help="Output directory; will contain index.json, prd/<m>/<f>.json, asset/<m>/...",
    )

    dash_parser = sub.add_parser("dashboard", help="Launch the local PRD dashboard")
    dash_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind (default: 127.0.0.1)"
    )
    dash_parser.add_argument("--port", type=int, default=8765, help="Port to bind (default: 8765)")
    dash_parser.add_argument(
        "--no-open", action="store_true", help="Do not open the dashboard in a browser"
    )
    dash_parser.add_argument(
        "--allow-no-tty",
        action="store_true",
        help="Override the interactive-terminal requirement (also: PRD_DASHBOARD_ALLOW_NO_TTY=1)",
    )

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
        sys.exit(print_stats(path, unfinished_only=args.unfinished))

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
        import xml.etree.ElementTree as ET

        from prd_tool.stats import has_unfinished_work

        refs: list[str] = []
        for xml in sorted(base.rglob("*.xml")):
            rel = xml.relative_to(root.prd_dir)
            if rel.name == "index.xml":
                continue
            if args.unfinished:
                try:
                    sub_root = ET.parse(xml).getroot()
                except (ET.ParseError, OSError):
                    # Treat unparseable files as unfinished so they remain visible.
                    refs.append(str(rel.with_suffix("")))
                    continue
                if sub_root.tag != "prd" or not has_unfinished_work(sub_root):
                    continue
            refs.append(str(rel.with_suffix("")))
        if refs:
            print("\n".join(refs))
        sys.exit(0)

    elif args.command == "export-json":
        from prd_tool.dashboard.export import export_static
        from prd_tool.root import find_root

        root = find_root()
        if root is None:
            print("prd export-json: no PRD root found from cwd", file=sys.stderr)
            sys.exit(1)

        out_dir = Path(args.out).resolve()
        counts = export_static(root.prd_dir, out_dir)
        print(
            f"Exported {counts['features']} feature(s) and {counts['assets']} asset(s) to {out_dir}"
        )
        sys.exit(0)

    elif args.command == "dashboard":
        import os

        allow_no_tty = args.allow_no_tty or os.environ.get(
            "PRD_DASHBOARD_ALLOW_NO_TTY", ""
        ).lower() in ("1", "true", "yes")
        if not sys.stdin.isatty() and not allow_no_tty:
            print(
                "prd dashboard: refusing to start without an interactive terminal.\n"
                "  The server runs until you stop it with Ctrl+C, so it needs a TTY\n"
                "  attached to stdin. Detected: stdin is not a TTY (backgrounded,\n"
                "  piped, nohup, CI, or agent harness).\n"
                "\n"
                "  Run `prd dashboard` directly in your shell.\n"
                "  If you really need to run under a process supervisor, pass\n"
                "  --allow-no-tty or set PRD_DASHBOARD_ALLOW_NO_TTY=1 — but make\n"
                "  sure something is responsible for stopping the server.",
                file=sys.stderr,
            )
            sys.exit(1)

        from prd_tool.root import find_root

        root = find_root()
        if root is None:
            cwd = Path.cwd().resolve()
            print(
                "prd dashboard: not a PRD repo\n"
                f"  searched upward from: {cwd}\n"
                "  looking for:          .prd-tool.toml  (preferred)\n"
                "                        prd/index.xml   (convention)",
                file=sys.stderr,
            )
            sys.exit(1)

        import socket

        import uvicorn

        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((args.host, args.port))
            except OSError as e:
                print(
                    f"prd dashboard: cannot bind {args.host}:{args.port} ({e.strerror}).\n"
                    "  Another process is probably using the port. Try `--port <n>`\n"
                    "  with a different number, or stop the other process.",
                    file=sys.stderr,
                )
                sys.exit(1)
        finally:
            probe.close()

        if args.host not in ("127.0.0.1", "localhost", "::1"):
            print(
                f"prd dashboard: warning: binding {args.host} exposes the dashboard\n"
                "  on the network with no authentication. Use 127.0.0.1 unless you\n"
                "  understand the risks.",
                file=sys.stderr,
            )

        from prd_tool.dashboard.server import create_app

        app = create_app(root.prd_dir)

        url = f"http://{args.host}:{args.port}"
        print(f"Dashboard at {url}  (PRD root: {root.prd_dir})")
        print("Press Ctrl+C to stop.")

        if not args.no_open:
            import threading
            import webbrowser

            def _open_when_ready() -> None:
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.settimeout(0.2)
                        try:
                            s.connect((args.host, args.port))
                            webbrowser.open(url)
                            return
                        except OSError:
                            time.sleep(0.1)

            threading.Thread(target=_open_when_ready, daemon=True).start()

        # Don't outlive the terminal that launched us. If SIGHUP arrives (the
        # shell's controlling terminal went away) or we get reparented to init
        # (PID 1, i.e. our parent shell died without forwarding SIGHUP), shut
        # down by raising SIGINT against ourselves — uvicorn handles SIGINT.
        import signal as _signal
        import threading as _threading

        def _request_shutdown() -> None:
            os.kill(os.getpid(), _signal.SIGINT)

        if hasattr(_signal, "SIGHUP"):
            _signal.signal(_signal.SIGHUP, lambda *_a: _request_shutdown())

        _orig_ppid = os.getppid()

        def _watch_parent() -> None:
            while True:
                time.sleep(2.0)
                ppid = os.getppid()
                if ppid == 1 or ppid != _orig_ppid:
                    _request_shutdown()
                    return

        _threading.Thread(target=_watch_parent, daemon=True).start()

        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
        sys.exit(0)
