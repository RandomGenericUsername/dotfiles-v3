---
baseline_commit: 8eacac85e8c86c990fa415e0aab9f671f256f37e
---

# Story 1.5: LocalProcessor + Generation Service

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want LocalProcessor to orchestrate backend extraction and return structured results,
So that the CLI command layer only handles presentation.

## Acceptance Criteria

### LocalProcessor Implementation

**Given** LocalProcessor implementing ColorSchemeProcessorPort
**When** `process_generate()` is called with a GenerationRequest and AppSettings
**Then** it looks up the active backend in BackendRegistry by `GeneratorConfig.backend`
**And** calls `PaletteGeneratorPort.generate(image_path, config)` to perform extraction
**And** returns a `GenerationResult` with:
- `success=True`
- `color_scheme` = the extracted ColorScheme
- `output_files` = empty tuple (no template rendering yet — added in Epic 2)
- `backend` = the Backend enum used
- `duration` = wall-clock time of extraction (use `time.monotonic()` before/after generate call)
- `stderr` = "" (handled by adapter internally)
- `return_code` = 0

**Given** `process_show()` is called with a GenerationRequest and AppSettings
**When** extraction succeeds
**Then** it runs extraction and returns the ColorScheme without writing any files
**And** `output_files` is empty tuple
**And** behaves identically to process_generate except no output_files tracking

### Availability Guard

**Given** the active backend's `is_available()` returns False
**When** `process_generate()` or `process_show()` is called
**Then** it raises `BackendNotAvailableError` before attempting any extraction
**And** does NOT call `PaletteGeneratorPort.generate()`

### Structural Subtyping

**Given** LocalProcessor instance
**When** verified via `isinstance(processor, ColorSchemeProcessorPort)`
**Then** it passes structural subtype checking

### BackendRegistry Construction

**Given** factory.py composition root
**When** `create_backend_registry()` is called
**Then** it returns a `dict[Backend, PaletteGeneratorPort]` with all three generators instantiated
**And** no auto-detection is performed (D10/ADR-010 — lookup table only)
**And** each generator is instantiated once at composition time (not lazily per-request)

### Backend Lookup Error

**Given** a backend not found in BackendRegistry (e.g. missing registry entry)
**When** LocalProcessor tries to look it up
**Then** it raises `PaletteGenerationError(message, backend=backend)` with a clear message

## Tasks / Subtasks

### Factory / Composition Root
- [x] Create `factory.py` with `CliDependencies` dataclass (AC: BackendRegistry Construction)
  - Fields: `backend_registry: dict[Backend, PaletteGeneratorPort]`, `output_adapter: OutputPort | None`
  - `from __future__ import annotations` convention
- [x] Implement `create_backend_registry()` helper (AC: BackendRegistry Construction)
  - Instantiate CustomGenerator, PywalGenerator, WallustGenerator
  - Return dict mapping each Backend enum to its generator instance
  - No auto-detection, no is_available() calls at construction time

### LocalProcessor
- [x] Create `adapters/local_processor.py` with LocalProcessor class (AC: LocalProcessor Implementation)
  - `from __future__ import annotations` convention
  - Constructor takes: `backend_registry: dict[Backend, PaletteGeneratorPort]`
  - `_get_backend_generator(backend) -> PaletteGeneratorPort` — lookup helper that raises PaletteGenerationError for missing backends (AC: Backend Lookup Error)
- [x] Implement `process_generate()` (AC: LocalProcessor Implementation)
  - Look up backend generator from registry
  - Check `is_available()`, raise BackendNotAvailableError if False (AC: Availability Guard)
  - Start timer with `time.monotonic()`
  - Call `generator.generate(request.image_path, request.config)`
  - Stop timer, calculate duration
  - Return GenerationResult(success=True, color_scheme=..., output_files=(), backend=..., stderr="", return_code=0, duration=...)
- [x] Implement `process_show()` (AC: LocalProcessor Implementation)
  - Same as process_generate but without tracking output_files
  - Returns GenerationResult with the extracted ColorScheme

### Tests
- [x] Create `tests/unit/adapters/test_local_processor.py`:
  - `process_generate()` with available backend returns successful GenerationResult with correct fields (AC: LocalProcessor Implementation)
  - `process_generate()` measures duration with time.monotonic() (AC: LocalProcessor Implementation)
  - `process_show()` returns GenerationResult with ColorScheme (AC: LocalProcessor Implementation)
  - Backend unavailable raises BackendNotAvailableError before generate() call (AC: Availability Guard)
  - `is_available()` not called on unavailable backend — guard triggers first (AC: Availability Guard)
  - Unknown backend raises PaletteGenerationError (AC: Backend Lookup Error)
  - `isinstance(local_processor, ColorSchemeProcessorPort)` is True (AC: Structural Subtyping)
  - `create_backend_registry()` returns dict with all three backends (AC: BackendRegistry Construction)

## Dev Notes

### Architecture Compliance

- `LocalProcessor` implements `ColorSchemeProcessorPort` — a `@runtime_checkable` Protocol with `process_generate(request, settings) -> GenerationResult` and `process_show(request, settings) -> GenerationResult` — defined in `ports/processor.py` (already existing from Story 1.2)
- `ColorSchemeProcessorPort` is runtime-agnostic by design (no local/container assumptions in the port itself — ADR-002)
- `BackendRegistry` is a plain `dict[Backend, PaletteGeneratorPort]` built in `factory.py` — lookup-only table, never iterated for auto-detection (D10/ADR-010, ADR-013)
- No Pydantic in adapters/ (D6, ADR-012)
- `from __future__ import annotations` in all new modules (established convention from stories 1.1-1.4)
- Package path: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/`
- `AppSettings` is a placeholder class in `domain/models.py` (no-op — will be fleshed out in Story 2.1) — just accept it as a parameter for now

### Key Domain Types Already Defined

From Story 1.1 (`domain/models.py`):
- `GeneratorConfig` — frozen dataclass: `backend: Backend`, `params: dict[str, Any]`, `formats: tuple[ColorFormat, ...]`, `output_dir: Path`
- `GenerationRequest` — frozen dataclass: `image_path: Path`, `config: GeneratorConfig`
- `GenerationResult` — frozen dataclass: `success: bool`, `color_scheme: ColorScheme | None`, `output_files: tuple[Path, ...]`, `backend: Backend`, `stderr: str`, `return_code: int`, `duration: float`

From Story 1.2 (`ports/palette_generator.py`):
- `PaletteGeneratorPort` — `@runtime_checkable` Protocol: `generate(image_path: Path, config: GeneratorConfig) -> ColorScheme`, `is_available() -> bool`

From Story 1.2 (`ports/processor.py`):
- `ColorSchemeProcessorPort` — `@runtime_checkable` Protocol: `process_generate(request, settings) -> GenerationResult`, `process_show(request, settings) -> GenerationResult`

From domain exceptions:
- `BackendNotAvailableError(backend, hint)` — raise when backend is unavailable
- `PaletteGenerationError(message, backend=None)` — raise for backend lookup failures

### Review Learnings (from Stories 1.3, 1.4)

**Critical patterns to follow:**
- Use `time.monotonic()` for duration measurement (not `time.time()`) — avoids system clock adjustments
- Duration should be measured around the `generator.generate()` call only, not including registry lookup or availability check
- `GenerationResult.output_files` must always be a tuple, never None — use `()`
- Error output is never raised as bare Exception — always a typed domain exception

**Past review findings to prevent:**
- [1.3] Saturation-after-sort bug → THIS STORY has no similar ordering concern, but be careful about exception ordering (availability check BEFORE generate call)
- [1.3] Missing I/O error coverage → cover all error paths in tests (unavailable backend, unknown backend)
- [1.3] config.params None crash → generation services handle this in story 1.3, but ensure LocalProcessor passes config through faithfully
- [1.3] n_clusters/saturation validation → not applicable in this layer — pass-through

### BackendRegistry Design

```python
# factory.py type sketch
BackendRegistry = dict[Backend, PaletteGeneratorPort]

def create_backend_registry() -> BackendRegistry:
    return {
        Backend.CUSTOM: CustomGenerator(),
        Backend.PYWAL: PywalGenerator(),
        Backend.WALLUST: WallustGenerator(),
    }
```

- No `is_available()` calls — generators are instantiated regardless of whether their deps are installed
- Availability is checked per-request by LocalProcessor before calling generate()
- PywalGenerator and WallustGenerator don't exist yet (Story 2.4, 2.5) — use `object()` or `None` placeholders that raise NotImplementedError when generate() is called, OR define minimal stubs. **Recommendation**: define adapter stubs now so BackendRegistry is complete; full implementations come in Epic 2.

### LocalProcessor Timing Pattern

```python
import time

start = time.monotonic()
color_scheme = generator.generate(request.image_path, request.config)
duration = time.monotonic() - start

return GenerationResult(
    success=True,
    color_scheme=color_scheme,
    output_files=(),
    backend=request.config.backend,
    stderr="",
    return_code=0,
    duration=duration,
)
```

### Error Handling Contract

1. `BackendNotAvailableError` — raised BEFORE `generate()` is called. Include hint string: for CUSTOM → `"pip install color-scheme-generator[custom]"`, for PYWAL → `"pip install color-scheme-generator[pywal]"`, for WALLUST → `"Install wallust binary"`.
2. `PaletteGenerationError` — raised when backend is not found in registry (programming error / incomplete wiring). Include backend in message.
3. Exceptions from `generator.generate()` (InvalidImageError, ColorExtractionError) propagate through unmodified — LocalProcessor does NOT catch them.

### Files This Story Creates

| File | Status |
|------|--------|
| `src/color_scheme_generator/factory.py` | CREATE — CliDependencies + create_backend_registry |
| `src/color_scheme_generator/adapters/local_processor.py` | CREATE — LocalProcessor |
| `tests/unit/adapters/test_local_processor.py` | CREATE |

### Testing Requirements

- Unit tests with Mock generators implementing PaletteGeneratorPort
- Test both success and error paths:
  - Available backend → successful GenerationResult
  - Unavailable backend → BackendNotAvailableError (verify generate() is NOT called — use mock.assert_not_called())
  - Unknown backend in registry → PaletteGenerationError
  - process_show() returns GenerationResult without files
- Duration measurement: mock timer or capture the values
- Structural isinstance check
- `create_backend_registry()` integration test: verify all three backends present
- Use `pytest` with capsys for stdout capture if needed, `unittest.mock` for mock generators
- Existing test count: 77 (Story 1.1: 46, Story 1.2: 6, Story 1.3: 10, Story 1.4: 15)

### Git Intelligence Summary

- Recent commits show active WEG + CSG development: container processor, config resolution, CLI commands
- CSG currently has 3 port interfaces, domain models/enums/exceptions, CustomGenerator adapter, and JsonOutput adapter
- No composition root (factory.py) or processor layer exists yet — this story creates both
- Codebase follows WEG reference patterns for factory composition root (CliDependencies dataclass, create_* helpers)

### Project Structure Notes

- Alignment with unified project structure (paths, modules, naming)
- Detected conflicts or variances (with rationale)

### References

- Architecture: `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md#L115` — LocalProcessor adapter section
- Architecture: `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md#L127` — BackendRegistry wiring helper
- Architecture: `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md#L678-L703` — factory.py composition root design
- Architecture: `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md#L14` — ADR-002: Domain Port for Processing
- Architecture: `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md#L21` — ADR-010: No auto Backend
- Architecture: `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md#L26` — ADR-013: BackendRegistry Replaces v2 Switch
- Architecture: `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md#L40-L43` — GenerationResult domain model definition

## Dev Agent Record

### Agent Model Used

deepseek-v4-flash-free

### Implementation Plan

1. Create `factory.py`:
   - `CliDependencies` dataclass with `backend_registry` and `output_adapter` fields
   - `create_backend_registry()` returning dict with all 3 backends
   - Placeholder stubs for PywalGenerator and WallustGenerator (raising NotImplementedError) for registry completeness
2. Create `adapters/local_processor.py`:
   - `LocalProcessor` class implementing `ColorSchemeProcessorPort`
   - Constructor: `__init__(self, backend_registry: dict[Backend, PaletteGeneratorPort])`
   - `_get_backend_generator()` — private lookup helper with PaletteGenerationError fallback
   - `process_generate()` — availability check → timer → generate → GenerationResult
   - `process_show()` — same as generate but no output_files tracking
3. Create `tests/unit/adapters/test_local_processor.py`:
   - Mock generators (successful, unavailable, unknown backend scenarios)
   - Test all 8-10 acceptance criteria
4. Verify test suite passes
5. Ruff lint passes on new/modified files

### Debug Log References

### Completion Notes List

- Implemented `factory.py` with `CliDependencies` dataclass and `create_backend_registry()` helper returning all three backend generators
- Created `PywalGenerator` and `WallustGenerator` stubs in `adapters/backends/` for registry completeness
- Implemented `LocalProcessor` in `adapters/local_processor.py` with `process_generate()` and `process_show()` methods
- Added availability guard (BackendNotAvailableError before generate call) and backend lookup error handling
- Added 12 new tests covering all acceptance criteria (success paths, error paths, structural subtyping, registry construction)
- All 89 tests pass (77 existing + 12 new)

### Debug Log References

- Resolved ruff B904: added `from None` to KeyError → PaletteGenerationError chain

### File List

| File | Status |
|------|--------|
| `src/color_scheme_generator/factory.py` | CREATE |
| `src/color_scheme_generator/adapters/local_processor.py` | CREATE |
| `src/color_scheme_generator/adapters/backends/pywal_generator.py` | CREATE |
| `src/color_scheme_generator/adapters/backends/wallust_generator.py` | CREATE |
| `src/color_scheme_generator/adapters/backends/__init__.py` | MODIFY |
| `tests/unit/adapters/test_local_processor.py` | CREATE |

### Review Findings (2026-07-16)

- [x] [Review][Patch] process_generate and process_show are byte-for-byte identical [local_processor.py:33-80] — Fixed: process_show now delegates to process_generate
- [x] [Review][Patch] PaletteGenerationError raised for registry-lookup failure [local_processor.py:26-29] — Fixed: introduced BackendNotRegisteredError in domain/exceptions.py
- [x] [Review][Patch] _availability_hint silently returns "" for unknown backends — Fixed: moved hints to Backend.install_hint property on the enum, removed _availability_hint static method
- [x] [Review][Defer] success=True hardcoded without post-generation validation [local_processor.py:47,70] — Matches current spec which mandates success=True. Expand if error-handling requirements grow.
- [x] [Review][Defer] generator.generate() exceptions propagate raw across port boundary [local_processor.py:43,66] — Design choice; the CLI layer handles exceptions. Could wrap in domain exceptions if needed later.
- [x] [Review][Defer] request.image_path not validated before use [local_processor.py:43,66] — Validation deferred to backend generators. Out of scope for this story's ACs.
- [x] [Review][Defer] settings parameter silently ignored [local_processor.py:34,57] — AppSettings is a known placeholder (noted in story 1.1 Dev Notes), will be fleshed out in Epic 2.
