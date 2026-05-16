# Dashboard Viewer — Implementation Spec

PRD: [`prd/dashboard/viewer.xml`](../../../prd/dashboard/viewer.xml)

## Stack

- **Backend:** FastAPI on `uvicorn`, packaged inside `prd_tool`. Runtime deps beyond stdlib: `fastapi`, `uvicorn`, `watchfiles`.
- **Frontend:** React 18 + TypeScript, built with Vite. Plain CSS; React Query for server data.
- **Transport:** REST for reads/writes, Server-Sent Events for file-watch invalidations.

The server never contacts Figma. The dashboard surfaces `<figma_node>` references as
plain links that the user's browser opens directly in Figma — there is no API
token, no image proxy, and no on-disk image cache.

## Layout

```
src/prd_tool/
  cli.py                     # `prd dashboard` subcommand
  dashboard/
    __init__.py
    server.py                # FastAPI app factory
    sse.py                   # /events stream + watcher
    repo.py                  # in-memory model of all PRDs (parses XML on demand)
    edits.py                 # status mutations -> XML, then format + validate
    static/                  # bundled frontend build output (gitignored, populated by CI)
frontend/                    # Vite project (separate, not installed as a Python dep)
  package.json
  vite.config.ts
  src/
    App.tsx, main.tsx
    api.ts, useSse.ts, types.ts
    components/Sidebar.tsx, RuleCard.tsx, BugCard.tsx, UiReviewBlock.tsx, FigmaThumb.tsx
    pages/Home.tsx, Feature.tsx
```

The Python package ships with `dashboard/static/` populated. Hatch's
`tool.hatch.build.targets.wheel.force-include` brings that gitignored directory
into the wheel.

## CLI surface

`prd dashboard [--port N] [--host 127.0.0.1] [--dev] [--no-open]`

Behavior:
- **TTY guard (R1.tty_required):** if `sys.stdin.isatty()` is False, print an
  error and exit non-zero before binding any port. Catches backgrounded
  invocations, `nohup`, CI runs, and agent harnesses — environments where the
  user has no way to send Ctrl+C and the server would otherwise become an
  orphan eating port 8765.
- Resolves `Root` via existing `prd_tool.root.find_root`. If `None`, exit
  non-zero with the same error shape as `prd root`.
- Starts uvicorn programmatically with `dashboard.server.create_app(prd_dir)`.
- Default port 8765; `--port` overrides.
- After bind, prints `Dashboard at http://127.0.0.1:<port>` and opens the
  browser unless `--no-open`.
- `--dev` makes the app proxy `/` to `http://127.0.0.1:5173` instead of serving
  `dashboard/static/`.

## REST endpoints

All JSON; mounted under `/api`.

| Method | Path | Returns |
|---|---|---|
| GET | `/api/index` | `{ modules: [{ name, features: [{ ref, name, stats }] }] }`. |
| GET | `/api/prd/{module}/{feature}` | parsed PRD JSON (requirements with rules + figma_nodes, bugs, ui_reviews, overview, implementations). |
| POST | `/api/prd/{module}/{feature}/rule/{rid}/status` | Body `{ status: "✅"\|"⚠️"\|"❌" }`. Atomically rewrites the XML, runs `format` then `validate`. |
| POST | `/api/prd/{module}/{feature}/bug/{bid}/status` | Body `{ status: "Open"\|"Fix Pending"\|"Fixed" }`. |
| POST | `/api/prd/{module}/{feature}/finding/{rule_qid}/resolve` | Removes the matching `<finding>`; if the requirement's `<ui_review>` has no findings left, sets its status to `✅`. |
| GET | `/api/events` | SSE stream of `{ type: "prd_changed" \| "index_changed" \| "invalid", path }` events. |
| GET | `/api/health` | `{ ok, prd_dir }`. |

### Edits pipeline

`edits.apply_change(path, mutation)`:
1. Parse XML with `lxml`-style ElementTree, preserving structure.
2. Apply mutation in-memory.
3. Write to a staging tempfile in the same directory, then run the existing
   `prd_tool.format.format_prd` and `prd_tool.validate.validate` against it.
4. On validation failure, raise `EditError(code="validation_failed", …)` →
   422; do not touch the target file.
5. On success, atomic-replace the target via `os.replace`.

### Watcher

`watchfiles.awatch(prd_dir)` running in an asyncio task. Each filesystem event:
- `prd/index.xml` changes → emit `index_changed`.
- `prd/<module>/<feature>.xml` changes → re-parse; if parse fails emit
  `invalid`; on success emit `prd_changed`.
- Debounce 100 ms to coalesce editor "save flurries".

## Figma references (link-only)

`FigmaThumb` (kept the name for the rule ID `figma_link`) renders a `<a>`
showing the node `name`, pointing at
`https://www.figma.com/file/{file}?node-id={node-with-colons}`. Node ids carry
a `-` separator in PRDs (e.g. `2565-207191`); convert to `:` for the URL.

No `/api/figma/*` endpoint exists. No Figma token is read, stored, or
transmitted. The server never makes outbound calls to Figma.

## Frontend

Pages:
- `/` — sidebar + rollup table. Default sort: `(open_bugs desc, rules_remaining desc, name asc)`.
- `/p/<module>/<feature>` — sidebar + detail view.

Live updates: single `EventSource('/api/events')` mounted at App root. On
`index_changed` invalidate `['index']`; on `prd_changed` invalidate
`['feature']`. React Query handles refetch.

Edits use optimistic updates with rollback on 422.

## Packaging

- `frontend/` is **not** a Python source dir; it is built separately. `npm run
  build` outputs to `src/prd_tool/dashboard/static/`.
- `pyproject.toml` includes `src/prd_tool/dashboard/static/**` in the wheel via
  Hatch's `force-include`. The directory is gitignored to avoid committing
  build output.
- CI: a new job runs `npm ci && npm run build` before `uv build`. Local users
  who clone the repo and want `prd dashboard` without Node either install from
  the published wheel or use `--dev`.
- `--dev` mode requires Node + a running Vite dev server on `:5173`; the
  FastAPI app proxies `/` and `/assets/*` to it.

## Sub-tasks

| # | Scope | Status | Covers rules |
|---|---|---|---|
| T1 | `prd dashboard` CLI subcommand, root resolution, uvicorn boot, port + open behavior | ✅ | R1.launch_command, R1.port_override, R1.no_root_error, R1.shutdown |
| T1b | TTY guard before binding port | ❌ | R1.tty_required |
| T2 | `repo.py` parser + `/api/index` + `/api/prd/{m}/{f}` endpoints | ✅ | R3.rollup_counts_match_stats, R4.* |
| T3 | Frontend shell: routing, sidebar tree, active highlight, empty state | ✅ | R2.feature_entry, R2.active_highlight, R2.empty_state |
| T4 | Status rollup page with sort + click-through | ✅ | R3.* |
| T5 | Feature detail page: overview, implementations, requirements, ui-review, bugs sections | ✅ | R4.* |
| T6 | Figma link rendering (no remote calls) | ❌ | R5.figma_link, R5.figma_node_id, R5.figma_no_remote_calls |
| T8 | Edits pipeline + rule / bug / finding endpoints with validate+format | ✅ | R6.* |
| T9 | Frontend optimistic-edit interactions for rule status, bug status, finding resolve | ✅ | R6.rule_status_toggle, R6.bug_status_cycle, R6.finding_resolve |
| T10 | File watcher + `/api/events` SSE + invalid-XML banner | ✅ | R7.* |
| T11 | Frontend EventSource hook + cache invalidation | ✅ | R7.watch_prd_dir, R7.index_refresh |
| T12 | Packaging: wheel includes `static/`, `--dev` proxy, CI builds frontend before publish | ⚠️ | R8.bundled_assets ✅, R8.dev_mode_flag ❌, R8.ci_builds_frontend ❌ |

## Out of scope

- Authoring new requirements, rules, bugs, or features from the dashboard.
- Multi-repo support — one server instance serves one PRD root.
- Remote hosting / multi-user / auth — strictly localhost.
- Bug-edit fields (current/expected/steps text); only status transitions in v1.
- Fetching, caching, or rendering Figma images. Reviewers click out to Figma.
