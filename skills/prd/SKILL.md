---
name: prd
description: Use when starting or referencing work on a feature module — loads PRD requirements, Figma nodes, and per-platform implementation spec context. Invoke with `/prd <module/feature>` or `/prd <module/feature>#R<n>`.
allowed-tools: Read, Write, Edit, Glob, Grep, mcp__figma__get_design_context, mcp__figma__get_screenshot
---

# PRD Loader

Load product requirements, Figma designs, and implementation context before starting work on a feature.

**Prerequisite:** Install the `prd` CLI via `uv tool install git+https://github.com/yjmeqt/prd-tool.git` before using this skill.

## Usage

```
/prd <module>/<feature>        # Load full PRD
/prd <module>/<feature>#R2     # Load specific requirement
```

If no argument is provided, infer the module from conversation context.

## Process

### Step 1: Resolve the PRD file

1. Run `prd root` to learn the PRD directory for this repo. Parse the tab-separated output: `repo_root\tprd_dir\tsource`. If `prd root` exits non-zero, fall back to `prd/` at cwd and surface a one-line warning to the user.
2. If an argument is given, map it to `<prd_dir>/<module>/<feature>.xml`.
3. If no argument, check conversation context for module references, then run `prd ls` and scan `prd/README.md` for matching entries.
4. If ambiguous, list available modules (from `prd ls` and `prd/README.md`) and ask the user to pick.

### Step 2: Read and validate the PRD

1. Read `prd/<module>/<feature>.xml`
2. Run `prd validate prd/<module>/<feature>.xml` — report any errors before proceeding
3. Parse the XML structure — see **PRD File Structure** below for the schema
4. Extract: `<implementation>` specs, `<requirement>` blocks with rules and statuses, `<ui_review>` findings, `<bug>` entries

### Step 3: Load Figma designs

For each `<figma_node>` found in the relevant rules (or all rules if loading the full PRD):

1. Read the `file` and `node` attributes from the `<figma_node>` element
2. Convert `node` from `-` to `:` separator (e.g. `2565-207191` → `2565:207191`)
3. Call `mcp__figma__get_design_context` with `fileKey` and `nodeId`; fall back to `mcp__figma__get_screenshot` on failure
4. If a node contains multiple screens side-by-side, use the **figma-extract-nodes** skill to extract individual screen node IDs

### Step 4: Read the implementation spec(s)

For each `<implementation>` element in the PRD:

1. Read its `platform` and `spec` attributes
2. Skip entries whose `spec` is `TBD`, missing, or otherwise unresolved
3. If the user scoped the request to a specific platform (e.g. `/prd <feature> --platform=iOS`, or inferred from conversation), only load that platform's spec; otherwise load all resolved specs
4. Read the file at the `spec` path
5. Extract the sub-tasks table and architecture notes
6. For any sub-task specs referenced, note their paths (don't read them yet — only read on demand)

### Step 5: Present context summary

Output a structured summary:

```
## PRD: <Feature Name>
**Status:** <status>

### Requirements
- R1: <name> — ✅ X/Y rules done
- R2: <name> — ❌ 0/Y rules done

### Open Bugs
- <bug_id>: <current summary> (rule: R<n>.<rule_id>)

### Figma Context
<key design details extracted from loaded figma_nodes>
```

Then ask: "Ready to proceed. What would you like to work on?"

## PRD File Structure

A PRD is a pure XML file. No markdown headings — all structure is expressed through XML tags.

```xml
<prd name="Feature Name">

<overview>
1-2 paragraph description of the feature.
</overview>

<implementation platform="iOS" spec="ios/docs/specs/<module>/<feature>.md" />
<implementation platform="Backend" spec="TBD" />

<requirement id="R1" name="Short Title">
  <description>Overview of this requirement.</description>
  <rule id="rule_name" status="✅">Testable behavior.</rule>
  <rule id="another_rule" status="❌" context="condition">Another behavior.
    <figma_node name="Screen" file="<fileKey>" node="<nodeId>" />
  </rule>
  <ui_review status="❌" date="YYYY-MM-DD">
    <finding rule="R1.rule_name">Description of visual discrepancy.</finding>
  </ui_review>
</requirement>

<bug id="bug_name" status="Open" date="YYYY-MM-DD" rule="R1.rule_name">
  <current>What is broken.</current>
  <expected>What should happen.</expected>
  <steps>1. Step one ...</steps>
</bug>

</prd>
```

**`<prd>` attributes:**
- `name` — feature name

Counters (rules done/total, open bugs, UI review progress) are **not stored**
on `<prd>` or in `prd/index.xml`. They are computed on demand from the rules,
bugs, and `<ui_review>` elements via:

```
prd stats prd/<module>/<feature>.xml
prd stats prd/index.xml   # roll up across all entries
```

`stats` is read-only — it never writes back to any XML.

**Element ordering inside `<prd>`:** `<overview>` → `<implementation>` → `<requirement>` → `<bug>`

**IDs are permanent:** Never rename or reuse a rule ID or bug ID. Bugs, specs, and conversation history reference them.

## Bug Writing Rules

Bugs in the PRD are standalone XML elements after the requirements.

### Bug Template

Use this template exactly:

```xml
<bug id="snake_case_name" status="Open|Fix Pending|Fixed" date="YYYY-MM-DD" rule="R<n>.rule_name">
  <current>
    What is actually happening — the broken behaviour the user observes.
  </current>
  <expected>
    What should happen instead — the correct behaviour per the PRD requirement.
  </expected>
  <steps>
    1. First step
    2. Second step
    ...
  </steps>
</bug>
```

**Field rules:**
- `id` — semantic snake_case name describing the bug (e.g. `mention_picker_scroll_leak`). **Permanent** — never rename or reuse.
- `status` — must be one of: `Open`, `Fix Pending`, `Fixed`
- `date` — date filed (YYYY-MM-DD)
- `rule` — the specific rule this bug violates (e.g. `R4.picker_insert`)
- `<current>` — required, describe the broken behaviour
- `<expected>` — required, describe the correct behaviour
- `<steps>` — required, numbered reproduction steps

**Example:**

```xml
<bug id="mention_picker_scroll_leak" status="Fixed" date="2026-04-08" rule="R4.picker_insert">
  <current>
    In sheet-style comment view (video/long text cards), when the mention picker panel is open:
    - Scrolling up/down on the mention picker list also scrolls the comment list sheet behind it
    - Both scroll views move simultaneously
  </current>
  <expected>
    When the mention picker is visible, it should capture all scroll/touch gestures within its area.
    The comment list sheet behind should remain stationary and not respond to any touch events while the picker is open.
  </expected>
  <steps>
    1. Open a video or long text card
    2. Tap the comment button to open the comment sheet
    3. Tap the input bar to open the keyboard
    4. Type @ to trigger the mention picker panel
    5. Scroll down on the mention picker user list
    6. Observe: the comment list behind the mention picker also scrolls down simultaneously
  </steps>
</bug>
```

### Bug Status Lifecycle

1. **Open** — bug is filed
2. **Fix Pending** — code fix is implemented; awaiting manual testing by the user
3. **Fixed** — user has manually tested and confirmed the fix works

**Never mark a bug as Fixed without user confirmation.** After implementing a fix, set the status to `Fix Pending` and ask the user to test. Only change to `Fixed` after the user explicitly approves.

## Requirement Writing Rules

Requirements in the PRD use a strict XML structure. Each requirement is wrapped in a `<requirement>` tag.

### Requirement Template

```xml
<requirement id="R<n>" name="Short Title">
  <description>
    Brief overview of what this requirement covers — one or two sentences.
  </description>

  <rule id="descriptive_name" status="✅">Single testable behavior or interaction.</rule>
  <rule id="another_name" status="❌" context="When X">What happens in this condition.
    <figma_node name="Screen showing this" file="<fileKey>" node="<nodeId>" />
  </rule>
  <rule id="third_name" status="✅">Rule without a Figma reference.</rule>
</requirement>
```

**Field rules:**
- `id` on `<requirement>` — sequential requirement number (R1, R2, ...)
- `name` — short title summarizing the requirement
- `<description>` — required, 1-2 sentence overview
- `<rule>` — each rule is a self-contained, testable statement with a unique `id`
- `<figma_node>` — optional, nested inside a `<rule>` to link it to a Figma design; a rule may have zero or more screens
  - `name` — human-readable label for the screen
  - `file` — the Figma file key (e.g. `FyPBukgq3fbyMNGRW8ho7i`), used as `fileKey` for `mcp__figma__get_design_context`
  - `node` — the Figma node ID with `-` separator (e.g. `2565-207191`), convert to `:` separator (e.g. `2565:207191`) when calling `mcp__figma__get_design_context` as `nodeId`

### Rule ID Format

Rule IDs are **snake_case names** scoped to their parent `<requirement>`:
- `send_button`, `draft_preserve`, `heart_icon`
- The name is a short, semantic mnemonic describing the rule's behavior
- The **qualified ID** is `R<n>.<rule_id>` (e.g. `R3.send_button`) — used in bug references and cross-references outside the requirement
- IDs are **permanent** — never rename or reuse an ID after it is created; bugs, specs, and conversation history reference them
- Each rule ID must be unique within its requirement (and ideally across the PRD)
- When inserting a new rule, pick a descriptive name — ordering in the file is canonical, not the ID

### Rule Attributes

- `id` — required, snake_case name unique within the requirement (e.g. `send_button`)
- `status` — required, one of: `✅` (implemented), `❌` (not implemented), `⚠️` (partial)
- `context` — optional, the condition or state under which this rule applies (e.g. `"keyboard shown"`, `"no comments exist"`, `"article cards only"`)

### Content Rules for `<rule>`

- Each `<rule>` must describe **one** testable behavior — what the user sees or does
- If a rule has sub-conditions, split them into separate rules with a shared `context`
- State the trigger/condition before the outcome: "Tapping X does Y"
- Never include implementation details (class names, hex codes, asset names, pixel values)
- A bug references a rule by its qualified ID: `rule="R<n>.<rule_id>"` (e.g. `rule="R4.picker_insert"`) — so rules must be granular enough that a single bug maps to a single rule
- Attach `<figma_node>` inside the rule that best demonstrates the behavior; if multiple rules share a screen, attach it to the most representative one

**Example:**

```xml
<requirement id="R7" name="Like">
  <description>
    Top-level comments and replies each have a reaction button with a count.
  </description>

  <rule id="heart_icon" status="✅">Each top-level comment has a like button (heart icon).
    <figma_node name="Comment list" file="FyPBukgq3fbyMNGRW8ho7i" node="2565-207191" />
  </rule>
  <rule id="upvote_icon" status="✅">Each reply has an upvote button (arrow-up icon) — visually distinct from the top-level like.</rule>
  <rule id="toggle" status="✅">Tapping either button toggles the state; the count updates immediately.</rule>
</requirement>
```

## UI Review Writing Rules

UI reviews track visual verification of implemented rules against Figma designs. Each `<ui_review>` lives inside its parent `<requirement>`, after all `<rule>` elements.

### UI Review Template

```xml
<ui_review status="✅|❌|⚠️" date="YYYY-MM-DD">
  <finding rule="R<n>.rule_id">Description of the visual discrepancy vs Figma.</finding>
</ui_review>
```

**Field rules:**
- `status` — required, one of: `✅` (all rules visually match Figma), `❌` (has unresolved findings), `⚠️` (partial — some findings resolved)
- `date` — required, date of last review (YYYY-MM-DD)
- `<finding>` — one per visual discrepancy; omit all findings when `status="✅"`
  - `rule` — required, the qualified rule ID this finding applies to (e.g. `R4.at_trigger`)

**Status lifecycle:**
1. **❌** — review found visual discrepancies
2. **⚠️** — some findings fixed, others remain
3. **✅** — all findings resolved; remove `<finding>` elements and keep the empty `<ui_review>` as proof of verification

**A `<ui_review>` is optional.** Only add it after performing a visual walkthrough (loading Figma designs and comparing against implemented code). Requirements without `<ui_review>` have not been visually verified.

**Content rules for `<finding>`:**
- Describe what differs visually: layout, spacing, font weight, color, missing/extra elements
- Reference the Figma state (e.g. "Figma shows single label; implementation has two")
- Do not include fix instructions or code references — those belong in the iOS spec or implementation plan

## PRD Content Rules

PRDs describe **what** the product does — not **how** it is built. Enforce these rules whenever writing or updating a PRD:

**Include:**
- User-facing behaviour, flows, and interactions
- Content and data to display (conceptual field names are OK, e.g. "username", "follower count")
- Entry points, navigation, and empty/error states
- Figma links for visual reference
- Cross-references to related PRDs

**Never include:**
- Implementation type names (Swift class/struct/protocol/method/property names)
- Package or module names (e.g. `SettingsKit`, `ProfileFeature`)
- Color hex codes or CSS-style values (e.g. `#FF6030`, `rgba(0,0,0,0.36)`)
- Icon asset names (e.g. `pen_on_doc`)
- Pixel-precise measurements or layout constants (e.g. `64×64pt`, `20pt from trailing`)
- Type annotations on data model fields (e.g. `(Int)`, `(String?)`)
- Git branch names
- Architecture or implementation decisions (those belong in the iOS spec)

## Implementation Spec Content Rules

Implementation specs (one per `<implementation>` entry — iOS, Backend, Web, etc.) describe **how** a feature is built on that platform. Enforce these rules whenever writing or updating a spec:

**Include:**
- Architecture decisions and key types
- Platform-appropriate layout / view / endpoint structure
- Data flow, state machines, and loading sequences
- Sub-tasks table with status

**Never include:**
- Git branch names
- References to temporary planning artifacts (e.g. `docs/superpowers/specs/`) — those should not be linked from permanent specs

## Before Implementation: Write Module Spec

Before any code is written on a given platform, ensure that platform's spec exists at the path declared by its `<implementation spec="…">` attribute and contains a complete plan:

1. Resolve the spec path from the matching `<implementation platform="…" spec="…"/>` element
2. If `spec` is `TBD`, pick a path appropriate for the platform (e.g. `<platform-dir>/docs/specs/<module>/<feature>.md`), update the `<implementation>` element to point at it, and create the file
3. If the spec is still a placeholder (empty sub-tasks, no architecture notes), **write the module spec first**:
   - Analyze the PRD requirements and Figma designs
   - Review existing code in the relevant feature directory
   - Define the sub-tasks breakdown with clear scope for each
   - Document architecture decisions and dependencies
   - Save to the path declared in `<implementation spec="…">`
4. Present the spec to the user for review before proceeding to implementation
5. Only after spec approval, proceed to implementation (brainstorming → writing-plans → code)

## After Implementation: Update PRD Status

When implementation of a rule is complete:

1. Update the `status` attribute on the `<rule>` to `✅`
2. Run `prd format prd/<module>/<feature>.xml` to normalize formatting and encode special characters
3. Update the sub-tasks table in the spec referenced by the platform's `<implementation spec="…">` with completion status

## Auto-trigger

This skill should be proactively invoked when:
- The user mentions working on a feature that has a PRD in `prd/`
- The user references a requirement number (e.g., "R2 of likes-saves")
- The user asks to implement, fix, or modify something in a module that has a PRD

Check `prd/README.md` to see if the mentioned module exists before triggering.

## UI Inspection

When the user asks to inspect, review, or do a visual walkthrough of implemented UI against a PRD section:

1. Identify the relevant PRD requirement(s) and their Figma node(s)
2. Locate the implemented source file(s) for those requirement(s) — resolve the platform's root directory from the `<implementation spec="…">` path (e.g. for `spec="ios/docs/specs/…"`, look under `ios/`)
3. Run a UI review over the Figma node(s) and code file path(s) to check design tokens and layout
4. Write the review findings back into the PRD:
   - Insert a `<ui_review>` element inside the reviewed `<requirement>`, after all `<rule>` children (see schema ordering in **UI Review Writing Rules** above)
   - Set `status` to `❌` if any findings exist, `⚠️` for partial resolution, `✅` when all findings are resolved; set `date` to today (YYYY-MM-DD)
   - Add one `<finding rule="R<n>.rule_id">…</finding>` per discrepancy; omit all findings when `status="✅"`
   - If a `<ui_review>` already exists for this requirement, update its `status`, `date`, and findings in place instead of adding a second one
5. Run `prd format prd/<module>/<feature>.xml` to normalize formatting
6. Run `prd validate prd/<module>/<feature>.xml` to confirm the PRD still parses
