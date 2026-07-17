---
baseline_commit: e05b8dadbb4009e3d52c99fce3cf7d696ede8b62
---

# Story 2.5: Wallust Backend Adapter

Status: done

## Story

As a theming user,
I want to extract palettes using wallust (Rust binary),
So that I get colors matching my wallust-based workflow.

## Acceptance Criteria

### AC 1: WallustGenerator implements PaletteGeneratorPort

**Given** WallustGenerator implementing PaletteGeneratorPort
**When** generate() is called
**Then** it shells out to `wallust run <image> --backend <type> -s -T -q --print-scheme` via subprocess
**And** reads the palette from stdout (using wallust's `--print-scheme` flag)
**Or** falls back to reading the wallust cache file at `~/.cache/wallust/colors.json`
**And** applies saturation adjustment via ColorAdjustmentService
**And** non-zero exit code raises ColorExtractionError with captured stderr
**And** subprocess has a configurable timeout (default 60s) — timeout raises ColorExtractionError

### AC 2: Backend availability detection

**Given** WallustGenerator.is_available()
**When** `wallust` is on PATH
**Then** returns True
**When** `wallust` is not on PATH
**Then** returns False (no exception)

### AC 3: Saturation adjustment

**Given** a successfully extracted palette
**When** saturation param is applied
**Then** all colors are adjusted via ColorAdjustmentService.adjust_saturation(color, factor)
**And** the saturation factor comes from GeneratorConfig.params["saturation"] (default 1.0)

### AC 4: Error handling

**Given** a subprocess that exits non-zero
**When** capture is attempted
**Then** ColorExtractionError is raised with the captured stderr and backend=Backend.WALLUST
**Given** a subprocess that times out
**When** the configured timeout (default 60s) is exceeded
**Then** ColorExtractionError is raised with a timeout message
**Given** the fallback cache file is partially written
**When** reading `~/.cache/wallust/colors.json`
**Then** the adapter retries once after a short delay before raising ColorExtractionError

### AC 5: Structural subtyping

**Given** WallustGenerator
**When** verified via `isinstance(obj, PaletteGeneratorPort)`
**Then** it passes structural subtype checking

## Tasks / Subtasks

- [x] Implement WallustGenerator.generate() (AC: 1)
  - [x] Build subprocess command: `wallust run <image> --backend <type> -s -T -q --print-scheme`
  - [x] Capture stdout — wallust supports `--print-scheme` flag (confirmed from wallust v3.5 source); falls back to `~/.cache/wallust/colors.json`
  - [x] Parse stdout output format: newline-separated hex colors (`#RRGGBB` per line)
  - [x] Parse cache file format (JSON with `color0`-`color15`, `special.background`, `special.foreground`)
  - [x] Build ColorScheme with background (darkest), foreground (lightest), cursor (highest contrast), and 16 sorted colors
  - [x] Apply saturation via ColorAdjustmentService
  - [x] Apply configurable subprocess timeout (default 60s)
- [x] Implement WallustGenerator.is_available() (AC: 2)
  - [x] Use `shutil.which("wallust")` — return True if found, False otherwise
- [x] Handle subprocess errors (AC: 4)
  - [x] Non-zero exit → ColorExtractionError(Backend.WALLUST, message, stderr)
  - [x] Timeout → ColorExtractionError with timeout message
  - [x] Partially written cache file → retry once with short delay, then raise
- [x] Wire into factory.py (AC: 1) — already wired, verify
  - [x] WallustGenerator() already registered in create_backend_registry() — verify existing wiring
- [x] Update adapters/backends/__init__.py exports — already present, verify
- [x] Write tests (AC: 1-5)
  - [x] is_available returns True when wallust is on PATH
  - [x] is_available returns False when wallust is not on PATH
  - [x] is_available is side-effect free
  - [x] generate shells out with correct args
  - [x] generate parses stdout correctly
  - [x] generate applies saturation
  - [x] generate raises ColorExtractionError on non-zero exit
  - [x] generate raises ColorExtractionError on timeout
  - [x] generate retries on partially written cache
  - [x] structural subtyping (isinstance check)

## Dev Notes

### Current State

The WallustGenerator stub already exists at `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/backends/wallust_generator.py`. It currently returns `False` from `is_available()` and raises `NotImplementedError` from `generate()`. Both methods must be replaced with real implementations.

The factory (`factory.py:32`) and `__init__.py` (`__init__.py:5,10`) already import and export WallustGenerator — no wiring changes needed, only the adapter implementation.

### Established Pattern (from PywalGenerator)

- Follow the exact same pattern as `adapters/backends/pywal_generator.py`:
  - Class-based adapter with `generate(image_path, config)` and `is_available()` methods
  - `generate()` calls `self.is_available()` first and raises `BackendNotAvailableError` if unavailable
  - Domain exceptions raised on errors (no bare `OSError` / `subprocess.CalledProcessError`)
  - `is_available()` is side-effect free (no subprocess calls, no file I/O)
  - Saturation factor clamped to [0.0, 1.0] via `_validate_saturation()` helper
  - Hex parsing via `_hex_to_color()` with validation fallback to black

### Wallust command to use (research confirmed)

From wallust v3.5 source (confirmed at `src/main.rs`):

```
wallust run <image> --backend <type> -s -T -q --print-scheme
```

Flag breakdown:
- `--backend <type>` — extraction algorithm (from config.params["algorithm"])
- `-s` / `--skip-sequences` — skip terminal sequence setting
- `-T` / `--skip-templates` — skip template rendering
- `-q` / `--quiet` — suppress info log messages
- `--print-scheme` — output the color scheme to stdout (machine-readable, newline-separated hex colors)

The `--print-scheme` flag (confirmed in main.rs line: `if cli.print_scheme { colors.output_nl(); }`) outputs each color value as a hex string on its own line. This is the wallust equivalent of wal's `--stdout`.

### Cache file format

Wallust cache at `~/.cache/wallust/` (platform-dependent via dirs crate, typically `~/.cache/wallust/`):
- JSON format with `color0`-`color15` keys
- Also contains `special` object with `background`, `foreground`, `cursor`
- Structure mirrors pywal's `~/.cache/wal/colors.json` format

### Algorithm choices

From `defaults/backends.yaml` (architecture plan line 663):
```yaml
wallust:
  algorithm:
    choices: ["kmeans", "kmeans-new", "kmeans-old", "kmeans-improved",
              "fastkmeans", "kmeans-euclid", "pam", "pam-new", "pam-old"]
```

### Key differences from PywalGenerator

| Aspect | Pywal | Wallust |
|--------|-------|---------|
| Binary | `wal` | `wallust` |
| Command | `wal -i <img> -n -s -t -e --backend <algo> --stdout` | `wallust run <img> --backend <type> -s -T -q --print-scheme` |
| is_available check | `shutil.which("wal")` | `shutil.which("wallust")` |
| Backend enum | `Backend.PYWAL` | `Backend.WALLUST` |
| Install hint | `"pip install color-scheme-generator[pywal]"` | `"Install wallust binary"` |
| Stdout flag | `--stdout` | `--print-scheme` |
| Cache path | `~/.cache/wal/colors.json` | `~/.cache/wallust/colors.json` |

### Previous Story Intelligence (from 2.4)

- **Review findings to pre-apply** (from 2.4 review patches):
  - Use `special` fields from cache for bg/fg/cursor instead of brightness sort
  - Include stdout flag in subprocess command
  - Handle empty color list (guard against IndexError on colors[0]/colors[-1])
  - Wrap hex conversion in try/except to prevent raw ValueError
  - Clamp saturation to [0.0, 1.0], reject NaN
  - Apply saturation BEFORE bg/fg/cursor selection (order matters)
  - Validate timeout is a positive number; default to 60s if 0/negative
  - No dead code paths (e.g., `return {}` in cache retry)
  - Use 0.5s cache retry delay (not 0.1s — improved from original pywal)
  - Hardcoded cache path accepted per spec (deferred XDG concern)
- **Test count target**: ~11 tests (matching pywal's 11 tests)
- **All 192 existing tests must pass** — zero regressions
- **Ruff clean required** for both implementation and test files

### Saturation application

After parsing colors from wallust output/cache, apply `ColorAdjustmentService.adjust_saturation(c, factor)` where `factor = config.params.get("saturation", 1.0)`. Same pattern as PywalGenerator.generate().

### Timeout handling

Use `subprocess.run(args, capture_output=True, timeout=timeout)` with a try/except for `subprocess.TimeoutExpired`. The timeout value comes from config.params or default 60s. On timeout, raise `ColorExtractionError(Backend.WALLUST, "subprocess timed out after 60s")`.

### Partially written cache retry

If the cache file read fails (e.g., `json.JSONDecodeError` or truncated content), wait 500ms and retry once. If still failing, raise `ColorExtractionError`. This pattern handles the race condition where wallust is still writing the cache file when the adapter reads it.

### Project Structure Notes

- Adapter location: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/backends/wallust_generator.py` (already exists as stub — replace implementation)
- Tests: `src/cli-tools/color-scheme-generator/tests/unit/adapters/backends/test_wallust_generator.py` (new file)
- Port interface: `ports/palette_generator.py` — PaletteGeneratorPort Protocol
- Factory wiring: `factory.py` — already has `Backend.WALLUST: WallustGenerator()` in `create_backend_registry()`, no change needed
- Domain models: `domain/enums.py` (Backend.WALLUST), `domain/models.py` (ColorScheme, GeneratorConfig), `domain/services.py` (ColorAdjustmentService)
- Domain exceptions: `domain/exceptions.py` (ColorExtractionError, BackendNotAvailableError)

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Dev Notes from Previous Story (2.4)

- PywalGenerator followed the established CustomGenerator pattern — follow same pattern for WallustGenerator
- Review findings from 2.4 identified 13 issues (9 patched, 4 deferred) — pre-apply all patched findings to avoid re-review
- 11 tests written for 2.4 pywal; ~11 tests expected for 2.5 wallust (same adapter pattern)
- All 192 existing tests passed in 2.4, no regressions — same rigor expected here
- Ruff clean required for both wallust_generator.py and test_wallust_generator.py

### Post-implementation verification

```bash
cd src/cli-tools/color-scheme-generator
pytest
ruff check --fix
```

### Implementation Plan

1. Implement `WallustGenerator.is_available()` using `shutil.which("wallust")`
2. Implement `WallustGenerator.generate()`:
   - Check availability first (raise BackendNotAvailableError if not)
   - Build subprocess command with params from GeneratorConfig.params
   - Capture stdout using `--print-scheme` flag
   - Parse stdout: newline-separated hex colors
   - Fall back to reading `~/.cache/wallust/colors.json`
   - Parse JSON, create Color objects, apply saturation
   - Build ColorScheme with background/foreground/cursor/16 colors
3. Handle error cases (non-zero exit, timeout, partial cache)
4. Verify factory wiring (already in place)
5. Write tests (mock subprocess, mock shutil.which, mock file reads)

### Completion Notes

- Implemented WallustGenerator.is_available() using shutil.which("wallust")
- Implemented WallustGenerator.generate() with full subprocess command, stdout parsing, cache fallback, saturation adjustment, and ColorScheme construction
- All 9 pre-applied review findings from 2.4 incorporated (special fields from cache, empty color list guard, hex conversion try/except, saturation clamping, pre-sort saturation, timeout validation, no dead code, 0.5s cache retry, --print-scheme flag)
- 11 tests written covering all acceptance criteria and error conditions
- All 203 tests pass (192 existing + 11 new)
- Ruff clean on both implementation and test files

### Dependencies

- No new PyPI dependencies — uses built-in `subprocess`, `shutil`, `json`, `pathlib`

### References

- [Source: epics.md:390-411] Story 2.5 acceptance criteria
- [Source: ARCHITECTURE_PLAN.md:119-120] WallustGenerator adapter spec
- [Source: ARCHITECTURE_PLAN.md:698-699] factory.py BackendRegistry wiring pattern
- [Source: ARCHITECTURE_PLAN.md:663] Wallust algorithm choices from backends.yaml
- [Source: domain/enums.py:6-9] Backend enum (WALLUST, install_hint property)
- [Source: domain/models.py:18-62] Color, ColorScheme, GeneratorConfig models
- [Source: domain/services.py:27-30] ColorAdjustmentService.adjust_saturation()
- [Source: domain/exceptions.py:20-32] ColorExtractionError, BackendNotAvailableError
- [Source: adapters/backends/pywal_generator.py] Established pattern reference (full implementation)
- [Source: tests/unit/adapters/backends/test_pywal_generator.py] Test pattern reference
- [Source: adapters/backends/wallust_generator.py] Current stub file
- [Source: wallust v3.5 man page] `--print-scheme` stdout flag confirmed
- [Source: wallust src/main.rs] `--print-scheme` outputs `colors.output_nl()` to stdout

### Review findings pre-applied (from 2.4 review)

Prevent re-review of issues already caught in 2.4:
1. Use `special` fields from cache for bg/fg/cursor instead of brightness sort
2. Include `--print-scheme` flag in subprocess command
3. Guard against empty color list (IndexError on colors[0]/colors[-1])
4. Wrap hex conversion in try/except (no bare ValueError)
5. Validate and clamp saturation to [0.0, 1.0], reject NaN
6. Apply saturation BEFORE bg/fg/cursor selection
7. Validate timeout is positive int/float; default to 60s if 0/negative
8. No dead code paths in cache retry
9. Use 0.5s cache retry delay (not 0.1s)

## File List

- `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/backends/wallust_generator.py` (modified — replace stub with full implementation)
- `src/cli-tools/color-scheme-generator/tests/unit/adapters/backends/test_wallust_generator.py` (new — ~11 test cases)

## Change Log

- 2026-07-16: Created comprehensive story spec for Wallust Backend Adapter
- 2026-07-16: Implemented WallustGenerator — replaced stub with full implementation, added 11 tests, all 203 pass, ruff clean

### Review Findings

- [x] [Review][Patch] `Path.home()` evaluated at import time for `_CACHE_FILE` [wallust_generator.py:20] — Defer to lazy property or function call; `Path.home()` raises `RuntimeError` in headless environments (containers, CI without $HOME).
- [x] [Review][Patch] Unhandled cache JSON crashes: root non-dict or `colors` field non-dict [wallust_generator.py:154-165] — `_read_cache_with_retry()` returns raw `json.load()` output; if cache file root is a JSON array/scalar, `data.get("colors", {})` raises `AttributeError`; if `colors` value is null/non-dict, `.get(key)` crashes. Add `isinstance` guards.
- [x] [Review][Patch] Variable color count from stdout crashes `ColorScheme` [wallust_generator.py:140-151] — `_parse_stdout()` can return 0–N colors but `ColorScheme.__post_init__` requires exactly 16. Use `PaletteNormalizationService.normalize()` to pad/truncate.
- [x] [Review][Patch] TOCTOU race on subprocess binary [wallust_generator.py:50-60] — If wallust is deleted between `shutil.which()` and `subprocess.run()`, `FileNotFoundError` is unhandled. Wrap in try/except and translate to `ColorExtractionError`.
- [x] [Review][Patch] NaN/Inf subprocess timeout bypasses guard [wallust_generator.py:36-40] — `float('nan')` passes `isinstance` check and `nan < 1` is `False`; `subprocess.run(timeout=nan)` raises `ValueError`. Add `math.isnan()` and `math.isinf()` checks.
- [x] [Review][Patch] `_hex_to_color` silently returns black for corrupt cache entries [wallust_generator.py:124-137] — Missing/ invalid cache entries produce `#000000` with no warning. Add logging.
- [x] [Review][Patch] Test imports private constant `_SUBPROCESS_TIMEOUT` [test_wallust_generator.py:11] — `_`-prefixed constants are implementation details; make public or have test define its own.
- [x] [Review][Patch] `test_is_available_side_effect_free` asserts nothing [test_wallust_generator.py:41-46] — Calls `is_available()` under two patches but never asserts any return value. Remove or add assertions.
- [x] [Review][Patch] Wrong return type annotation on `_parse_cache_file` [wallust_generator.py:154] — `dict[str, str]` is incorrect; values can be `None` from `.get()`. Fix to `dict[str, str | None]` or `dict[str, Any]`.
- [x] [Review][Defer] Naive sort key `sum(c.rgb)` for luminance [wallust_generator.py:84] — Uses `sum(c.rgb)` which perceptually underweights blue. However, this matches the codebase-wide `PaletteNormalizationService.sort_by_brightness()`, so it's a pre-existing project pattern, not specific to this change.
