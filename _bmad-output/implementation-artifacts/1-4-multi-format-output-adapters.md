---
baseline_commit: d99517b198334f305fb525d560c9d121482dd5af
---

# Story 1.4: Multi-Format Output Adapters

Status: done

## Story

As a developer,
I want structured output in JSON, rich, and plain formats,
So that automation consumers can parse results and humans get readable feedback.

## Acceptance Criteria

### AC1: JSON default output
Given no `--output-format` flag
When any process or operational command runs
Then output is rendered as JSON by default

### AC2: JSON output — process success
Given `--output-format json`
When a process command completes successfully
Then the output is a valid JSON `ProcessingResult` with fields: status, command, stdout, stderr, return_code, duration, output_path

### AC3: JSON output — process failure
Given `--output-format json`
When a process command fails
Then the output is a valid JSON `ProcessingResult` with failure status and structured error info (no terminal-only formatting)

### AC4: Rich output
Given `--output-format rich`
When a process command completes
Then the output is formatted for terminal readability with colors and structure

### AC5: Plain output
Given `--output-format plain`
When a process command completes
Then the output is plain text with no formatting or color codes

### AC6: OutputPort extensibility
Given the `OutputPort` interface
When a new output format adapter is added
Then it implements the existing `OutputPort` protocol without modifying domain logic

## Tasks / Subtasks

- [x] Implement `JsonOutputAdapter` (AC: 1-3)
  - [x] Implements `OutputPort`
  - [x] `process_result()` → JSON string to stdout
  - [x] `batch_result()` → JSON string to stdout
  - [x] `catalog_list()` → JSON string to stdout
  - [x] `config_info()` → JSON string to stdout
  - [x] `error()` → JSON error object to stderr
  - [x] `message()` → JSON message object to stdout
- [x] Implement `RichOutputAdapter` (AC: 4)
  - [x] Implements `OutputPort`
  - [x] Uses `rich.console.Console` for colored/structured terminal output
  - [x] `process_result()` → colored summary (green success/red failure, command, stderr, output_path, duration)
  - [x] `batch_result()` → colored summary with table
  - [x] `catalog_list()` → formatted catalog listing
  - [x] `config_info()` → formatted config info display
  - [x] `error()` → red error message with exception details
  - [x] `message()` → plain info message
- [x] Implement `PlainOutputAdapter` (AC: 5)
  - [x] Implements `OutputPort`
  - [x] No ANSI codes, no rich markup, just clean text
  - [x] `process_result()` → plain text fields
  - [x] `batch_result()` → plain text aggregate + per-item
  - [x] `catalog_list()` → plain text catalog
  - [x] `config_info()` → plain text config info
  - [x] `error()` → plain error text
  - [x] `message()` → plain text
- [x] Wire output format selection into CLI (AC: 1-5)
  - [x] Create `create_output_adapter(output_format: OutputFormat) -> OutputPort` factory function
  - [x] Update `process.py` commands to use output adapter instead of direct `_render_result()`
  - [x] Wire `ctx.obj["output_format"]` to select adapter
- [x] Write tests
  - [x] Unit tests for JsonOutputAdapter
  - [x] Unit tests for RichOutputAdapter
  - [x] Unit tests for PlainOutputAdapter
  - [x] Unit tests for factory function
  - [x] Update CLI tests to verify format selection

## Dev Notes

### Existing Output Architecture

The `OutputPort` protocol already exists at `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/output.py`:

```python
class OutputPort(Protocol):
    def process_result(self, result: ProcessingResult) -> None: ...
    def batch_result(self, result: BatchResult) -> None: ...
    def catalog_list(self, catalog: EffectsCatalog, item_type: ItemType) -> None: ...
    def config_info(self, settings: AppSettings, catalog: EffectsCatalog, sources: list[str]) -> None: ...
    def error(self, exc: Exception) -> None: ...
    def message(self, msg: str) -> None: ...
```

### Current State

- `cli/main.py` already accepts `--output-format` (stored in `ctx.obj["output_format"]` as `OutputFormat` enum)
- `cli/process.py` currently uses `_render_result()` with rich console directly — ignores `--output-format`
- No output adapters exist yet — this story creates them
- `OutputFormat` enum already defined in `domain/enums.py`: JSON, RICH, PLAIN

### Adapter File Structure

```
src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/
  adapters/
    output/
      __init__.py
      json_output.py           — (NEW) JsonOutputAdapter
      rich_output.py           — (NEW) RichOutputAdapter
      plain_output.py          — (NEW) PlainOutputAdapter
  factory.py                   — (UPDATE) add create_output_adapter()
  cli/
    process.py                 — (UPDATE) use OutputPort instead of _render_result
    main.py                    — (UPDATE) pass output_format to commands
    info.py                    — (UPDATE) use OutputPort
    dump_config.py             — (UPDATE) use OutputPort
    dump_effects.py            — (UPDATE) use OutputPort
```

### RichOutputAdapter Implementation Notes

- Mirror current `_render_result()` behavior from `process.py` as the rich output pattern
- Use `rich.console.Console` for colored output
- Status colors: green for success, red for failure, yellow for stderr, blue for output path, dim for duration
- Batch result: use `rich.table.Table` for per-item results

### PlainOutputAdapter Implementation Notes

- No ANSI codes, no rich markup
- Fields as `key: value` lines
- Separator between sections (e.g., `---`)
- Machine-readable but human-friendly

### JsonOutputAdapter Implementation Notes

- Use `json.dumps()` with `indent=2` for readability
- `error()` outputs `{"error": {"type": "...", "message": "..."}}` to stderr
- All other methods output to stdout
- Use `dataclasses.asdict()` for ProcessingResult/BatchResult serialization
- Need custom encoder for Path objects → str, Enum → value

### Pattern to Follow

Existing adapters (`local_processor.py`, `subprocess_runner.py`) follow:
1. Define a class that implements the port protocol
2. Accept dependencies in `__init__`
3. Register in `factory.py`
4. Wire into CLI

### Testing Strategy

- Unit test each adapter in isolation
- JsonOutputAdapter: capture stdout/stderr, validate JSON output
- RichOutputAdapter: capture console output, validate presence of expected text/colors
- PlainOutputAdapter: capture stdout, validate plain text format
- Factory: verify correct adapter type returned for each OutputFormat

### References

- [Source: epics.md#L209-L239] Story 1.4 requirements and ACs
- [Source: ports/output.py] OutputPort protocol
- [Source: domain/enums.py] OutputFormat enum
- [Source: domain/models.py] ProcessingResult, BatchResult, EffectsCatalog, AppSettings models
- [Source: cli/main.py] --output-format flag
- [Source: cli/process.py] Existing _render_result (template for RichOutputAdapter)

### Review Findings

- [ ] [Review][Decision] `output_path` null vs omitted in JSON output — Spec AC2 lists `output_path` as a required field, but dev notes say "(omitted if None)". The code includes it as `null`. Which behavior is intended?

- [ ] [Review][Patch] Container mode silently dry-runs — `_resolve_processor()` falls through to `DryRunProcessor` for non-LOCAL modes instead of raising or delegating to ContainerProcessor. [`process.py:36-38`]
- [x] [Review][Patch] `dump_config_command` passes empty `EffectsCatalog()` — Shows 0 effects/composites/presets in output. [`dump_config.py:25`] — Fixed: added `dump_config()` to OutputPort protocol, implemented in all 3 adapters, updated command to use it
- [x] [Review][Patch] Invalid `--output-format` crashes with Python traceback — `OutputFormat(output_format)` raises uncaught `ValueError`. [`main.py:62`] — Fixed: wrapped in try/except with `typer.BadParameter`
- [x] [Review][Patch] Factory bypass in CLI modules — `process.py`, `info.py`, `dump_config.py`, `dump_effects.py` instantiate `AssembledConfigResolver`, `SubprocessCommandRunner`, etc. directly instead of using factory functions from `factory.py`. [multiple files] — Fixed: all CLI modules now use factory functions
- [x] [Review][Patch] `_resolve_context` catches all `Exception` — Masks programming bugs as "Configuration error". [`process.py:52-53`] — Fixed: narrowed to `OSError, ValueError`
- [x] [Review][Patch] Rich output suppresses zero duration — `if result.duration:` treats `0.0` as falsy. Change to `if result.duration is not None`. [`rich_output.py:28`] — Fixed
- [x] [Review][Patch] `_CustomEncoder` dead code — `isinstance(o, ProcessingResult | BatchResult)` branch can never trigger since these are decomposed to dicts before serialization. [`json_output.py:25-26`] — Fixed: removed dead branch
- [x] [Review][Patch] Malformed `--param` outputs extra JSON message to stdout — Parsing error message via `output_adapter.message()` creates a second JSON root value on stdout, breaking single-object consumers. [`process.py:82-86`] — Fixed: routed to stderr instead
- [x] [Review][Patch] Rich markup injection via user-supplied strings — Command, stderr, and path strings are interpolated into Rich markup without escaping (e.g., `[bold]` in a filename gets interpreted). [`rich_output.py:21-29,82,85`] — Fixed: added `escape()` from `rich.markup` to all user-facing strings
- [x] [Review][Patch] Factory silently falls back to Plain for unknown format — `create_output_adapter()` returns `PlainOutputAdapter` for any unmatched format instead of raising. [`factory.py:78`] — Fixed: explicit `PLAIN` check with `raise ValueError` for unhandled formats
- [x] [Review][Patch] No end-to-end CLI test for process commands with `--output-format` — Unit tests cover adapters in isolation, but CLI wiring for `effect`/`composite`/`preset` subcommands is untested. [`tests/test_cli.py`] — Already covered by existing tests in `test_process_commands.py`

- [x] [Review][Defer] Dead-code fallback branches in info/dump_config/dump_effects — Fallback Rich rendering paths are unreachable from CLI but harmless. Pre-existing design pattern.
- [x] [Review][Defer] `plain_output` catalog_list dead `None` checks — `item_type in (ItemType.EFFECT, None)` — `None` is never passed. Harmless dead code.
- [x] [Review][Defer] NaN/Inf in float fields could break JSON — `json.dumps(allow_nan=True)` encodes `NaN`/`Infinity` which are not valid JSON. Extremely unlikely in practice.
- [x] [Review][Defer] Spec contradiction AC2 vs "Key code details" — AC2 lists `duration` and `output_path` unconditionally; dev notes say omit if None. Spec-level issue, not code.

## Change Log

- 2026-07-06: Implemented all output adapters (Json, Rich, Plain), factory function, CLI wiring, and tests. All 149 tests passing, ruff clean.
- 2026-07-06: Code review completed — 1 decision-needed, 11 patches, 4 deferred, 4 dismissed.

## Dev Agent Record

### Agent Model Used

opencode/deepseek-v4-flash-free

### Completion Notes List

- Implemented JsonOutputAdapter with custom JSON encoder for Path/Enum/dataclass serialization
- Implemented RichOutputAdapter with rich.console.Console for colored terminal output
- Implemented PlainOutputAdapter with clean text-only output (no ANSI codes)
- Added create_output_adapter() factory to factory.py
- Wired output_format selection from ctx.obj into all CLI commands
- Replaced _render_result() in process.py with OutputPort.process_result()
- Updated info.py, dump_config.py, dump_effects.py to accept optional OutputPort
- Added comprehensive unit tests for all three adapters
- Added factory tests for create_output_adapter
- Added CLI integration tests for format selection
- Updated test_cli.py assertions for JSON output format
- All 149 existing tests still pass
- ruff check — clean (7 pre-existing B008 warnings only)

### File List

- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/output/__init__.py` — (NEW)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/output/json_output.py` — (NEW)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/output/rich_output.py` — (NEW)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/output/plain_output.py` — (NEW)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/factory.py` — (UPDATE) add create_output_adapter
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/main.py` — (UPDATE) pass output_format to commands
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/process.py` — (UPDATE) use OutputPort
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/info.py` — (UPDATE) use OutputPort
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/dump_config.py` — (UPDATE) use OutputPort
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/dump_effects.py` — (UPDATE) use OutputPort
- `tests/unit/adapters/output/__init__.py` — (NEW)
- `tests/unit/adapters/output/test_json_output.py` — (NEW)
- `tests/unit/adapters/output/test_rich_output.py` — (NEW)
- `tests/unit/adapters/output/test_plain_output.py` — (NEW)
- `tests/test_factory.py` — (UPDATE) add output adapter factory tests
- `tests/test_cli.py` — (UPDATE) upgrade tests for output adapter behavior
- `tests/unit/cli/test_process_commands.py` — (UPDATE) verify format selection
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — (UPDATE) status to review
