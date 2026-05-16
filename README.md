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

## Remove the skill

```bash
npx skills remove yjmeqt/prd-tool
```

## Use the CLI directly

```bash
prd validate prd/<module>/<feature>.xml
prd format   prd/<module>/<feature>.xml
prd stats    prd/<module>/<feature>.xml
prd stats    prd/index.xml   # roll up across all entries
```

`stats` is read-only and never writes back.

## PRD file shape

See [`skills/prd/SKILL.md`](skills/prd/SKILL.md) for the full XML schema, requirement/rule/bug/ui-review writing rules, and the load workflow.
