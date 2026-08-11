# Status Overlay Migration

> **Current model:** shared product **detail** (what) in **AppLovin/Gist-PRDs**, per-platform **progress** (`[rules]` only) under `prd-status/<platform>/…`, and **bugs** as a separate dimension (not in the progress overlay).  
> Platforms today: **ios** + **android**. Specs stay in app repos (`Gist-iOS`, `Gist-Android`).  
> Scope refined 2026-08-05; namespaced multi-platform overlay landed afterward.

## Problem (why we migrated)

Rule / bug / UI-review **status used to be embedded in PRD XML** (`status="✅"` on `<rule>`, etc.).

That is wrong for a shared product-requirements repo:

- One task often needs work on **multiple platforms**.
- A single `status` on a rule cannot mean “done on iOS and not on Android”.
- Progress is an implementation concern; the PRD should describe **what**, not **who finished it**.
- The same flaw applies to bugs: a defect can be `Fixed` on iOS while still `Open` on Android.

## Target model — three dimensions

| Dimension | Question | Contents | Where (current) |
|---|---|---|---|
| **Detail** | What should the product do? | overview, requirements, rules (text + figma), implementations | `*.xml` in **Gist-PRDs** — no rule status |
| **Progress** | How far is this platform? | per-rule glyphs only (`[rules]`) | `prd-status/<platform>/<module>/<feature>.toml` |
| **Bugs** | What defect, and fixed where? | definition (shared-capable) + lifecycle status (**per-platform**) | separate from progress — see below |

```
Gist-PRDs/                         # shared product PRDs (was Gist-iOS-PRDs)
  <module>/<feature>.xml           # pure detail — no rule/bug/ui status
  prd-status/
    ios/<module>/<feature>.toml    # iOS [rules] only
    android/<module>/<feature>.toml
  index.xml
  .prd-tool.toml                   # dir only — no default platform
```

Join at read time (progress): rule text from XML + glyph from overlay (missing rule key → `❌`).

### Multi-platform progress (supported in prd-tool)

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

**Gist-PRDs** uses the namespaced layout and does **not** set a default `platform` — consumers pass `--platform` / `PRD_PLATFORM`, or set `platform` in the app repo’s `.prd-tool.toml`.

### Progress overlay format

Canonical **shared** progress shape:

```toml
[rules]
"R1.sheet_present" = "✅"
"L3.auto_submit" = "❌"
```

Glyphs: `✅` / `⚠️` / `❌`.

**Not in the shared Gist-PRDs progress overlay:** `[notes]`, `[[platform_rule]]` / `[[android_rule]]`, `[[bug]]`, `[[ui_review]]`.

Android may keep notes / platform_rule / bugs / ui_reviews in a **local residual** `Gist-Android/prd-status/` (joined by Android’s own scripts). The tool’s general overlay schema still allows `[notes]` / `[[platform_rule]]` for platform-local use; shared multi-platform overlays stay **`[rules]` only**.

### Bugs — separate dimension

A bug has two layers:

| Layer | Contents | Shared? |
|---|---|---|
| **Definition** | id, rule ref, current / expected / steps, filed date | can be shared (same product defect) |
| **Status** | `Open` → `Fix Pending` → `Fixed` | **must be per-platform** |

Implications:

- Do **not** store a single bug `status` in shared detail XML or in the shared progress overlay.
- Do **not** migrate XML bugs into shared `prd-status/` as one status field.
- Future shape can be shared definition + per-platform status maps, or platform-local bug stores that reference a shared rule id — TBD when bugs are needed cross-platform.

### UI review

Visual verification / findings are closer to defects than to rule progress. **Out of the shared progress overlay.** Leave in XML for legacy mode; Android residuals may keep `[[ui_review]]` locally.

## Scope (what landed)

| In scope | Out of scope / deferred |
|---|---|
| **`prd-tool`** — progress overlay read/write + namespaced platforms | Full multi-platform **bugs** store |
| **`Gist-PRDs`** — extract **rule** overlay, strip XML rule status, rename from `Gist-iOS-PRDs`, namespace `ios`/`android` | Touching `Gist-iOS` / `Gist-Android` app code |
| Shared overlays = **`[rules]` only** | Putting notes / platform_rule / bugs / ui_reviews in shared progress |
| Sibling-checkout consumption (`GIST_PRD_DIR` / `detail_dir`) | Submodules (none) |

### Consumption model (current reality)

App repos resolve detail as a **sibling checkout** (or env / toml) — not a git submodule:

1. `GIST_PRD_DIR`
2. `.prd-tool.toml` → `detail_dir`
3. Convention: `../Gist-PRDs` (some checkouts still named `Gist-iOS-PRDs`)

- **Gist-iOS** / **Gist-Android**: set `platform` in their own `.prd-tool.toml` (or pass `--platform`).
- **Gist-Android**: shared `[rules]` live upstream under `prd-status/android/`; local `prd-status/` is a residual for notes / platform_rule / bugs / ui_reviews (+ a few Android-only leftovers without a shared XML twin).

## Phase 1 — `prd-tool` (done)

Make the tool support status-free detail + **progress** overlay **before** stripping production XML.

### Behaviors

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
6. **Migrate command**: XML rule `status` → write `prd-status/*.toml` (`[rules]` only) + strip `status` from `<rule>`; do **not** extract bugs / ui_reviews.

### Acceptance (tool)

- Detail XML with **no** rule `status` + progress TOML → `prd validate` / `stats` / `view` work.
- Toggling a rule status updates **only** the TOML.
- Legacy fixture repo without `prd-status/` still works.
- Namespaced layout requires an explicit platform (CLI / env / consumer toml).

## Phase 2 — `Gist-PRDs` (done / in flight)

1. **Extract** XML **rule** statuses → progress TOML (`[rules]` only).
2. **Strip** `status=` from `<rule>` in XML (pure detail).
3. **Rename** repo **`Gist-iOS-PRDs` → `Gist-PRDs`**.
4. **Namespace** progress: `prd-status/ios/…` + import Android `[rules]` into `prd-status/android/…`.
5. **Docs**: shared product PRDs; no default platform in Gist-PRDs toml; sibling checkout; rules-only shared overlay.

### Acceptance (repo)

- XML has no rule `status`.
- `prd-status/<platform>/` round-trips platform **rule** counts.
- Shared `prd-status/` has no notes / platform_rule / bug / ui_review tables from this migration.
- `prd stats --platform ios` / `--platform android` / `--all-platforms` work against the shared repo.

## Repo rename

| Old | New |
|---|---|
| `Gist-iOS-PRDs` | **`Gist-PRDs`** |

Rationale: the repo is the **cross-platform product requirements** source, not an iOS-only companion. Local folder names may lag the remote rename.

## Non-goals / explicit skips

- Do **not** add `prd-status/` to `Gist-iOS` (app repo).
- Do **not** keep writing rule status into detail XML once overlay mode is active.
- Do **not** fold bugs, ui_reviews, notes, or platform_rule into the **shared** progress overlay.
- Do **not** implement the multi-platform bugs store here — only reserve the dimension.
- Do **not** imply a default platform inside Gist-PRDs — selection is CLI / env / consumer toml.

## Reference

- Shared repo README: `AppLovin/Gist-PRDs`
- Android residual: `Gist-Android/prd-status/README.md` (+ local `scripts/prd_status.py` may still merge residual tables)
- Skill overlay section: `skills/prd/SKILL.md` (“Overlay mode”)
- Tool coupling: `constants.RULE_REQUIRED_ATTRS`, `validate.py`, `stats.py`, `dashboard/edits.py`, `dashboard/repo.py`
