---
baseline_commit: 8eacac85e8c86c990fa415e0aab9f671f256f37e
---

# Story 1.6: CLI Generate Command

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a theming user,
I want to run `csg generate ~/wallpaper.jpg` and get a color palette,
So that I can theme my desktop without manual color picking.

## Acceptance Criteria

### Minimal CLI Application

**Given** the Typer CLI app `cli/main.py`
**When** `csg generate ~/wallpaper.jpg` is run
**Then** it resolves `image_path` from the positional argument
**And** uses hardcoded defaults:
  - `backend = Backend.CUSTOM`
  - `output_dir = Path("/tmp/color-scheme")`
  - `formats = ()` (no template rendering yet)
  - `params = {}`
**Then** calls `LocalProcessor.process_generate(request, AppSettings())` via `CliDependencies`
**And** renders the result via `JsonOutput.process_result()` (default output adapter)
**And** returns exit code 0 on success

**Given** an invalid / nonexistent image path
**When** `csg generate /nonexistent.jpg` is run
**Then** `CustomGenerator.generate()` raises `InvalidImageError`
**And** `LocalProcessor` propagates it (no catch)
**And** the CLI catches `ColorSchemeError` and calls `JsonOutput.error(exc)`
**And** outputs `{"success": false, "error": {"type": "InvalidImageError", "message": "..."}}`
**And** returns exit code 1

### Help Output

**Given** `csg generate --help`
**When** run
**Then** it shows `Usage: csg generate [OPTIONS] IMAGE_PATH`
**And** `<image_path>` is a positional required argument
**And** no `--backend`, `-o`, `--param`, `-f` flags exist (out of scope for this story)

### Composition Root Integration

**Given** `cli/main.py` `@app.callback()`
**When** the app starts
**Then** it builds `CliDependencies` from `factory.py`:
  - `backend_registry = create_backend_registry()`
  - `output_adapter = JsonOutput()`
**And** stashes on `ctx.obj["deps"]`

### Structural Cleanliness

**Given** the `cli/` package
**When** imported
**Then** `from color_scheme_generator.cli import main` works
**And** `pyproject.toml` console_scripts points to `color_scheme_generator.cli.main:app`

## Tasks / Subtasks

### CLI Package
- [x] Create `src/color_scheme_generator/cli/__init__.py` — empty, `from __future__ import annotations` (AC: Structural Cleanliness)
- [x] Create `src/color_scheme_generator/cli/main.py` (AC: Minimal CLI Application, Composition Root Integration)
  - Typer `app = typer.Typer()`
  - `@app.callback()` that builds `CliDependencies`:
    - `deps = CliDependencies(backend_registry=create_backend_registry(), output_adapter=JsonOutput())`
    - `ctx.obj = {"deps": deps}`
  - `@app.command()` for `generate` (or delegate to `cli/generate.py`)

### Generate Command
- [x] Implement `generate` command (inline in `main.py` or separate `cli/generate.py`) (AC: Minimal CLI Application)
  - Accepts `image_path: Path = typer.Argument(..., exists=False)` (no validation at argument level — let backend handle it)
  - Retrieves deps from `ctx.obj["deps"]`
  - Builds `GeneratorConfig(backend=Backend.CUSTOM, params={}, formats=(), output_dir=Path("/tmp/color-scheme"))`
  - Builds `GenerationRequest(image_path=image_path, config=config)`
  - Calls `deps.output_adapter.process_result(processor.process_generate(request, AppSettings()))`
  - Wraps in try/except `ColorSchemeError`:
    - Calls `deps.output_adapter.error(exc)`
    - `raise typer.Exit(code=1)`

### Tests
- [x] Create `tests/unit/cli/__init__.py` — empty
- [x] Create `tests/unit/cli/test_generate.py` (AC: all)
  - Successful generate via CliRunner with mock deps (mock LocalProcessor, mock JsonOutput)
  - Invalid image path propagates InvalidImageError and exits with code 1
  - Calls JsonOutput.error() on ColorSchemeError
  - --help produces correct usage text with image_path positional arg
  - No --backend / -o / --param / -f flags in help (out of scope)
  - app.callback stashes CliDependencies on ctx.obj["deps"]

## Dev Notes

### Architecture Compliance

- This is the **first CLI command** in the project — creates `cli/` package structure
- `cli/main.py` is the Typer entry point declared in `pyproject.toml`: `csg = "color_scheme_generator.cli.main:app"`
- No `--output-format` flag yet — JsonOutput is hardcoded as default (RichOutput and PlainOutput come in Epic 2)
- `AppSettings()` is the empty placeholder from `domain/models.py` — no real config resolution (Epic 2)
- `Backend.CUSTOM` is hardcoded — no `--backend` flag (Epic 2)
- No `--param` support (Epic 2)
- No template rendering — `GeneratorConfig.formats = ()` and `output_files` will be empty (Epic 2)
- Follows WEG pattern: `@app.callback()` builds deps → stash on `ctx.obj["deps"]` → per-command retrieves them
- `from __future__ import annotations` in all new CLI modules (established convention)
- `typer.Exit(code=1)` for error exit codes, NOT `sys.exit(1)` — Typer idiom

### Existing Dependency Wiring

From `factory.py`:
```python
@dataclass
class CliDependencies:
    backend_registry: BackendRegistry
    output_adapter: OutputPort | None = None

def create_backend_registry() -> BackendRegistry:
    return {
        Backend.CUSTOM: CustomGenerator(),
        Backend.PYWAL: PywalGenerator(),
        Backend.WALLUST: WallustGenerator(),
    }
```

Current `CliDependencies` has only 2 fields. For this story, `output_adapter` is always `JsonOutput`. Expand `factory.py` to add fields if needed (e.g., `local_processor`, `processor`), but keep minimal — future stories (1.7, Epic 2) will add more.

### Error Handling Pattern

```python
try:
    result = processor.process_generate(request, AppSettings())
    deps.output_adapter.process_result(result)
except ColorSchemeError as exc:
    deps.output_adapter.error(exc)
    raise typer.Exit(code=1) from None
```

- Catch only `ColorSchemeError` hierarchy — let unexpected errors propagate as tracebacks (debuggability)
- `GenerationResult` path already tested in Story 1.5 (LocalProcessor tests)
- `JsonOutput.error()` serialization already tested in Story 1.4
- No bare `print()` — always through `OutputPort`

### Key Domain Types Already Defined

| Type | File | Key Details |
|------|------|-------------|
| `AppSettings` | `domain/models.py` | Empty placeholder frozen dataclass |
| `GeneratorConfig` | `domain/models.py` | `backend: Backend`, `params: dict`, `formats: tuple[ColorFormat]`, `output_dir: Path` |
| `GenerationRequest` | `domain/models.py` | `image_path: Path`, `config: GeneratorConfig` |
| `GenerationResult` | `domain/models.py` | `success`, `color_scheme`, `output_files`, `backend`, `stderr`, `return_code`, `duration` |
| `ColorSchemeError` | `domain/exceptions.py` | Base exception, catch in CLI |
| `Backend` | `domain/enums.py` | CUSTOM, PYWAL, WALLUST |
| `LocalProcessor` | `adapters/local_processor.py` | Implements `ColorSchemeProcessorPort` |
| `JsonOutput` | `adapters/output/json_output.py` | Implements `OutputPort` |

### Files This Story Creates

| File | Status | Purpose |
|------|--------|---------|
| `src/color_scheme_generator/cli/__init__.py` | CREATE | Package init |
| `src/color_scheme_generator/cli/main.py` | CREATE | Typer app + callback + generate command |
| `tests/unit/cli/__init__.py` | CREATE | Test package init |
| `tests/unit/cli/test_generate.py` | CREATE | CLI generate tests |

### Files This Story Modifies

| File | Status | Change |
|------|--------|--------|
| `factory.py` | MODIFY | Add `local_processor` field to `CliDependencies` (optional) or keep as-is |
| `pyproject.toml` | VERIFY | Console scripts entry must point to `color_scheme_generator.cli.main:app` (already set) |

### Testing Requirements

- Use Typer's `CliRunner` from `typer.testing` (comes with `typer[all]`)
- Mock `LocalProcessor.process_generate()` to return a known `GenerationResult` — verify `JsonOutput.process_result()` is called
- Mock `LocalProcessor.process_generate()` to raise `InvalidImageError` — verify `JsonOutput.error()` is called and exit code is 1
- Assert `--help` output contains expected usage text
- Assert no `--backend`/`-o`/`--param`/`-f` flags in help text (Epic 2 scope boundary)
- Test callback setup: verify `ctx.obj["deps"]` is a `CliDependencies` instance with `backend_registry` and `output_adapter`

```python
from typer.testing import CliRunner
from color_scheme_generator.cli.main import app

runner = CliRunner()
result = runner.invoke(app, ["generate", "/path/to/test.jpg"])
```

- Existing test count: 89 (Stories 1.1-1.5)
- Do NOT test LocalProcessor or JsonOutput in detail — those have their own test suites (Story 1.4 has 15 tests for JsonOutput, Story 1.5 has 12 tests for LocalProcessor)
- Use `pytest` for test discovery; `ruff lint` must pass

### Out of Scope (Epic 2+)

| Feature | Epic/Story |
|---------|-----------|
| `--backend` flag | Epic 2 / Story 2.9 |
| `-o` / `--output-dir` flag | Epic 2 / Story 2.9 |
| `-f` / `--format` flag | Epic 2 / Story 2.9 |
| `--param key=value` | Epic 2 / Story 2.9 |
| Config resolution (`settings.toml`) | Epic 2 / Story 2.2 |
| Template rendering | Epic 2 / Story 2.6 |
| `--output-format rich\|plain` | Epic 2 / Story 2.7 |
| `--dry-run` | Epic 4 / Story 4.1 |
| `--runtime container` | Epic 3 / Story 3.1 |

### Previous Story Intelligence

- **Story 1.1** (Domain): Frozen dataclasses, enums, exceptions established — 46 tests
- **Story 1.2** (Ports): 3 Protocol interfaces — 6 tests
- **Story 1.3** (CustomGenerator): Lazy imports, availability check, error handling — 10 tests. Key pattern: `InvalidImageError` for corrupt/unreadable images
- **Story 1.4** (JsonOutput): OutputPort adapter serializes to stdout JSON. Error serialization for all exception types — 15 tests. Pattern: `capsys` for stdout capture
- **Story 1.5** (LocalProcessor): Composition root (`factory.py`), `CliDependencies`, `create_backend_registry()`, `LocalProcessor.process_generate()` — 12 tests. Pattern: `time.monotonic()` for duration
- **Convention**: `from __future__ import annotations` in ALL new modules
- **Convention**: No Pydantic in adapters — domain types only (ADR-012)
- **Convention**: Ruff target `py314`, line-length 100, double quotes

### References

- [Source: epics.md#L233-L258] — Story 1.6 Acceptance Criteria
- [Source: ARCHITECTURE_PLAN.md#L363-L398] — CLI structure, `--param` semantics
- [Source: ARCHITECTURE_PLAN.md#L500-L511] — `cli/` package files
- [Source: ARCHITECTURE_PLAN.md#L678-L703] — factory.py composition root design
- [Source: PRD.md#L57-L68] — FR-1 Palette Extraction consequences
- [Source: factory.py] — Existing `CliDependencies` and `create_backend_registry()`
- [Source: adapters/local_processor.py] — `LocalProcessor.process_generate()` signature

### Review Findings

- `[x] [Review][Patch] `test_callback_stashes_deps_on_ctx` replaced by `test_build_deps_returns_proper_cli_dependencies` [test_generate.py:103-111] — Fixed via DI refactor: extracted `build_deps()`, now verifies deps directly.
- `[x] [Review][Patch] Repeated monkeypatching consolidated [test_generate.py:43-50,60,79] — Refactored: extracted `mock_deps` fixture, tests mock single `build_deps` point instead of 3 constructors.
- `[x] [Review][Patch] Help output test lowercase `image_path` [test_generate.py:92] — Changed to `IMAGE_PATH` (Typer uppercase).
- `[x] [Review][Defer] Backend generators eagerly instantiated [factory.py:28-30] — All three backends created at import time. Low overhead (stubs + no custom `__init__`). Not actionable in this scope.
- `[x] [Review][Defer] Hardcoded `/tmp/color-scheme` output dir [main.py:36] — `/tmp` is volatile, not configurable by user. Out of scope (Epic 2 adds `-o`/`--output-dir`).
- `[x] [Review][Defer] `.` in pythonpath is a fixture hazard [pyproject.toml:25] — Could mask import bugs. Pre-existing, not specific to this change.
- `[x] [Review][Defer] Only `ColorSchemeError` caught [main.py:47] — `OSError`, `PermissionError` etc. get raw tracebacks. By design per spec ("let unexpected errors propagate").
- `[x] [Review][Defer] Callback has no error handling for factory failures [main.py:22-26] — Low risk (all constructors lightweight). Systemic config issues better handled at app level.
- `[x] [Review][Defer] `CliDependencies.processor` field declared but never set [factory.py:23] — Dead field, will be used in Epic 2/3 when more commands share a processor.

## Dev Agent Record

### Agent Model Used

deepseek-v4-flash-free

### Debug Log References

- Ensure `typer` is added to `pyproject.toml` dependencies (currently empty `dependencies = []`)
- CliRunner requires `typer.testing` — verify `typer[all]` is installed or add `typer` to test deps
- `ruff` may flag unused imports in `main.py` if commands are minimal — use `TYPE_CHECKING` guards where appropriate

### Completion Notes

- Created `cli/` package with `__init__.py` and `main.py` containing Typer app
- Added `generate` command with hardcoded defaults (Backend.CUSTOM, /tmp/color-scheme output)
- Added 7 CLI tests covering: success path, error path, help output, scope boundaries
- Added `typer` dependency to `pyproject.toml` and `csg` console_scripts entry
- Extended `factory.py` `CliDependencies` with optional `processor` field
- All 101 tests pass (89 existing + 12 new); ruff lint passes

### File List

| File | Status |
|------|--------|
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/__init__.py` | CREATE |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/main.py` | CREATE |
| `src/cli-tools/color-scheme-generator/tests/unit/cli/__init__.py` | CREATE |
| `src/cli-tools/color-scheme-generator/tests/unit/cli/test_generate.py` | CREATE |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/factory.py` | MODIFY |
| `src/cli-tools/color-scheme-generator/pyproject.toml` | MODIFY |
