# Status Overlay Migration

> Decision summary: separate PRD **detail** (what) from per-platform **progress** (how far).  
> Bugs are a **third dimension** (definition vs per-platform lifecycle) — not part of the progress overlay.  
> Scope refined in discussion 2026-08-05.

## Problem

Today, rule / bug / UI-review **status is embedded in PRD XML** (`status="✅"` on `<rule>`, etc.).

That is wrong for a shared product-requirements repo:

- One task often needs work on **multiple platforms**.
- A single `status` on a rule cannot mean “done on iOS and not on Android”.
- Progress is an implementation concern; the PRD should describe **what**, not **who finished it**.
- The same flaw applies to bugs: a defect can be `Fixed` on iOS while still `Open` on Android (different release trains). One XML `status` cannot express that.

## Target model — three dimensions

| Dimension | Question | Contents | Where (target) |
|---|---|---|---|
| **Detail** | What should the product do? | overview, requirements, rules (text + figma), implementations | `*.xml` — no status |
| **Progress** | How far is this platform? | per-rule glyphs, notes, platform-only rules | `prd-status/` overlay TOML |
| **Bugs** | What defect, and fixed where? | definition (shared) + lifecycle status (**per-platform**) | separate from progress — see below |

```
<prd-repo>/
  <module>/<feature>.xml              # pure detail — no rule/bug/ui status
  prd-status/<module>/<feature>.toml  # progress only (Phase 1: flat / historically iOS)
  index.xml
  .prd-tool.toml
```

Join at read time (progress): rule text from XML + glyph from overlay (missing rule key → `❌`).

Later, multi-platform progress in the same repo:

```
prd-status/ios/<module>/<feature>.toml
prd-status/android/<module>/<feature>.toml
```

**Phase 1 of the repo migration:** flat `prd-status/<module>/<feature>.toml` holding the **rule** statuses currently in XML (historically iOS progress). Split by platform only when a second platform’s overlay also lives in this repo.

### Progress overlay format (align with Gist-Android `[rules]`)

Canonical **progress** shape (subset of what Android stores today):

```toml
[rules]
"R1.sheet_present" = "✅"
"L3.auto_submit" = "❌"

[notes]
"R5.fab_opens_feedback" = "Opens shared FeedbackScreen via …"

[[platform_rule]]        # local-only; Android historically used [[android_rule]]
id = "R99.local_only"
status = "✅"
description = "…"
```

Glyphs stay the same: `✅` / `⚠️` / `❌`.

**Not in the progress overlay:** `[[bug]]`, `[[ui_review]]`. Android may keep those tables in its local `prd-status/` as a platform extension; the shared schema and `prd-tool` Phase 1 treat progress as rule glyphs (+ notes / platform_rule) only.

### Bugs — separate dimension

A bug has two layers:

| Layer | Contents | Shared? |
|---|---|---|
| **Definition** | id, rule ref, current / expected / steps, filed date | can be shared (same product defect) |
| **Status** | `Open` → `Fix Pending` → `Fixed` | **must be per-platform** |

Example: iOS `Fixed`, Android still `Open` (or different Fix Pending / release versions).

Implications:

- Do **not** store a single bug `status` in shared detail XML or in the shared progress overlay.
- Do **not** migrate today’s XML bugs (currently ~0) into shared `prd-status/` as one status field.
- Future shape (out of Phase 1/2) can be e.g. shared definition + per-platform status maps, or platform-local bug stores that reference a shared rule id — TBD when bugs are actually needed cross-platform.

Lifecycle glyphs unchanged when status exists: `Open` → `Fix Pending` → `Fixed`.

### UI review

Visual verification / findings are closer to defects than to rule progress. **Out of this migration’s progress overlay.** Leave in XML for legacy mode; do not extract into shared `prd-status/` in Phase 2. Revisit with the bugs dimension later if needed.

## Scope

| In scope | Out of scope |
|---|---|
| **`prd-tool`** — first-class **progress** overlay support | **`Gist-iOS`** — do not touch |
| **`Gist-iOS-PRDs`** — extract **rule** overlay, strip XML rule status, rename | Submodules (none anymore) |
| Align with Gist-Android **`[rules]` / `[notes]` / platform rules** read path | Migrating bugs / ui_reviews into shared overlay |
| | Designing the full multi-platform bugs store |
| | Automatic reindex / unrelated dashboard work |

### Consumption model (current reality)

App repos no longer vendor PRDs via git submodule. They resolve detail as a **sibling checkout** (or env / toml):

1. `GIST_PRD_DIR`
2. `.prd-tool.toml` → `detail_dir`
3. Convention: `../Gist-iOS-PRDs` (→ new name after rename)

Android already uses this + local `prd-status/`. After migration, the shared PRD repo itself also holds a `prd-status/` (extracted **rule** statuses from today’s XML).

## Phase 1 — `prd-tool`

Make the tool support status-free detail + **progress** overlay **before** stripping any production XML.

### Behaviors

1. **Detect overlay mode** when `prd-status/` exists (or `status_dir` in `.prd-tool.toml`).
2. **Validate / format**
   - Detail: `status` on `<rule>` becomes **optional** (absent OK).
   - Prefer no status in detail; if present in legacy mode, still validate glyphs.
3. **Join layer** — single load path used by `stats`, `ls --unfinished`, dashboard, search:
   - text / structure from XML
   - **rule** status (+ notes / platform_rule) from progress overlay
   - bugs / ui_review: **unchanged path for now** (legacy XML if present; not joined from progress TOML)
4. **Writes**
   - `set_rule_status` → **progress TOML only** in overlay mode
   - `set_bug_status` / `resolve_finding` → **not** wired to progress TOML in Phase 1 (keep legacy XML behavior, or no-op / error if detail has no bugs — do not invent a shared bug overlay)
5. **Legacy mode** — no `prd-status/`: keep reading/writing XML rule `status` (e.g. this tool’s own `prd/` fixtures during transition).
6. **Migrate command** (or scripted equivalent):
   - XML rule `status` → write `prd-status/*.toml` (`[rules]` only) + strip `status` from `<rule>`
   - Do **not** extract bugs / ui_reviews into that TOML
   - Idempotent / dry-run friendly

### Suggested PR split

| PR | Deliverable |
|---|---|
| A | Progress overlay read + join; validate allows missing rule status; `stats` / `ls -u` use join |
| B | Progress overlay writes (`set_rule_status`); migrate command (rules only); dashboard rule edits target overlay |
| C | Docs / skill updates; dual-mode tests |

### Acceptance (tool)

- Detail XML with **no** rule `status` + progress TOML → `prd validate` / `stats` / `view` work.
- Toggling a rule status updates **only** the TOML.
- Legacy fixture repo without `prd-status/` still works.
- Progress TOML without `[[bug]]` / `[[ui_review]]` is valid and complete for Phase 1.

## Phase 2 — `Gist-iOS-PRDs` (then rename)

**Current snapshot (approx., excluding `.worktrees`):**

- ~45 feature XML files  
- ~1588 rules: ~844 ✅ / ~24 ⚠️ / ~720 ❌  
- 0 bugs / 0 ui_reviews in XML  

### Steps (order is hard)

1. **Extract** current XML **rule** statuses → `prd-status/<module>/<feature>.toml` **inside this repo** (`[rules]` only).
2. **Verify** join totals match pre-migration rule counts.
3. **Strip** all `status=` from `<rule>` in XML (pure detail). Leave any future bugs/ui_reviews problem for their own dimension — none to strip today.
4. **Update README**: shared product PRDs; **progress** in `prd-status/`; bugs are not this overlay; no submodule story.
5. **Rename repo** (recommended: **`Gist-PRDs`**) — drop the iOS-only implication.
6. Point consumers’ default paths / docs / `GIST_PRD_DIR` examples at the new name (`Gist-Android` skill paths, etc.). **Do not** change `Gist-iOS`.

### Acceptance (repo)

- XML has no rule `status`.
- `prd-status/` round-trips previous **rule** counts.
- Android overlay check against the new detail still makes sense (new upstream rules → untracked ❌).
- Shared `prd-status/` has no bug/ui_review tables from this migration.

## Repo rename

| Old | New (preferred) |
|---|---|
| `Gist-iOS-PRDs` | **`Gist-PRDs`** |

Rationale: after status extraction, the repo is the **cross-platform product requirements** source, not an iOS-only tree.

Rename can land in the same wave as strip, or immediately after. No submodule pointer bumps (nothing uses submodules).

## Non-goals / explicit skips

- Do **not** add `prd-status/` to `Gist-iOS`.
- Do **not** require Android to move its overlay into the shared repo in this migration (Android keeps its own `prd-status/`; shared repo overlay holds the **rule** statuses that today live in the XML).
- Do **not** keep writing rule status into detail XML once overlay mode is active.
- Do **not** fold bugs or ui_reviews into the shared progress overlay.
- Do **not** implement the multi-platform bugs store in Phase 1/2 — only reserve the dimension (definition shared-capable, status per-platform).

## Reference

- Android overlay README + tool: `Gist-Android/prd-status/README.md`, `scripts/prd_status.py`, `scripts/prd_migrate.py` (tooling may still read `[[bug]]` locally; shared migration aligns on `[rules]` only)
- Skill overlay section: `skills/prd/SKILL.md` (“Overlay mode” — to be added in PR C)
- Today’s coupling in tool: `constants.RULE_REQUIRED_ATTRS`, `validate.py`, `stats.py`, `dashboard/edits.py`, `dashboard/repo.py`
