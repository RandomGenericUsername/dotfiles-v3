---
baseline_commit: 8eacac85e8c86c990fa415e0aab9f671f256f37e
---

# Story 1.7: CLI Show + Version Commands

Status: review

## Story

As a theming user,
I want to preview a palette without writing files and check the tool version,
So that I can decide whether to run the full generate and verify which version is installed.

## Acceptance Criteria

### Show Command

**Given** the CLI show command
**When** `csg show ~/wallpaper.jpg` is run
**Then** it runs extraction via `LocalProcessor.process_show()`
**And** displays the palette via `OutputPort.palette_display(result.color_scheme)`
**And** does not write any output files
**And** returns exit code 0 on success

**Given** an invalid image path
**When** `csg show /nonexistent.jpg` is run
**Then** it returns a JSON error payload and exit code 1

**Given** `csg show --help`
**When** run
**Then** it shows `Usage: csg show [OPTIONS] IMAGE_PATH`
**And** `<image_path>` is a positional required argument
**And** no `--backend`, `--param`, `--dry-run` flags exist (out of scope for this story)

### Version Command

**Given** the CLI version command
**When** `csg version` is run
**Then** it outputs the version from `importlib.metadata.version("color-scheme-generator")`
**And** returns exit code 0

**Given** `csg version --help`
**When** run
**Then** it shows `Usage: csg version [OPTIONS]`
**And** no required arguments

## Tasks / Subtasks

### Show Command
- [x] Create `src/color_scheme_generator/cli/show.py` (AC: Show Command)
  - `show` Typer command function accepting `image_path: Path`
  - Retrieves deps from `ctx.obj["deps"]`
  - Builds `GeneratorConfig` with hardcoded defaults (same as generate: `Backend.CUSTOM`, empty params/formats)
  - Calls `deps.processor.process_show(request, AppSettings())`
  - Calls `deps.output_adapter.palette_display(result.color_scheme)`
  - Wraps in try/except `ColorSchemeError`: calls `deps.output_adapter.error(exc)`, `raise typer.Exit(code=1)`

### Version Command
- [x] Create `src/color_scheme_generator/cli/version_cmd.py` (AC: Version Command)
  - `version` Typer command function (no arguments)
  - Uses `importlib.metadata.version("color-scheme-generator")` directly (no VersionProviderPort needed yet — keep it simple)
  - Outputs version string as JSON: `{"version": "0.1.0"}`
  - Returns exit code 0

### CLI Wiring
- [x] Wire `show` and `version` commands into `cli/main.py`
  - Add `from color_scheme_generator.cli.show import show` and `app.command()(show)` or use `add_typer` / `app.command()`
  - Same for `version`
  - Verify `csg show --help` and `csg version --help` work

### Tests
- [x] Create `tests/unit/cli/test_show.py` (AC: Show Command)
  - Successful show via CliRunner with mock deps (mock LocalProcessor.process_show, mock OutputPort.palette_display)
  - Invalid image path propagates error and exits with code 1
  - Calls `OutputPort.palette_display()` on success, not `process_result()`
  - No output files written
  - `--help` produces correct usage text
  - No `--backend` / `--param` / `--dry-run` flags in help (Epic 2 scope boundary)
- [x] Create `tests/unit/cli/test_version.py` (AC: Version Command)
  - Version outputs expected JSON
  - Exit code 0
  - `--help` produces correct usage text
  - Verify version string matches `importlib.metadata.version("color-scheme-generator")`

## Dev Notes

### Architecture Compliance

- `show` uses `LocalProcessor.process_show()` which currently delegates to `process_generate()` (same extraction, no file writes). In Epic 2 this will be enhanced with template rendering skip.
- `version` uses `importlib.metadata` directly — no `VersionProviderPort` adapter needed yet. The architecture plan mentions it but it's overengineering for this story. If the port is needed later (Epic 2), it can be extracted then.
- Both commands use the same `build_deps()` / `CliDependencies` pattern established in Story 1.6.
- No `--output-format` flag yet — `JsonOutput` is hardcoded (RichOutput/PlainOutput come in Epic 2).
- `show` uses `OutputPort.palette_display()` — already implemented in `JsonOutput`.
- Follow WEG pattern: `cli/show.py` and `cli/version_cmd.py` each export a callable registered in `main.py`.

### Existing Patterns to Follow

From Story 1.6 (test_generate.py):
```python
from typer.testing import CliRunner
from color_scheme_generator.cli.main import app

runner = CliRunner()
result = runner.invoke(app, ["show", "/tmp/test.jpg"])

# Mock pattern:
monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)
```

### Key Domain Types Already Defined

| Type | File | Key Details |
|------|------|-------------|
| `LocalProcessor.process_show()` | `adapters/local_processor.py` | Delegates to `process_generate()` |
| `OutputPort.palette_display()` | `ports/output.py` | Protocol method |
| `JsonOutput.palette_display()` | `adapters/output/json_output.py` | Serializes ColorScheme to JSON dict |
| `AppSettings` | `domain/models.py` | Empty placeholder frozen dataclass |
| `GeneratorConfig` | `domain/models.py` | `backend`, `params`, `formats`, `output_dir` |
| `GenerationRequest` | `domain/models.py` | `image_path`, `config` |
| `ColorSchemeError` | `domain/exceptions.py` | Base exception, catch in CLI |

### Files This Story Creates

| File | Status | Purpose |
|------|--------|---------|
| `src/color_scheme_generator/cli/show.py` | CREATE | Show command |
| `src/color_scheme_generator/cli/version_cmd.py` | CREATE | Version command |
| `tests/unit/cli/test_show.py` | CREATE | Show command tests |
| `tests/unit/cli/test_version.py` | CREATE | Version command tests |

### Files This Story Modifies

| File | Status | Change |
|------|--------|--------|
| `cli/main.py` | MODIFY | Wire `show` and `version` commands into the Typer app |

### Testing Requirements

- Use Typer's `CliRunner` from `typer.testing`
- Mock `LocalProcessor.process_show()` to return a known `GenerationResult` — verify `OutputPort.palette_display()` is called with `color_scheme`
- Mock `LocalProcessor.process_show()` to raise `InvalidImageError` — verify `OutputPort.error()` is called and exit code is 1
- Assert `--help` output for `show` contains expected usage text and `IMAGE_PATH` positional arg
- Assert no `--backend`/`--param`/`--dry-run` flags in `show --help` (Epic 2 scope boundary)
- For `version`: assert JSON output with version string, exit code 0
- Existing test count: 101 (Stories 1.1-1.6)
- Use `pytest` for test discovery; `ruff lint` must pass

### Out of Scope (Epic 2+)

| Feature | Epic/Story |
|---------|-----------|
| `--backend` flag on `show` | Epic 2 / Story 2.9 |
| `--param` flag | Epic 2 / Story 2.9 |
| `--dry-run` flag | Epic 4 / Story 4.1 |
| `--output-format rich\|plain` | Epic 2 / Story 2.7 |
| VersionProviderPort abstraction | Epic 2 / Story 2.1 |

### References

- [Source: epics.md#L258-L276] — Story 1.7 Acceptance Criteria
- [Source: ARCHITECTURE_PLAN.md#L138] — ShowColors use case flow
- [Source: ARCHITECTURE_PLAN.md#L145] — Version use case flow
- [Source: ARCHITECTURE_PLAN.md#L374-L377] — `show` CLI signature
- [Source: ARCHITECTURE_PLAN.md#L389] — `version` CLI signature
- [Source: ARCHITECTURE_PLAN.md#L504] — `cli/show.py` file in structure
- [Source: ARCHITECTURE_PLAN.md#L511] — `cli/version_cmd.py` file in structure
- [Source: main.py] — Existing build_deps() and generate command pattern
- [Source: adapters/local_processor.py#L54-L57] — `process_show()` delegates to `process_generate()`
- [Source: adapters/output/json_output.py#L38-L41] — `palette_display()` implementation
- [Source: test_generate.py] — Test patterns (mock deps via monkeypatch, CliRunner)

## Dev Agent Record

### Agent Model Used

deepseek-v4-flash

### Debug Log References

- `typer` is already in dependencies from Story 1.6
- `importlib.metadata` is stdlib (Python 3.14) — no additional dependency needed
- Version string in `__init__.py` is `"0.1.0"` — `importlib.metadata.version("color-scheme-generator")` uses package metadata
- Ensure `color-scheme-generator` package name in pyproject.toml matches the importlib.metadata lookup string

### Completion Notes List

- Implemented `show` command with LocalProcessor.process_show() + OutputPort.palette_display()
- Implemented `version` command using importlib.metadata, outputs JSON version string
- Wired both commands into cli/main.py with app.command() registration
- Created test_show.py and test_version.py with full AC coverage
- All 109 tests pass (101 existing + 8 new)
- Mocked importlib.metadata in version tests since package not installed in CI

### File List

| File | Status |
|------|--------|
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/show.py` | CREATE |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/version_cmd.py` | CREATE |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/main.py` | MODIFY |
| `src/cli-tools/color-scheme-generator/tests/unit/cli/test_show.py` | CREATE |
| `src/cli-tools/color-scheme-generator/tests/unit/cli/test_version.py` | CREATE |
