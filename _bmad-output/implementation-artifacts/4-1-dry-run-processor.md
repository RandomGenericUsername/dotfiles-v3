---
baseline_commit: 8b19e87
---

# Story 4.1: Dry-Run Processor

Status: review

## Story

As a maintainer debugging a CI failure,
I want to pre-flight a command without executing it,
So that I can validate inputs, backends, and params before running.

## Acceptance Criteria

### AC 1: Full validation on dry-run
**Given** DryRunProcessor implementing ColorSchemeProcessorPort
**When** process_generate() or process_show() is called with --dry-run
**Then** it validates: input exists and is readable, backend available (local) or engine+image available (container), output dir writable, templates dir resolvable, all --param overrides coerce cleanly against BACKEND_DEFINITIONS[backend].parameters
**And** renders the resolved command via OutputPort without executing

### AC 2: Container mode skips host backend check
**Given** dry-run in container mode with no host backend
**When** the backend is not installed on the host
**Then** it does NOT check host-side is_available — only validates engine availability + image existence
**And** does NOT attempt to pull the image — only checks existence

### AC 3: Invalid param produces clear error
**Given** dry-run with invalid --param values
**When** validation fails
**Then** it raises the first validation error with a clear message

## Tasks / Subtasks

### Refactor DryRunProcessor constructor with dependencies
- [x] Update `DryRunProcessor.__init__()` to accept: `backend_catalog_loader: BackendCatalogLoaderPort`, `container_runtime: ContainerRuntimePort | None`, `output_adapter: OutputPort`, `template_dir_resolver: TemplateDirResolver | None`, `backend_registry: dict[Backend, PaletteGeneratorPort]` (AC: 1)
  - `backend_catalog_loader` — for parameter schema validation
  - `container_runtime` — for engine/image validation (None in local mode)
  - `output_adapter` — to render resolved command without executing
  - `template_dir_resolver` — for templates dir validation
  - `backend_registry` — for backend availability check in local mode
- [x] Update factory.py `create_dry_run_processor()` to wire all dependencies (AC: 1)

### Implement pre-flight validation
- [x] Implement `_pre_flight_generate(request, settings)`:
  - [x] Validate input image exists and is readable (`request.image_path.is_file()`) (AC: 1)
  - [x] Validate output dir is writable (`request.config.output_dir`) — check parent exists or can be created (AC: 1)
  - [x] Validate templates dir resolvable — use `template_dir_resolver.resolve()` or fallback path logic from `ContainerProcessor` (AC: 1)
  - [x] If local mode (`settings.runtime.mode == RuntimeMode.LOCAL`): check backend is registered in `backend_registry` (AC: 1)
  - [x] If container mode (`settings.runtime.mode == RuntimeMode.CONTAINER`): check engine is available (`container_runtime` not None), check image exists via `container_runtime.image_exists()`, do NOT pull image, do NOT check host-side backend availability (AC: 2)
- [x] Implement `_validate_params(backend, params, settings)`:
  - [x] Look up BackendDefinition for the target backend from catalog (AC: 3)
  - [x] For each param in `params`: find matching BackendParameterDefinition by name, attempt type coercion (AC: 3)
  - [x] If coercion fails: raise the first validation error with param name, expected type, and received value (AC: 3)
  - [x] If param is unknown (not in BackendDefinition.parameters): raise validation error (AC: 3)

### Implement process_generate with dry-run
- [x] In `process_generate()`: call `_pre_flight_generate()` and `_validate_params()`, build the resolved CLI command string, render via `output_adapter.process_result()` with a `GenerationResult` that contains the command plan as stderr/stdout, return `GenerationResult(success=True, ...)` (AC: 1)

### Implement process_show with dry-run
- [x] In `process_show()`: same pattern as `process_generate` but builds the `show` inner command instead of `generate` (AC: 1)

### Write tests
- [x] Unit test: `test_pre_flight_input_not_found` — missing input raises clear error (AC: 1)
- [x] Unit test: `test_pre_flight_local_backend_not_available` — unregistered backend raises error (AC: 1)
- [x] Unit test: `test_pre_flight_container_mode_checks_engine` — container mode validates engine availability (AC: 2)
- [x] Unit test: `test_pre_flight_container_mode_does_not_pull` — image existence check does not call `pull_image` (AC: 2)
- [x] Unit test: `test_pre_flight_container_mode_skips_host_check` — does not check host backend availability (AC: 2)
- [x] Unit test: `test_validate_params_invalid_type` — param with wrong type raises clear error (AC: 3)
- [x] Unit test: `test_validate_params_unknown_param` — unknown param raises error (AC: 3)
- [x] Unit test: `test_process_generate_returns_success_with_command` — dry-run returns command plan, not executed (AC: 1)
- [x] Unit test: `test_process_show_returns_success_with_command` — dry-run show returns command plan (AC: 1)
- [x] Unit test: `test_isinstance_check_passes` — update existing stub test to still pass
- [x] Run full test suite — verify zero regressions
- [x] Run ruff lint — clean

### Update existing tests and clean up stub
- [x] Remove/update `test_dry_run_processor_stub.py` — replace NotImplementedError tests with real behavior tests
- [x] Run full test suite — verify zero regressions

## Dev Notes

### Current State

**`adapters/dry_run_processor.py`** — empty stub (27 lines):
- Constructor takes no arguments
- Both `process_generate()` and `process_show()` raise `NotImplementedError`

**`factory.py`** — `create_dry_run_processor()` returns bare `DryRunProcessor()` with no wiring.

**Reference pattern** — `wallpaper-effects-generator/adapters/dry_run_processor.py`:
- Takes `command_runner`, `catalog`, `output_dir` plus optional services via DI
- `_pre_flight(request)` validates input exists, binary available, output dir writable
- Each `process_*` method: pre-flight → lookup → resolve params → render command → return result with command string

### Validation Error Design

All validation failures should raise specific `ColorSchemeError` subclasses or a single `PaletteGenerationError` with a clear message. The ACs require "raises the first validation error with a clear message" — do NOT aggregate errors.

Use existing domain exceptions where possible:
- `InvalidImageError` — bad input path
- `BackendNotAvailableError` — backend unavailable (local mode)
- `PaletteGenerationError` — generic validation failure with message
- `ContainerImageNotFoundError` — image missing (container mode)
- `ContainerRuntimeUnavailableError` — engine not available (container mode)

### Type Coercion Rules

`BackendParameterDefinition.type_` values from `backends.yaml`:
- `float` → coerce via `float(value)`
- `int` → coerce via `int(value)`
- `str` → accept as-is
- `choices` constraint → validate value is in the tuple

Use the same coercion logic pattern as the config resolver pipeline (AssembleConfiguration's override coercion).

### File Structure

| File | Action |
|------|--------|
| `src/color_scheme_generator/adapters/dry_run_processor.py` | MODIFY — implement full DryRunProcessor |
| `src/color_scheme_generator/factory.py` | MODIFY — wire dependencies in `create_dry_run_processor()` |
| `tests/unit/adapters/test_dry_run_processor_stub.py` | REPLACE — stub tests with real tests |
| `tests/unit/adapters/test_dry_run_processor.py` | CREATE — comprehensive test suite |

### Architecture Compliance

- **Hexagonal Architecture:** `DryRunProcessor` implements `ColorSchemeProcessorPort` (port/adapter boundary). It depends on ports (`BackendCatalogLoaderPort`, `ContainerRuntimePort`, `OutputPort`) and services (`TemplateDirResolver`), never on concrete adapters except through DI.
- **Runtime Parity:** Same validation flow for both local and container modes with mode-specific branches. Dry-run output is a rendered command plan, not execution results.
- **NFR-2 (Reliability):** Pre-flight catches configuration errors before execution, preventing partial failures and orphaned containers.
- **Dependency Rule:** Processor imports from domain and ports only. No circular deps.

### Previous Story Intelligence (3.x)

- Stories 3.1-3.4 established `ContainerProcessor` with mount logic, image selection, inner command construction, and error mapping via `map_oci_error()`.
- `container_processor.py` has the pattern for building inner commands (`_select_image()`, `_serialize_settings()`, mount list construction) — reference for command rendering in dry-run.
- `local_processor.py` has the pattern for `_generate_extract()` — reference for local backend lookup.
- Error mapping pattern from story 3.4 (`error_mapping.py`) should not be needed here since dry-run doesn't execute containers.

### Git Intelligence

- Current HEAD: `8b19e87` (feat: auto-commit story implementation)
- Branch: `master`
- Baseline commit for this story: `8b19e87`

### Testing Patterns

**Unit tests** with mocked dependencies:
```python
def test_pre_flight_input_not_found():
    from color_scheme_generator.adapters.dry_run_processor import DryRunProcessor
    from color_scheme_generator.domain.exceptions import InvalidImageError

    processor = DryRunProcessor(
        backend_catalog_loader=MagicMock(),
        container_runtime=None,
        output_adapter=MagicMock(),
        template_dir_resolver=MagicMock(),
        backend_registry={Backend.CUSTOM: MagicMock()},
    )
    request = GenerationRequest(
        image_path=Path("/nonexistent/input.png"),
        config=GeneratorConfig(backend=Backend.CUSTOM, params={}, ...),
    )
    settings = _make_settings(runtime_mode=RuntimeMode.LOCAL)

    with pytest.raises(InvalidImageError):
        processor.process_generate(request, settings)
```

**Parameter coercion tests:**
```python
def test_invalid_param_type():
    # Backend definitions loaded from mocked catalog
    # Verify param "clusters=abc" for pywal backend (expects int) raises clear error
```

### References

- [Source: epics.md#705-733] — Epic 4 and Story 4.1 acceptance criteria
- [Source: prd.md#105-116] — FR-5 Dry-Run Mode consequences
- [Source: epics.md#82-83] — FR-5 dry-run mode
- [Source: prd.md#1-7] — --dry-run / -n flag on generate and show
- [Source: wallpaper-effects-generator/adapters/dry_run_processor.py:1-190] — Reference implementation pattern
- [Source: adapters/container_processor.py:42-213] — ContainerProcessor inner command construction pattern
- [Source: adapters/local_processor.py:1-104] — LocalProcessor backend lookup pattern
- [Source: adapters/yaml_backend_catalog_loader.py:1-108] — Backend catalog loading and schema→domain conversion
- [Source: domain/models.py:82-98] — BackendParameterDefinition and BackendDefinition
- [Source: defaults/backends.yaml:1-76] — Backend parameter schemas (float, int, str, choices)

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

### Completion Notes List

- Implemented full DryRunProcessor with DI constructor accepting backend_catalog_loader, container_runtime (optional), output_adapter, template_dir_resolver (optional), backend_registry (optional)
- Implemented `_pre_flight_generate()` validating: input file exists, output dir writable, templates dir resolvable, local mode backend registration, container mode engine+image availability (no pull, no host check)
- Implemented `_validate_params()` with type coercion (float, int, str/choices) and unknown param detection
- Implemented `process_generate()` and `process_show()` building command plan via `_build_command_plan()` and rendering through OutputPort
- Updated factory.py `create_dry_run_processor()` with all dependency wiring
- Created comprehensive test suite: 11 tests covering pre-flight validation, param validation, process generate/show, container mode edge cases
- Updated stub test file to match new constructor signature
- Updated test_runtime_mode.py factory test to pass backend_catalog_loader mock
- Full test suite: 408 passed, 0 failed
- Ruff lint: clean

### File List

| File | Action |
|------|--------|
| `src/color_scheme_generator/adapters/dry_run_processor.py` | MODIFY |
| `src/color_scheme_generator/factory.py` | MODIFY |
| `tests/unit/cli/test_runtime_mode.py` | MODIFY |
| `tests/unit/adapters/test_dry_run_processor_stub.py` | REPLACE |
| `tests/unit/adapters/test_dry_run_processor.py` | CREATE |
| `src/color_scheme_generator/adapters/local_processor.py` | READ (reference only) |
| `src/color_scheme_generator/adapters/container_processor.py` | READ (reference only) |
| `src/color_scheme_generator/domain/models.py` | READ (reference only) |
| `src/color_scheme_generator/domain/exceptions.py` | READ (reference only) |
| `src/color_scheme_generator/domain/enums.py` | READ (reference only) |

## Change Log

- 2026-07-22: Implemented DryRunProcessor with DI constructor, pre-flight validation, param coercion, process_generate/show with command plan rendering, comprehensive test suite (12 tests), factory wiring updated
