"""CLI entry point for prd-tool."""

from __future__ import annotations

import argparse
import os
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


_DETACH_SENTINEL_ENV = "_PRD_VIEW_DETACHED"


def _run_native_view(refs: list[str], detach: bool) -> None:
    from prd_tool.root import find_root

    root = find_root()
    if root is None:
        cwd = Path.cwd().resolve()
        print(
            "prd view: not a PRD repo\n"
            f"  searched upward from: {cwd}\n"
            "  looking for:          .prd-tool.toml  (preferred)\n"
            "                        prd/index.xml   (convention)",
            file=sys.stderr,
        )
        sys.exit(1)

    # When --detach (default) is requested and we are not already the detached
    # child, spawn a fresh subprocess in its own session and exit. Doing this
    # with subprocess.Popen + start_new_session is reliable on macOS;
    # os.fork() in a process that may have transitively imported PyObjC/AppKit
    # corrupts WebKit in the forked child (window opens, JS never runs, blank
    # white screen).
    if detach and os.environ.get(_DETACH_SENTINEL_ENV) != "1":
        _respawn_detached(root.prd_dir)
        return

    from prd_tool.dashboard.native import run_native

    run_native(root.prd_dir, refs)


def _respawn_detached(prd_dir: Path) -> None:
    """Spawn `prd view --no-detach` as a new session-leader process and exit."""
    import subprocess
    import tempfile

    log_path = Path(tempfile.gettempdir()) / f"prd-view-{os.getpid()}.log"
    log_fd = os.open(str(log_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    devnull_fd = os.open(os.devnull, os.O_RDONLY)
    try:
        # Re-exec the same `prd` command with --no-detach and a sentinel env
        # var so the child knows it is the detached worker (and would not
        # respawn again if --no-detach were stripped by argv munging).
        env = {**os.environ, _DETACH_SENTINEL_ENV: "1"}
        new_argv = [a for a in sys.argv if a != "--no-detach"]
        if "--no-detach" not in new_argv:
            new_argv = [*new_argv, "--no-detach"]
        proc = subprocess.Popen(
            new_argv,
            env=env,
            stdin=devnull_fd,
            stdout=log_fd,
            stderr=log_fd,
            start_new_session=True,
            close_fds=True,
        )
    finally:
        os.close(log_fd)
        os.close(devnull_fd)
    print(f"prd view: launched pid={proc.pid} (PRD root: {prd_dir}, log: {log_path})")


def _run_server_view(args: argparse.Namespace) -> None:
    allow_no_tty = args.allow_no_tty or os.environ.get(
        "PRD_DASHBOARD_ALLOW_NO_TTY", ""
    ).lower() in ("1", "true", "yes")
    if not sys.stdin.isatty() and not allow_no_tty:
        print(
            "prd view --server: refusing to start without an interactive terminal.\n"
            "  The server runs until you stop it with Ctrl+C, so it needs a TTY\n"
            "  attached to stdin. Detected: stdin is not a TTY (backgrounded,\n"
            "  piped, nohup, CI, or agent harness).\n"
            "\n"
            "  Run `prd view --server` directly in your shell.\n"
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
            "prd view --server: not a PRD repo\n"
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
                f"prd view --server: cannot bind {args.host}:{args.port} ({e.strerror}).\n"
                "  Another process is probably using the port. Try `--port <n>`\n"
                "  with a different number, or stop the other process.",
                file=sys.stderr,
            )
            sys.exit(1)
    finally:
        probe.close()

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            f"prd view --server: warning: binding {args.host} exposes the dashboard\n"
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

    view_parser = sub.add_parser("view", help="Open the PRD viewer")
    view_parser.add_argument(
        "refs",
        nargs="*",
        help="Optional list of <module>/<feature> refs to open in separate windows. "
        "If empty, opens the index.",
    )
    view_parser.add_argument(
        "--server",
        action="store_true",
        help="Run the FastAPI dashboard on http://127.0.0.1:<port> instead of a native window.",
    )
    view_parser.add_argument(
        "--no-detach",
        action="store_true",
        help="(native only) Keep the launcher attached to the terminal so logs and "
        "crashes print to stdout. Default: detach like `open` so the shell returns "
        "immediately.",
    )
    view_parser.add_argument(
        "--host", default="127.0.0.1", help="(--server only) Host to bind (default: 127.0.0.1)"
    )
    view_parser.add_argument(
        "--port", type=int, default=8765, help="(--server only) Port to bind (default: 8765)"
    )
    view_parser.add_argument(
        "--no-open",
        action="store_true",
        help="(--server only) Do not open the dashboard in a browser",
    )
    view_parser.add_argument(
        "--allow-no-tty",
        action="store_true",
        help="(--server only) Override the interactive-terminal requirement "
        "(also: PRD_DASHBOARD_ALLOW_NO_TTY=1)",
    )

    # Hidden deprecated alias for one release.
    dash_alias = sub.add_parser("dashboard", help=argparse.SUPPRESS)
    dash_alias.add_argument("--host", default="127.0.0.1")
    dash_alias.add_argument("--port", type=int, default=8765)
    dash_alias.add_argument("--no-open", action="store_true")
    dash_alias.add_argument("--allow-no-tty", action="store_true")

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

    elif args.command in ("view", "dashboard"):
        if args.command == "dashboard":
            print(
                "prd dashboard: deprecated — use `prd view --server` instead.",
                file=sys.stderr,
            )
            _run_server_view(args)
            sys.exit(0)

        if args.server:
            _run_server_view(args)
            sys.exit(0)

        _run_native_view(args.refs or [], detach=not args.no_detach)
        sys.exit(0)
