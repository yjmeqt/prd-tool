# prd-tool

The `prd` skill plus its companion `prd-tool.py` validator/formatter for product requirement documents authored as XML.

PRDs are stored per-project as `prd/<module>/<feature>.xml` and describe **what** a feature does (requirements, rules, bugs, UI-review findings, Figma references) — separate from per-platform implementation specs that describe **how** it is built. The skill loads a PRD, walks each `<implementation platform="…" spec="…"/>` entry to read the right spec, fetches referenced Figma nodes, and presents a structured context summary before coding starts.

## Layout

- [`skills/prd/`](skills/prd/) — the skill consumed by Claude Code / Cursor / Codex
- [`skills/prd/scripts/prd-tool.py`](skills/prd/scripts/prd-tool.py) — XML validator, formatter, and stats roll-up (no external dependencies; uses the stdlib)

## Install the skill

From any worktree:

```bash
npx skills add yjmeqt/prd-tool
```

This populates `.claude/skills/prd/` (and `.agents/skills/prd/`) via symlinks into the local skills cache. Run `npx skills update` after pushing skill edits.

## Use the tool directly

`prd-tool.py` is a self-contained Python 3 script — no install step needed:

```bash
python3 .claude/skills/prd/scripts/prd-tool.py validate prd/<module>/<feature>.xml
python3 .claude/skills/prd/scripts/prd-tool.py format   prd/<module>/<feature>.xml
python3 .claude/skills/prd/scripts/prd-tool.py stats    prd/<module>/<feature>.xml
python3 .claude/skills/prd/scripts/prd-tool.py stats    prd/index.xml   # roll up across all entries
```

`stats` is read-only and never writes back.

## PRD file shape

See [`skills/prd/SKILL.md`](skills/prd/SKILL.md) for the full XML schema, requirement/rule/bug/ui-review writing rules, and the load workflow.
