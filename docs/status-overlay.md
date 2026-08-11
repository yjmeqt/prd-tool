# Status Overlay & Multi-Platform Progress

> **Model:** shared product **detail** (what) in PRD XML, per-platform **progress** (`[rules]` only) under `prd-status/<platform>/…`, and **bugs** as a separate dimension (not in the progress overlay).  
> Specs stay in per-platform app / implementation repos.

## Why overlay mode exists

Rule / bug / UI-review **status used to be embedded in PRD XML** (`status="✅"` on `<rule>`, etc.).

That breaks down when one requirements tree serves multiple platforms:

- One task often needs work on **multiple platforms**.
- A single `status` on a rule cannot mean “done on iOS and not on Android”.
- Progress is an implementation concern; the PRD should describe **what**, not **who finished it**.
- The same flaw applies to bugs: a defect can be `Fixed` on one platform while still `Open` on another.

## Three dimensions

| Dimension | Question | Contents | Where |
|---|---|---|---|
| **Detail** | What should the product do? | overview, requirements, rules (text + figma), implementations | `*.xml` under the PRD tree — no rule status in overlay mode |
| **Progress** | How far is this platform? | per-rule glyphs only (`[rules]`) | `prd-status/<platform>/<module>/<feature>.toml` |
| **Bugs** | What defect, and fixed where? | definition (shared-capable) + lifecycle status (**per-platform**) | separate from progress — see below |

```
<prd-repo>/
  <module>/<feature>.xml           # pure detail — no rule/bug/ui status
  prd-status/
    ios/<module>/<feature>.toml    # platform [rules] only
    android/<module>/<feature>.toml
  index.xml
  .prd-tool.toml                   # dir / status_dir; optional default platform
```

Join at read time (progress): rule text from XML + glyph from overlay (missing rule key → `❌`).

## Multi-platform progress

```
prd-status/ios/<module>/<feature>.toml
prd-status/android/<module>/<feature>.toml
```

**Layout detection** under `status_dir` (or `prd-status/`):

- **Namespaced** if any immediate child is a known platform name (`ios` / `android`), or is a directory that itself contains a `<module>/<feature>.toml` layout.
- **Flat (legacy)** if only module dirs with `*.toml` exist. No platform segment.

**Platform selection precedence** (namespaced only; flat ignores platform for paths):

1. CLI `--platform`
2. Env `PRD_PLATFORM`
3. `.prd-tool.toml` → `[prd].platform`
4. If still unset → actionable error (do **not** silently pick a platform)

`prd stats --all-platforms` (and `prd ls -u --all-platforms`) iterate every platform dir. Writes (`set_rule_status`) always target the **selected** platform’s TOML only.

Shared multi-platform PRD repos typically use the namespaced layout and **omit** a default `platform` — consumers pass `--platform` / `PRD_PLATFORM`, or set `platform` in the consuming app repo’s `.prd-tool.toml`.

## Progress overlay format

Canonical **shared** progress shape:

```toml
[rules]
"R1.sheet_present" = "✅"
"L3.auto_submit" = "❌"
```

Glyphs: `✅` / `⚠️` / `❌`.

**Not in a shared multi-platform progress overlay:** `[notes]`, `[[platform_rule]]` / `[[android_rule]]`, `[[bug]]`, `[[ui_review]]`.

The tool’s overlay schema still allows `[notes]` / `[[platform_rule]]` for **platform-local** overlays when a single platform owns extra tables. Shared multi-platform overlays stay **`[rules]` only**.

## Bugs — separate dimension

A bug has two layers:

| Layer | Contents | Shared? |
|---|---|---|
| **Definition** | id, rule ref, current / expected / steps, filed date | can be shared (same product defect) |
| **Status** | `Open` → `Fix Pending` → `Fixed` | **must be per-platform** |

Implications:

- Do **not** store a single bug `status` in shared detail XML or in the shared progress overlay.
- Do **not** migrate XML bugs into shared `prd-status/` as one status field.
- Future shape can be shared definition + per-platform status maps, or platform-local bug stores that reference a shared rule id — TBD when bugs are needed cross-platform.

## UI review

Visual verification / findings are closer to defects than to rule progress. **Out of the shared progress overlay.** Leave in XML for legacy mode; platform-local overlays may keep `[[ui_review]]` if a consumer needs them.

## Tool behavior (prd-tool)

### Overlay vs legacy

1. **Detect overlay mode** when `prd-status/` exists (or `status_dir` in `.prd-tool.toml`).
2. **Validate / format**
   - Detail: `status` on `<rule>` becomes **optional** (absent OK).
   - Prefer no status in detail; if present in legacy mode, still validate glyphs.
3. **Join layer** — single load path used by `stats`, `ls --unfinished`, dashboard, search:
   - text / structure from XML
   - **rule** status (+ notes / platform_rule when present) from progress overlay
   - bugs / ui_review: **unchanged path for now** (legacy XML if present; not joined from progress TOML)
4. **Writes**
   - `set_rule_status` → **progress TOML only** in overlay mode
   - `set_bug_status` / `resolve_finding` → **not** wired to progress TOML (keep legacy XML behavior, or no-op / error if detail has no bugs)
5. **Legacy mode** — no `prd-status/`: keep reading/writing XML rule `status` (e.g. this tool’s own `prd/` fixtures).
6. **Migrate command**: `prd migrate-status` — XML rule `status` → write `prd-status/*.toml` (`[rules]` only) + strip `status` from `<rule>`; do **not** extract bugs / ui_reviews. Namespaced layout requires `--platform`.

### Acceptance

- Detail XML with **no** rule `status` + progress TOML → `prd validate` / `stats` / `view` work.
- Toggling a rule status updates **only** the TOML.
- Legacy fixture repo without `prd-status/` still works.
- Namespaced layout requires an explicit platform (CLI / env / consumer toml).

## Non-goals

- Do **not** keep writing rule status into detail XML once overlay mode is active.
- Do **not** fold bugs, ui_reviews, notes, or platform_rule into the **shared** progress overlay.
- Do **not** implement the multi-platform bugs store here — only reserve the dimension.
- Do **not** silently pick a platform when the layout is namespaced — selection is CLI / env / consumer toml.

## Reference

- Skill overlay section: `skills/prd/SKILL.md` (“Overlay mode”)
- Tool coupling: `constants.RULE_REQUIRED_ATTRS`, `validate.py`, `stats.py`, `overlay.py`, `migrate_status.py`, `dashboard/edits.py`, `dashboard/repo.py`
