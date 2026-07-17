---
baseline_commit: 9f9c9b12ac8939cebc885a6d0f5d2da72999e237
---

# Story 2.4: Pywal Backend Adapter

Status: done

## Story

As a theming user,
I want to extract palettes using pywal (wal binary),
So that I get colors matching my pywal-based workflow.

## Acceptance Criteria

### AC 1: PywalGenerator implements PaletteGeneratorPort

**Given** PywalGenerator implementing PaletteGeneratorPort
**When** generate() is called
**Then** it shells out to `wal -i <image> -n -s -t -e --backend <algorithm>` via subprocess
**And** reads the palette from stdout (using wal's `--stdout` flag — investigated in this story)
**Or** falls back to reading `~/.cache/wal/colors.json` if stdout mode is unavailable
**And** applies saturation adjustment via ColorAdjustmentService
**And** non-zero exit code raises ColorExtractionError with captured stderr
**And** subprocess has a configurable timeout (default 60s) — timeout raises ColorExtractionError

### AC 2: Backend availability detection

**Given** PywalGenerator.is_available()
**When** `wal` is on PATH
**Then** returns True
**When** `wal` is not on PATH
**Then** returns False (no exception)

### AC 3: Saturation adjustment

**Given** a successfully extracted palette
**When** saturation param is applied
**Then** all colors are adjusted via ColorAdjustmentService.adjust_saturation(color, factor)
**And** the saturation factor comes from GeneratorConfig.params["saturation"] (default 1.0)

### AC 4: Error handling

**Given** a subprocess that exits non-zero
**When** capture is attempted
**Then** ColorExtractionError is raised with the captured stderr and backend=Backend.PYWAL
**Given** a subprocess that times out
**When** the configured timeout (default 60s) is exceeded
**Then** ColorExtractionError is raised with a timeout message
**Given** the fallback cache file is partially written
**When** reading `~/.cache/wal/colors.json`
**Then** the adapter retries once after a short delay before raising ColorExtractionError

### AC 5: Structural subtyping

**Given** PywalGenerator
**When** verified via `isinstance(obj, PaletteGeneratorPort)`
**Then** it passes structural subtype checking

## Tasks / Subtasks

- [x] Implement PywalGenerator.generate() (AC: 1)
  - [x] Build subprocess command: `wal -i <image> -n -s -t -e --backend <algorithm>`
  - [x] Capture stdout — investigate wal's `--stdout` support; fall back to `~/.cache/wal/colors.json`
  - [x] Parse extracted colors from JSON cache file format
  - [x] Build ColorScheme with background (darkest), foreground (lightest), cursor (highest contrast), and 16 sorted colors
  - [x] Apply saturation via ColorAdjustmentService
  - [x] Apply configurable subprocess timeout (default 60s)
- [x] Implement PywalGenerator.is_available() (AC: 2)
  - [x] Use `shutil.which("wal")` — return True if found, False otherwise
- [x] Handle subprocess errors (AC: 4)
  - [x] Non-zero exit → ColorExtractionError(Backend.PYWAL, message, stderr)
  - [x] Timeout → ColorExtractionError with timeout message
  - [x] Partially written cache file → retry once with short delay, then raise
- [x] Wire into factory.py (AC: 1)
  - [x] Add PywalGenerator() to BackendRegistry in create_backend_registry()
- [x] Update adapters/backends/__init__.py exports
- [x] Write tests (AC: 1-5)
  - [x] is_available returns True when wal is on PATH
  - [x] is_available returns False when wal is not on PATH
  - [x] generate shells out with correct args
  - [x] generate parses stdout/cache correctly
  - [x] generate applies saturation
  - [x] generate raises ColorExtractionError on non-zero exit
  - [x] generate raises ColorExtractionError on timeout
  - [x] generate retries on partially written cache
  - [x] structural subtyping (isinstance check)

## Dev Notes

### Current State

The PywalGenerator stub already exists at `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/backends/pywal_generator.py`. It currently returns `False` from `is_available()` and raises `NotImplementedError` from `generate()`. Both methods must be replaced with real implementations.

### Established Pattern (from CustomGenerator)

- Follow the same pattern as `adapters/backends/custom_generator.py`:
  - Class-based adapter with `generate(image_path, config)` and `is_available()` methods
  - `generate()` calls `self.is_available()` first and raises `BackendNotAvailableError` if unavailable
  - Domain exceptions raised on errors (no bare `OSError` / `subprocess.CalledProcessError`)
  - `is_available()` is side-effect free (no subprocess calls, no file I/O)
  - Lazy imports are not needed here (no heavy optional deps)

### Command to investigate

Research wal's `--stdout` flag support. The wal binary (pywal) version >= 3.3.0 should support `--stdout` or equivalent flag. If available, prefer stdout parsing over cache file reading for determinism (no stale cache state).

### Cache file format

`~/.cache/wal/colors.json` format:
```json
{
  "wallpaper": "/path/to/image",
  "alpha": "100",
  "special": {
    "background": "#1a1b26",
    "foreground": "#a9b1d6",
    "cursor": "#c0caf5"
  },
  "colors": {
    "color0": "#1a1b26",
    "color1": "#f7768e",
    ...
    "color15": "#a9b1d6"
  }
}
```

- `special.background` → `ColorScheme.background`
- `special.foreground` → `ColorScheme.foreground`
- `special.cursor` → `ColorScheme.cursor`
- `colors.color0` through `colors.color15` → `ColorScheme.colors`
- Each value is a hex string like `"#1a1b26"` — can be directly used as `Color.hex`
- Generate RGB using `int(hex[1:3], 16)` pattern

### Saturation application

After parsing colors from wal output/cache, apply `ColorAdjustmentService.adjust_saturation(c, factor)` where `factor = config.params.get("saturation", 1.0)`. Same pattern as CustomGenerator.generate() lines 68-76.

### Timeout handling

Use `subprocess.run(args, capture_output=True, timeout=timeout)` with a try/except for `subprocess.TimeoutExpired`. The timeout value comes from a constant (default 60s). On timeout, raise `ColorExtractionError(Backend.PYWAL, "subprocess timed out after 60s")`.

### Partially written cache retry

If the cache file read fails (e.g., `json.JSONDecodeError` or truncated content), wait 100ms and retry once. If still failing, raise `ColorExtractionError`. This pattern handles the race condition where wal is still writing the cache file when the adapter reads it.

### Project Structure Notes

- Adapter location: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/backends/pywal_generator.py` (already exists as stub)
- Tests: `src/cli-tools/color-scheme-generator/tests/unit/adapters/backends/test_pywal_generator.py` (new file)
- Port interface: `ports/palette_generator.py` — PaletteGeneratorPort Protocol
- Factory wiring: `factory.py` — add to `create_backend_registry()` alongside CustomGenerator
- Domain models: `domain/enums.py` (Backend.PYWAL), `domain/models.py` (ColorScheme, GeneratorConfig), `domain/services.py` (ColorAdjustmentService)
- Domain exceptions: `domain/exceptions.py` (ColorExtractionError, BackendNotAvailableError)

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Dev Notes from Previous Story (2.3)

- config-assembler-engine is at `src/shared/config-assembler-engine/` — not directly relevant here (PywalGenerator doesn't use it)
- Review finding: empty-string paths and missing-existence checks are concerns to validate
- 15 tests written for 2.3 backend catalog; ~11 tests expected here (similar adapter pattern)
- All 181 existing tests + 15 new passed in 2.3, no regressions — same rigor expected here

### Post-implementation verification

```bash
cd src/cli-tools/color-scheme-generator
pytest
ruff check --fix
```

### Implementation Plan

1. Implement `PywalGenerator.is_available()` using `shutil.which("wal")`
2. Implement `PywalGenerator.generate()`:
   - Check availability first (raise BackendNotAvailableError if not)
   - Build subprocess command with params from GeneratorConfig.params
   - Try to capture stdout (if `--stdout` is supported by wal)
   - Fall back to reading `~/.cache/wal/colors.json`
   - Parse JSON, create Color objects, apply saturation
   - Build ColorScheme with background/foreground/cursor/16 colors
3. Handle error cases (non-zero exit, timeout, partial cache)
4. Wire into factory.py BackendRegistry
5. Write tests (mock subprocess, mock shutil.which, mock file reads)

### Completion Notes

- Implemented `PywalGenerator.is_available()` using `shutil.which("wal")` — side-effect free
- Implemented `PywalGenerator.generate()` with subprocess shell-out to `wal -i <image> -n -s -t -e --backend <algorithm>`
  - Captures stdout first; falls back to `~/.cache/wal/colors.json` cache file
  - Parses 16 colors from cache JSON (`color0`–`color15`)
  - Sorts colors by brightness, applies saturation via `ColorAdjustmentService`
  - Configurable subprocess timeout (default 60s)
- Error handling: non-zero exit → `ColorExtractionError` with stderr; timeout → `ColorExtractionError`; partially written cache → retry once with 100ms delay
- Factory wiring and `__init__.py` exports were already in place (pre-existing)
- 11 tests written: availability (4), subprocess args, cache parsing, saturation, non-zero exit, timeout, cache retry, structural subtyping
- 192 tests pass (181 existing + 11 new), zero regressions
- Ruff clean for pywal_generator.py and test_pywal_generator.py

### Dependencies

- No new PyPI dependencies — uses built-in `subprocess`, `shutil`, `json`, `pathlib`

### References

- [Source: epics.md:367-389] Story 2.4 acceptance criteria
- [Source: ARCHITECTURE_PLAN.md:119-120] PywalGenerator adapter spec
- [Source: ARCHITECTURE_PLAN.md:698-699] factory.py BackendRegistry wiring pattern
- [Source: ARCHITECTURE_PLAN.md:537-552] Dependencies — pywal extra, optional dep
- [Source: domain/enums.py:6-23] Backend enum (PYWAL, install_hint property)
- [Source: domain/models.py:18-54] Color, ColorScheme models
- [Source: domain/models.py:57-62] GeneratorConfig (params dict)
- [Source: domain/services.py:27-31] ColorAdjustmentService.adjust_saturation()
- [Source: domain/exceptions.py:20-26] ColorExtractionError
- [Source: domain/exceptions.py:28-32] BackendNotAvailableError
- [Source: adapters/backends/custom_generator.py] Established pattern reference
- [Source: tests/unit/adapters/backends/test_custom_generator.py] Test pattern reference
- [Source: adapters/backends/pywal_generator.py] Current stub file

## File List

- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/backends/pywal_generator.py` (modified — replaced stub with full implementation)
- `src/cli-tools/color-scheme-generator/tests/unit/adapters/backends/test_pywal_generator.py` (new — 11 test cases)

## Change Log

- 2026-07-16: Implemented PywalGenerator with subprocess-based palette extraction, cache fallback, error handling, and 11 tests

### Review Findings

- [x] [Review][Patch] Use `special` fields from cache for bg/fg/cursor instead of brightness sort [pywal_generator.py:76-78]
- [x] [Review][Patch] Missing `--stdout` flag in subprocess command [pywal_generator.py:38-43]
- [x] [Review][Patch] Empty color list crashes on background/foreground/cursor access [pywal_generator.py:76-78]
- [x] [Review][Patch] Invalid hex conversion in stdout parsing raises raw ValueError [pywal_generator.py:96]
- [x] [Review][Patch] Invalid hex conversion in cache parsing raises raw ValueError [pywal_generator.py:112]
- [x] [Review][Patch] Non-numeric saturation value raises ValueError [pywal_generator.py:70]
- [x] [Review][Patch] Background/foreground selected before saturation — order may shift [pywal_generator.py:69-77]
- [x] [Review][Patch] Custom timeout of 0 or negative causes spurious TimeoutExpired [pywal_generator.py:35]
- [x] [Review][Patch] Dead code `return {}` in `_read_cache_with_retry` [pywal_generator.py:129]
- [x] [Review][Patch] Cache race condition — 0.1s retry delay may be insufficient [pywal_generator.py:11]
- [x] [Review][Defer] Hardcoded cache path ignores XDG_CACHE_HOME [pywal_generator.py:19] — deferred, pre-existing per spec
- [x] [Review][Defer] Stdout parsing only accepts 6-digit hex [pywal_generator.py:95] — deferred, wal uses 6-digit format
- [x] [Review][Defer] Cache parsing doesn't handle 8-digit ARGB [pywal_generator.py:110-112] — deferred, wal uses 6-digit
- [x] [Review][Defer] No test validates bg/fg/cursor selection semantics — deferred, test gap
- [x] [Review][Defer] No isolated tests for parse methods — deferred, tested indirectly
