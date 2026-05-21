# prd-tool

The `prd` skill plus its companion `prd` CLI (validate, format, stats) for product requirement documents authored as XML.

PRDs are stored per-project as `prd/<module>/<feature>.xml` and describe **what** a feature does (requirements, rules, bugs, UI-review findings, Figma references) — separate from per-platform implementation specs that describe **how** it is built. The skill loads a PRD, walks each `<implementation platform="…" spec="…"/>` entry to read the right spec, fetches referenced Figma nodes, and presents a structured context summary before coding starts.

## Layout

- [`skills/prd/`](skills/prd/) — the skill consumed by Claude Code / Cursor / Codex
- [`src/prd_tool/`](src/prd_tool/) — the `prd` CLI (validate, format, stats)

## Install

1. Install the CLI tool:

```bash
uv tool install git+https://github.com/yjmeqt/prd-tool.git
```

2. Install the skill:

```bash
npx skills add yjmeqt/prd-tool
```

This populates `.claude/skills/prd/` (and `.agents/skills/prd/`) via symlinks into the local skills cache.

## Update the skill

After pushing skill edits to the repo:

```bash
npx skills update
```

## Upgrade the CLI

```bash
uv tool upgrade prd-tool
```

## Remove the skill

```bash
npx skills remove yjmeqt/prd-tool
```

## Uninstall the CLI

```bash
uv tool uninstall prd-tool
```

## Use the CLI directly

```bash
prd validate prd/<module>/<feature>.xml
prd format   prd/<module>/<feature>.xml
prd stats    prd/<module>/<feature>.xml
prd stats    prd/index.xml   # roll up across all entries
```

`stats` is read-only and never writes back.

## Viewing PRDs

`prd view` opens a native macOS window backed by your local PRD files. No HTTP
server, no localhost, no browser.

```bash
prd view                   # open the index
prd view content/rich      # open one PRD in a window
prd view content/rich a/b  # open two windows at once
```

Cmd-click any feature in the sidebar or the rollup to open it in a new native
window. Edits made in any window are reflected across the others and persisted
to disk.

If you'd rather use a browser (e.g. for remote viewing or screen-sharing):

```bash
prd view --server          # FastAPI on http://127.0.0.1:8765
```

`prd dashboard` is a deprecated alias for `prd view --server` and will be
removed in a future release.

## PRD file shape

See [`skills/prd/SKILL.md`](skills/prd/SKILL.md) for the full XML schema, requirement/rule/bug/ui-review writing rules, and the load workflow.

## Contributor setup

Enable the pre-push hook so local checks match CI:

```bash
git config core.hooksPath .githooks
```

The hook runs `ruff check`, `ruff format --check`, `mypy`, and `pytest` — the same steps `.github/workflows/ci.yml` runs.

## Repo Discovery

`prd` walks up from your current directory to find the PRD root, like
`git`. The first marker wins:

1. `.prd-tool.toml` at an ancestor directory (preferred). Minimal schema:

   ```toml
   [prd]
   dir = "prd"   # optional, relative to the toml's directory; default "prd"
   ```

2. An ancestor containing `prd/index.xml` (zero-config convention).

Once a root is found, all subcommands accept short refs in place of
paths:

```
prd validate comments/likes-saves     # resolves to <prd_dir>/comments/likes-saves.xml
prd stats                             # defaults to <prd_dir>/index.xml
prd ls                                # list all refs
prd ls comments                       # list refs under one module
prd root                              # debug: print the resolved root
```

Existing absolute or relative paths still work unchanged.
