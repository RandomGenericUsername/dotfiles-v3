---
baseline_commit: 8eacac85e8c86c990fa415e0aab9f671f256f37e
---

# Story 1.2: Core Ports (Minimal)

Status: done

## Story

As a developer,
I want the minimal port interfaces for palette extraction defined,
So that backend adapters and output adapters implement against stable contracts.

## Acceptance Criteria

### PaletteGeneratorPort (Protocol)

**Given** PaletteGeneratorPort (Protocol)
**When** defined
**Then** it has `generate(image_path: Path, config: GeneratorConfig) -> ColorScheme`
**And** `is_available() -> bool`
**And** it is `@runtime_checkable`

### ColorSchemeProcessorPort (Protocol)

**Given** ColorSchemeProcessorPort (Protocol)
**When** defined
**Then** it has `process_generate(request: GenerationRequest, settings: AppSettings) -> GenerationResult`
**And** `process_show(request: GenerationRequest, settings: AppSettings) -> GenerationResult`
**And** the interface is runtime-agnostic (no local/container assumptions)

### OutputPort (Protocol)

**Given** OutputPort (Protocol)
**When** defined
**Then** it has `process_result(result: GenerationResult)` and `error(exc: ColorSchemeError)`
**And** `palette_display(scheme: ColorScheme)`

### Structural Subtyping

**Given** all three protocols
**When** verified via `isinstance(obj, Protocol)`
**Then** they pass structural subtype checking

## Tasks / Subtasks

### Port Interfaces
- [x] Create `src/color_scheme_generator/ports/__init__.py` re-exporting all port symbols (AC: all)
- [x] Create `src/color_scheme_generator/ports/palette_generator.py` with `PaletteGeneratorPort` (AC: PaletteGeneratorPort)
- [x] Create `src/color_scheme_generator/ports/processor.py` with `ColorSchemeProcessorPort` (AC: ColorSchemeProcessorPort)
- [x] Create `src/color_scheme_generator/ports/output.py` with `OutputPort` (AC: OutputPort)

### Tests
- [x] Create `tests/unit/ports/__init__.py`
- [x] Create `tests/unit/ports/test_interfaces.py` with mock implementations verifying structural subtype checks (AC: structural subtyping)

## Dev Notes

### Architecture Compliance

- All ports are `@runtime_checkable` Protocols — no ABCs, no inheritance. Structural subtyping means any object with matching methods satisfies the contract.
- `PaletteGeneratorPort` is an outbound port (domain calls it). `ColorSchemeProcessorPort` is the core processing port. `OutputPort` is an outbound port (processor calls it).
- `AppSettings` is a forward reference — not defined until Epic 2 (Story 2.1). Use `TYPE_CHECKING` guard for the import. The port method signatures annotate it by name; runtime isinstance checks for `ColorSchemeProcessorPort` can only work once `AppSettings` exists in domain.
- Domain types referenced by all ports already exist from Story 1.1: `Path`, `Backend`, `ColorScheme`, `GeneratorConfig`, `GenerationRequest`, `GenerationResult`, `ColorSchemeError`.
- `from __future__ import annotations` in all port modules (matching Story 1.1 convention).
- No Pydantic imports in ports — domain types only. Pydantic lives at adapter boundary (D6, ADR-012).
- Ports directory mirrors architecture plan §10 structure.

### Previous Story Intelligence

- Story 1.1 established domain foundation: enums, models, services, exceptions, test suite (46 tests).
- Package path: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/`
- All domain modules use `from __future__ import annotations`.
- `__init__.py` files re-export public symbols with `__all__`.
- Domain layer: zero I/O, stdlib-only imports for domain.

### Library & Dependency Requirements

- Python >= 3.14
- Standard library only (Protocol, runtime_checkable from `typing`)
- `hatchling` for build backend

### Files This Story Creates

| File | Status |
|------|--------|
| `src/color_scheme_generator/ports/__init__.py` | CREATE |
| `src/color_scheme_generator/ports/palette_generator.py` | CREATE |
| `src/color_scheme_generator/ports/processor.py` | CREATE |
| `src/color_scheme_generator/ports/output.py` | CREATE |
| `tests/unit/ports/__init__.py` | CREATE |
| `tests/unit/ports/test_interfaces.py` | CREATE |

### Testing Requirements

Create `tests/unit/ports/` with:
- `test_interfaces.py` — structural subtype testing for each port using mock implementations

Each test creates a minimal mock class that matches the protocol's method signatures and verifies `isinstance(mock, Protocol) is True`. Also verify that a clearly wrong class (missing methods) does NOT pass isinstance.

Domain tests: no fixtures, no temp files, no mocking — pure function calls only (NFR-6).

### Git Intelligence Summary

Story 1.1 established the domain layer with 14 files and 46 tests. No prior port interface work exists. Architecture plan §4 defines all port interfaces; this story implements the minimal subset needed for Epic 1.

### Review Findings

- [x] [Review][Patch] AppSettings imported from a module that does not define it — added `class AppSettings: pass` placeholder in `domain/models.py`. Typechecker import resolves. Will be fleshed out in Story 2.1.
- [x] [Review][Defer] `@runtime_checkable` does not enforce signatures or method-ness — deferred. `runtime_checkable` limitation is a well-known Python trait; real signature enforcement belongs to a static typechecker in CI, which is out of scope for this story.
- [x] [Review][Defer] Mock `process_generate` / `process_show` use `settings: object` while port declares `settings: AppSettings` — deferred. `AppSettings` doesn't exist yet — will fix when it lands in Story 2.1. Mock annotations cannot match the port until the type is defined.
- [x] [Review][Resolved] `process_show` returns bare `ColorScheme` with no failure channel — resolved by changing to `GenerationResult` return type. Both processor methods now return `GenerationResult` with symmetric success/failure shape. Updated port, test mock, AC in epics.md, and architecture plan.
- [x] [Review][Defer] `OutputPort.error` restricted to `ColorSchemeError` only — deferred. AC explicitly defines `error(exc: ColorSchemeError)`; broaden to `Exception` if needed in Epics 3 or 4 when real adapter error scenarios emerge.
- [x] [Review][Resolved] Two competing truth sources for backend — resolved by removing `backend_name` from `PaletteGeneratorPort`. Backend identity is now solely the `Backend` enum key in `BackendRegistry` dict and `GeneratorConfig.backend`. `backend_name` property was unused by all downstream consumers.
- [x] [Review][Patch] Negative-case tests only exercise the empty-class case — added partial-implementation negative tests for each port (missing `is_available`, `process_show`, `palette_display`).
- [x] [Review][Patch] `__import__("datetime").datetime.now()` is opaque and non-deterministic — replaced with top-of-file `from datetime import datetime` and `datetime.now()`. Mocks now use a single shared `_now` constant for reproducibility.

## Change Log

- (2026-07-15) Story created from epics.md definition
- (2026-07-15) Removed `backend_name` property from `PaletteGeneratorPort` — resolved review finding about competing truth sources (removed source). Backend identity is now solely the `Backend` enum key in `BackendRegistry`. Updated AC, architecture plan, test mock, and port code accordingly.
- (2026-07-15) Changed `process_show` return type from `ColorScheme` to `GenerationResult` — symmetric with `process_generate`. Resolved review finding about failure channel. Updated AC, architecture plan, test mock, and port code accordingly.

## Dev Agent Record

### Agent Model Used

deekseek-v4-flash-free

### Implementation Plan

1. Create `ports/__init__.py` re-exporting PaletteGeneratorPort, ColorSchemeProcessorPort, OutputPort
2. Create `ports/palette_generator.py` with PaletteGeneratorPort (Protocol with generate, is_available)
3. Create `ports/processor.py` with ColorSchemeProcessorPort (Protocol with process_generate, process_show) — uses TYPE_CHECKING for AppSettings forward reference
4. Create `ports/output.py` with OutputPort (Protocol with process_result, error, palette_display)
5. Create `tests/unit/ports/__init__.py`
6. Create `tests/unit/ports/test_interfaces.py` with 3 mock classes + 6 test cases (pass/fail for each port)
7. Run tests

### Debug Log

### Completion Notes List

- Created 3 `@runtime_checkable` Protocol port interfaces: `PaletteGeneratorPort`, `ColorSchemeProcessorPort`, `OutputPort`
- `PaletteGeneratorPort`: `generate()`, `is_available()`
- `ColorSchemeProcessorPort`: `process_generate()`, `process_show()` — both return `GenerationResult`; `TYPE_CHECKING` guard for `AppSettings`
- `OutputPort`: `process_result()`, `error()`, `palette_display()`
- Created tests: 6 cases (valid/invalid isinstance checks for each of 3 ports)
- All 52 tests pass (46 existing + 6 new)

### File List

- `src/color_scheme_generator/ports/__init__.py`
- `src/color_scheme_generator/ports/palette_generator.py`
- `src/color_scheme_generator/ports/processor.py`
- `src/color_scheme_generator/ports/output.py`
- `tests/unit/ports/__init__.py`
- `tests/unit/ports/test_interfaces.py`
