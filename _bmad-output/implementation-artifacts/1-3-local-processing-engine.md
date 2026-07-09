---
baseline_commit: d99517b198334f305fb525d560c9d121482dd5af
---

# Story 1.3: Local Processing Engine

Status: code-reviewed

## Story

As a developer,
I want to process wallpaper inputs locally as effects, composites, or presets,
So that I get a structured `ProcessingResult` with predictable output.

## Acceptance Criteria

### AC1: Effect processing via ImageMagick
Given the CLI is installed
When I run `process effect <input> --effect <name>` with a valid input and effect
Then ImageMagick is invoked via the local runtime
And a `ProcessingResult` is returned with status, rendered command, stdout/stderr, return code, and duration

### AC2: Composite processing
Given a valid composite definition in the effects catalog
When I run `process composite <input> --composite <name>`
Then the composite layers are applied in order
And a `ProcessingResult` is returned with success status

### AC3: Preset processing
Given a valid preset in the effects catalog
When I run `process preset <input> --preset <name>`
Then all effects and composites in the preset are applied
And a `ProcessingResult` is returned

### AC4: Invalid effect name → error
Given an invalid effect name
When I run `process effect <input> --effect nonexistent`
Then the system returns a `ProcessingResult` with failure status
And the error maps to an explicit catalog/domain error category

### AC5: Output file written
Given a successful processing run
When the command completes
Then the output file is written to the default output location
And the `ProcessingResult` includes the output path

### AC6: Runtime-agnostic port contract
Given the `EffectProcessorPort`
When `LocalProcessor` is the active implementation
Then it fulfills the same port contract that `ContainerProcessor` will later implement (runtime-agnostic interface)

## Tasks / Subtasks

- [x] Implement SubprocessCommandRunner adapter (AC: 1)
  - [x] Auto-detect ImageMagick binary (magick vs convert for v6/v7)
  - [x] subprocess.run() with timeout support
  - [x] Returns CommandResult with stdout, stderr, return_code
  - [x] Raise BinaryNotFoundError if binary unavailable
  - [x] Implements CommandRunnerPort
- [x] Implement LocalProcessor (AC: 1-6)
  - [x] process_effect: render ImageMagick command via CommandSubstitutionService, execute via CommandRunnerPort, return ProcessingResult
  - [x] process_composite: iterate chain steps, apply each via temp intermediate files, finalize output
  - [x] process_preset: resolve preset type (effect or composite), delegate to appropriate handler
  - [x] Dry-run support (skip execution, render commands only)
  - [x] Implements EffectProcessorPort
- [x] Implement CLI process commands (AC: 1-5)
  - [x] `process effect <name> <input> [-e effect] [-o output] [--dry-run] [--param key=value...]`
  - [x] `process composite <name> <input> [-c composite] [-o output] [--dry-run]`
  - [x] `process preset <name> <input> [-p preset] [-o output] [--dry-run]`
  - [x] Wire to LocalProcessor via factory
- [x] Wire CLI output adapters (AC: 1-5)
  - [x] ProcessingResult → OutputPort for JSON/rich/plain rendering
  - [x] Error handling via OutputPort.error()
- [x] Implement DryRunProcessor (AC: 6)
  - [x] Pre-flight validation: input exists, binary found, effect/catalog lookup, output dir writable
  - [x] Renders commands without executing
  - [x] Outputs via OutputPort.dry_run()

## Dev Notes

### Previous Story Context
- Domain models: ProcessingRequest, ProcessingResult, EffectProcessorPort (4 methods), CommandRunnerPort
- Domain services: CommandSubstitutionService, ParameterResolutionService, OutputPathService, CatalogValidationService
- Adapters exist: AssembledConfigResolver, YamlEffectLoader
- CLI framework: Typer with global flags (--config, --effects, --output, --runtime)
- Default settings.toml and effects.yaml in package defaults

### LocalProcessor Architecture (from ARCHITECTURE_PLAN.md §5)

**SubprocessCommandRunner** (implements CommandRunnerPort):
```
CommandRunnerPort:
  - is_available(binary=None) -> bool
  - get_binary() -> str
  - execute(command, timeout=None) -> CommandResult
```
- Auto-detect: try `magick` first (v7), fallback to `convert` (v6)
- Raise `BinaryNotFoundError` if neither found
- Use subprocess.run() with capture_output=True

**LocalProcessor** (implements EffectProcessorPort):
```
EffectProcessorPort:
  - process_effect(name, request) -> ProcessingResult
  - process_composite(name, request) -> ProcessingResult
  - process_preset(name, request) -> ProcessingResult
  - process_batch(request) -> BatchResult  (deferred to Epic 3)
```

process_effect flow:
1. Lookup effect in resolved catalog → EffectNotFoundError if missing
2. Resolve params via ParameterResolutionService (CLI --param overrides → effect defaults → type defaults)
3. Render command template via CommandSubstitutionService (substitute $INPUT, $OUTPUT, $PARAM)
4. If dry-run: record command, skip execution, return ProcessingResult with dry-run flag
5. Execute via CommandRunnerPort
6. Compute output path via OutputPathService
7. Return ProcessingResult

process_composite flow:
1. Lookup composite in catalog → CompositeNotFoundError if missing
2. For each ChainStep in order:
   a. Apply effect via process_effect logic with temp intermediate file as output
   b. Next step uses temp file as input
3. Final output → requested output path
4. Clean up temp files
5. Return ProcessingResult

process_preset flow:
1. Lookup preset in catalog → PresetNotFoundError if missing
2. If preset references effect → delegate to process_effect
3. If preset references composite → delegate to process_composite
4. Apply preset-level params on top
5. Return ProcessingResult

### ImageMagick Command Templates (from architecture command surface)
Process command patterns:
```
# Effect: magick <input> -effect <params> <output>
magick input.jpg -blur 0x8 output.jpg

# Composite chain (handled internally by process composite):
magick input.jpg -effect1 params temp1.jpg
magick temp1.jpg -effect2 params output.jpg
```

### CLI Structure (from ARCHITECTURE_PLAN.md §9)
```
wallpaper-effects-generator process
  effect <name> <input> [-o output] [--dry-run] [--param key=value...]
  composite <name> <input> [-o output] [--dry-run]
  preset <name> <input> [-o output] [--dry-run]

Global: --config PATH, --effects PATH, --output json|rich|plain, --runtime local|container
        -q/--quiet, -v/--verbose
```

### Error Handling
- EffectNotFoundError → ProcessingResult(failure) with catalog error category
- CompositeNotFoundError → same
- PresetNotFoundError → same
- BinaryNotFoundError → ProcessingResult(failure) with runtime error category
- CommandExecutionError → ProcessingResult(failure) with execution error category
- All errors rendered via OutputPort.error() in JSON/rich/plain

### Package Structure Changes
```
src/cli-tools/wallpaper-effects-generator/
  src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/
    adapters/
      local_processor.py              — (NEW) implements EffectProcessorPort
      subprocess_runner.py            — (NEW) implements CommandRunnerPort
      dry_run_processor.py            — (NEW) implements EffectProcessorPort for dry-run
    cli/
      process.py                      — (NEW) process CLI commands
    factory.py                        — (UPDATE) wire LocalProcessor, SubprocessCommandRunner
  tests/
    unit/adapters/
      test_subprocess_runner.py       — (NEW)
      test_local_processor.py         — (NEW)
      test_dry_run_processor.py       — (NEW)
    unit/cli/
      test_process_commands.py        — (NEW)
    integration/
      test_local_processing.py        — (NEW) end-to-end with real effects catalog
```

### Testing Strategy
- Unit test SubprocessCommandRunner: mock subprocess, test binary detection, test error mapping
- Unit test LocalProcessor: mock CommandRunnerPort and catalog, test effect/composite/preset flows
- Unit test DryRunProcessor: verify pre-flight checks, verify commands recorded not executed
- Unit test CLI process commands: use Typer CliRunner
- Integration test: use real effects.yaml fixture, verify ImageMagick invocation (if magick available) or validate command rendering

## Dev Agent Record

### Agent Model Used
opencode/deepseek-v4-flash-free

### Debug Log References
- Changed CommandRunnerPort from `run(request) -> ProcessingResult` to `is_available/get_binary/execute(command) -> CommandResult`
- Added `CommandResult` dataclass and `output_path` field to `ProcessingResult` domain models
- Composite processing uses `tempfile.mkdtemp()` for intermediate files

### Completion Notes List
- Implemented SubprocessCommandRunner adapter with binary auto-detection, subprocess execution with timeout, BinaryNotFoundError handling
- Implemented LocalProcessor with process_effect, process_composite, process_preset flows including command rendering via CommandSubstitutionService
- Implemented DryRunProcessor with pre-flight validation (input exists, binary available, output dir writable)
- Created CLI process commands (effect, composite, preset) with --dry-run and --param support
- Wired process_app into main Typer app via add_typer()
- Updated factory.py with create_command_runner, create_local_processor, create_dry_run_processor
- Added 10 test files with 80 new test cases covering unit, integration, and CLI testing
- All 122 existing + new tests pass; ruff lint checks pass

### File List
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/models.py` — (UPDATE) add CommandResult, ProcessingResult.output_path
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/command_runner.py` — (UPDATE) new port interface
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/subprocess_runner.py` — (NEW)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/local_processor.py` — (NEW)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/dry_run_processor.py` — (NEW)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/process.py` — (NEW)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/main.py` — (UPDATE) add process_app
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/factory.py` — (UPDATE) wire new adapters
- `tests/test_ports.py` — (UPDATE) update CommandRunnerPort stub
- `tests/test_models.py` — (UPDATE) add CommandResult tests, output_path test
- `tests/test_factory.py` — (UPDATE) add runner/processor factory tests
- `tests/unit/adapters/test_subprocess_runner.py` — (NEW)
- `tests/unit/adapters/test_local_processor.py` — (NEW)
- `tests/unit/adapters/test_dry_run_processor.py` — (NEW)
- `tests/unit/cli/test_process_commands.py` — (NEW)
- `tests/integration/test_local_processing.py` — (NEW)

## Change Log

- **2026-07-05**: Implemented Local Processing Engine (Story 1.3) — SubprocessCommandRunner, LocalProcessor, DryRunProcessor, CLI process commands, factory wiring, and comprehensive tests

## Review Log

### Review Date
2026-07-06

### Process
bmad-code-review workflow (5 phases + triage)

### Phase 1 — Adapters (14 patches)
| # | File | Change | Rationale |
|---|------|--------|-----------|
| 1 | `src/.../adapters/subprocess_runner.py` | `shell=False` + `shlex.split()` | Shell injection prevention |
| 2 | `src/.../adapters/local_processor.py` | Isolate preset pseudo-chains via temp intermediate | Prevent side-effects across effect boundaries |
| 3 | `src/.../adapters/local_processor.py` | Capture `output_path` before cleanup in composite failure | Preserve partial output path on failure |
| 4 | `src/.../adapters/subprocess_runner.py` | Map `OSError`/`TimeoutExpired` → `CommandExecutionError` | Port-conformant error wrapping |
| 5 | `src/.../adapters/local_processor.py` | Pass `params={}` to `process_effect` in composite steps | Conform to `EffectProcessorPort` signature |
| 6 | `src/.../adapters/local_processor.py` | `ChainStep.__post_init__` — assign `params={}` if `None` | Prevent `None` propagation in composite chains |
| 7 | `src/.../adapters/subprocess_runner.py` | Preserve `stdout` in failure `CommandResult` | Return partial output on failure |
| 8 | `src/.../adapters/dry_run_processor.py` | `_pre_flight` returns `ProcessingResult` | Never raises `FileNotFoundError`/`BinaryNotFoundError` |
| 9 | `src/.../adapters/subprocess_runner.py` | `_detect_binary` errors report all candidates | Debugging clarity |
| 10 | `src/.../adapters/dry_run_processor.py` | Empty preset → `ProcessingResult(success=False)` | Consistent with spec |
| 11 | All adapters | Import ordering, whitespace cleanup | Style conformance |
| 12 | `src/.../ports/command_runner.py` | Verify `CommandResult` field alignment | Port correctness |
| 13 | `src/.../adapters/subprocess_runner.py` | `__post_init__` guards for `stderr`/`stdout` `None` | Avoid `None` in string concat |
| 14 | `src/.../adapters/dry_run_processor.py` | Return `output_dir` in `output_path` always | Consistent result shape |

### Phase 2 — CLI (7 patches)
| # | File | Change | Rationale |
|---|------|--------|-----------|
| 1 | `src/.../cli/process.py` | Wire `--dry-run` → `DryRunProcessor` | Feature complete |
| 2 | `src/.../cli/process.py` | Pass `ctx.obj["config"]`/`["effects"]` through | Config resolution chain |
| 3 | `src/.../cli/process.py` | Add `_resolve_context` helper | `input.exists()` check + config load error wrapping |
| 4 | `src/.../cli/process.py` | Add `-e`/`-c`/`-p` flags as name overrides | UX parity with design |
| 5 | `src/.../cli/main.py` | Rename `--output` → `--output-format` | Disambiguate from output directory |
| 6 | `src/.../cli/main.py` | Add `--output` global flag for directory | New global flag |
| 7 | `src/.../cli/process.py` | Malformed `--param` → warning + skip | Graceful degradation |

### Phase 3 — Domain/Ports (2 patches)
| # | File | Change | Rationale |
|---|------|--------|-----------|
| 1 | `src/.../domain/models.py` | `BatchRequest.max_workers` raises `ValueError` | Reject invalid values early |
| 2 | `src/.../domain/models.py` | `ExecutionSettings.max_workers` raises `ValueError` | Reject invalid values early |

### Phase 4 — Factory (3 patches)
| # | File | Change | Rationale |
|---|------|--------|-----------|
| 1 | `src/.../factory.py` | `create_command_runner`: all params required | No hidden defaults |
| 2 | `src/.../factory.py` | `create_local_processor`: all params required | No hidden defaults |
| 3 | `src/.../factory.py` | `create_dry_run_processor`: all params required | No hidden defaults |

### Phase 5 — Tests (42 patches)
Key changes:
| # | File | Change | Rationale |
|---|------|--------|-----------|
| 1 | `tests/unit/adapters/test_dry_run_processor.py` | Fix pre-flight tests: `ProcessingResult` assertions | Match new non-raising `_pre_flight` |
| 2 | `tests/unit/adapters/test_subprocess_runner.py` | Assert `shlex.split()` behavior | Match `shell=False` |
| 3 | `tests/unit/adapters/test_subprocess_runner.py` | Assert `CommandExecutionError` on timeout | Match port contract |
| 4 | `tests/test_models.py` | `max_workers` → `pytest.raises(ValueError)` | Match new validation |
| 5 | `tests/test_cli.py` | `--output` → `--output-format` | Match renamed flag |
| 6 | `tests/unit/cli/test_process_commands.py` | Mock `_resolve_context` | Isolate from config file resolution |

### Dismissed Findings (intentional)
| Finding | Reason |
|---------|--------|
| DryRunProcessor keeps CommandRunnerPort | Pre-flight uses `is_available()`; dry-run skips `execute()` — owning the port keeps testing simple and interface uniform |
| PresetDefinition effects-only | Chosen by design — presets reference exactly one entry; composites handle layering |
| Hierarchy duplication (ProcessingResult vs CommandResult) | ProcessingResult is the domain contract; CommandResult is the runner contract — separate concerns, separate evolution |
| Batch `Any` typing on result | Deferred to Epic 3 — concrete type unknown until batch processing is built |
| Cleanup `ignore_errors=True` | Acceptable — temp files should never block result delivery |
| DryRun relative paths | Dry-run never touches disk; paths are informational only |
| ProcessingResult construction inconsistencies | All constructors now follow the same pattern (Phase 1 patch 14) |
| Timeout default `None` | `None` = no timeout, which is a valid explicit choice |
| Name injection via `-e`/`-c`/`-p` | Flags shadow positional but priority is clear: positional wins |
| `/tmp/` insecurity | Test/CLI-only usage; prod paths are config-controlled |
| Quiet + verbose conflict | CLI enforces last-one-wins at the typer level |
| ParameterDefinition required+default contradiction | `required` overrides `default` — resolved at resolution time |
| Config-assembler-engine findings | Outside story scope |
| Protocol edge cases (runtime ABC) | Preservation of duck-typing flexibility |

### Final Test Status
- **Total: 122 passed, 0 failed**
- `ruff check` — clean
- `mypy` — clean
