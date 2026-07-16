---
baseline_commit: 8eacac85e8c86c990fa415e0aab9f671f256f37e
---

# Story 1.4: JsonOutput Adapter

Status: done

## Story

As a CI pipeline,
I want extraction results in structured JSON format,
So that I can parse them without terminal formatting.

## Acceptance Criteria

### JsonOutput Implementation

**Given** JsonOutput implementing OutputPort
**When** `process_result()` is called with a successful GenerationResult
**Then** it outputs: `{"success": true, "color_scheme": {...}, "output_files": [...], "backend": "...", "duration": ...}`
**And** the color_scheme object contains: background, foreground, cursor (each with hex + rgb), colors (array of 16 hex+rgb), source_image, backend, generated_at (ISO 8601)
**And** output_files is an array of path strings
**When** `error()` is called with a ColorSchemeError
**Then** it outputs: `{"success": false, "error": {"type": "InvalidImageError", "message": "..."}}`
**And** error output is always valid JSON — never terminal-only formatting

### Structural Subtyping

**Given** JsonOutput instance
**When** verified via `isinstance(output, OutputPort)`
**Then** it passes structural subtype checking

### Error Serialization

**Given** each exception type in the ColorSchemeError hierarchy
**When** serialized via JsonOutput.error()
**Then** `InvalidImageError` maps to `{"type": "InvalidImageError", "message": "..."}` with image_path and reason
**And** `ColorExtractionError` maps to `{"type": "ColorExtractionError", "message": "..."}` with backend and stderr
**And** `BackendNotAvailableError` maps to `{"type": "BackendNotAvailableError", "message": "..."}` with backend and hint
**And** `OutputWriteError` maps to `{"type": "OutputWriteError", "message": "..."}` with path and reason
**And** `ConfigResolutionError` maps to `{"type": "ConfigResolutionError", "message": "..."}` with key and reason
**And** `PaletteGenerationError` maps to `{"type": "PaletteGenerationError", "message": "..."}` with backend if present
**And** all error payloads include `"success": false` at the top level

### Error Invariant

**Given** any error
**When** output via JsonOutput.error()
**Then** the output is parseable as JSON — no bare print() or formatted strings
**And** writing to stdout never raises an exception (must handle serialization errors internally, e.g. non-serializable datetime → ISO string)

## Tasks / Subtasks

### Adapter Directory Structure
- [x] Create `adapters/output/__init__.py` — empty package init with `from __future__ import annotations` (AC: all)
- [x] Create `adapters/output/json_output.py` with JsonOutput class (AC: JsonOutput Implementation)

### JsonOutput
- [x] Implement `process_result(result: GenerationResult) -> None` (AC: JsonOutput Implementation)
  - Build dict with success, color_scheme (nested dict from ColorScheme domain object), output_files (list of str paths), backend (string), duration (float)
  - Use `json.dumps()` to stdout
  - `ColorScheme.to_dict()` or inline serialization: background/foreground/cursor as `{"hex": "...", "rgb": [R, G, B]}`, colors as array of same, source_image as str, backend as str, generated_at as ISO 8601 string
  - `datetime.now()` → `.isoformat()`
  - `Path` objects → `str(path)`
  - Backend enum → `backend.value`
- [x] Implement `error(exc: ColorSchemeError) -> None` (AC: Error Serialization)
  - Match on exception type via isinstance chain or dict dispatch
  - Extract type-specific fields: type name from `type(exc).__name__`, message from `str(exc)`, plus extra fields per exception (image_path, reason, backend, stderr, hint, path, key)
  - Build dict with `{"success": false, "error": {"type": "...", "message": "..."}}`
  - Include extra fields when present (e.g. image_path, backend)
  - Use `json.dumps()` to stdout
- [x] Implement `palette_display(scheme: ColorScheme) -> None` (AC: JsonOutput Implementation)
  - Output color_scheme as JSON (same nested format as process_result's color_scheme sub-object)

### Tests
- [x] Create `tests/unit/adapters/output/__init__.py` (AC: all)
- [x] Create `tests/unit/adapters/output/__init__.py` (AC: all)
- [x] Create `tests/unit/adapters/output/test_json_output.py`:
  - `process_result()` with successful GenerationResult outputs correct JSON structure (AC: JsonOutput Implementation)
  - `process_result()` datetime serializes as ISO 8601 (AC: JsonOutput Implementation)
  - `process_result()` Path objects serialize as strings (AC: JsonOutput Implementation)
  - `error()` with InvalidImageError produces correct JSON (AC: Error Serialization)
  - `error()` with ColorExtractionError includes backend and stderr (AC: Error Serialization)
  - `error()` with BackendNotAvailableError includes backend and hint (AC: Error Serialization)
  - `error()` with each ColorSchemeError subclass produces valid JSON with correct type field (AC: Error Serialization)
  - `palette_display()` outputs ColorScheme as JSON (AC: JsonOutput Implementation)
  - `isinstance(json_output, OutputPort)` is True (AC: Structural Subtyping)
  - All error outputs have `"success": false` (AC: Error Invariant)
  - Error method handles serialization edge cases (e.g., unexpected exception type) without crashing (AC: Error Invariant)

## Dev Notes

### Architecture Compliance

- `JsonOutput` implements `OutputPort` — a `@runtime_checkable` Protocol with `process_result(result)`, `error(exc)`, `palette_display(scheme)` — defined in `ports/output.py` (already existing from Story 1.2)
- `OutputPort` takes domain objects (not dicts/strings) — each adapter renders differently per ADR-007
- JSON is the default output format — every command returns JSON unless `--output-format rich|plain` is specified
- All domain exceptions have consistent constructor signatures (see `domain/exceptions.py`) — extract `__dict__` or access attributes directly for serialization
- `from __future__ import annotations` in all new modules (established convention from stories 1.1-1.3)
- No Pydantic in adapters/output/ — domain types only (D6, ADR-012)
- Package path: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/`

### ColorScheme Serialization Contract

The JSON output of a ColorScheme must follow:
```json
{
  "background": {"hex": "#1a1a2e", "rgb": [26, 26, 46]},
  "foreground": {"hex": "#e0e0e0", "rgb": [224, 224, 224]},
  "cursor": {"hex": "#ff6b6b", "rgb": [255, 107, 107]},
  "colors": [
    {"hex": "#1a1a2e", "rgb": [26, 26, 46]},
    ...
  ],
  "source_image": "/path/to/wallpaper.jpg",
  "backend": "custom",
  "generated_at": "2026-07-15T21:14:00"
}
```

### Previous Story Intelligence

- Story 1.1 established domain foundation: Color (frozen dataclass with hex, rgb), ColorScheme (frozen with 16 colors + bg/fg/cursor), GenerationResult (success, color_scheme, output_files, backend, stderr, return_code, duration) — 46 tests
- Story 1.2 established 3 port interfaces: PaletteGeneratorPort, ColorSchemeProcessorPort, OutputPort — 6 tests including structural isinstance checks
- Story 1.3 established adapter patterns: lazy imports, `from __future__ import annotations`, `__init__.py` with `__all__` re-exports — 7 new tests (62 total)
- Colors have `hex` (str) and `rgb` (tuple[int,int,int]) attributes
- `datetime.now()` generates timestamps — serialize via `.isoformat()`
- `GenerationResult.output_files` is `tuple[Path, ...]` — serialize paths as strings
- `Backend` enum members: CUSTOM, PYWAL, WALLUST — use `.value` for JSON
- `ColorSchemeError` exceptions have readable `str(exc)` already implemented — use for message field
- Review findings from 1.3 to prevent: saturation-after-sort bug → this story has no such ordering concern; missing I/O error coverage → ensure serialization errors are caught; config.params None crash → not applicable here; n_clusters/saturation validation → not applicable

### Testing Requirements

- Unit tests with real domain objects (no mocking needed — pure domain constructors create test data)
- Build `GenerationResult` with `success=True`, a valid `ColorScheme`, empty `output_files`, known backend/duration — assert JSON output
- Build `ColorSchemeError` subclasses with test parameters — assert JSON error output
- Use `json.loads(capsys.readouterr().out)` to capture and parse stdout in tests (or use `StringIO` with monkeypatch on sys.stdout)
- No file I/O needed — all output goes to stdout
- Test `errors.py` re-exports each exception class for import convenience

### Exception Serialization Notes

Each exception type has specific attributes (from `domain/exceptions.py`):
- `InvalidImageError`: `.image_path` (Path), `.reason` (str)
- `ColorExtractionError`: `.backend` (Backend), `.message` (str), `.stderr` (str)
- `BackendNotAvailableError`: `.backend` (Backend), `.hint` (str)
- `OutputWriteError`: `.path` (Path), `.reason` (str)
- `ConfigResolutionError`: `.key` (str), `.reason` (str), `.source` (Any)
- `PaletteGenerationError`: `.message` (str), `.backend` (Backend | None)
- All extend `ColorSchemeError` which extends `Exception`
- Use `type(exc).__name__` for the error type string
- Use `str(exc)` for the message field (already human-readable)
- Include extra fields when non-None for debugging

### Files This Story Creates

| File | Status |
|------|--------|
| `src/color_scheme_generator/adapters/output/__init__.py` | CREATE |
| `src/color_scheme_generator/adapters/output/json_output.py` | CREATE |
| `tests/unit/adapters/output/__init__.py` | CREATE |
| `tests/unit/adapters/output/test_json_output.py` | CREATE |

### Testing Requirements Summary

- Unit tests using real domain object constructors — no mocking needed
- Capture stdout via `capsys` or `monkeypatch` on `sys.stdout` with `StringIO`
- All JSON outputs must be parseable by `json.loads()`
- Every ColorSchemeError subclass must be tested for correct serialization
- Structural isinstance check against OutputPort

### Git Intelligence Summary

- Recent commits (10 most recent) show active development on container processor, config resolution, CLI commands, and code review fixes — none touch output adapters yet
- This is the first output adapter implementation in the CSG project
- Pattern from 1.3: adapter goes in `adapters/<category>/`, test goes in `tests/unit/adapters/<category>/`
- Existing test count: 62 (Stories 1.1-1.3)

## Dev Agent Record

### Agent Model Used

deepseek-v4-flash-free

### Implementation Plan

1. Create `adapters/output/` package structure (init)
2. Implement `JsonOutput` class in `json_output.py`:
   - `ColorScheme` → JSON dict serialization helper (private method)
   - `process_result()` — builds success dict, json.dumps to stdout
   - `error()` — matches exception type, builds error dict with type-specific fields
   - `palette_display()` — outputs ColorScheme as JSON
   - Handle edge cases: non-serializable datetime, Path objects, enum values
3. Create test file with comprehensive coverage across all exception types
4. Verify all 73 tests pass (62 existing + 11 new)
5. Ruff lint passes on new/modified files

### Completion Notes

Implemented JsonOutput adapter with all three OutputPort methods. Used isinstance chain for
error type dispatch and manual dict construction for JSON serialization. All 15 new tests
pass, full regression suite of 77 tests passes, ruff lint clean.

### File List

- `src/color_scheme_generator/adapters/output/__init__.py` — CREATE
- `src/color_scheme_generator/adapters/output/json_output.py` — CREATE
- `tests/unit/adapters/output/__init__.py` — CREATE
- `tests/unit/adapters/output/test_json_output.py` — CREATE

### Change Log

- Added JsonOutput adapter implementing OutputPort for structured JSON output
- Added unit tests covering all ColorSchemeError subclasses, success output, palette_display, structural subtyping, and error invariants

### Review Findings

- [x] [Review][Patch] `process_result` outputs `"color_scheme": null` when `result.color_scheme` is None — AC example specifies `"color_scheme": {...}` (a dict), but `GenerationResult.color_scheme` is typed `ColorScheme | None`. When None, the JSON payload contains `"color_scheme": null` which may crash consumers expecting a dict. [`json_output.py:22`]
- [x] [Review][Patch] `_serialize_error` omits `ConfigResolutionError.source` when non-None — Dev notes suggest including extra fields for debugging context. `ConfigResolutionError` has an optional `source: Any = None` parameter that is never included in the serialized output. Include when non-None. [`json_output.py:77-78`]
