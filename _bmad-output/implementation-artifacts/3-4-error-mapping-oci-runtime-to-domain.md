# Story 3.4: Error Mapping (oci-runtime → Domain)

Status: ready-for-dev

## Story

As a developer,
I want OCI runtime exceptions mapped to domain exceptions,
so that container errors produce structured, typed error output.

## Acceptance Criteria

### AC 1: ImageNotFoundError mapping
**Given** error_mapping.py
**When** oci-runtime raises `ImageNotFoundError`
**Then** it maps to `ContainerImageNotFoundError(image, backend)`

### AC 2: RuntimeNotAvailableError mapping
**Given** error_mapping.py
**When** oci-runtime raises `RuntimeNotAvailableError`
**Then** it maps to `ContainerRuntimeUnavailableError(runtime)`

### AC 3: ImagePullAccessDeniedError mapping
**Given** error_mapping.py
**When** oci-runtime raises `ImagePullAccessDeniedError`
**Then** it maps to `ImagePullAccessError(image, registry)`

### AC 4: OperationTimeoutError mapping
**Given** error_mapping.py
**When** oci-runtime raises `OperationTimeoutError`
**Then** it maps to `ContainerTimeoutError`

### AC 5: Fallback for unknown oci-runtime errors
**Given** error_mapping.py
**When** any other oci-runtime exception (base `OciError`) is raised
**Then** it maps to a generic `ColorSchemeError` with the original message preserved

### AC 6: JSON serialization
**Given** the mapped domain exception
**When** serialized by `OutputPort.error()`
**Then** it produces a valid JSON error payload with type code and message

## Tasks / Subtasks

### Create error_mapping.py module
- [ ] Create `src/color_scheme_generator/adapters/error_mapping.py` with `map_oci_error()` function (AC: 1-5)
  - Uses same pattern as `wallpaper-effects-generator/adapters/error_mapping.py`
  - Imports all oci-runtime exception types needed
  - Maps every known `OciError` subclass to corresponding `ColorSchemeError` subclass
  - Fallback clause maps unknown `OciError` to `ColorSchemeError` preserving message
- [ ] Add `ContainerError` family mapping: `ContainerNotFoundError`, `ContainerRuntimeError` → `ContainerRuntimeUnavailableError`
- [ ] Handle `OperationTimeoutError` → `ContainerTimeoutError` (ensure image/backend context is preserved where available)

### Refactor OciContainerRuntimeAdapter to use error_mapping
- [ ] In `run()` method: wrap `self._engine.containers.run()` and `exec_container()` calls with `map_oci_error()` (AC: 1, 2, 4, 5)
  - Currently raw `OciError` subclasses can bubble up uncaught
- [ ] In `image_exists()`: wrap with `map_oci_error()` for defensive mapping
- [ ] In `pull_image()`: wrap with `map_oci_error()` (AC: 3)
- [ ] `build_image()` and `remove_image()` already have inline error mapping — refactor to use `map_oci_error()` for consistency (or keep as-is since they have backend context the mapper doesn't)

### Update ContainerProcessor error handling
- [ ] In `process_generate()` exception block (line 208): replace fragile `isinstance(exc, ContainerTimeoutError) or "timeout" in str(exc).lower()` with proper mapping via `map_oci_error()` (AC: 4)
- [ ] In `process_show()` exception block (line 323): same replacement
- [ ] Remove direct dependency on `oci_runtime.domain.exceptions` — only import through `error_mapping` module

### Update errors.py re-exports
- [ ] Add container-related domain exceptions to `errors.py` public API (AC: 6)
  - `ContainerImageNotFoundError`, `ContainerRuntimeUnavailableError`, `ImagePullAccessError`, `ContainerTimeoutError`, `ImageBuildError`, `ImageRemoveError`
- [ ] Update `__all__` in `errors.py`

### Write tests
- [ ] Unit test: `map_oci_error(ImageNotFoundError)` → `ContainerImageNotFoundError` (AC: 1)
- [ ] Unit test: `map_oci_error(RuntimeNotAvailableError)` → `ContainerRuntimeUnavailableError` (AC: 2)
- [ ] Unit test: `map_oci_error(ImagePullAccessDeniedError)` → `ImagePullAccessError` (AC: 3)
- [ ] Unit test: `map_oci_error(OperationTimeoutError)` → `ContainerTimeoutError` (AC: 4)
- [ ] Unit test: `map_oci_error(OciError("generic"))` → `ColorSchemeError` (AC: 5)
- [ ] Unit test: `map_oci_error(ContainerNotFoundError)` → `ContainerRuntimeUnavailableError`
- [ ] Unit test: `map_oci_error(ContainerRuntimeError)` → `ContainerRuntimeUnavailableError`
- [ ] Unit test: mapped exception → JSON output via JsonOutput.error() (AC: 6)
- [ ] Unit test: `run()` raises `ImageNotFoundError` → adapter re-raises as `ContainerImageNotFoundError`
- [ ] Unit test: `run()` raises `OperationTimeoutError` → adapter re-raises as `ContainerTimeoutError`
- [ ] Unit test: `pull_image()` raises `ImagePullAccessDeniedError` → adapter re-raises as `ImagePullAccessError`
- [ ] Integration test: `ContainerProcessor.process_generate()` with mock that raises oci-runtime `OperationTimeoutError` → returns error `GenerationResult`
- [ ] Run full test suite — verify zero regressions
- [ ] Run ruff lint — clean

## Dev Notes

### Current State

**`adapters/oci_container_runtime.py`** — inline error mapping is partial:
- `run()` (line 18-58): NO error mapping — raw `OciError` subclasses bubble up uncaught through `self._engine.containers.run()` and `exec_container()`
- `image_exists()` (line 60-61): NO error mapping
- `pull_image()` (line 63-64): NO error mapping
- `build_image()` (line 66-86): HAS inline mapping — catches `ImageError` → `ImageBuildError`
- `remove_image()` (line 88-100): HAS inline mapping — catches `ImageError` → `ImageRemoveError`

**`adapters/container_processor.py`** — weak timeout detection:
- `process_generate()` line 208: `except Exception as exc: if isinstance(exc, ContainerTimeoutError) or "timeout" in str(exc).lower()`
- `process_show()` line 323: same pattern
- `OperationTimeoutError` from oci-runtime would be caught by the generic `Exception` handler but NOT detected as timeout

**`domain/exceptions.py`** — existing container exceptions (lines 82-125):
- `ContainerImageNotFoundError(image, backend)` — exists but `image` field name conflicts with oci-runtime's `image_name`
- `ContainerRuntimeUnavailableError(runtime)` — exists, maps from oci-runtime `RuntimeNotAvailableError.runtime`
- `ImagePullAccessError(image, registry)` — exists, maps from oci-runtime `ImagePullAccessDeniedError.image_name + .registry`
- `ContainerTimeoutError` — exists (no-arg), maps from `OperationTimeoutError`
- `ImageBuildError(image, reason, backend)` — added in story 3.3
- `ImageRemoveError(image, reason, backend)` — added in story 3.3

**`errors.py`** — currently only exports non-container exceptions. Must add container exceptions for public API.

**Reference pattern** — `wallpaper-effects-generator/adapters/error_mapping.py`:
```python
def map_oci_error(error: Exception) -> WallpaperEffectsError:
    if isinstance(error, RuntimeNotAvailableError):
        return ContainerRuntimeUnavailableError(runtime=error.runtime)
    if isinstance(error, ImageNotFoundError):
        return ContainerImageNotFoundError(image=error.image_name)
    if isinstance(error, ImagePullAccessDeniedError):
        return ImagePullAccessError(image=error.image_name, registry=error.registry)
    if isinstance(error, ImageError):
        return CommandExecutionError(...)
    return CommandExecutionError(...)
```

### oci-runtime Exception Hierarchy (know what to map)

```
OciError
  ├── ParsingError
  ├── ContainerError
  │   ├── ContainerNotFoundError(container_id)
  │   └── ContainerRuntimeError
  ├── ImageError
  │   ├── ImageNotFoundError(image_name)
  │   ├── ImagePullAccessDeniedError(image_name, registry)
  │   └── ImageRuntimeError
  ├── VolumeError
  │   ├── VolumeNotFoundError(volume_name)
  │   └── VolumeRuntimeError
  ├── NetworkError
  │   ├── NetworkNotFoundError(network_name)
  │   └── NetworkRuntimeError
  ├── OperationTimeoutError(command, timeout)
  ├── RuntimeNotAvailableError(runtime)
  └── ProviderNotRegisteredError(kind)
```

All inherit from `OciError` which has: `.message`, `.command`, `.exit_code`, `.stderr`.

### Error Mapping Design

Create a single `map_oci_error(error: Exception, **context) -> ColorSchemeError` in `adapters/error_mapping.py`:

| oci-runtime Exception | Domain Exception | Context |
|---|---|---|
| `ImageNotFoundError` | `ContainerImageNotFoundError(image, backend)` | Extract `image` from `error.image_name`; backend from context |
| `RuntimeNotAvailableError` | `ContainerRuntimeUnavailableError(runtime)` | Extract `runtime` from `error.runtime` |
| `ImagePullAccessDeniedError` | `ImagePullAccessError(image, registry)` | Extract from `error.image_name`, `error.registry` |
| `OperationTimeoutError` | `ContainerTimeoutError` | No context needed |
| `ContainerNotFoundError` | `ContainerRuntimeUnavailableError(runtime="docker\|podman")` | Use error.message |
| `ContainerRuntimeError` | `ContainerRuntimeUnavailableError(runtime="docker\|podman")` | Use error.message |
| `ImageRuntimeError` | `ColorSchemeError(message)` | Preserve `str(error)` |
| `VolumeError` / `NetworkError` | `ColorSchemeError(message)` | Preserve `str(error)` |
| `ProviderNotRegisteredError` | `ContainerRuntimeUnavailableError(runtime=str(error.kind))` | Extract from error.kind |
| Any other `OciError` | `ColorSchemeError(message=str(error))` | Preserve full message |

The `**context` kwarg allows callers to pass `backend=Backend.CUSTOM` etc. for richer domain exceptions.

### Implementation Strategy

**Step 1: Create `adapters/error_mapping.py`**
```python
def map_oci_error(error: Exception, **context: Any) -> ColorSchemeError:
    from oci_runtime.domain.exceptions import (
        ContainerNotFoundError, ContainerRuntimeError,
        ImageError, ImageNotFoundError, ImagePullAccessDeniedError,
        ImageRuntimeError, OciError, OperationTimeoutError,
        ProviderNotRegisteredError, RuntimeNotAvailableError,
    )

    if isinstance(error, RuntimeNotAvailableError):
        return ContainerRuntimeUnavailableError(runtime=error.runtime)
    if isinstance(error, ImageNotFoundError):
        return ContainerImageNotFoundError(
            image=error.image_name,
            backend=context.get("backend"),
        )
    if isinstance(error, ImagePullAccessDeniedError):
        return ImagePullAccessError(image=error.image_name, registry=error.registry)
    if isinstance(error, OperationTimeoutError):
        return ContainerTimeoutError()
    if isinstance(error, (ContainerNotFoundError, ContainerRuntimeError)):
        return ContainerRuntimeUnavailableError(runtime=error.message)
    if isinstance(error, ProviderNotRegisteredError):
        return ContainerRuntimeUnavailableError(runtime=str(error.kind))
    if isinstance(error, ImageError):
        return ColorSchemeError(str(error))
    if isinstance(error, OciError):
        return ColorSchemeError(str(error))
    return ColorSchemeError(str(error))
```

**Step 2: Refactor `OciContainerRuntimeAdapter`** — wrap `run()`, `image_exists()`, `pull_image()` with `map_oci_error()`. Keep `build_image()` and `remove_image()` as-is since they already have domain-aware error mapping with backend context.

**Step 3: Refactor `ContainerProcessor`** — replace weak timeout detection with proper mapping:
```python
try:
    container_result = self._container_runtime.run(...)
except ContainerTimeoutError:
    raise
except Exception as exc:
    raise map_oci_error(exc) from exc
```

Or better, handle all mapped errors at the adapter level so `ContainerProcessor` never sees raw oci-runtime exceptions.

**Step 4: Update `errors.py`** — add all container exceptions to public API.

### File Structure

| File | Action |
|------|--------|
| `src/color_scheme_generator/adapters/error_mapping.py` | CREATE — OCI error → domain error mapper |
| `src/color_scheme_generator/adapters/oci_container_runtime.py` | MODIFY — wrap run/image_exists/pull_image with error mapping |
| `src/color_scheme_generator/adapters/container_processor.py` | MODIFY — replace weak timeout detection, remove raw oci-runtime exception deps |
| `src/color_scheme_generator/errors.py` | MODIFY — add container exceptions to public API |
| `tests/unit/adapters/test_error_mapping.py` | CREATE — test all mapping paths |
| `tests/unit/adapters/test_oci_container_runtime.py` | MODIFY — add tests for error mapping in run/image_exists/pull_image |
| `tests/unit/adapters/test_container_processor.py` | MODIFY — add integration test for OperationTimeoutError path |

### Architecture Compliance

- **ADR (Error Mapping):** Centralized `map_oci_error()` function follows `wallpaper-effects-generator` pattern — single module, isinstance dispatch, domain exception return
- **ADR (Adapter Isolation):** `ContainerProcessor` only imports from domain + ports; raw oci-runtime exceptions never leak past the adapter boundary
- **NFR-2 (Reliability):** Every oci-runtime failure produces a structured `ColorSchemeError` — never raw `OciError` — ensuring JSON error serialization via `OutputPort.error()`
- **NFR-3 (Observability):** Mapped exceptions preserve diagnostic context (image name, backend, runtime, message)
- **Dependency Rule:** `adapters/error_mapping.py` imports from `oci_runtime.domain.exceptions` (adapter → oci-runtime) and `domain.exceptions` (adapter → domain). No circular deps.

### Previous Story Intelligence (3.3)

- `build_image()`/`remove_image()` error mapping is inline in `OciContainerRuntimeAdapter` via `ImageError` catch — works but inconsistent with `run()`/`image_exists()`/`pull_image()` which have no mapping
- 382 tests passing, ruff clean
- `oci_runtime.domain.exceptions.ImageError` caught, `ImageBuildError`/`ImageRemoveError` raised with backend context
- `ContainerProcessor` has fragile timeout detection: `"timeout" in str(exc).lower()` — this story replaces that pattern
- `errors.py` does NOT export container exceptions — add them in this story
- Review findings from story 3.3 noted: "non-ImageError engine exceptions unhandled [oci_container_runtime.py:74-76, 87-89] — deferred, pre-existing" — this story addresses that

### Git Intelligence

Recent commits show the codebase is actively developed with auto-commit patterns. Story 3.3 (install/uninstall) was recently completed — the pattern for error mapping was identified as a deferred concern. The `OciContainerRuntimeAdapter` was extended with `build_image`/`remove_image` in that story, each with inline error mapping. This story tackles the remaining unhandled oci-runtime exceptions systematically.

### Testing Patterns

**Error mapping tests** — direct function tests (new file `tests/unit/adapters/test_error_mapping.py`):
```python
def test_image_not_found_mapping():
    from oci_runtime.domain.exceptions import ImageNotFoundError
    from color_scheme_generator.adapters.error_mapping import map_oci_error
    from color_scheme_generator.domain.exceptions import ContainerImageNotFoundError

    oci_error = ImageNotFoundError(image_name="test-image:latest")
    domain_error = map_oci_error(oci_error)

    assert isinstance(domain_error, ContainerImageNotFoundError)
    assert domain_error.image == "test-image:latest"
```

**Adapter integration tests** — mock `self._engine.containers.run()` to raise `ImageNotFoundError`, verify `OciContainerRuntimeAdapter.run()` raises `ContainerImageNotFoundError`.

**ContainerProcessor integration tests** — mock `ContainerRuntimePort.run()` to raise `ContainerTimeoutError`, verify `process_generate()` returns error `GenerationResult`.

### References

- [Source: epics.md#683-703] — Story 3.4 acceptance criteria
- [Source: epics.md#82-83] — FR-6 install, FR-7 uninstall
- [Source: prd.md#122-147] — FR-6 and FR-7 detailed consequences
- [Source: prd.md#313-316] — NFR-2 reliability: errors never produce unstructured output
- [Source: wallpaper-effects-generator/adapters/error_mapping.py:1-36] — Reference implementation pattern
- [Source: oci-runtime/domain/exceptions.py:1-185] — Complete oci-runtime exception hierarchy
- [Source: domain/exceptions.py:82-125] — Existing container domain exceptions
- [Source: adapters/oci_container_runtime.py:18-58] — run() method with NO error mapping (needs fixing)
- [Source: adapters/oci_container_runtime.py:66-86] — build_image() with existing inline error mapping (reference)
- [Source: adapters/container_processor.py:208-211] — Weak timeout detection needs replacement
- [Source: adapters/container_processor.py:323-326] — Same pattern in process_show()
- [Source: errors.py:1-25] — Current limited public API (missing container exceptions)

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

### Completion Notes List

### File List

| File | Action |
|------|--------|
| `src/color_scheme_generator/adapters/error_mapping.py` | CREATE |
| `src/color_scheme_generator/adapters/oci_container_runtime.py` | MODIFY |
| `src/color_scheme_generator/adapters/container_processor.py` | MODIFY |
| `src/color_scheme_generator/errors.py` | MODIFY |
| `tests/unit/adapters/test_error_mapping.py` | CREATE |
