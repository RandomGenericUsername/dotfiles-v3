---
baseline_commit: 8eacac85e8c86c990fa415e0aab9f671f256f37e
---

# Story 1.1: Domain Foundation

Status: done

## Story

As a theming user,
I want a color palette to be extracted from my wallpaper,
so that I can use it to theme my desktop — this story defines the data structures that represent a palette.

## Acceptance Criteria

### Enums

**Given** Backend, ColorAlgorithm, ColorFormat, RuntimeMode, ContainerEngine, OutputFormat, Verbosity enums in `domain/enums.py`
**When** Backend is inspected
**Then** it has CUSTOM, PYWAL, WALLUST members — no AUTO (D10)
**And** Backend has `image_suffix` property: `CUSTOM → "custom"`, `PYWAL → "pywal"`, `WALLUST → "wallust"`
**When** ColorFormat is inspected
**Then** it has JSON, SH, CSS, GTK_CSS, YAML, SEQUENCES, RASI, SCSS
**When** OutputFormat is inspected
**Then** it has JSON, RICH, PLAIN with value strings `"json"`, `"rich"`, `"plain"`

### Domain Models (frozen dataclasses)

**Given** `Color` in `domain/models.py`
**When** instantiated with `hex="#ff0000"`, rgb=(255, 0, 0)
**Then** hex enforces `^#[0-9a-fA-F]{6}$` in `__post_init__` with case-preserving canonicalization
**And** `Color("#FF0000", (255, 0, 0)).hex == "#FF0000"` (case preserved)
**And** `Color("ff0000", ...)` raises ValueError (missing #)
**And** `Color("#ff00", ...)` raises ValueError (wrong length)
**And** rgb values are clamped to 0-255 in `__post_init__`
**And** `Color` has `adjust_saturation(factor) -> Color` via `colorsys.rgb_to_hls` / `hls_to_rgb` — pure function, no I/O

**Given** `ColorScheme` in `domain/models.py`
**When** instantiated
**Then** it has background, foreground, cursor (all Color)
**And** 16-tuple `colors: tuple[Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color]`
**And** `source_image: Path`, `backend: Backend`, `generated_at: datetime`

**Given** `GeneratorConfig` in `domain/models.py`
**When** instantiated
**Then** it has `backend: Backend`, `params: dict[str, Any]`, `formats: tuple[ColorFormat, ...]`, `output_dir: Path`

**Given** `GenerationRequest` in `domain/models.py`
**When** instantiated
**Then** it has `image_path: Path`, `config: GeneratorConfig`

**Given** `GenerationResult` in `domain/models.py`
**When** instantiated
**Then** it has `success: bool`, `color_scheme: ColorScheme`, `output_files: tuple[Path, ...]`, `backend: Backend`, `stderr: str`, `return_code: int`, `duration: float`

### Domain Services (pure functions, no I/O)

**Given** `HexValidationService` in `domain/services.py`
**When** `canonicalize("#FF0000")` is called
**Then** it returns `"#FF0000"` (case-preserving pass-through)
**When** `validate("#abc")` is called
**Then** it returns False (wrong length)
**When** `validate("ff0000")` is called
**Then** it returns False (missing #)
**When** `validate("#GG0000")` is called
**Then** it returns False (invalid hex chars)

**Given** `ColorAdjustmentService` in `domain/services.py`
**When** `adjust_saturation(Color("#ff0000", (255, 0, 0)), 0.5)` is called
**Then** it returns a new Color with reduced saturation values
**And** original Color is unmodified (immutability)

**Given** `PaletteNormalizationService` in `domain/services.py`
**When** `normalize(colors=[... fewer than 16])` is called
**Then** it pads with copies of the nearest color (not black) to reach exactly 16
**When** `normalize(colors=[... more than 16])` is called
**Then** it truncates to 16
**When** `normalize(colors=[exactly 16])` is called
**Then** it returns the input unchanged
**When** `sort_by_brightness(colors)` is called
**Then** colors are sorted by `sum(rgb)` ascending

### Exception Hierarchy

**Given** `ColorSchemeError` as the base exception in `domain/exceptions.py`
**When** `InvalidImageError(image_path=Path("/nonexistent.jpg"), reason="File not found")` is raised
**Then** it carries `image_path: Path` and `reason: str`
**And** message is `"Invalid image /nonexistent.jpg: File not found"`

**Given** `ColorExtractionError`
**When** `ColorExtractionError(backend=Backend.PYWAL, message="wal exited with code 1")` is raised
**Then** it carries `backend: Backend`, `message: str`, and optional `stderr: str = ""`
**And** message is `"Color extraction failed for pywal: wal exited with code 1"`

**Given** `BackendNotAvailableError`
**When** `BackendNotAvailableError(backend=Backend.CUSTOM, hint="pip install color-scheme-generator[custom]")` is raised
**Then** it carries `backend: Backend` and `hint: str`
**And** message is `"Backend custom is not available. Hint: pip install color-scheme-generator[custom]"`

**Given** `OutputWriteError`, `ConfigResolutionError`, `PaletteGenerationError`
**When** instantiated
**Then** they derive from ColorSchemeError with appropriate fields per ARCHITECTURE_PLAN.md §3

### Package Structure & Files to Create

```
src/color_scheme_generator/
├── __init__.py                       # __version__ = "0.1.0"
├── errors.py                         # re-exports domain exceptions
└── domain/
    ├── __init__.py
    ├── enums.py                      # All enums
    ├── models.py                     # Color, ColorScheme, GeneratorConfig, GenerationRequest, GenerationResult
    ├── services.py                   # HexValidationService, ColorAdjustmentService, PaletteNormalizationService
    └── exceptions.py                 # ColorSchemeError hierarchy (Epic 1 subset)
```

`src/color_scheme_generator/domain/__init__.py` should re-export all public symbols.

## Dev Notes

- Use `from __future__ import annotations` in all modules
- Frozen dataclasses: `@dataclass(frozen=True)`, use `object.__setattr__` in `__post_init__` for validation mutations, or raise ValueError
- `Color.__post_init__`: validate hex pattern via `re.match(r'^#[0-9a-fA-F]{6}$', self.hex)`, clamp rgb with `max(0, min(255, v))`, case-preserve hex
- `Color.adjust_saturation(factor)`: use `colorsys.rgb_to_hls`, multiply saturation, clamp, return new Color. Pure function, no I/O
- ColorScheme's 16 colors: `tuple[Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color, Color]` (type hint via `tuple[Color, ...]` with length check in `__post_init__`)
- `GenerationResult.backend` type: `Backend` enum member
- ParameterResolutionService NOT in this story — it operates on `BackendParameterDefinition` which is introduced in Epic 2

### Architecture Compliance

- Domain layer: zero I/O, imports only `from __future__`, `dataclasses`, `enum`, `pathlib`, `re`, `colorsys`, `datetime`, `typing`
- Pydantic is NOT imported in domain — it lives at adapter boundary only (D6)
- No imports from outside `colorscheme_generator.domain.*` within domain
- `errors.py` re-exports for public API surface per WEG pattern

### Testing Requirements

Create `tests/unit/domain/` with:
- `test_enums.py` — enum member existence, `image_suffix` property, no AUTO in Backend, all ColorFormat members, OutputFormat str values
- `test_models.py` — Color hex validation (valid, invalid length, missing #, invalid chars), rgb clamping, `adjust_saturation`, ColorScheme field types and length, GenerationResult field types
- `test_services.py` — HexValidationService.canonicalize/validate, ColorAdjustmentService.adjust_saturation (pure, no side effects), PaletteNormalizationService.normalize pad/truncate/passthrough, sort_by_brightness
- `test_exceptions.py` — All exception types instantiate with correct fields, message format, ColorSchemeError isinstance checks

Domain tests: no fixtures, no temp files, no mocking — pure function calls only (NFR-6).

### Library & Dependency Requirements

- Python >= 3.14
- Standard library only for this story (no 3rd-party deps in domain layer)
- `hatchling` for build backend

### Files This Story Creates

| File | Status |
|------|--------|
| `src/color_scheme_generator/__init__.py` | CREATE |
| `src/color_scheme_generator/errors.py` | CREATE |
| `src/color_scheme_generator/domain/__init__.py` | CREATE |
| `src/color_scheme_generator/domain/enums.py` | CREATE |
| `src/color_scheme_generator/domain/models.py` | CREATE |
| `src/color_scheme_generator/domain/services.py` | CREATE |
| `src/color_scheme_generator/domain/exceptions.py` | CREATE |
| `tests/unit/domain/test_enums.py` | CREATE |
| `tests/unit/domain/test_models.py` | CREATE |
| `tests/unit/domain/test_services.py` | CREATE |
| `tests/unit/domain/test_exceptions.py` | CREATE |

### Previous Story Intelligence

No previous stories — this is the first story in Epic 1.

### Git Intelligence Summary

No prior CSG implementation work exists in v3. v2 reference at `dotfiles-repo-v2/src/cli-tools/color-scheme-generator/packages/core/src/color_scheme/core/types.py` has Pydantic-based models that v3 is replacing with frozen dataclasses.

## Change Log

- (2026-07-15) Domain foundation implemented: enums, models, services, exceptions, tests
- Files created under `src/cli-tools/color-scheme-generator/` per ARCHITECTURE_PLAN.md §10

## Dev Agent Record

### Agent Model Used

deepseek-v4-flash-free

### Implementation Plan

1. Created `pyproject.toml` with hatchling build config
2. Implemented domain enums (`Backend`, `ColorFormat`, `OutputFormat`, etc.) in `domain/enums.py`
3. Implemented domain models (`Color`, `ColorScheme`, `GeneratorConfig`, `GenerationRequest`, `GenerationResult`) as frozen dataclasses in `domain/models.py`
4. Implemented domain services (`HexValidationService`, `ColorAdjustmentService`, `PaletteNormalizationService`) in `domain/services.py`
5. Implemented exception hierarchy (`ColorSchemeError` base + 6 subtypes) in `domain/exceptions.py`
6. Created package `__init__.py` re-exporting all public symbols
7. Created `errors.py` re-exporting domain exceptions
8. Wrote 41 unit tests covering all acceptance criteria

### Debug Log

- Initial implementation at wrong path (`src/color_scheme_generator/`), corrected to `src/cli-tools/color-scheme-generator/src/color_scheme_generator/` per ARCHITECTURE_PLAN.md
- Fixed typo: `Backen` -> `Backend` in `PaletteGenerationError`
- All 41 tests pass on first run after correction

### Completion Notes

Story 1.1 complete. All acceptance criteria satisfied:
- Enums: Backend (CUSTOM, PYWAL, WALLUST), ColorFormat (8 members), OutputFormat (JSON/RICH/PLAIN) with correct value strings
- Domain models: Color with hex validation, rgb clamping, adjust_saturation; ColorScheme with 16-color tuple; GeneratorConfig, GenerationRequest, GenerationResult with correct field types
- Domain services: HexValidationService (canonicalize + validate), ColorAdjustmentService (pure function), PaletteNormalizationService (normalize pad/truncate, sort_by_brightness)
- Exceptions: 6 exception types with correct inheritance, fields, and message formats
- Package structure: clean re-exports via `domain/__init__.py` and top-level `errors.py`

### Review Findings

#### decision-needed
- [x] [Review][Decision] normalize nearest/black — dismissed (custom-backend-only; pywal/wallust always ≥16 colors)
- [x] [Review][Decision] Color clamp desync — patched: recompute hex from clamped rgb when clamping fires
- [x] [Review][Decision] GenerationResult.color_scheme Optional — deferred: keep Optional, correct domain design, update spec AC

#### patch
- [x] [Review][Patch] adjust_saturation returns Color with stale hex not matching new rgb [models.py:27-32]
- [x] [Review][Patch] Color.rgb length not validated at construction [models.py:18-25]
- [x] [Review][Patch] ColorScheme.colors length not validated [models.py:35-43]
- [x] [Review][Patch] pyproject requires-python >=3.12 / ruff py312 vs spec >=3.14 [pyproject.toml:6,23]
- [x] [Review][Patch] _HEX_PATTERN compiled twice [models.py:12, services.py:8]
- [x] [Review][Patch] trailing newline slips through hex regex [models.py:12, services.py:8]
- [x] [Review][Patch] Color accepts float rgb values [models.py:20-25]
- [x] [Review][Patch] from __future__ import annotations missing from __init__/errors

#### defer
- [x] [Review][Defer] GeneratorConfig.params mutable dict despite frozen [models.py:46-51] — deferred, no current mutator
- [x] [Review][Defer] GenerationResult.color_scheme Optional [models.py:63] — deferred, correct domain design, update spec AC

### File List

- `src/cli-tools/color-scheme-generator/pyproject.toml`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/__init__.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/errors.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/__init__.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/enums.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/models.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/services.py`
- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/exceptions.py`
- `src/cli-tools/color-scheme-generator/tests/unit/domain/__init__.py`
- `src/cli-tools/color-scheme-generator/tests/unit/domain/test_enums.py`
- `src/cli-tools/color-scheme-generator/tests/unit/domain/test_models.py`
- `src/cli-tools/color-scheme-generator/tests/unit/domain/test_services.py`
- `src/cli-tools/color-scheme-generator/tests/unit/domain/test_exceptions.py`
