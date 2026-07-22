# Story 3.1: Runtime Mode Wiring & Composition Root

Status: ready-for-dev

## Story

As a developer,
I want the composition root wired with runtime mode selection,
So that `--runtime` and `--container-engine` flags work orthogonally and
the correct processor (LocalProcessor / ContainerProcessor) is selected at runtime.

## Acceptance Criteria

### AC 1: CliDependencies with all ports and adapters

**Given** `factory.py` composition root
**When** the Typer app starts
**Then** `CliDependencies` are built in `@app.callback()` with all ports and adapters:
  - `config_resolver: AssembledConfigResolver`
  - `template_renderer: TemplateRendererPort`
  - `backend_registry: dict[Backend, PaletteGeneratorPort]`
  - `backend_catalog_loader: YamlBackendCatalogLoader`
  - `output_adapter: OutputPort`
  - `template_dir_resolver: TemplateDirResolver`
  - `container_engine: ContainerRuntimePort | None` (lazily created)
  - `processor: ColorSchemeProcessorPort` (selected by runtime mode)

**And** `create_*` helpers exist for: `config_resolver`, `template_renderer`,
`template_dir_resolver`, `backend_registry`, `backend_catalog_loader`,
`container_engine`, `output_adapter`

### AC 2: Runtime mode selection

**Given** `--runtime local` (default)
**When** the user runs `csg generate`
**Then** `LocalProcessor` is selected as the active processor
**When** `--runtime container` is passed
**Then** `ContainerProcessor` is selected

### AC 3: Container engine selection

**Given** `--container-engine docker` (default)
**When** container mode is active
**Then** `oci_runtime.factory.RuntimeFactory.create(RuntimePreference(RuntimeKind.DOCKER, "docker"))` is used
**When** `--container-engine podman` is passed
**Then** `RuntimePreference(RuntimeKind.PODMAN, "podman")` is used

### AC 4: ContainerRuntimePort abstraction

**Given** the `ContainerRuntimePort` protocol at `ports/container_runtime.py`
**When** container mode is selected
**Then** `ContainerProcessor` depends on `ContainerRuntimePort`, not directly on oci-runtime
**And** the port is resolved via `RuntimeFactory.create()` in the composition root
**And** the port is wrapped as a CSG-typed adapter

### AC 5: pyproject.toml entry point and deps

**Given** the `pyproject.toml` `[project.scripts]` entry point
**When** the package is installed
**Then** `csg` points to `color_scheme_generator.cli.main:app`

**Given** `[project.optional-dependencies]`
**When** `pip install color-scheme-generator[custom]` is run
**Then** pillow, numpy, scikit-learn are installed
**When** `pip install color-scheme-generator[pywal]` is run
**Then** pywal is installed

**Given** `oci-runtime` dependency
**When** the package is installed
**Then** oci-runtime is available (add to main `[project.dependencies]`)

## Tasks / Subtasks

### Factory: Update CliDependencies and create_* helpers
- [ ] Add `container_engine: ContainerRuntimePort | None` field to `CliDependencies` (AC: 1)
- [ ] Add `processor: ColorSchemeProcessorPort | None = None` field (replacing concrete `LocalProcessor` type) (AC: 1, 2)
- [ ] Create `create_container_engine(container_settings: ContainerSettings) -> ContainerRuntimePort` — wraps `RuntimeFactory.create()` (AC: 3, 4)
- [ ] Create `create_local_processor(backend_registry, template_renderer) -> LocalProcessor` (AC: 1)
- [ ] Create `create_container_processor(container_engine, default_templates_dir) -> ContainerProcessor` (lazy-import ContainerProcessor) (AC: 1, 4)
- [ ] Create `create_dry_run_processor(backend_registry, template_renderer) -> DryRunProcessor` (lazy-import DryRunProcessor) (AC: 1)

### CLI main.py: Global callback wiring
- [ ] Add `--runtime: RuntimeMode` global option with default `RuntimeMode.LOCAL` (AC: 2)
- [ ] Add `--container-engine: ContainerEngine` global option with default `ContainerEngine.DOCKER` (AC: 3)
- [ ] In `@app.callback()`, build deps including `container_engine` lazily (AC: 1)
- [ ] Select processor based on `runtime` mode: `LocalProcessor` for local, `ContainerProcessor` for container (AC: 2)
- [ ] Store deps on `ctx.obj["deps"]` — keep existing pattern (AC: 1)
- [ ] Keep backward compat: when no `processor` is set, fall back to existing behavior

### Domain exceptions: Add container error types
- [ ] Add `ContainerImageNotFoundError(image: str, backend: Backend)` (needed for error mapping in 3.4)
- [ ] Add `ContainerRuntimeUnavailableError(runtime: str)`
- [ ] Add `ImagePullAccessError(image: str, registry: str)`
- [ ] Add `ContainerTimeoutError`

### pyproject.toml: Add oci-runtime dependency
- [ ] Add `oci-runtime` to `[project.dependencies]` (AC: 5)
- [ ] Add dev deps if needed for testing

### Write tests
- [ ] Test `CliDependencies` construction with all fields (AC: 1)
- [ ] Test `create_container_engine` produces `ContainerRuntimePort` instance (AC: 3, 4)
- [ ] Test `--runtime local` selects LocalProcessor (AC: 2)
- [ ] Test `--runtime container` selects ContainerProcessor (AC: 2)
- [ ] Test `--container-engine docker` / `--container-engine podman` wiring (AC: 3)
- [ ] Test `@app.callback()` builds deps with both global flags (AC: 1)
- [ ] Test all existing tests still pass (regression)

## Dev Notes

### Current State

**`factory.py`** is minimal (68 lines):
- `CliDependencies` has: `backend_registry`, `backend_catalog_loader`, `config_resolver`, `output_adapter`, `processor: LocalProcessor | None`, `template_dir_resolver`, `template_renderer`. No `container_engine` field.
- `create_*` helpers: `create_backend_registry`, `create_backend_catalog_loader`, `create_template_dir_resolver`, `create_template_renderer`, `create_config_resolver`, `create_output_adapter`. No container-related helpers.
- `processor` field is typed as `LocalProcessor | None` — must become `ColorSchemeProcessorPort | None` to accommodate `ContainerProcessor` and `DryRunProcessor`.

**`cli/main.py`** (133 lines):
- `build_deps()` creates a `LocalProcessor` directly in `CliDependencies`
- `@app.callback()` only has `--output-format` global flag
- `generate()` and `show()` use `deps.processor` directly — no runtime mode switching
- All command registration via `app.command()(fn)` pattern
- Test pattern: `monkeypatch.setattr("color_scheme_generator.cli.main.build_deps", lambda: mock_deps)`

**`ports/container_runtime.py`** exists with `ContainerRuntimePort` protocol:
```python
@runtime_checkable
class ContainerRuntimePort(Protocol):
    def run(self, image: str, command: list[str], mounts: list[ContainerMount], timeout: int) -> ContainerResult: ...
    def image_exists(self, image: str) -> bool: ...
    def pull_image(self, image: str) -> None: ...
```

**`ContainerProcessor` does NOT exist** — must be created. It implements `ColorSchemeProcessorPort` via `ContainerRuntimePort`. It is stubbed here (full implementation is story 3.2). For this story, it can be a minimal class that:
- Accepts `container_runtime: ContainerRuntimePort`, `template_dir_resolver`, `default_settings_path`
- `process_generate` raises `NotImplementedError` (will be implemented in 3.2)
- `process_show` raises `NotImplementedError` (will be implemented in 3.2)

**`DryRunProcessor` does NOT exist** — must be created. Same pattern: stub for now.

**`oci-runtime`** API:
- `RuntimeFactory.create(RuntimePreference(kind=RuntimeKind.DOCKER, binary="docker"))` returns `ContainerEngine` (ABC with `.images`, `.containers`, `.is_available()`, `.version()`)
- `RuntimeFactory` is in `oci_runtime.factory`
- `RuntimePreference` is in `oci_runtime.domain.types`
- `RuntimeKind` is in `oci_runtime.domain.enums`
- The `create_container_engine` helper wraps this creation and returns a CSG-typed `ContainerRuntimePort` adapter

**Missing container exceptions** (in `domain/exceptions.py`):
```python
class ContainerImageNotFoundError(ColorSchemeError):
    def __init__(self, image: str, backend: Backend): ...
class ContainerRuntimeUnavailableError(ColorSchemeError):
    def __init__(self, runtime: str): ...
class ImagePullAccessError(ColorSchemeError):
    def __init__(self, image: str, registry: str): ...
class ContainerTimeoutError(ColorSchemeError): ...
```

### Architecture Compliance

- **ADR-006 (Runtime/Engine Orthogonality)**: `--runtime` and `--container-engine` are independent flags. `runtime.mode` decides WHERE (local/container); `container.engine` decides WHICH runtime (docker/podman). Changing one must not affect the other.
- **ADR-002 (Domain Port for Processing)**: `ColorSchemeProcessorPort` is the contract. `LocalProcessor`, `ContainerProcessor`, `DryRunProcessor` each implement it. The CLI selects by `--runtime` and `--dry-run` at the composition root.
- **ADR-013 (BackendRegistry)**: `factory.py` builds `dict[Backend, PaletteGeneratorPort]` — lookup table, no auto-detect iteration.
- **ADR-012 (Frozen Domain, Pydantic at Boundary)**: `oci-runtime` types are domain-level in CSG's port; the actual `RuntimeFactory` wrapping happens in the adapter layer (`create_container_engine` helper).

### Previous Story Intelligence (from 2.10)

- **Test patterns**: `CliRunner` with `runner.invoke(app, [...])`, monkeypatch `build_deps` on `color_scheme_generator.cli.main`
- **CLI pattern**: All commands use `ctx: typer.Context` and `deps: CliDependencies = ctx.obj["deps"]`
- **Ruff**: Must be clean for all new/modified files (line-length 100, py314 target, select E,F,I,N,W,UP,B ignore B905)
- **All 330 existing tests must pass** — zero regressions
- Default `OutputFormat` is `JSON`
- The `@app.callback()` sets `ctx.obj = {"deps": build_deps()}` then sets `output_adapter` separately

### Files to modify

| File | Action |
|------|--------|
| `src/color_scheme_generator/factory.py` | MODIFY — add container_engine field, add create_* helpers |
| `src/color_scheme_generator/cli/main.py` | MODIFY — add --runtime, --container-engine flags, runtime mode wiring |
| `src/color_scheme_generator/domain/exceptions.py` | MODIFY — add 4 container exception classes |
| `pyproject.toml` | MODIFY — add oci-runtime dependency |

### Files to create

| File | Action |
|------|--------|
| `src/color_scheme_generator/adapters/container_processor.py` | CREATE — stub ContainerProcessor (full impl in 3.2) |
| `src/color_scheme_generator/adapters/dry_run_processor.py` | CREATE — stub DryRunProcessor (full impl in 4.1) |
| `tests/unit/adapters/test_container_processor_stub.py` | CREATE — verify ContainerProcessor implements ColorSchemeProcessorPort |
| `tests/unit/adapters/test_dry_run_processor_stub.py` | CREATE — verify DryRunProcessor implements ColorSchemeProcessorPort |
| `tests/unit/cli/test_runtime_mode.py` | CREATE — --runtime and --container-engine flag tests |

### References

- [Source: epics.md#578-611] — Story 3.1 acceptance criteria with full AC detail
- [Source: ARCHITECTURE_PLAN.md#676-705] — factory.py wiring spec (CliDependencies, create_* helpers)
- [Source: ARCHITECTURE_PLAN.md#676-705] — `--param` parsing in CLI section
- [Source: ARCHITECTURE_PLAN.md#362-398] — CLI structure with --runtime and --container-engine flags
- [Source: ARCHITECTURE_PLAN.md#85-103] — Error hierarchy including container exceptions
- [Source: ARCHITECTURE_PLAN.md#53] — RuntimeSettings.mode vs ContainerSettings.engine orthogonality
- [Source: oci_runtime.factory:248-392] — `RuntimeFactory.create()` API
- [Source: oci_runtime.domain.types:247-255] — `RuntimePreference` dataclass
- [Source: oci_runtime.domain.enums:4-15] — `RuntimeKind` enum
- [Source: oci_runtime.ports.engine:12-37] — `ContainerEngine` ABC (`.images`, `.containers`, `.is_available()`)
- [Source: adapters/local_processor.py:21-104] — LocalProcessor reference implementation
- [Source: ports/container_runtime.py:1-23] — ContainerRuntimePort protocol definition
- [Source: ports/processor.py:1-19] — ColorSchemeProcessorPort protocol definition
- [Source: tests/unit/cli/test_info_command.py:1-254] — Test pattern example (CliRunner + monkeypatch build_deps)
- [Source: pyproject.toml:1-48] — Build config with ruff settings and deps

### Package structure verification

Expected paths (all already exist unless marked NEW):
- `src/color_scheme_generator/factory.py` ✓
- `src/color_scheme_generator/cli/main.py` ✓
- `src/color_scheme_generator/domain/exceptions.py` ✓
- `src/color_scheme_generator/domain/enums.py` ✓ (RuntimeMode, ContainerEngine present)
- `src/color_scheme_generator/domain/models.py` ✓ (ContainerMount, ContainerResult, RuntimeSettings, ContainerSettings present)
- `src/color_scheme_generator/ports/processor.py` ✓ (ColorSchemeProcessorPort)
- `src/color_scheme_generator/ports/container_runtime.py` ✓ (ContainerRuntimePort)
- `src/color_scheme_generator/adapters/local_processor.py` ✓
- `src/color_scheme_generator/adapters/container_processor.py` **NEW**
- `src/color_scheme_generator/adapters/dry_run_processor.py` **NEW**
- `tests/unit/adapters/test_container_processor_stub.py` **NEW**
- `tests/unit/adapters/test_dry_run_processor_stub.py` **NEW**
- `tests/unit/cli/test_runtime_mode.py` **NEW**

## Dev Agent Record

### Implementation Plan

1. Add 4 container exceptions to `domain/exceptions.py`
2. Create stub `adapters/container_processor.py` (implements ColorSchemeProcessorPort, raises NotImplementedError)
3. Create stub `adapters/dry_run_processor.py` (implements ColorSchemeProcessorPort, raises NotImplementedError)
4. Update `factory.py`:
   - Change `processor` field type to `ColorSchemeProcessorPort | None`
   - Add `container_engine: ContainerRuntimePort | None` field
   - Add `create_container_engine()`, `create_container_processor()`, `create_dry_run_processor()` helpers
5. Update `cli/main.py`:
   - Add `--runtime` and `--container-engine` global options in `@app.callback()`
   - In `build_deps()`, wire container_engine lazily
   - Select processor based on runtime mode
6. Add `oci-runtime` to `pyproject.toml` dependencies
7. Write tests for runtime mode selection, container engine selection, deps construction
8. Run full test suite — verify zero regressions
9. Run ruff lint — must be clean

### Completion Notes

### File List

#### Modified
- `src/color_scheme_generator/domain/exceptions.py` — Add ContainerImageNotFoundError, ContainerRuntimeUnavailableError, ImagePullAccessError, ContainerTimeoutError
- `src/color_scheme_generator/factory.py` — Add container_engine field, change processor type, add create_* helpers
- `src/color_scheme_generator/cli/main.py` — Add --runtime and --container-engine global flags, runtime mode wiring
- `pyproject.toml` — Add oci-runtime dependency

#### Created
- `src/color_scheme_generator/adapters/container_processor.py` — Stub implementing ColorSchemeProcessorPort
- `src/color_scheme_generator/adapters/dry_run_processor.py` — Stub implementing ColorSchemeProcessorPort
- `tests/unit/adapters/test_container_processor_stub.py` — Port contract test for ContainerProcessor
- `tests/unit/adapters/test_dry_run_processor_stub.py` — Port contract test for DryRunProcessor
- `tests/unit/cli/test_runtime_mode.py` — Runtime mode and container engine flag tests
