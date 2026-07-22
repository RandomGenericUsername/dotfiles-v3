---
baseline_commit: a7f767bc182cb08bd69c180e9ce3f44dbdaa74df
---

# Story 3.2: Container Processor

Status: done

## Story

As a theming user,
I want to extract palettes in container mode when backends aren't installed locally,
So that I don't need to install wal/wallust/sklearn on my host.

## Acceptance Criteria

### AC 1: Pre-flight validation

**Given** ContainerProcessor implementing ColorSchemeProcessorPort via ContainerRuntimePort
**When** process_generate() is called with RuntimeMode.CONTAINER
**Then** it pre-flights: resolves config, templates, and backend params
**And** selects image `[registry/]color-scheme-<backend>:<tag>`
**And** verifies engine is available via ContainerRuntimePort (raises ContainerRuntimeUnavailableError)
**And** verifies image exists (raises ContainerImageNotFoundError)

### AC 2: Host pre-resolution and mount construction

**Given** all pre-flight checks pass
**When** process_generate() runs
**Then** it serializes AppSettings as-resolved (no rewrite) to a temp TOML file
**And** mounts are constructed with 4 BIND mounts:
  - input parent dir `/input` (RO)
  - output dir `/output` (RW)
  - temp TOML `/csg-config/settings.toml` (RO)
  - templates dir `/templates` (RO)

### AC 3: Inner command construction

**Given** a container generate command
**When** the container runs
**Then** the inner command receives `--runtime local` (prevents recursion via CLI override priority)
**And** `--backend <value>`, `--param key=value` pairs are forwarded verbatim
**And** format and output-dir flags are forwarded

### AC 4: Temp file cleanup

**Given** a container run completes or fails
**When** the finally block executes
**Then** the temp settings TOML file is cleaned up
**And** cleanup happens even when engine.containers.run() raises

### AC 5: Root filesystem guard

**Given** input file's parent dir is `/` (filesystem root)
**When** mount paths are resolved
**Then** it raises InvalidImageError — mounting `/` is rejected

### AC 6: process_show in container mode

**Given** a container-mode process_show()
**When** called
**Then** it runs extraction inside the container but does not mount an output directory
**And** returns the ColorScheme for host-side display

### AC 7: Temp TOML permissions

**Given** the temp TOML file
**When** written on host
**Then** it is world-readable (non-root container user can read it)
**And** contains the AppSettings as-resolved (runtime.mode is honest — CLI --runtime local overrides it)

### AC 8: Timeout handling

**Given** an OCI runtime that times out
**When** execution exceeds the configured timeout
**Then** OperationTimeoutError maps to ContainerTimeoutError via error mapping

### AC 9: Output parity with LocalProcessor

**Given** equivalent input and settings in local and container mode
**When** both complete successfully
**Then** both return the same GenerationResult contract shape (same fields, same structure)
**And** differences surface only through explicit runtime errors

## Tasks / Subtasks

### Implement ContainerProcessor.process_generate
- [x] Accept and store `template_dir_resolver` and `default_settings_path` in constructor (AC: 1, 2)
- [x] Pre-flight: select image `color-scheme-<backend>:<tag>` using `Backend.image_suffix` and `ContainerSettings.image_prefix`/`image_tag` (AC: 1)
- [x] Pre-flight: call `container_runtime.image_exists(image)` and raise `ContainerImageNotFoundError` if absent (AC: 1)
- [x] Pre-flight: verify runtime is available (AC: 1)
- [x] Serialize AppSettings to temp TOML via manual TOML construction (AC: 2)
- [x] Set temp file permissions to 0o644 (world-readable) (AC: 7)
- [x] Resolve input parent dir: `request.image_path.parent` — guard against `/` (AC: 5)
- [x] Resolve output dir: `request.config.output_dir` — create parents if not exist (AC: 2)
- [x] Resolve templates dir: use `template_dir_resolver.resolve()` or fallback to bundled defaults (AC: 2)
- [x] Build mount list: 4 `ContainerMount` entries (input, output, settings, templates) (AC: 2)
- [x] Build inner command: `csg generate <image_path> --runtime local --backend <backend>` plus `--param`, `--format`, `-o` flags (AC: 3)
- [x] Set inner image path to container path `/input/<filename>` (AC: 3)
- [x] Call `container_runtime.run(image, command, mounts, timeout)` with `settings.container.timeout_seconds` (AC: 1, 8)
- [x] Map result to `GenerationResult` with same shape as `LocalProcessor` (AC: 9)
- [x] Wrap in try/finally: clean up temp TOML in finally (AC: 4)

### Implement ContainerProcessor.process_show
- [x] Similar to process_generate but:
  - [x] No output dir mount (AC: 6)
  - [x] No template rendering
  - [x] Returns `GenerationResult` with empty `output_files`
- [x] Must pass `--runtime local` for inner command (AC: 3)

### Error mapping
- [x] Map OCI timeout to `ContainerTimeoutError` (AC: 8)
- [x] Let existing error mapping (story 3.4) handle other OCI errors
- [x] Ensure all errors produce valid `GenerationResult(success=False)` (AC: 9)

### Update factory.py
- [x] Update `create_container_processor` to accept and forward `template_dir_resolver` (fixes deferred issue from 3.1)
- [ ] Consider also forwarding `default_settings_path` from `build_deps()` or `AppSettings`

### Update main.py
- [x] In `@app.callback()`, pass `template_dir_resolver` and `default_settings_path` to `create_container_processor`

### Write tests
- [x] Unit test: pre-flight raises `ContainerImageNotFoundError` when image missing (AC: 1)
- [x] Unit test: pre-flight raises `ContainerRuntimeUnavailableError` when engine unavailable (AC: 1)
- [x] Unit test: correct mount construction for generate (AC: 2)
- [x] Unit test: root filesystem guard raises `InvalidImageError` (AC: 5)
- [x] Unit test: show mode does not mount output dir (AC: 6)
- [x] Unit test: inner command contains `--runtime local` (AC: 3)
- [x] Unit test: params forwarded verbatim (AC: 3)
- [x] Unit test: temp TOML cleaned up in finally on success and failure (AC: 4)
- [x] Unit test: temp TOML is world-readable (AC: 7)
- [x] Unit test: timeout maps to `ContainerTimeoutError` (AC: 8)
- [x] Unit test: GenerationResult contract matches LocalProcessor (AC: 9)
- [x] Mock `ContainerRuntimePort` for all unit tests
- [x] Run full test suite — zero regressions (363 tests passing)
- [x] Run ruff lint — must be clean

## Dev Notes

### Current State

**`adapters/container_processor.py`** is a stub:
```python
class ContainerProcessor:
    def __init__(self, container_runtime, template_dir_resolver=None, default_settings_path=None):
        ...
    def process_generate(self, request, settings): raise NotImplementedError
    def process_show(self, request, settings): raise NotImplementedError
```

**`factory.py`** `create_container_processor`:
```python
def create_container_processor(
    container_engine: ContainerRuntimePort,
    default_settings_path: Path | None = None,
) -> ColorSchemeProcessorPort:
    return ContainerProcessor(container_engine, default_settings_path=default_settings_path)
```
Note: `template_dir_resolver` is NOT forwarded — this was deferred from 3.1 review. Must fix in this story.

**`cli/main.py`** callback wires container processor without template_dir_resolver:
```python
deps.processor = create_container_processor(container_runtime)
```

**`adapters/oci_container_runtime.py`** — adapter wrapping oci-runtime's `ContainerEngine` to CSG's `ContainerRuntimePort`:
- `run()` uses `detach=True, remove=False` pattern with `exec_container`
- `duration` is hardcoded to `0.0` (known deferred issue; consider fixing in this story)
- Mounts are converted from `ContainerMount` → `oci_runtime.domain.types.VolumeMount`

**`ports/container_runtime.py`** — CSG port:
```python
class ContainerRuntimePort(Protocol):
    def run(self, image, command, mounts, timeout) -> ContainerResult: ...
    def image_exists(self, image) -> bool: ...
    def pull_image(self, image) -> None: ...
```

**`ports/processor.py`** — CSG port:
```python
class ColorSchemeProcessorPort(Protocol):
    def process_generate(self, request, settings) -> GenerationResult: ...
    def process_show(self, request, settings) -> GenerationResult: ...
```

**`domain/models.py`** — relevant models (all frozen dataclasses):
- `ContainerMount(source: Path, target: PurePosixPath, read_only: bool)`
- `ContainerResult(return_code: int, stdout: str, stderr: str, duration: float)`
- `GenerationResult(success, color_scheme, output_files, backend, stderr, return_code, duration)`
- `GenerationRequest(image_path, config)`
- `GeneratorConfig(backend, params, formats, output_dir)`
- `ContainerSettings(image_prefix, image_tag, timeout_seconds, memory_limit, mount_timeout_seconds)`
- `TemplateSettings(templates_dir, custom_templates_dir)`

**`domain/enums.py`**:
- `RuntimeMode.LOCAL`, `RuntimeMode.CONTAINER`
- `ContainerEngine.DOCKER`, `ContainerEngine.PODMAN`
- `Backend.CUSTOM`, `Backend.PYWAL`, `Backend.WALLUST` (each has `.image_suffix` property)

**`domain/exceptions.py`** — container exceptions already defined (from 3.1):
- `ContainerImageNotFoundError(image, backend)`
- `ContainerRuntimeUnavailableError(runtime)`
- `ContainerTimeoutError`
- `InvalidImageError(image_path, reason)` — reuse for root-fs guard

### Implementation Strategy

The ContainerProcessor follows the same pattern as LocalProcessor but delegates extraction to a container instead of running it locally.

**Host pre-resolution flow:**
1. Validate input image exists and is readable
2. Select image tag: `f"{settings.container.image_prefix}color-scheme-{backend.image_suffix}:{settings.container.image_tag}"`
3. Check engine is available (no dedicated check method — `container_runtime.run()` will fail if not; or use `oci_runtime` engine's `.is_available()` if needed)
4. Check image exists via `container_runtime.image_exists(image)` — if False, raise `ContainerImageNotFoundError`
5. Serialize AppSettings to temp TOML (use `tomli_w.dumps()` or construct manually)
6. Build mount list
7. Build inner command
8. Run container
9. Map result
10. Cleanup in finally

**Inner command strategy:**
The inner `csg` command runs inside the container with `--runtime local` to prevent container-recursion:
```
csg generate /input/wallpaper.jpg --runtime local --backend custom --param saturation=1.0 -f json -f css -o /output
```
The `--runtime local` override is critical (ADR-003 improved): the CLI's override priority means `--runtime local` in the flag wins over whatever `settings.toml` says, preventing the container from trying to launch another container.

Image paths inside the container follow mount targets:
- Input: `/input/<original-filename>`
- Output: `/output`
- Settings: `/csg-config/settings.toml`
- Templates: `/templates`

**Mount details:**
- Input: `(source=request.image_path.parent, target=PurePosixPath("/input"), read_only=True)`
- Output: `(source=request.config.output_dir, target=PurePosixPath("/output"), read_only=False)`
- Settings temp: `(source=temp_toml_path, target=PurePosixPath("/csg-config/settings.toml"), read_only=True)`
- Templates: `(source=resolved_templates_dir, target=PurePosixPath("/templates"), read_only=True)`

**Root filesystem guard:**
If `request.image_path.parent == Path("/")`, raise `InvalidImageError(image_path, "Cannot mount filesystem root")`.

**Temp TOML serialization:**
Use `tomli_w` (already in deps per addendum G). Settings are serialized as-resolved — no rewrite of `runtime.mode`. The inner `--runtime local` CLI flag handles the override.

TTL temp file with `NamedTemporaryFile(delete=False, suffix=".toml", mode="w")`, then `os.chmod(path, 0o644)`.

### Architecture Compliance

- **ADR-003 (Pre-resolved Host Config)**: Host serializes resolved AppSettings to temp TOML; the temp file is mounted as `/csg-config/settings.toml`. No in-container re-resolution.
- **ADR-005 (One Image Per Backend)**: Image tag is `color-scheme-<backend>:<tag>` — matches per-backend Dockerfiles from Dockerfile.base.
- **ADR-006 (Runtime/Engine Orthogonality)**: `--runtime` selects local vs container; `--container-engine` selects docker vs podman. ContainerProcessor uses whichever engine was wired by factory.
- **ADR-007 (JSON-First Output)**: Output contract matches LocalProcessor's GenerationResult shape.
- **ADR-008 (Ephemeral In-Container Cache)**: No host cache mount. Cache is ephemeral inside the container.
- **ADR-014 (Shared Dockerfile.base)**: One image per backend built on shared base. ContainerProcessor uses image name convention matching the build convention.

### Deferred Issues from 3.1 Review to Fix

1. **[Patch] `create_container_processor` doesn't forward `template_dir_resolver`** [factory.py:99-105] — must accept and forward `TemplateDirResolver` to ContainerProcessor for templates mount resolution.
2. **[Defer] `duration` hardcoded to 0.0** [oci_container_runtime.py:54] — consider calculating from real wall-clock time in `ContainerProcessor` by wrapping the `container_runtime.run()` call with `time.monotonic()`.

### Test Patterns

Follow existing test patterns from `tests/unit/adapters/test_local_processor.py`:
- Mock `ContainerRuntimePort` via Protocol structural typing
- Use `unittest.mock.create_autospec` or manual mock implementing the port
- Use `pytest` fixtures for common test data (GenerationRequest, AppSettings, etc.)
- Verify GenerationResult field-by-field (success, color_scheme, output_files, backend, stderr, return_code, duration)

CLI integration tests should go in `tests/unit/cli/` following the pattern in `test_runtime_mode.py`:
- `CliRunner` with monkeypatched `build_deps`
- Verify `--runtime container` dispatches to mock processor

### Files to Create

| File | Action |
|------|--------|
| `tests/unit/adapters/test_container_processor.py` | CREATE — full test suite for ContainerProcessor |

### Files to Modify

| File | Action |
|------|--------|
| `src/color_scheme_generator/adapters/container_processor.py` | MODIFY — implement full ContainerProcessor |
| `src/color_scheme_generator/factory.py` | MODIFY — forward template_dir_resolver to create_container_processor |
| `src/color_scheme_generator/cli/main.py` | MODIFY — pass template_dir_resolver and default_settings_path to create_container_processor |

### References

- [Source: epics.md#612-649] — Story 3.2 acceptance criteria
- [Source: PRD.md#268-298] — FR-19 and FR-20 container execution requirements
- [Source: addendum.md#38-52] — Container execution contract with mount model
- [Source: adapters/local_processor.py:1-104] — LocalProcessor reference implementation (same port, same result model)
- [Source: ports/processor.py:1-19] — ColorSchemeProcessorPort protocol
- [Source: ports/container_runtime.py:1-23] — ContainerRuntimePort protocol
- [Source: adapters/oci_container_runtime.py:1-61] — OciContainerRuntimeAdapter (wraps oci-runtime to CSG port)
- [Source: factory.py:104-110] — create_container_processor (needs template_dir_resolver forwarding)
- [Source: cli/main.py:83-86] — Container mode wiring in callback
- [Source: deferred-work.md#84-89] — Deferred items from 3.1 code review
- [Source: tests/unit/adapters/test_local_processor.py] — Test pattern reference
- [Source: tests/unit/cli/test_runtime_mode.py:1-120] — CLI test pattern reference

### Project Structure Notes

- `ContainerProcessor` lives alongside `LocalProcessor` in `adapters/` — same module level, same pattern
- `OciContainerRuntimeAdapter` in `adapters/oci_container_runtime.py` is the only adapter implementing `ContainerRuntimePort`
- Image name convention: `{settings.container.image_prefix}color-scheme-{backend.image_suffix}:{settings.container.image_tag}`
- Template directory resolved via `TemplateDirResolver.resolve()` — returns the resolved templates dir Path
- All container exceptions are in `domain/exceptions.py` (added in story 3.1)
- No changes to domain models, enums, or ports needed — they already have everything this story needs

### Review Findings

- [x] [Review][Patch] TOML string values not escaped in `_serialize_settings` [container_processor.py:57,70] — fixed
- [x] [Review][Patch] `_parse_color_scheme_from_json` crashes with `KeyError` on missing fields [container_processor.py:100-109] — fixed
- [x] [Review][Patch] Root FS guard bypassable via symlink [container_processor.py:124-125] — fixed
- [x] [Review][Patch] Timeout heuristic too broad and `except ContainerTimeoutError: raise` is dead code [container_processor.py:199-204] — fixed
- [x] [Review][Patch] `output_dir.iterdir()` races with overlay filesystem commit [container_processor.py:211-212] — dismissed (false alarm — bind mounts are synchronous)
- [x] [Review][Patch] No validation that `templates_dir` exists before mounting [container_processor.py:134-143] — fixed
- [x] [Review][Patch] No validation that `request.image_path` exists on disk [container_processor.py:119-124] — fixed
- [x] [Review][Defer] `return_code=-1` for timeouts is non-standard [container_processor.py:227,338] — POSIX exit codes are 0-255; `-1` conflicts with conventions. Deferred: would require documenting/changing `GenerationResult.return_code` contract.
- [x] [Review][Defer] Code duplication between `process_generate` and `process_show` [container_processor.py:112-232,234-343] — ~90% body shared. Deferred: maintenance concern, not a bug.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Implemented full `ContainerProcessor` with `process_generate` and `process_show`
- Pre-flight validation: image selection, image existence check, root FS guard
- Manual TOML serialization (tomli_w not available in env)
- Temp TOML file with 0o644 permissions, cleaned up in finally
- 4 BIND mounts: input (RO), output (RW), settings (RO), templates (RO)
- Inner command with `--runtime local` override to prevent recursion
- Timeout mapping: `ContainerTimeoutError` from engine timeouts
- `process_show` mode: no output dir mount, parses JSON stdout for ColorScheme
- Factory: `create_container_processor` now forwards `template_dir_resolver`
- CLI callback passes `template_dir_resolver` to `create_container_processor`
- 13 new tests covering all ACs; 363 total tests passing; ruff clean
- Removed stale `test_container_processor_stub.py` (replaced by full test suite)
- Fixed pre-existing `test_runtime_mode.py` failures (missing `_pkg_version` patch)
- Fixed `build_deps()` processor pre-wiring (from 3.1 review patch)

### File List

| File | Action |
|------|--------|
| `src/color_scheme_generator/adapters/container_processor.py` | MODIFIED — full implementation |
| `src/color_scheme_generator/factory.py` | MODIFIED — forward template_dir_resolver |
| `src/color_scheme_generator/cli/main.py` | MODIFIED — pass template_dir_resolver |
| `tests/unit/adapters/test_container_processor.py` | CREATED — 13 new tests |
| `tests/unit/adapters/test_container_processor_stub.py` | DELETED — replaced by full tests |
| `tests/unit/cli/test_runtime_mode.py` | MODIFIED — patch _pkg_version |
| `tests/unit/cli/test_generate.py` | MODIFIED — update build_deps test assertion |
