# Plan: CSG Fix Known Bugs (the 8 xfails)

Status: **ready to execute** — blocked only by plan-mode edit permission. Flip plan mode off (or allow `edit` on the repo) and re-run; this file is the complete work order.

## Context

`csg` = `src/cli-tools/color-scheme-generator/`. The 8 `@pytest.mark.xfail` markers (all `strict=False`) were introduced by the archived change `2026-07-31-csg-test-characterization` task §8 as "flag, don't fix". They document 4 real defects without locking any actual behavior. Decision: **fix all 4 defects**, remove the 8 xfail markers (tests become real characterization tests), add pytest hardening. Scope: bugs only — do NOT rewrite the mock-heavy command tests (audit R1/R5) in this change.

## OpenSpec change to create

`openspec/changes/2026-07-31-csg-fix-known-bugs/` with:

- `proposal.md` — Why (4 defects, strict=False problem), What Changes, Capabilities, Impact (see draft below).
- `design.md` — Decisions D1–D5 (see below).
- `tasks.md` — Numbered tasks (see below).
- `specs/` deltas:
  - Modified: `csg-cli-integration-tests` (add "commands route through OutputPort" requirement), `help-text-display` (add "--help lists all 5 config strategies" requirement).
  - New: `csg-output-port-routing`, `csg-settings-schema-validation`, `csg-backend-catalog-min-version` (each a `spec.md`).

## Source edits

### Bug 1 — `default_formats` unvalidated (2 xfails)
**File:** `src/color_scheme_generator/adapters/settings/schema.py`
- Import `ColorFormat` from `color_scheme_generator.domain.enums` (already imports `Backend, ContainerEngine, RuntimeMode` on line 9).
- Add `@field_validator("default_formats")` on `OutputSettingsSchema` (class at line 14) that raises `ValueError` if any entry is not in `{m.value for m in ColorFormat}`. Keep field type `list[str]` (validate-not-coerce) so `test_schema.py:139`'s `["json","sh"]` equality still holds and the serializer keeps owning enum coercion downstream.

### Bug 3 — `min_version` hardcoded (1 xfail)
**Files:** `adapters/schemas/backends_catalog_schema.py`, `adapters/yaml_backend_catalog_loader.py:57`
- Add `min_version: str = "0.0.0"` field to `BackendDefinitionSchema` (after `display_name`).
- In `_schema_to_domain` (line 52-58), replace `min_version="0.0.0"` with `min_version=def_schema.min_version`.

### Bug 4 — `--help` omits `--config` step (1 xfail)
**File:** `cli/main.py:60-74` (the `help=...` string on the `typer.Typer(...)` call)
- Rewrite the settings discovery block so the numbered list has 5 entries:
  ```
  1. --config flag
  2. COLORSCHEME_CONFIG_FILE_PATH env var
  3. settings.toml in CWD or up to 3 parent levels
  4. XDG default: <xdg path>
  5. Package-bundled defaults
  ```
  Keep the Templates directory block (4 steps, unchanged) and ENV overrides line as-is.

### Bug 5-8 — 4 commands bypass `OutputPort` (4 xfails)
**Files:** `ports/output.py`, `adapters/output/{json,plain,rich}_output.py`, `cli/{install,uninstall,version,list_backends}_cmd.py`

1. `ports/output.py` — add 4 method signatures to `OutputPort` Protocol (after `config_info`, line 28):
   ```python
   def install_result(self, results: list[dict]) -> None: ...
   def uninstall_result(self, results: list[dict]) -> None: ...
   def version_info(self, version: str) -> None: ...
   def backends_catalog(self, backends: list[dict], hint: str = "") -> None: ...
   ```

2. Each of `JsonOutput`, `PlainOutput`, `RichOutput` — implement the 4 methods by moving the per-adapter rendering code currently inline in the command files:
   - `install_result` ← `install_cmd.py` lines doing `isinstance` dispatch + `print(json.dumps({"install": results}))` / `Table` / plain loop.
   - `uninstall_result` ← `uninstall_cmd.py` equivalent.
   - `version_info` ← `version_cmd.py` equivalent (`{"version": ver}` / `console.print(...)` / plain).
   - `backends_catalog` ← `list_backends_cmd.py` equivalent (payload with `backends`/`hint` / per-backend Tables / plain loop). Note the payload key is `backends`; the `hint` is conditionally added in JSON.

3. Each command file — replace the `adapter = deps.output_adapter; if isinstance(adapter, …): … elif …` block with a single `deps.output_adapter.<method>(...)` call. Remove now-unused imports (`json`, `JsonOutput`, `RichOutput`, `PlainOutput`, `Table` where applicable). Keep the rest of each command's logic (container engine calls, settings resolution, error handling) untouched.

## Test edits

### Remove the 8 xfails
- `tests/unit/adapters/settings/test_schema.py` — remove both `@pytest.mark.xfail(...)` decorators in `TestKnownBugsXfail` (keep the test methods; they now pass). Optional: rename class to `TestDefaultFormatsValidation` — skip per "keep filename" preference at file level; class rename is harmless, do it.
- `tests/unit/adapters/test_yaml_backend_catalog_loader.py` — remove the 1 xfail decorator in `TestKnownBugsXfail`.
- `tests/unit/cli/test_known_bugs.py` — remove all 5 xfail decorators (keep filename, keep test methods; the 4 `TestCommandsRouteThroughOutputPortXfail` tests now pass because commands route through `OutputPort`).

### Update port conformance fakes
- `tests/unit/ports/test_contracts.py` + `tests/unit/ports/conftest.py` — the conformance fake adapters (the ones used for `isinstance(x, OutputPort)` assertions) must add the 4 new methods (one-line stubs). Inspect `conftest.py` first; there's a `_RecordingOutputAdapter`-style fake that needs the 4 methods.

### pytest hardening
- `pyproject.toml:33-35` — change:
  ```toml
  [tool.pytest.ini_options]
  testpaths = ["tests"]
  pythonpath = ["src", "."]
  addopts = ["--strict-markers", "-rxX"]
  ```

## Verification (no behavior assumptions)

1. `uv run pytest -q` from `src/cli-tools/color-scheme-generator/` → expect **544 passed, 0 xfailed** (the 8 absorbed as passing). If any new failure, inspect — likely a conformance fake missed a method.
2. `uv run ruff check && uv run ruff format --check` → clean.
3. `uv run csg --help` → settings discovery lists 5 steps, `1. --config flag` first.
4. `uv run csg list-backends --output-format json|rich|plain` → renders identically to today (regression check).
5. `uv run csg install --dry-run --backend custom` → JSON payload shape unchanged (regression check).
6. After verification, optionally archive the openspec change per house convention (separate step; ask user).

## Risks

- `OutputPort` Protocol change is additive but **breaking for out-of-tree adapters** — none exist in repo; conformance fakes updated in same change. Low risk.
- Bug 1 validator must validate-not-coerce (documented D1) to preserve `test_schema.py:139`.
- The mock-heavy `install`/`uninstall`/`list-backends`/`info`/`dump-*` tests (R1/R5) keep passing unchanged — they mock the container engine, not output routing. Out of scope here; flagged for a follow-up openspec change.

## Draft openspec content

### proposal.md (short version; expand when creating)

Why: 4 defects behind 8 silent xfails (strict=False, no CI gate). What Changes: validate default_formats; thread min_version; rewrite help to 5 steps; extend OutputPort with 4 named methods and route 4 commands through them; remove 8 xfails; add `--strict-markers -rxX`. Capabilities: Modified `csg-cli-integration-tests` + `help-text-display`; New `csg-output-port-routing`, `csg-settings-schema-validation`, `csg-backend-catalog-min-version`. Impact: CSG module only, no shared-lib changes, no new deps.

### design.md decisions

- **D1** default_formats: validate against `ColorFormat` enum *values*, keep field `list[str]` (no coerce) → preserves `test_schema.py:139` equality; serializer keeps owning enum coercion.
- **D2** min_version: add `min_version: str = "0.0.0"` to `BackendDefinitionSchema` (backward compat); loader passes `def_schema.min_version`.
- **D3** help: rewrite hand-written string to mirror the 5-strategy resolver chain (`--config` first); keep templates block (4 steps) and ENV-overrides line unchanged.
- **D4** OutputPort: 4 named methods matching existing convention (`process_result`/`palette_display`/`config_info`); per-adapter print/Table code moved into adapter methods; command files call `adapter.<method>(...)` only.
- **D5** xfails: remove all 8 decorators (tests now pass); add `--strict-markers -rxX` so future xfail misuse trips CI.

### tasks.md

1. Bug 1 — schema default_formats validator
2. Bug 3 — schema min_version field + loader
3. Bug 4 — help string rewrite
4. Bug 5-8 — OutputPort + 3 adapters + 4 command files
5. Remove 8 xfails + port conformance fakes + pyproject addopts
6. Verify (pytest, ruff, manual CLI)
7. Archive openspec change (separate user-approved step)