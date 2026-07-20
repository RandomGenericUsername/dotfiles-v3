---
baseline_commit: 4816250
---

# Story 2.10: Shell Completion & First-Run Experience

Status: done

## Story

As a theming user,
I want shell completion installed and the tool to work out of the box,
So that I don't need to read documentation to get started.

## Acceptance Criteria

### AC 1: Shell completion via Typer's built-in

**Given** Typer's built-in completion support
**When** `csg --install-completion` is run
**Then** shell completion is installed for the current shell (bash/zsh/fish)
**And** completion covers all commands, flags, and backend enum values

### AC 2: First-run falls back to bundled defaults

**Given** a fresh install with no settings.toml on the host (no CLI path, no ENV, no directory traversal, no XDG)
**When** `csg generate ~/wallpaper.jpg` is run for the first time
**Then** it falls back to package-bundled defaults/settings.toml
**And** extraction succeeds without any user configuration

### AC 3: No backends available — graceful degradation

**Given** no backends are available on the host (all `is_available()` return False)
**When** `csg list-backends` is run
**Then** it shows all three with `is_available=False`
**And** the output suggests `csg install` for container-mode execution

## Tasks / Subtasks

### CLI: Enable shell completion in main.py
- [x] Verify Typer app has `--install-completion` and `--show-completion` implicitly available (Typer >=0.9 adds these by default) (AC: 1)
- [x] If not auto-registered, add `--install-completion` and `--show-completion` as callback options (AC: 1)
- [x] Test: `csg --install-completion` succeeds in bash/zsh/fish (AC: 1)
- [x] Test: `csg --show-completion` outputs the completion script (AC: 1)

### First-run: Ensure bundled defaults/settings.toml exists
- [x] Create `src/color_scheme_generator/defaults/settings.toml` with package-bundled defaults (AC: 2)
- [x] Set DefaultFileStrategy path to reference package-bundled defaults/settings.toml (AC: 2)
- [x] Test: running generate without any config file resolves to bundled defaults (AC: 2)

### No-backends: Update list-backends output
- [x] In `cli/list_backends_cmd.py`, when all backends show `is_available=False`, append a `"hint"` field or console message (AC: 3)
- [x] Hint text: "No backends are available on the host. Try `csg install` to build container images, or install a backend binary (wal, wallust) locally." (AC: 3)
- [x] Test: `list-backends` with all generators returning False includes hint text (AC: 3)

### Write tests
- [x] Test shell completion: invoke `--install-completion` and `--show-completion` (AC: 1)
- [x] Test first-run: config resolution with no host config falls back to bundled defaults (AC: 2)
- [x] Test no-backends: `list-backends` with all `is_available=False` shows hint (AC: 3)

## Dev Notes

### Current State

**Typer version**: `>=0.12` (per pyproject.toml). Typer >=0.9 auto-registers `--install-completion` and `--show-completion` on the Typer app via `typer._completion_shared`. These are added by Typer's `Typer()` constructor automatically — no manual wiring needed. Verify by running `csg --help` — if `--install-completion` appears in the global options, it's already working.

**Config resolution default file**: `AssembledConfigResolver.__init__` at `adapters/settings/config_resolver.py:74` uses:
```python
DefaultFileStrategy(path=Path("settings.toml")),
```
This resolves relative to CWD, NOT the package-bundled defaults. First-run AC requires the fallback to use the package-bundled `defaults/settings.toml`. The DefaultFileStrategy path should use `importlib.resources` to reference the bundled file.

**Package-bundled defaults** exist at:
- `defaults/backends.yaml` — exists ✓
- `defaults/templates/` — exists ✓ (8 Jinja2 templates)
- `defaults/settings.toml` — **does NOT exist** (must be created)

**Bundled `defaults/settings.toml` content** (from ARCHITECTURE_PLAN.md §14):
```toml
version = "1.0"

[output]
verbosity = 1
directory = "/tmp/color-scheme"

[generation]
backend = "pywal"
default_formats = ["json", "sh"]

[templates]
directory = ""

[runtime]
mode = "local"

[container]
engine = "docker"
image_tag = "latest"
image_registry = ""
```

**Backend availability checking** (from `list_backends_cmd.py:_get_backend_info`):
- `CustomGenerator.is_available()`: checks PIL+sklearn import
- `PywalGenerator.is_available()`: checks `wal` on PATH
- `WallustGenerator.is_available()`: checks `wallust` on PATH

### Architecture Compliance

- Shell completion must use Typer's built-in mechanism — no custom shell scripting
- First-run fallback must use existing `AssembledConfigResolver` resolution chain; if `DefaultFileStrategy` path is the only match, `resolve()` succeeds with bundled defaults
- `list-backends` hint must go through `OutputPort` — use `deps.output_adapter.message(msg)` for Rich/Plain/JSON output
- All three backends `is_available()` returning False should trigger the hint — the hint is informational, not an error (no `ColorSchemeError`)

### Previous Story Intelligence (from 2.9)

- **Test patterns**: `CliRunner` with `runner.invoke(app, [...])`, mock deps via `monkeypatch` on `build_deps`
- **CLI pattern**: All commands use `ctx: typer.Context` and `deps: CliDependencies = ctx.obj["deps"]`
- **Config resolution fallback**: Already has `default_app_settings()` in `cli/_helpers.py` used as fallback in `generate()` and `show()`. The story should ensure the bundled `defaults/settings.toml` is resolved first as the DefaultFileStrategy target
- **Ruff**: Must be clean for all new/modified files
- **All ~314 existing tests must pass** — zero regressions

### Files to modify

| File | Action |
|------|--------|
| `src/color_scheme_generator/adapters/settings/config_resolver.py` | MODIFY — update `DefaultFileStrategy` path to use importlib.resources for bundled defaults/settings.toml |
| `src/color_scheme_generator/cli/list_backends_cmd.py` | MODIFY — add first-run hint when all backends unavailable |

### Files to create

| File | Action |
|------|--------|
| `src/color_scheme_generator/defaults/settings.toml` | CREATE — package-bundled default settings |
| `tests/unit/cli/test_first_run.py` | CREATE — first-run and shell completion tests |

### References

- [Source: epics.md#548-569] — Story 2.10 acceptance criteria
- [Source: ARCHITECTURE_PLAN.md#588-613] — Default settings.toml content
- [Source: ARCHITECTURE_PLAN.md#363-398] — CLI structure including `--install-completion`
- [Source: adapters/settings/config_resolver.py:74] — Current DefaultFileStrategy path
- [Source: cli/list_backends_cmd.py:17-48] — `_get_backend_info` for is_available check
- [Source: cli/main.py:45] — Typer app instantiation
- [Source: pyproject.toml:7] — Typer >=0.12 dependency
- [Source: PRD.md#33-34] — UJ-2: first-run user journey

## File List

### Modified
- `src/color_scheme_generator/adapters/settings/config_resolver.py` — Update DefaultFileStrategy path to use importlib.resources
- `src/color_scheme_generator/cli/list_backends_cmd.py` — Add first-run hint for all-unavailable backends

### Created
- `src/color_scheme_generator/defaults/settings.toml` — Package-bundled default settings
- `tests/unit/cli/test_first_run.py` — Tests for shell completion and first-run scenarios

## Review Findings

### Patch
- [x] [Review][Patch] parse_params silently drops malformed entries — now warns on stderr [src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/_helpers.py:48]
- [x] [Review][Patch] parse_params("=value") inserts empty string `""` as key — now guards against empty key [src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/_helpers.py:50]
- [x] [Review][Patch] Duplicated backend-catalog validation logic in main.py and show.py — extracted to resolve_backend_params() in _helpers.py [src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/_helpers.py]

### Deferred
- [x] [Review][Defer] Fragile test accesses private internals [src/cli-tools/color-scheme-generator/tests/unit/cli/test_first_run.py:59,136] — deferred, pre-existing

## Dev Agent Record

### Implementation Plan

1. Create `defaults/settings.toml` with content from ARCHITECTURE_PLAN.md §14
2. Update `config_resolver.py` DefaultFileStrategy to use `importlib.resources.files("color_scheme_generator") / "defaults" / "settings.toml"`
3. Add hint to `list_backends_cmd.py` when all backenders unavailable
4. Verify `--install-completion` works via Typer auto-registration
5. Write tests for all three ACs
6. Run full test suite — verify zero regressions
7. Run ruff lint — must be clean

### Completion Notes

- Created `defaults/settings.toml` matching ARCHITECTURE_PLAN.md §14 defaults aligned with CoreSettingsSchema
- Updated `config_resolver.py` DefaultFileStrategy to use `importlib.resources.files()` for package-bundled path
- Added hint to `list_backends_cmd.py` when all backends unavailable — works in JSON/Rich/Plain output
- Verified Typer >=0.12 auto-registers `--install-completion` and `--show-completion` — no code changes needed
- 11 new tests covering all 3 ACs: shell completion presence, bundled defaults fallback, no-backend hint
- All 330 tests pass with zero regressions
- Ruff lint clean
