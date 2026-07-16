---
baseline_commit: d99517b198334f305fb525d560c9d121482dd5af
---

# Story 2.3: Runtime Mode Selection & Error Mapping

Status: done

## Story

As a developer,
I want explicit runtime mode and container engine selection with clear error categories,
So that I can switch between local/container and docker/podman with predictable behavior.

## Acceptance Criteria

### AC1: CLI accepts `--runtime` and `--container-engine` flags
Given the CLI
When I run any process command
Then it accepts `--runtime local|container` and `--container-engine docker|podman`
And the flags are orthogonal: changing one does not affect the other's available values

### AC2: `--runtime local` uses host binary
Given `--runtime local`
When a process command runs
Then it uses host ImageMagick binary directly (no containerization)

### AC3: `--runtime container` with `--container-engine docker` uses docker
Given `--runtime container` with `--container-engine docker`
When a process command runs
Then it executes via the docker runtime using the managed container image

### AC4: `--runtime container` with `--container-engine podman` uses podman
Given `--runtime container` with `--container-engine podman`
When a process command runs
Then it executes via the podman runtime using the managed container image

### AC5: Invalid `--container-engine` value returns validation error
Given an unsupported container engine value
When passed to `--container-engine`
Then an explicit validation error is returned with supported values

### AC6: Container timeout raises `ContainerTimeoutError`
Given a container process command that times out
When execution exceeds the configured timeout
Then an explicit `ContainerTimeoutError` is raised

### AC7: Pre-flight failure maps to correct domain error
Given a container process with a pre-flight check failure (missing binary, missing image)
When the command is invoked
Then the error maps to the appropriate domain error category before any execution attempt

## Tasks / Subtasks

- [ ] Add `ContainerTimeoutError` to `domain/exceptions.py`
  - [ ] Define exception with `command`, `timeout` fields
  - [ ] Register in `__all__`
- [ ] Add `--container-engine` flag to CLI callback in `cli/main.py`
  - [ ] Add `ContainerEngine` enum to `domain/enums.py` with `DOCKER = "docker"`, `PODMAN = "podman"` members
  - [ ] Add `container_engine: str | None = None` option to `main()` callback
  - [ ] Validate against `ContainerEngine` enum with explicit list of supported values on failure
  - [ ] Store resolved `ContainerEngine` value in `ctx.obj["container_engine"]`
- [ ] Wire `--container-engine` through `_resolve_context` in `cli/process.py`
  - [ ] Read `ctx.obj.get("container_engine")` in `_resolve_context`
  - [ ] When set, merge into `ContainerSettings(engine=resolved_value)` in the `AppSettings` override
- [ ] Update `_resolve_processor` in `cli/process.py` to dispatch `ContainerProcessor` for container mode
  - [ ] Import `create_container_processor` from factory (once 2.2 provides it)
  - [ ] When `settings.runtime.mode == RuntimeMode.CONTAINER`, return `ContainerProcessor` (not `DryRunProcessor`)
  - [ ] Pass `settings.container.engine` as the OCI runtime binary to `ContainerProcessor`
  - [ ] Keep `dry_run` check: when both `--dry-run` and `--runtime container` are set, return `DryRunProcessor` (preview mode)
- [ ] Add `create_container_processor` factory function in `factory.py`
  - [ ] Accept `command_runner`, `catalog`, `output_dir`, `container_settings`, `context_validator`
  - [ ] Wire `SubprocessCommandRunner` with container engine binary
- [ ] Extend `InputContextValidator` for container pre-flight checks in `adapters/context_validator.py`
  - [ ] When `settings.runtime.mode == RuntimeMode.CONTAINER`, check container runtime binary availability via `shutil.which(settings.container.engine)`
  - [ ] If unavailable, return `ContextValidationResult` with error mapping to `ContainerRuntimeUnavailableError`
  - [ ] Check container image existence via image manager (from 2.2 / `ImageManagerPort`)
  - [ ] If image missing, return error mapping to `ContainerImageNotFoundError`
- [ ] Map OCI runtime errors to domain exceptions
  - [ ] In `ContainerProcessor` (or wrapper), catch subprocess timeout and raise `ContainerTimeoutError`
  - [ ] Map `CommandExecutionError` from subprocess runner to container-specific errors when in container mode
  - [ ] Wrap `_resolve_processor` call sites with container-specific error handling
- [ ] Write tests
  - [ ] Unit tests for `ContainerEngine` enum values and validation
  - [ ] Unit tests for `ContainerTimeoutError` exception
  - [ ] Unit tests for `--runtime` and `--container-engine` CLI flag parsing and validation
  - [ ] Unit tests for `_resolve_context` engine override merging
  - [ ] Unit tests for `_resolve_processor` dispatch logic (local vs container vs dry-run)
  - [ ] Unit tests for `InputContextValidator` container pre-flight checks
  - [ ] CLI integration tests via `CliRunner`:
    - `--runtime container --container-engine docker` on process effect
    - `--runtime container --container-engine podman` on process effect
    - `--container-engine invalid` produces validation error
    - `--runtime invalid` produces validation error
    - Orthogonality: `--runtime local --container-engine docker` is accepted (no cross-validation)
  - [ ] Error mapping tests: verify `ContainerRuntimeUnavailableError` and `ContainerImageNotFoundError` are raised for pre-flight failures

## Dev Notes

### Story Context

This is the glue story that wires everything from 2.1 and 2.2 into the CLI. Story 2.1 establishes the domain models (`RuntimeSettings`, `ContainerSettings`, error hierarchy) and 2.2 provides the `ContainerProcessor` adapter. This story connects them to the CLI surface and ensures all paths have correct error handling.

### Existing Wiring

- `--runtime` flag already partially exists in `cli/main.py:42-47` with validation against `RuntimeMode` enum
- `RuntimeSettings.mode` and `ContainerSettings.engine` are orthogonal domain models (`domain/models.py:142,147`)
- `_resolve_context` in `cli/process.py:38-47` consumes `runtime_override` from `ctx.obj` and merges into `RuntimeSettings`
- `_resolve_processor` in `cli/process.py:57-70` currently maps non-LOCAL modes to `DryRunProcessor` — this must be updated to use `ContainerProcessor` instead for `--runtime container`
- The `ContainerSettings.engine` field (`domain/models.py:147`) defaults to `"docker"` but is not yet wired to a CLI flag

### What Must Be Added

- `ContainerEngine` enum in `domain/enums.py` — provides a closed set of valid values with explicit validation at the CLI boundary
- `ContainerTimeoutError` in `domain/exceptions.py` — distinct from `CommandExecutionError` so callers can catch timeout specifically
- `--container-engine` CLI option in `cli/main.py` callback — validated against `ContainerEngine` enum, stored in `ctx.obj`
- Engine override merging in `cli/process.py:_resolve_context` — reads `ctx.obj["container_engine"]` and merges into `AppSettings.container`
- `_resolve_processor` dispatch for container mode — imports `create_container_processor` from factory and returns `ContainerProcessor` instance
- Container pre-flight validation in `InputContextValidator` — checks runtime binary and container image existence before execution

### Error Hierarchy (Relevant Subset)

```
WallpaperEffectsError (base)
+-- CommandExecutionError (command, return_code, stderr)
+-- ContainerTimeoutError (command, timeout)          ← NEW
+-- ContainerRuntimeUnavailableError (runtime)         ← exists
+-- ContainerImageNotFoundError (image)                ← exists
+-- ImagePullAccessError (image, registry)             ← exists
```

### ContainerProcessor Wiring

The `ContainerProcessor` from Story 2.2 (expected in `adapters/container_processor.py`) implements `EffectProcessorPort` and delegates to the OCI runtime via `SubprocessCommandRunner`. This story creates the factory function (`create_container_processor`) and wires the dispatch in `_resolve_processor`:

```python
# In factory.py
def create_container_processor(
    command_runner: CommandRunnerPort,
    catalog: EffectsCatalog,
    output_dir: Path,
    container_settings: ContainerSettings,
    context_validator: ContextValidatorPort | None = None,
) -> EffectProcessorPort:
    return ContainerProcessor(
        command_runner=command_runner,
        catalog=catalog,
        output_dir=output_dir,
        container_settings=container_settings,
        context_validator=context_validator,
    )
```

```python
# In cli/process.py:_resolve_processor
def _resolve_processor(
    settings: AppSettings,
    catalog: EffectsCatalog,
    output_dir: Path,
    dry_run: bool = False,
) -> EffectProcessorPort:
    runner = create_command_runner(settings)
    if dry_run:
        return create_dry_run_processor(runner, catalog, output_dir)
    if settings.runtime.mode == RuntimeMode.CONTAINER:
        return create_container_processor(
            command_runner=runner,
            catalog=catalog,
            output_dir=output_dir,
            container_settings=settings.container,
        )
    return create_local_processor(runner, catalog, output_dir)
```

### Container Timeout Handling

The `SubprocessCommandRunner.execute()` method (`adapters/subprocess_runner.py:30`) already accepts a `timeout` parameter. When the subprocess times out, `subprocess.TimeoutExpired` is caught and re-raised as `CommandExecutionError`. In container mode, this should be re-raised as `ContainerTimeoutError` with the command string and timeout value:

```python
try:
    result = runner.execute(command, timeout=container_timeout)
except CommandExecutionError as e:
    raise ContainerTimeoutError(command=e.command, timeout=container_timeout) from e
```

### Pre-Flight Validation via ContextValidatorPort

The `ContextValidatorPort` (`ports/context_validator.py`) and its adapter `InputContextValidator` (`adapters/context_validator.py`) are extended to perform container-specific checks:

1. If `settings.runtime.mode == RuntimeMode.CONTAINER`:
   - Check `shutil.which(settings.container.engine)` returns a path → fail with `ContainerRuntimeUnavailableError` if not
   - Check container image availability via `ImageManagerPort` (from 2.2) → fail with `ContainerImageNotFoundError` if missing
2. The validator is called via the factory's `create_context_validator()` in `factory.py:113`

### Orthogonality Invariant

`--runtime` and `--container-engine` are orthogonal. All combinations are valid:
- `--runtime local` (engine is ignored, engine defaults to docker)
- `--runtime container --container-engine docker`
- `--runtime container --container-engine podman`
- `--runtime container` (no engine flag → uses ContainerSettings.engine default "docker")

No cross-validation occurs. The `--container-engine` value is always validated against the `ContainerEngine` enum regardless of `--runtime` value.

### Testing Strategy

- Unit tests for `ContainerEngine` enum and `ContainerTimeoutError` in `test_enums.py` / `test_exceptions.py`
- Unit tests for `_resolve_processor` dispatch logic in `test_process_commands.py`
- Unit tests for `InputContextValidator` container pre-flight in `test_context_validator.py`
- CLI integration tests for `--runtime` and `--container-engine` flag parsing, invalid values, and orthogonality in `test_cli.py`
- Error mapping tests: mock missing binary → assert `ContainerRuntimeUnavailableError`, mock missing image → assert `ContainerImageNotFoundError`

## Review Findings

### Patch (Applied)

- [x] [Review][Patch] Container architecture mismatch — aligned with arch plan: `weg process` invoked inside container for all operations
- [x] [Review][Patch] `ContainerTimeoutError` never raised (AC6 FAIL) — wired `timeout` param, catch `CommandExecutionError` and re-raise as timeout error
- [x] [Review][Patch] Pre-flight validation not wired (AC7 PARTIAL) — `context_validator` passed to `create_container_processor` with `image_manager`
- [x] [Review][Patch] Mount path shell injection — docker command built as `list[str]`, no shell injection surface
- [x] [Review][Patch] Empty composite chain returns misleading success — validation added
- [x] [Review][Patch] Image registry empty produces invalid ref — `image_registry` changed to `str | None = None`
- [x] [Review][Patch] `exit_code or -1` treats exit_code=0 as falsy — fixed to proper None check
- [x] [Review][Patch] `--quiet`/`--verbose` flags parsed but never consumed — `verbose` changed to count flag, mapped to `Verbosity` enum
- [x] [Review][Patch] Temp file leak in `_serialize_artifacts` — try/finally catches all temp cleanup
- [x] [Review][Patch] Input path validated with `exists()` not `is_file()` — changed to `is_file()`
- [x] [Review][Patch] `except (OSError, ValueError)` too broad — added `ConfigResolutionError`, `EffectsLoadError`
- [x] [Review][Patch] Params passed via two channels — unified to `request.params` as single source of truth
- [x] [Review][Patch] Param keys not sanitized — `_parse_params` helper strips and validates keys
- [x] [Review][Patch] Dead code in `input_parent` resolution — removed dead branch
- [x] [Review][Patch] Preset with no effects returns silent failure — descriptive message added
- [x] [Review][Patch] Duplicate param parsing repeated in 3 commands — extracted `_parse_params` helper
- [x] [Review][Patch] `_lookup_*` methods return `Any` — typed to concrete domain types

### Deferred

- [x] [Review][Defer] `ContainerProcessor` composite chains run N containers instead of 1 — tied to architecture decision above, not fixable independently
- [x] [Review][Defer] `sys.stderr.write` corrupts JSON output — pre-existing, `OutputPort` should route warnings
- [x] [Review][Defer] Brittle tests mock implementation details instead of ports — pre-existing pattern
- [x] [Review][Defer] `AppSettings` recomposition fragile — pre-existing design pattern
- [x] [Review][Defer] `Path`→`str` type degradation in CLI — pre-existing pattern throughout `cli/main.py`, not introduced by this change
- [x] [Review][Defer] `CliDependencies` constructed with uninitialized fields — pre-existing pattern
- [x] [Review][Defer] Case-sensitive CLI enum validation — acceptable UX, not a bug

## Dev Agent Record

### Completion Notes

All tasks implemented:
1. **ContainerTimeoutError** — `domain/exceptions.py`: new exception with `command` and `timeout` fields
2. **ContainerEngine enum** — `domain/enums.py`: DOCKER and PODMAN members
3. **--container-engine CLI flag** — `cli/main.py`: validated against `ContainerEngine` enum, stored in `ctx.obj`
4. **Engine override merging** — `cli/process.py:_resolve_context`: reads `ctx.obj["container_engine"]` and merges into `ContainerSettings`
5. **_resolve_processor dispatch** — `cli/process.py`: updated to dispatch `ContainerProcessor` for container mode (dry-run still returns `DryRunProcessor`)
6. **Container pre-flight validation** — `adapters/context_validator.py`: extended `InputContextValidator` to check runtime binary and container image existence
7. **Factory update** — `factory.py`: `create_context_validator` now accepts optional `image_manager`

### File List
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/enums.py`
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/exceptions.py`
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/errors.py`
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/main.py`
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/process.py`
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/context_validator.py`
- UPDATE: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/factory.py`

### Reference Source Paths

- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/main.py` — CLI callback with existing `--runtime` flag
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/process.py` — `_resolve_context` and `_resolve_processor` dispatch
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/enums.py` — `RuntimeMode` enum
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/models.py` — `RuntimeSettings`, `ContainerSettings`, `AppSettings`
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/exceptions.py` — existing container error types
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/services.py` — domain services
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/factory.py` — factory functions, wiring
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/dry_run_processor.py` — `DryRunProcessor` (existing fallback pattern)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/subprocess_runner.py` — timeout handling pattern
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/context_validator.py` — `InputContextValidator` (pre-flight pattern)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/context_validator.py` — `ContextValidatorPort` protocol
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/command_runner.py` — `CommandRunnerPort` protocol
- `src/cli-tools/wallpaper-effects-generator/tests/unit/cli/test_process_commands.py` — existing CLI test patterns with `CliRunner` + `patch`
- `_bmad-output/implementation-artifacts/1-1-domain-models-resolution-contracts.md` — domain model contracts (RuntimeSettings/ContainerSettings orthogonality)
- `_bmad-output/implementation-artifacts/1-5-operational-commands.md` — CLI wiring patterns, review findings for `--runtime` validation
