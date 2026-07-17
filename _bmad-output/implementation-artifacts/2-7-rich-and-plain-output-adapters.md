# Story 2.7: Rich + Plain Output Adapters

Status: ready-for-dev

## Story

As a theming user,
I want terminal-formatted and pipe-friendly output,
So that I can read results in a terminal or pipe them to other tools.

## Acceptance Criteria

### AC 1: RichOutput implements OutputPort

**Given** RichOutput implementing OutputPort
**When** process_result() is called with a successful GenerationResult
**Then** it renders with Rich formatting (colors, tables)
**When** error() is called with a ColorSchemeError
**Then** it renders a Rich-formatted error message (red text, styled)
**When** palette_display() is called with a ColorScheme
**Then** it renders a Rich-formatted palette preview (color swatches)
**When** verified via `isinstance(obj, OutputPort)`
**Then** it passes structural subtype checking

### AC 2: PlainOutput implements OutputPort

**Given** PlainOutput implementing OutputPort
**When** process_result() is called with a successful GenerationResult
**Then** it renders plain text with no formatting or color codes
**When** error() is called
**Then** it renders a plain-text error message (no formatting)
**When** palette_display() is called
**Then** it renders colors as hex values only (no ANSI codes)
**When** verified via `isinstance(obj, OutputPort)`
**Then** it passes structural subtype checking

### AC 3: --output-format flag selects the right adapter

**Given** the --output-format flag on generate, show, version commands
**When** --output-format json is passed
**Then** JsonOutput is selected
**When** --output-format rich is passed
**Then** RichOutput is selected
**When** --output-format plain is passed
**Then** PlainOutput is selected
**When** no flag is passed
**Then** JSON is the default

### AC 4: Output format is set in the global callback

**Given** the Typer app callback
**When** any command runs
**Then** `--output-format` is parsed in the global callback (not per-command)
**And** the output adapter is set on `ctx.obj["deps"].output_adapter` before the command handler runs

### AC 5: version command supports --output-format

**Given** the version command
**When** `csg version --output-format json` is run
**Then** it outputs `{"version": "0.1.0"}`
**When** `csg version --output-format rich` is run
**Then** it renders a Rich-formatted version string
**When** `csg version --output-format plain` is run
**Then** it outputs plain text like `color-scheme-generator 0.1.0`

## Tasks / Subtasks

### RichOutput adapter (new)
- [ ] Create `adapters/output/rich_output.py` (AC: 1)
  - Implements `OutputPort`
  - Uses `rich.console.Console` for output
  - `process_result()`: renders with Rich formatting
    - Success: green "✓ Success" header + color scheme summary + output files list
    - Uses `rich.table.Table` for structured data
  - `error()`: renders Rich-formatted error
    - Red "✗ Error" header + error type and message
    - Uses `rich.panel.Panel` for error display
  - `palette_display()`: renders color swatches
    - Uses `rich.color.Color` to render actual color blocks
    - Shows 16 colors in a row with hex labels
    - Shows background, foreground, cursor separately
  - All output goes to `Console()` (stdout)
  - Structural subtyping via `isinstance(obj, OutputPort)`

### PlainOutput adapter (new)
- [ ] Create `adapters/output/plain_output.py` (AC: 2)
  - Implements `OutputPort`
  - No formatting, no color codes, no Rich dependency
  - `process_result()`:
    - Success: `"Success"` + `"Backend: <value>"` + `"Duration: <n>s"` + output files list
  - `error()`: `"Error: <type> - <message>"` with relevant fields on separate lines
  - `palette_display()`: hex values only, one per line
    - `"Background: #1a1b26"`
    - `"Foreground: #c0caf5"`
    - `"Cursor: #f7768e"`
    - `"Colors: #1a1b26 #... (16 hex values space-separated)"`
  - All output via `print()` to stdout
  - Structural subtyping via `isinstance(obj, OutputPort)`

### Update adapters/output/__init__.py (existing)
- [ ] Export `RichOutput` and `PlainOutput` from `adapters/output/__init__.py`

### Factory wiring (existing file: factory.py)
- [ ] Add `create_output_adapter(fmt: OutputFormat) -> OutputPort` helper
  - Dispatches on `OutputFormat.JSON` → `JsonOutput()`, `OutputFormat.RICH` → `RichOutput()`, `OutputFormat.PLAIN` → `PlainOutput()`

### CLI update: main.py (existing)
- [ ] Add `--output-format` as a global Typer option in `@app.callback()`
  - Type: `OutputFormat` enum
  - Default: `OutputFormat.JSON`
  - Store on `ctx.obj["deps"].output_adapter` via `create_output_adapter(format)`
- [ ] Remove hardcoded `output_adapter=JsonOutput()` from `build_deps()`
- [ ] Ensure `generate` command respects `deps.output_adapter` (already done via `deps.output_adapter.process_result` / `.error`)

### CLI update: show.py (existing)
- [ ] Remove `--output-format` flag from show command (it's now global)
- [ ] Remove any hardcoded format selection

### CLI update: version_cmd.py (existing)
- [ ] Refactor to use `deps.output_adapter` pattern
  - Add `ctx: typer.Context` parameter
  - Accept version text from `deps.output_adapter.message(ver)` or similar
  - Or use `process_result` with a special lightweight result type
  - For now: format version output manually based on output adapter type

### Dependencies
- [ ] Add `rich>=13.0` to `pyproject.toml` dependencies

### Write tests

#### test_rich_output.py (new, ~15 tests)
- [ ] `test_process_result_renders_rich_success` (AC: 1)
- [ ] `test_error_formats_rich_error_message` (AC: 1)
- [ ] `test_palette_display_renders_color_swatches` (AC: 1)
- [ ] `test_structural_subtyping` (AC: 1)
- [ ] `test_process_result_with_none_color_scheme` (edge case)
- [ ] `test_all_output_goes_to_stdout` (capsys check)
- [ ] `test_rich_output_never_raises` (with all error types)

#### test_plain_output.py (new, ~15 tests)
- [ ] `test_process_result_outputs_plain_text` (AC: 2)
- [ ] `test_error_outputs_plain_text_error` (AC: 2)
- [ ] `test_palette_display_outputs_hex_values` (AC: 2)
- [ ] `test_no_color_codes_in_output` (AC: 2)
- [ ] `test_structural_subtyping` (AC: 2)
- [ ] `test_plain_output_never_raises` (with all error types)
- [ ] `test_plain_output_format_matches_expected_pattern`

#### test_output_format_selection.py (new, ~8 tests)
- [ ] `test_create_output_adapter_returns_json_output` (AC: 3)
- [ ] `test_create_output_adapter_returns_rich_output` (AC: 3)
- [ ] `test_create_output_adapter_returns_plain_output` (AC: 3)
- [ ] `test_create_output_adapter_json_default` (AC: 3)

#### CLI-level tests (update or create)
- [ ] Update existing CLI tests if they reference `output_adapter` selection
- [ ] Test `--output-format` flag propagation from global callback (AC: 4)
- [ ] Test version command with all three output formats (AC: 5)

## Dev Notes

### Current State

The `OutputPort` protocol already exists at `ports/output.py:9-18`:
```python
@runtime_checkable
class OutputPort(Protocol):
    def process_result(self, result: GenerationResult) -> None: ...
    def error(self, exc: ColorSchemeError) -> None: ...
    def palette_display(self, scheme: ColorScheme) -> None: ...
```

`JsonOutput` already exists at `adapters/output/json_output.py` — full implementation with:
- `process_result()` — JSON payload with `success`, `color_scheme`, `output_files`, `backend`, `duration`
- `error()` — JSON with `success: False`, `error: {type, message, ...}`
- `palette_display()` — serializes ColorScheme as JSON

The `OutputFormat` enum is already defined at `domain/enums.py:57-62`:
```python
class OutputFormat(Enum):
    JSON = "json"
    RICH = "rich"
    PLAIN = "plain"
```

The `adapters/output/__init__.py` currently only exports `JsonOutput`. Must add `RichOutput` and `PlainOutput`.

**`cli/main.py`** currently hardcodes `output_adapter=JsonOutput()` in `build_deps()` at line 41. The `--output-format` flag must be added as a global Typer option in the callback.

**`factory.py`** has `CliDependencies.output_adapter: OutputPort | None = None` — no `create_output_adapter()` helper exists yet.

### Established Pattern (from JsonOutput)

- Class-based adapter implementing `OutputPort` protocol
- No constructor injection needed (stateless formatters)
- `capsys` fixture for testing stdout output
- `_make_color_scheme()` / `_make_result()` helper factories in test class
- Test pattern: call method → capture stdout via `capsys.readouterr()` → assert output shape
- Structural subtyping test: `assert isinstance(adapter, OutputPort)`
- Edge case: `error()` must never raise for any `ColorSchemeError` subclass — test with parametrized error list
- Edge case: `process_result()` with `None` color_scheme in result

### Rich API Hints

RichOutput should use these Rich API components:
- `rich.console.Console` — output to stdout by default
- `rich.table.Table` — structured data display
- `rich.panel.Panel` — error display with border styling
- `rich.text.Text` — styled text with colors
- `rich.color.Color` — for color swatch rendering
- `rich.style.Style` — for custom text styles

Example structure for `process_result()`:
```python
console = Console()
table = Table(title="Extraction Result")
table.add_column("Property", style="cyan")
table.add_column("Value")
table.add_row("Backend", result.backend.value)
table.add_row("Duration", f"{result.duration:.2f}s")
# ...
console.print(table)
```

For `palette_display()`:
```python
console = Console()
# Show background, foreground, cursor as colored squares
console.print(f"[on #{bg.hex[1:]}]{' ' * 20}[/] Background: {bg.hex}")
# Show 16 colors in a row
for color in scheme.colors:
    console.print(f"[on #{color.hex[1:]}]{' ' * 10}[/] {color.hex}", end=" ")
console.print()
```

### PlainOutput Format Specification

PlainOutput output must be deterministic and grep-friendly:
```
Success
Backend: custom
Duration: 1.50s
Output files:
  /tmp/color-scheme/colors.json
  /tmp/color-scheme/colors.sh
```

Error format:
```
Error: InvalidImageError
Message: Invalid image /bad.jpg: corrupt header
Image path: /bad.jpg
Reason: corrupt header
```

Palette display:
```
Background: #1a1b26
Foreground: #c0caf5
Cursor: #f7768e
Colors: #1a1b26 #... (16 hex values space-separated)
```

### Output Format Selection Architecture

The `--output-format` flag is a **global** Typer option defined in `@app.callback()`, not a per-command flag. The factory function `create_output_adapter(fmt)` is called once during the callback and the adapter is stored on `ctx.obj["deps"].output_adapter`.

This means:
- `build_deps()` no longer creates a default `output_adapter`
- The callback sets it after parsing `--output-format`
- All commands read `deps.output_adapter` — no command knows about format selection

For `version`, the command needs access to `deps.output_adapter`. Refactor `version_cmd.py` to accept `ctx: typer.Context` and use `ctx.obj["deps"].output_adapter`. The version output can be wrapped as a simple `GenerationResult`-like payload or use a new lightweight method. Since `OutputPort` only has 3 methods, use `palette_display` shape:
- JSON: `{"version": "0.1.0"}`
- Rich: Rich-formatted text like `"color-scheme-generator v0.1.0"`
- Plain: `"color-scheme-generator 0.1.0"`

For version, the simplest approach is to add a `message` method to `OutputPort` (or handle version specially). Since adding to the protocol would require updating all adapters, handle version output inline in the version command by checking the adapter type or keeping version independent.

**Recommended approach for version**: Keep version's own output logic simple — detect the format from `deps.output_adapter`'s class (or add a lightweight format indicator) and format accordingly. Or better: output version directly in the version command based on the resolved `--output-format` from the callback. Simplest: the version command stores its own format selection and formats independently.

### CLI Architecture for Global Flags

Current `main.py`:
```python
@app.callback()
def main_callback(ctx: typer.Context) -> None:
    ctx.obj = {"deps": build_deps()}
```

Target:
```python
@app.callback()
def main_callback(
    ctx: typer.Context,
    output_format: OutputFormat = typer.Option(OutputFormat.JSON, "--output-format", ...),
) -> None:
    ctx.obj = {"deps": build_deps()}
    ctx.obj["deps"].output_adapter = create_output_adapter(output_format)
```

The `build_deps()` function no longer creates a default output adapter — it's set in the callback.

### Conventions & Constraints

- `JsonOutput`, `RichOutput`, `PlainOutput` are independent classes — no shared base class, no inheritance from each other
- All three implement `OutputPort` structural protocol
- RichOutput depends on `rich>=13.0` external library (must add to pyproject.toml)
- PlainOutput uses only stdlib (`print()`) — zero external deps
- `error()` must handle ALL `ColorSchemeError` subclasses without raising
- `error()` must also handle unknown/unexpected `ColorSchemeError` subclasses gracefully (tested in JsonOutput at `test_json_output.py:239-253`)
- All output goes to stdout (not stderr) — consistent with JsonOutput
- No color codes or ANSI escape sequences in PlainOutput (even for error messages)
- All three adapters must satisfy structural subtyping: `isinstance(obj, OutputPort)` returns True

### Previous Story Intelligence (from 2.6)

- **Review findings to pre-apply** (from 2.6 review patches):
  - All new exceptions exported from `domain/__init__.py` and `errors.py` (not applicable here — no new exceptions)
  - No bare Python exceptions — wrap all I/O in domain exceptions
  - Coverage target: all acceptance criteria covered by tests
  - Ruff clean required for all new/modified files
- **Test count target**: ~38+ tests (two new adapters + factory tests + CLI-level tests)
- **All existing ~218 tests must pass** — zero regressions
- **Ruff clean required** for all new/modified files

### Previous Story Patterns (from 2.5 review, inherited via 2.6)

- No `Path.home()` at import time — defer to lazy evaluation (not applicable here but good practice)
- `isinstance` guards on file content reads (not applicable but pattern awareness)
- No bare exceptions — wrap all I/O in domain exceptions
- Tests use `unittest.mock` (patch, MagicMock) where needed
- `capsys` fixture for stdout capture

### Architecture Plan Reference

From `ARCHITECTURE_PLAN.md:121`:
```
| `JsonOutput` / `RichOutput` / `PlainOutput` | `OutputPort` | Per WEG: status JSON by default ({"success": ...}, {"error": {"type":..., "message":...}}), Rich for humans, Plain for pipes |
```

From `ARCHITECTURE_PLAN.md:96`:
```
| `OutputPort` | `process_result(result)`, `palette_display(scheme)`, ..., `error(exc)`, ... — takes **domain objects** | Outbound |
```

From `ARCHITECTURE_PLAN.md:396-397`:
```
Global:
  --output-format json|rich|plain               (default: json)  — selects OutputPort adapter
```

From `ARCHITECTURE_PLAN.md:537`:
```
| `rich` | >= 13.0 | rich output adapter | PyPI |
```

From `ARCHITECTURE_PLAN.md:703`:
```
`create_output_adapter(fmt)` — dispatches on `OutputFormat`.
```

### File naming convention for output

Output files follow the pattern: `<output_dir>/colors.<format>` where format is the ColorFormat value (already handled by LocalProcessor — not changing in this story).

### Test patterns to follow

Follow the existing test patterns from `tests/unit/adapters/output/test_json_output.py`:
- Class-based test suite (`TestRichOutput`, `TestPlainOutput`)
- `capsys` fixture for stdout capture
- `pytest.raises` for exception testing
- Helper methods `_make_color_scheme()` and `_make_result()`
- Edge case: `error()` with unknown `ColorSchemeError` subclass
- Edge case: `error()` with all error types — never raises
- Structural subtyping test

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Dev Notes from Previous Story (2.6)

- Follow established adapter pattern (JsonOutput is reference)
- Pre-apply review findings from 2.6
- All ~218 existing tests must pass — zero regressions
- Ruff clean required for all new/modified files
- Test count target: ~38 tests minimum

### Post-implementation verification

```bash
cd src/cli-tools/color-scheme-generator
pytest
ruff check --fix
```

### Implementation Plan

1. Add `rich>=13.0` to `pyproject.toml` dependencies
2. Create `adapters/output/rich_output.py` — RichOutput implementing OutputPort (AC: 1)
3. Create `adapters/output/plain_output.py` — PlainOutput implementing OutputPort (AC: 2)
4. Update `adapters/output/__init__.py` — export both new adapters
5. Add `create_output_adapter(fmt)` to `factory.py` (AC: 3)
6. Update `cli/main.py` — add `--output-format` global option in callback, remove hardcoded adapter from `build_deps()` (AC: 4)
7. Update `cli/show.py` — ensure it reads from `deps.output_adapter` (already done)
8. Refactor `cli/version_cmd.py` — support `--output-format` via global flag and `deps.output_adapter` (AC: 5)
9. Write tests for RichOutput (~15 tests)
10. Write tests for PlainOutput (~15 tests)
11. Write tests for output format selection (~8 tests)
12. Run full test suite and ruff

### Completion Notes

### Dependencies

- New PyPI dependency: `rich>=13.0` (add to pyproject.toml)
- Uses built-in `print()` for PlainOutput (no external deps)
- Uses `rich.console.Console`, `rich.table.Table`, `rich.panel.Panel` for RichOutput

### References

- [Source: epics.md:443-469] Story 2.7 acceptance criteria
- [Source: ARCHITECTURE_PLAN.md:121] RichOutput/PlainOutput adapter spec
- [Source: ARCHITECTURE_PLAN.md:396-397] --output-format global flag specification
- [Source: ARCHITECTURE_PLAN.md:537] rich>=13.0 dependency
- [Source: ARCHITECTURE_PLAN.md:703] create_output_adapter helper
- [Source: ports/output.py] OutputPort Protocol
- [Source: domain/enums.py:57-62] OutputFormat enum
- [Source: domain/models.py] GenerationResult, ColorScheme, Color models
- [Source: adapters/output/json_output.py] Reference implementation
- [Source: tests/unit/adapters/output/test_json_output.py] Test patterns to follow
- [Source: factory.py] Factory to add create_output_adapter to
- [Source: cli/main.py] CLI to add --output-format global option
- [Source: cli/show.py] Show command to verify
- [Source: cli/version_cmd.py] Version command to refactor

### Review findings pre-applied (from 2.6 review)

Prevent re-review of issues already caught in 2.6:
1. No broad `except Exception` — catch specific exceptions only
2. All error serialization must handle unknown `ColorSchemeError` subclasses gracefully
3. PlainOutput must not emit any ANSI/terminal escape codes
4. RichOutput must not crash if terminal doesn't support colors (Rich handles this automatically)
5. Factory typed to port interface (`OutputPort`) not concrete class
6. Consistent test patterns — follow `test_json_output.py` exactly

## File List

### New files
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/output/rich_output.py` (new — RichOutput implementing OutputPort)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/output/plain_output.py` (new — PlainOutput implementing OutputPort)
- `src/cli-tools/color-scheme-generator/tests/unit/adapters/output/test_rich_output.py` (new tests)
- `src/cli-tools/color-scheme-generator/tests/unit/adapters/output/test_plain_output.py` (new tests)
- `src/cli-tools/color-scheme-generator/tests/unit/adapters/output/test_output_format_selection.py` (new tests)

### Modified files
- `src/cli-tools/color-scheme-generator/pyproject.toml` (add rich dependency)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/output/__init__.py` (export new adapters)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/factory.py` (add create_output_adapter)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/main.py` (add --output-format global option)
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/version_cmd.py` (add --output-format support)

## Change Log

- 2026-07-17: Created comprehensive story spec for Rich + Plain Output Adapters
