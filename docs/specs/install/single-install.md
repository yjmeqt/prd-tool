# Single-Step CLI Install — Implementation Spec

PRD: [`prd/install/single-install.xml`](../../../prd/install/single-install.xml)

## Decision

Fold the `dashboard` optional-extra back into the base package. Every dependency
the CLI can reach at runtime — including the dashboard server stack — ships
with the default install.

Rationale:
- The only subcommand gated by the extra is `prd dashboard`, which is
  advertised in `prd --help` alongside `validate`, `format`, `stats`, `root`,
  `ls`. A user who sees it in help expects it to run.
- The dashboard deps (`fastapi`, `uvicorn`, `watchfiles` + transitive
  `starlette`, `anyio`, `h11`, `click`, `pydantic`) add roughly 15 MB to a
  fresh install. Acceptable for a developer tool installed once per machine.
- The auto-install-on-first-run alternative requires shelling out to `uv` or
  `pip` from inside `prd`, only helps `uv tool` users, and introduces new
  failure modes around tool location, PATH, and write permissions.

## Changes

### `pyproject.toml`

Move the three dashboard deps from `[project.optional-dependencies].dashboard`
into `[project].dependencies`, then delete the `[project.optional-dependencies]`
table:

```toml
[project]
# ...
dependencies = [
  "fastapi>=0.115",
  "uvicorn>=0.30",
  "watchfiles>=0.22",
]
```

`[dependency-groups].dev` already lists the same packages explicitly, so dev
installs are unaffected.

### `src/prd_tool/cli.py` and `src/prd_tool/dashboard/__init__.py`

Remove the runtime "dashboard dependencies are not installed" guard — with the
deps now mandatory, an `ImportError` from `fastapi`/`uvicorn`/`watchfiles` is a
broken install, not a user-facing condition. Let the import fail naturally.

### `README.md`

Collapse the install section back to one command:

```bash
uv tool install git+https://github.com/yjmeqt/prd-tool.git
```

Delete the "if you already installed without the extra…" recovery block.

### `skills/prd/SKILL.md`

Prerequisite reverts to one line, no extras, no recovery command.

### `~/.claude/skills/prd/SKILL.md`

Same edit as the in-repo skill copy (the user's local cache that was updated
earlier in this session).

## Sub-tasks

| # | Scope | Status | Covers rules |
|---|---|---|---|
| T1 | `pyproject.toml`: promote dashboard deps to required, remove `[project.optional-dependencies]` | ✅ | R1.single_command, R1.no_extras_flag, R1.dashboard_works |
| T2 | Remove "dashboard dependencies not installed" runtime guard in CLI | ✅ | R2.no_reinstall_prompt, R3.help_matches_runtime |
| T3 | `README.md`: one install command, no recovery block | ✅ | R3.readme_one_block, R4.readme_no_recovery |
| T4 | `skills/prd/SKILL.md` + local skill cache: one-line prerequisite | ✅ | R4.skill_prerequisite |
| T5 | Verify `uv tool upgrade prd-tool` keeps dashboard working on an existing install | ❌ | R2.upgrade_preserves_features |

## Out of scope

- Migrating away from `uv tool` as the recommended installer.
- Trimming dashboard deps (e.g. swapping FastAPI for `http.server`). Tracked
  separately if install size becomes a real complaint.
- Changing the frontend build pipeline or wheel layout — the existing
  `force-include` of `dashboard/static` is unaffected.
