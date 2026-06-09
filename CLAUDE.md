# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`prd-tool` is a CLI (validate, format, stats, view) plus a companion Claude Code skill for product requirement documents authored as XML. PRDs live in `prd/<module>/<feature>.xml` and describe **what** a feature does (requirements, rules, bugs, UI-review findings, Figma references) — separate from per-platform implementation specs that describe **how** it's built.

## Build & Test Commands

### Python (root)

All Python tooling uses `uv`. Python 3.11+ required.

```bash
uv sync --dev                 # install all deps including dev
uv run ruff check src/ tests/ # lint
uv run ruff format --check src/ tests/  # format check
uv run mypy src/              # type check (strict mode)
uv run pytest                 # run all tests
uv run pytest tests/test_validate.py -k "test_name"  # single test
```

### Frontend (`frontend/`)

Package manager is `pnpm@10`. Node 22+.

```bash
cd frontend
pnpm install                  # install deps
pnpm run dev                  # Vite dev server (proxies /api to :8765)
pnpm run build                # tsc --noEmit + vite build → src/prd_tool/dashboard/static/
pnpm run typecheck            # tsc --noEmit only
pnpm run lint                 # eslint
pnpm run format:check         # prettier --check
pnpm run test                 # vitest run
pnpm run check                # all four: typecheck + lint + format:check + test
```

### Pre-push hook

```bash
git config core.hooksPath .githooks
```

Runs ruff check, ruff format --check, mypy, pytest, and (if `frontend/node_modules` exists) frontend typecheck, lint, format:check, and test. CI runs the same steps.

### Static export for read-only hosting

```bash
prd export-json out/          # writes index.json + prd/<m>/<f>.json + asset/<m>/...
VITE_STATIC_BASE=../out pnpm --dir frontend build  # builds SPA that reads static JSON
```

## Architecture

### Python package (`src/prd_tool/`)

The package is structured in layers:

**CLI layer** — `cli.py` is the entry point (`prd` command). It defines argparse subcommands: `validate`, `format`, `stats`, `root`, `ls`, `export-json`, `view`. The `view` subcommand dispatches to either native mode (pywebview) or server mode (FastAPI) based on `--server`.

**PRD root discovery** — `root.py` walks up from cwd looking for `.prd-tool.toml` (preferred) or `prd/index.xml` (convention). Returns a `Root` dataclass with `repo_root`, `prd_dir`, and `source`. All subcommands use `resolve_ref()` to turn `<module>/<feature>` strings into concrete paths.

**Validate / Format / Stats** — `validate.py` checks XML structure against the schema (required attrs, ID sequencing, child ordering, cross-references). `format.py` normalizes XML (attribute ordering, indentation, stripping deprecated attrs, XHTML serialization). `stats.py` computes rule/bug/UI counters from a parsed XML tree — counters are derived, never stored in the XML. `constants.py` holds canonical statuses, required attributes, child element order, and attribute order.

**Dashboard subsystem** (`dashboard/`):

- `repo.py` — in-memory model. Parses XML from disk into JSON-serializable dicts for the frontend. Handles rich-text (XHTML) serialization via `_inner_html()` — child elements become HTML, `<figma_node>` children are excluded and emitted as JSON instead. `load_feature()` loads one PRD; `build_index()` loads all.
- `ops.py` — transport-agnostic operations class (`DashboardOps`). Called by both FastAPI (`server.py`) and the pywebview JS bridge (`native.py`). Exposes `index()`, `feature()`, `set_rule_status()`, `set_bug_status()`, `resolve_finding()`, `asset_path()`. Returns Python types and raises `OpsError` — never HTTP/JSON aware.
- `edits.py` — persisted mutations to PRD XML. Core pattern: read file → capture stat → mutate in-memory → write to temp file → format+validate → check stat hasn't changed (concurrent write detection via mtime/size/inode) → atomic replace. All three mutation types (rule status, bug status, resolve finding) follow this pattern.
- `server.py` — FastAPI app factory. Serves the Vite-built SPA from `static/`, mounts `/api/*` endpoints, and provides SSE streaming.
- `sse.py` — file-watch driven Server-Sent Events. Uses `watchfiles.awatch` to detect XML changes, classifies them (index_changed / prd_changed / invalid), and yields SSE-formatted bytes.
- `native.py` — macOS native window entry point. Uses `pywebview` to create a WKWebView window. Exposes `JsApi` to JavaScript — Python methods become `window.pywebview.api.*` with a result envelope (`{ok, data}` | `{ok, error}`). Key details:
  - The Vite-built HTML is rewritten at launch to make asset paths relative (`/assets/` → `./assets/`) and to strip `crossorigin` attributes (WKWebView CORS under `file://`).
  - An error forwarder script is injected before `</head>` to capture JS runtime errors and forward them to stderr via the bridge.
  - `watchfiles` runs in a background thread and pushes change events to open windows via `evaluate_js`.
  - The detached launch mode (`--detach`, default) spawns a new subprocess via `Popen` with `start_new_session` rather than using `os.fork()` (which corrupts WebKit in forked children that import PyObjC).
- `export.py` — static JSON export. Materializes the same shapes served by the API as files on disk, plus copies non-XML assets. Used with `VITE_STATIC_BASE` for read-only hosting.

### Frontend (`frontend/src/`)

React 18 SPA with Vite, Tailwind CSS 4, shadcn/ui (Radix primitives), react-router-dom v6, @tanstack/react-query.

**Routing**: Hash-based in native mode, browser-history in server mode. Routes: `/` (Home page — the index listing), `/p/:module/:feature` (Feature page — one PRD detail).

**API layer** (`api.ts`): The `api` object dispatches between three modes transparently:
1. **Native** (`isNative()` → true): calls `window.pywebview.api.*` with snake_case method names, unwraps result envelopes.
2. **Static** (`IS_READONLY` → true): fetches static JSON from the path set by `VITE_STATIC_BASE`.
3. **Server** (default): fetches from `/api/*` on the FastAPI backend.

Native mode detection is a function (`isNative()`), not a module-level constant — `window.pywebview` is injected AFTER ESM evaluation, so a top-level check is always false.

**Key components**: `RuleCard.tsx` (rule status toggle with Figma thumbnails), `BugCard.tsx` (bug status lifecycle: Open → Fix Pending → Fixed), `UiReviewBlock.tsx` (UI review findings), `RichContent.tsx` (renders XHTML, resolves local image `src` to file:// or asset URLs, intercepts `prd:` cross-reference links). `Sidebar.tsx` provides module navigation.

**Live updates**: `useSse.ts` connects to the SSE endpoint and invalidates react-query cache on file changes. In native mode, the watchfiles thread pushes events via `window.__prdOnFsEvent` instead.

**Theme**: `ThemeProvider.tsx` applies `dark`/`light` class on `<html>` via `next-themes`.

### Skill (`skills/prd/SKILL.md`)

The `/prd` skill consumed by Claude Code. Loads a PRD file, fetches referenced Figma nodes, reads per-platform implementation specs, and presents a structured context summary before coding starts. Also defines the XML schema and writing rules for requirements, rules, bugs, and UI reviews.

### Hatch build hook (`hatch_build.py`)

Runs `pnpm install --frozen-lockfile && pnpm build` in `frontend/` before packaging the wheel, so `uv tool install git+...` always ships a matching frontend bundle. Skipped when `PRD_SKIP_FRONTEND_BUILD` is set or pnpm is unavailable.

## PRD File Schema

- Root: `<prd name="...">` containing `<overview>`, `<implementation platform="..." spec="..."/>`, `<requirement id="R<n>" name="...">`, `<bug id="..." status="..." date="..." rule="...">`
- Rule statuses: `✅` (done), `❌` (not done), `⚠️` (partial)
- Bug statuses: `Open`, `Fix Pending`, `Fixed` (never mark Fixed without user confirmation)
- UI review statuses: `✅`, `❌`, `⚠️`
- IDs are permanent — never rename or reuse rule IDs or bug IDs
- Counters are computed on demand via `prd stats`, never stored in XML

## Rich Content (XHTML)

Certain fields support inline XHTML: `<overview>`, `<description>`, rule text, bug children (`<current>`, `<expected>`, `<steps>`), finding text. Both server.py (`_inner_html`) and native mode render this as HTML. Cross-references use `prd:` URIs inside `<a href="prd:module/feature#R<n>">` — the viewer intercepts and routes client-side.

## Key Conventions

- The `prd` CLI uses Python 3.11+ features including `tomllib` (stdlib TOML parser)
- Frontend uses `@/` as a path alias for `frontend/src/`
- The wheel's `force-include` ships `src/prd_tool/dashboard/static` — the Vite build output goes there
- Native mode rewrites the HTML post-build (asset paths, crossorigin stripping, error forwarder injection) into `index.native.html` alongside the original `index.html`
- Detached native viewer logs go to `$TMPDIR/prd-view-<pid>.log`
