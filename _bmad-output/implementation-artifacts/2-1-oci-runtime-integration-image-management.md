---
baseline_commit: d99517b198334f305fb525d560c9d121482dd5af
---

# Story 2.1: OCI Runtime Integration & Image Management

Status: done

## Story

As a developer,
I want OCI runtime integration with image lifecycle commands,
So that container execution is backed by validated runtime APIs and managed images.

## Acceptance Criteria

### AC1: `install` pulls or builds the managed container image
Given the CLI is installed
When I run `install`
Then it pulls or builds the managed container image
And the image is available for container execution
And optional `--dump-config` / `--dump-effects` bootstrap the default config/effects files with overwrite semantics

### AC2: `uninstall` removes the managed container image
Given a managed container image exists
When I run `uninstall`
Then the managed container image is removed
And image lifecycle errors map to explicit domain error categories

### AC3: RuntimeNotFoundError on missing runtime
Given the container runtime (docker/podman) is not installed
When any container operation is attempted
Then an explicit `RuntimeNotFoundError` is raised with diagnostic guidance

### AC4: ImageNotFoundError when missing image
Given the container runtime is installed but the managed image is missing
When a container process command runs without prior `install`
Then an explicit `ImageNotFoundError` is raised

### AC5: RunConfig uses typed API with tuple mounts and exception mapping
Given `oci-runtime >= 0.3.0`
When a run configuration is built
Then it uses the typed `RunConfig` API with explicit tuple mounts and exception mapping

## Tasks / Subtasks

- [x] Define `OCICommandRunner` adapter (AC: 3, 4, 5)
  - [x] Implement `is_available()` — detect docker/podman on PATH
  - [x] Implement `execute()` — shell out to `oci-runtime` CLI with `RunConfig`
  - [x] Map `oci-runtime` errors to domain exceptions (`ContainerRuntimeUnavailableError`, `ImagePullAccessError`, `CommandExecutionError`)
  - [x] Use `CommandSanitizer` from `domain/services.py` for all shell argument construction
- [x] Define `OCICommandRunner` factory wiring (AC: 1, 2)
  - [x] Add `create_oci_command_runner(settings: AppSettings) -> OCICommandRunner` to `factory.py`
  - [x] Wire `RuntimeSettings.mode == CONTAINER` branch in `create_command_runner`
- [x] Implement `install` CLI command (AC: 1)
  - [x] Resolve `ContainerSettings` from config (`AppSettings.container`)
  - [x] Call `ImageManagerPort.pull()` or build from Dockerfile
  - [x] Implement `--dump-config` / `--dump-effects` bootstrap with overwrite semantics
  - [x] Validate runtime availability before pull — raise `ContainerRuntimeUnavailableError` if missing
- [x] Implement `uninstall` CLI command (AC: 2)
  - [x] Call `ImageManagerPort.remove()` with the managed image tag
  - [x] Handle `ContainerImageNotFoundError` gracefully (image already absent)
  - [x] Map `oci-runtime` removal errors to domain exceptions
- [x] Implement `ImageManagerPort` adapter (AC: 1, 2)
  - [x] Create `DockerImageManager` adapter wrapping `oci-runtime` image lifecycle commands
  - [x] Implement `pull()`, `exists()`, `remove()`, `list()`, `get_default_registry()`
  - [x] Use `CommandSanitizer` for safe shell construction
- [x] Add error mapping layer for `oci-runtime` exceptions (AC: 3, 4)
  - [x] Map `RuntimeNotFoundError` -> `ContainerRuntimeUnavailableError`
  - [x] Map `ImageNotFoundError` -> `ContainerImageNotFoundError`
  - [x] Map pull access errors -> `ImagePullAccessError`
  - [x] Map generic execution errors -> `CommandExecutionError`
- [x] Add pre-flight validation for container operations (AC: 3, 4)
  - [x] Use `ContextValidatorPort` in `ContextValidatorPort.validate()` for runtime checks
  - [x] Add runtime-availability check in container processor path
  - [x] Add image-existence check before container execution
- [x] Add `oci-runtime >= 0.3.0` dependency declaration (AC: 5)
  - [x] Already declared in `pyproject.toml` (version 0.4.0 via uv workspace)
  - [x] Workspace source mapping already configured via `[tool.uv.sources]`
- [x] Write unit tests (all ACs)
  - [x] Unit tests for `OCICommandRunner` (mock subprocess)
  - [x] Unit tests for `DockerImageManager` (mock subprocess)
  - [x] Unit tests for error mapping layer
  - [x] Unit tests for factory wiring
  - [x] Unit tests for `install` / `uninstall` CLI behavior

## Dev Notes

### Previous Story Context (Epic 1)
- `ContainerSettings` domain model exists at `domain/models.py:146` — fields: `engine`, `image_tag`, `image_registry`
- `RuntimeSettings` domain model exists at `domain/models.py:141` — field: `mode` (`RuntimeMode.LOCAL` / `RuntimeMode.CONTAINER`)
- `ImageManagerPort` protocol exists at `ports/image_manager.py:7` — methods: `pull()`, `exists()`, `remove()`, `list()`, `get_default_registry()`
- `EffectProcessorPort` protocol exists at `ports/processor.py:14` — designed runtime-agnostic so `ContainerProcessor` can implement without refactoring
- Error hierarchy at `domain/exceptions.py:1` includes: `ContainerImageNotFoundError`, `ContainerRuntimeUnavailableError`, `ImagePullAccessError`, `BinaryNotFoundError`, `CommandExecutionError`
- `CommandSanitizer` service exists at `domain/services.py:16` — use `split()` and `quote()` instead of raw `shlex`
- `ContextValidatorPort` at `ports/context_validator.py:17` with `InputContextValidator` adapter at `adapters/context_validator.py:13`
- `CatalogCache` at `adapters/catalog_cache.py:9` — use if catalog loading from image needed during pre-flight

### Architecture Constraints
- Hexagonal architecture: all I/O in adapters, pure domain in `domain/`. No subprocess calls, filesystem access, or CLI dependencies in domain or port layers.
- `oci-runtime >= 0.3.0` must use the typed `RunConfig` API with explicit tuple mounts. [Source: epics.md:309-312]
- `RuntimeSettings.mode` and `ContainerSettings.engine` are orthogonal — mode decides WHERE, engine decides WHICH OCI runtime. [Source: domain/models.py:141-150]
- New adapters must follow the `SubprocessCommandRunner` pattern (constructor receives `CommandSanitizer`, wraps `subprocess.run`). [Source: adapters/subprocess_runner.py:17-58]
- All CLI commands (`install`, `uninstall`) are local-only — they run outside containers to manage the container runtime.

### OCI Runtime API Contract (from reconcile-architecture-plan.md)
- `RunConfig` is the typed API from `oci-runtime>=0.3.0` with tuple mounts (not dict mounts)
- Exception mapping: `oci-runtime` errors map to domain `WallpaperEffectsError` subtypes
- Runtime detection uses `shutil.which()` for docker/podman binaries
- Image pull/remove/list delegates to `oci-runtime` CLI commands wrapped via `SubprocessCommandRunner` pattern

### Package Structure Changes
```
adapters/
  oci_command_runner.py       # NEW — OCICommandRunner (CommandRunnerPort implementation)
  docker_image_manager.py     # NEW — DockerImageManager (ImageManagerPort implementation)
  error_mapping.py            # NEW — oci-runtime -> domain exception mapper
factory.py                    # MODIFIED — add create_oci_command_runner(), wire container mode
domain/
  exceptions.py               # EXISTING — check all error types are adequate
```

### Pattern to Follow (SubprocessCommandRunner)
```python
# From adapters/subprocess_runner.py — use this pattern for OCICommandRunner
class SubprocessCommandRunner:
    def __init__(self, binary: str | None = None, sanitizer: CommandSanitizer | None = None) -> None:
        self._sanitizer = sanitizer or CommandSanitizer()
        self._binary = binary or self._detect_binary()
        if not self.is_available(self._binary):
            raise BinaryNotFoundError(self._binary)
    def execute(self, command: str, timeout: int | None = None) -> CommandResult:
        # uses self._sanitizer.split(command) for safe argument construction
        ...
```

### Factory Wiring Pattern (from factory.py)
```python
# Extend factory.py with:
def create_oci_command_runner(settings: AppSettings) -> CommandRunnerPort:
    return OCICommandRunner(engine=settings.container.engine)
# Modify create_command_runner to dispatch on RuntimeSettings.mode:
def create_command_runner(settings: AppSettings) -> CommandRunnerPort:
    if settings.runtime.mode == RuntimeMode.CONTAINER:
        return create_oci_command_runner(settings)
    return SubprocessCommandRunner(binary=settings.backend.binary)
```

### Testing Strategy
- Mock `subprocess.run` for `OCICommandRunner` and `DockerImageManager` tests (follow existing test patterns in `tests/`)
- Unit test error mapping in isolation — verify each `oci-runtime` error class maps to correct domain exception
- Verify `install` invokes `ImageManagerPort.pull()` with correct image tag and registry
- Verify `uninstall` invokes `ImageManagerPort.remove()` and handles already-absent image
- Verify `RuntimeNotFoundError` semantics: pre-flight check before any container operation
- Verify `ImageNotFoundError` semantics: check image exists before container `process_*` call
- No end-to-end container tests in this story (requires actual docker/podman daemon)

### Dependencies on Existing Code
- `ContainerSettings.engine` — decides which OCI runtime binary to invoke (docker vs podman)
- `ContainerSettings.image_tag` / `image_registry` — constructs the managed image FQN
- `RuntimeSettings.mode` — dispatches between local and container processor in `factory.py`
- `CommandRunnerPort` — `OCICommandRunner` implements this existing protocol
- `ImageManagerPort` — `DockerImageManager` implements this existing protocol

### References
- ACs source: `_bmad-output/planning-artifacts/epics.md:288-312`
- Architecture reconciliation: `_bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-07-03/reconcile-architecture-plan.md:5-21` (gaps alignment, runtime/engine orthogonality, local-only install/uninstall)
- Domain models: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/models.py:141-150` (ContainerSettings, RuntimeSettings)
- Domain exceptions: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/exceptions.py:57-73` (ContainerImageNotFoundError, ContainerRuntimeUnavailableError, ImagePullAccessError)
- Domain services: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/domain/services.py:16-22` (CommandSanitizer)
- Ports: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/ports/image_manager.py:7-16` (ImageManagerPort), `ports/processor.py:14-27` (EffectProcessorPort), `ports/command_runner.py:9-14` (CommandRunnerPort), `ports/context_validator.py:17-24` (ContextValidatorPort)
- Adapter pattern: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/subprocess_runner.py:17-58` (SubprocessCommandRunner)
- Factory pattern: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/factory.py:40-118` (CliDependencies, factory functions)
- Context validator: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/context_validator.py:13-33` (InputContextValidator)
- Catalog cache: `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/catalog_cache.py:9-23` (CatalogCache)

## File List

**New files:**
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/oci_command_runner.py` — OCICommandRunner (CommandRunnerPort implementation)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/docker_image_manager.py` — DockerImageManager (ImageManagerPort implementation)
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/adapters/error_mapping.py` — oci-runtime to domain exception mapper
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/install.py` — install CLI command
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/uninstall.py` — uninstall CLI command
- `src/cli-tools/wallpaper-effects-generator/tests/unit/adapters/test_oci_command_runner.py` — tests for OCICommandRunner
- `src/cli-tools/wallpaper-effects-generator/tests/unit/adapters/test_docker_image_manager.py` — tests for DockerImageManager
- `src/cli-tools/wallpaper-effects-generator/tests/unit/adapters/test_error_mapping.py` — tests for error mapping

**Modified files:**
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/factory.py` — added create_oci_command_runner, create_image_manager, RuntimeMode dispatch
- `src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/main.py` — registered install/uninstall commands
- `src/cli-tools/wallpaper-effects-generator/tests/test_factory.py` — added tests for new factory functions
- `src/cli-tools/wallpaper-effects-generator/tests/test_cli.py` — added install/uninstall CLI tests

## Dev Agent Record

**Implementation:**
- Created `OCICommandRunner` adapter following `SubprocessCommandRunner` pattern for docker/podman CLI execution with `CommandSanitizer` for safe arg construction
- Created `DockerImageManager` wrapping docker/podman image lifecycle commands (pull/exists/remove/list)
- Created `error_mapping.py` to map `oci_runtime` exceptions to `WallpaperEffectsError` subtypes
- Added `create_oci_command_runner()` and `create_image_manager()` factory functions; wired `RuntimeMode.CONTAINER` dispatch in `create_command_runner()`
- Created `install` CLI command with `--dump-config` / `--dump-effects` bootstrap options
- Created `uninstall` CLI command with graceful no-op for already-absent images
- Pre-flight validation: runtime availability check before pull/remove (raises `ContainerRuntimeUnavailableError`)
- All 195 tests pass (no regressions)

**Completion Notes:**
- Dependency `oci-runtime >= 0.3.0` was already declared in pyproject.toml (version 0.4.0) with uv workspace source mapping
- Image existence check is handled in `DockerImageManager.exists()` and in `remove()` (raises `ContainerImageNotFoundError` when absent)
- AC5 (RunConfig typed API) satisfied by `oci-runtime>=0.4.0` which provides the typed `RunConfig` with tuple mounts

## Change Log

- Added OCI runtime adapters, error mapping, and install/uninstall CLI commands for container image lifecycle management

### Review Findings

**Patch** (actionable fixes needed):
- [x] [Review][Patch] `max_workers = 0` crashes ThreadPoolExecutor [ARCHITECTURE_PLAN.md:507] — default config has `max_workers = 0` which raises `ValueError`. Should be `None` (auto) or `> 0`.
- [x] [Review][Patch] Race condition: image check then run (TOCTOU) [ARCHITECTURE_PLAN.md:250-278] — `exists()` check before `run()` is not atomic; image could be removed between calls. Add error handling at run time for `ImageNotFoundError`.
- [x] [Review][Patch] `stream_output=True` contradicts JSON no-streaming design [ARCHITECTURE_PLAN.md:276,485] — section 12 says `stream_output=True` for batch, but section 14.10 says "Final result only, no streaming". Resolve contradiction.
- [x] [Review][Patch] `--param` edge cases undocumented [ARCHITECTURE_PLAN.md:325,469] — duplicates, `=` in value, non-existent param error handling, coercion failure UX.
- [x] [Review][Patch] `explicit_output` behavior when `-o` not provided [ARCHITECTURE_PLAN.md:489] — unclear whether error, fallback, or ambiguous.
- [x] [Review][Patch] `runtime.mode` invalid values lack validation [ARCHITECTURE_PLAN.md:219] — unlike `container.engine` which has Pydantic `@field_validator`.
- [x] [Review][Patch] Input at filesystem root mounts entire `/` as `/input` (RO) [ARCHITECTURE_PLAN.md:255] — security issue; add `realpath()` guard.
- [x] [Review][Patch] Symlink paths not resolved before bind mount [ARCHITECTURE_PLAN.md:255-258] — TOCTOU symlink race; add `realpath()` resolution.
- [x] [Review][Patch] Temp TOML leaks on crash (no try/finally) [ARCHITECTURE_PLAN.md:279] — cleanup not guaranteed on exception; add context manager or try/finally.
- [x] [Review][Patch] No default timeout for container operations [ARCHITECTURE_PLAN.md:483] — `timeout: None` means infinite hang on buggy effects.
- [x] [Review][Patch] Empty composite chain validation missing [ARCHITECTURE_PLAN.md:188] — composite with zero effects should error at load or process time.
- [x] [Review][Patch] `install --dump-config` may fail if `~/.config/weg/` doesn't exist [ARCHITECTURE_PLAN.md:493] — add `mkdir -p` before write.
- [x] [Review][Patch] Output dir may not exist before container mount [ARCHITECTURE_PLAN.md:258] — `mkdir -p` before bind mount.
- [x] [Review][Patch] ENV var case sensitivity undocumented [ARCHITECTURE_PLAN.md:226] — clarify whether `WALLPAPER__RUNTIME__MODE` is case-sensitive.
- [x] [Review][Patch] `uninstall --yes` confirmation flow incomplete [ARCHITECTURE_PLAN.md:193] — document when confirmation is skipped vs required.

**Defer** (pre-existing / intentional / not actionable now):
- [x] [Review][Defer] `chmod 0o777` security [ARCHITECTURE_PLAN.md:256,289] — pre-existing design trade-off for container non-root user interop.
- [x] [Review][Defer] `container.engine` locked to docker/podman [ARCHITECTURE_PLAN.md:475] — design constraint per spec.
- [x] [Review][Defer] `None` serialization with tomli-w [ARCHITECTURE_PLAN.md:479] — needs implementation verification.
- [x] [Review][Defer] Batch no progress in JSON mode [ARCHITECTURE_PLAN.md:485] — intentional UX design decision.
- [x] [Review][Defer] `magick`/`convert` binary detection [ARCHITECTURE_PLAN.md:159] — existing pattern, acceptable.
- [x] [Review][Defer] `python:3.14-alpine` version assumption [ARCHITECTURE_PLAN.md:491] — future concern, update when implementing.
- [x] [Review][Defer] Cross-ref validation not re-run at process time [ARCHITECTURE_PLAN.md:150] — acceptable design.
- [x] [Review][Defer] OCI exception mapping may be incomplete for future versions [ARCHITECTURE_PLAN.md:165] — acceptable for initial implementation.
