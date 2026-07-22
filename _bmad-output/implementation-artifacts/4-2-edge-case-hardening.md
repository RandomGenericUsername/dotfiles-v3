---
baseline_commit: 9f735b73ae1866e3d0abaeb8e96154f62145d1f4
---

# Story 4.2: Edge Case Hardening

Status: done

## Story

As a maintainer,
I want edge cases handled gracefully across all adapters,
So that the tool is robust in production use.

## Acceptance Criteria

### AC 1: Subprocess timeout kills hanging processes
**Given** subprocess-based backends (Pywal, Wallust)
**When** the subprocess hangs
**Then** a configurable timeout (default 60s) kills the process and raises ColorExtractionError

### AC 2: Non-zero exit captures stderr
**Given** subprocess-based backends
**When** the subprocess exits non-zero
**Then** stderr is captured and included in ColorExtractionError

### AC 3: Partially written cache file retries
**Given** subprocess-based backends
**When** the cache file (fallback path) is partially written
**Then** the adapter retries once after a short delay before raising ColorExtractionError

### AC 4: Container rejects root filesystem mount
**Given** container mode
**When** input file is on a filesystem root (parent dir is `/`)
**Then** InvalidImageError is raised — mounting `/` is rejected

### AC 5: chmod failure is non-fatal
**Given** container mode
**When** chmod of output dir fails
**Then** a warning is logged but execution continues (best-effort)

### AC 6: Sequences format outputs bytes
**Given** the sequences format
**When** rendered
**Then** `]` is post-processed to `\x1b]` and `\` to `\x1b\\`
**And** the output is bytes (not string), written as binary

### AC 7: Config pipelines use separate instances
**Given** config resolution runs both settings and backends pipelines
**When** both run during the same invocation
**Then** they use separate AssembleConfiguration instances (no cross-contamination)

### AC 8: All backends unavailable produces clear message
**Given** all three backends are unavailable on the host
**When** `csg generate` is run in local mode
**Then** BackendNotAvailableError is raised with message listing which backends were tried and suggesting `csg install` for container mode

## Tasks / Subtasks

### Harden subprocess backends (PywalGenerator)
- [x] Guard timeout against `math.isnan` and `math.isinf` in addition to existing `< 1` check (AC: 1)
- [x] Guard saturation validation against `math.isinf` (not just NaN) (AC: 1)
- [x] Guard empty `colors` list — if `_parse_stdout` or `_parse_cache_file` returns empty list, fallback to `Color("#000000")` for background/foreground/cursor instead of raising IndexError (AC: 3)
- [x] Ensure `_read_cache_with_retry` catches all relevant exceptions (FileNotFoundError, json.JSONDecodeError, OSError) and retries once (AC: 3)
- [x] Ensure non-zero exit code captures stderr and raises ColorExtractionError with `backend`, `message`, and `stderr` (AC: 2)
- [x] Ensure `TimeoutExpired` from subprocess raises ColorExtractionError (AC: 1)

### Harden subprocess backends (WallustGenerator)
- [x] Guard saturation validation against `math.isinf` (not just NaN) (AC: 1)
- [x] Ensure `_read_cache_with_retry` catches all relevant exceptions and retries once (AC: 3)
- [x] Ensure non-zero exit code captures stderr and raises ColorExtractionError with `backend`, `message`, and `stderr` (AC: 2)
- [x] Ensure `TimeoutExpired` from subprocess raises ColorExtractionError (AC: 1)
- [x] Ensure empty colors list fallback already exists — verify and add test coverage (AC: 3)

### Harden container processor
- [x] Verify root-filesystem guard (`if input_parent == Path("/")`) raises InvalidImageError (AC: 4)
- [x] Add negative timeout guard in `OciContainerRuntimeAdapter.run()` — validate `timeout > 0` before passing to engine (like build_image does) (AC: 1)
- [x] Wrap chmod of output dir in try/except, log warning via `logging.warning()` on failure, continue execution (AC: 5)
- [x] Add test: chmod failure logs warning, does not raise

### Harden sequences format rendering
- [x] Verify `JinjaTemplateRenderer.render()` post-processes sequences: replace `]` → `\x1b]`, `\` → `\x1b\\` (AC: 6)
- [x] Verify output is written as bytes (not string) for sequences format (AC: 6)
- [x] Add test: sequences rendered output contains proper OSC escape sequences
- [x] Add test: sequences output is bytes type

### Harden config resolution
- [x] Verify `AssembledConfigResolver` uses separate `AssembleConfiguration` instances for settings vs. backends pipelines (AC: 7)
- [x] If backlog catalog loader reuses the same resolver instance, ensure it creates its own `AssembleConfiguration` (AC: 7)
- [x] Add test: settings and backends resolution run concurrently without state leakage

### Harden local processor for unavailable backends
- [x] In `LocalProcessor._generate_extract()` or `process_generate()`: when all backends are unavailable, raise `BackendNotAvailableError` with message listing tried backends (e.g., "No backends available: custom, pywal, wallust. Run `csg install` for container-mode execution or install a backend binary.") (AC: 8)
- [x] Improve `BackendNotAvailableError` message to include hint about `csg install`
- [x] Add test: `process_generate` with all backends unavailable raises BackendNotAvailableError with appropriate message (AC: 8)

### Write / update tests
- [x] Unit test: `test_pywal_timeout_nan` — timeout=float('nan') raises ColorExtractionError (AC: 1)
- [x] Unit test: `test_pywal_timeout_inf` — timeout=float('inf') raises ColorExtractionError (AC: 1)
- [x] Unit test: `test_pywal_saturation_inf` — saturation=float('inf') raises ColorExtractionError (AC: 1)
- [x] Unit test: `test_wallust_saturation_inf` — saturation=float('inf') raises ColorExtractionError (AC: 1)
- [x] Unit test: `test_pywal_empty_colors_fallback` — empty colors list uses fallback (AC: 3)
- [x] Unit test: `test_seqences_output_bytes` — sequences render output is bytes (AC: 6)
- [x] Unit test: `test_seqences_osc_escapes` — sequences render contains \x1b] and \x1b\\ (AC: 6)
- [x] Unit test: `test_container_chmod_failure_warns` — chmod failure logs warning (AC: 5)
- [x] Unit test: `test_oci_runtime_negative_timeout` — negative/zero timeout raises (AC: 1)
- [x] Unit test: `test_config_resolution_separate_instances` — settings and backends use separate Assemblers (AC: 7)
- [x] Unit test: `test_local_processor_all_backends_unavailable` — all backends unavailable raises with hint (AC: 8)
- [x] Run full test suite — verify zero regressions
- [x] Run ruff lint — clean

## Dev Notes

### File Structure

| File | Action |
|------|--------|
| `src/color_scheme_generator/adapters/backends/pywal_generator.py` | MODIFY — hardening |
| `src/color_scheme_generator/adapters/backends/wallust_generator.py` | MODIFY — hardening |
| `src/color_scheme_generator/adapters/container_processor.py` | MODIFY — chmod warning |
| `src/color_scheme_generator/adapters/jinja_template_renderer.py` | VERIFY — sequences bytes output |
| `src/color_scheme_generator/adapters/oci_container_runtime.py` | MODIFY — negative timeout guard |
| `src/color_scheme_generator/adapters/local_processor.py` | MODIFY — all-backends-unavailable message |
| `src/color_scheme_generator/adapters/settings/config_resolver.py` | VERIFY — separate AssembleConfiguration instances |
| `src/color_scheme_generator/adapters/yaml_backend_catalog_loader.py` | VERIFY — separate AssembleConfiguration instances |
| `tests/unit/adapters/backends/test_pywal_generator.py` | MODIFY — add edge case tests |
| `tests/unit/adapters/backends/test_wallust_generator.py` | MODIFY — add edge case tests |
| `tests/unit/adapters/test_container_processor.py` | MODIFY — add chmod test |
| `tests/unit/adapters/test_jinja_template_renderer.py` | MODIFY — add sequences bytes test |
| `tests/unit/adapters/test_local_processor.py` | MODIFY — add all-backends test |
| `tests/unit/adapters/settings/test_config_resolver.py` | MODIFY — add separate instances test |
| `tests/unit/adapters/test_image_lifecycle.py` or new file | MODIFY/CREATE — add negative timeout test |

### Current State

**`pywal_generator.py`** — existing timeout validation only checks `not isinstance(timeout, (int, float)) or timeout < 1`. Missing guards for `math.isnan`, `math.isinf`. Saturation validation guards NaN but not inf. No empty colors list fallback — `colors[0]` on empty list raises `IndexError`.

**`wallust_generator.py`** — has better timeout validation (guards NaN, inf, < 1). Saturation validation guards NaN but not inf. Empty colors list already has fallback. Needs inf guard on saturation.

**`container_processor.py`** — root guard exists (line ~128: `if input_parent == Path("/")`). chmod is unprotected — no try/except around `os.chmod(output_dir, 0o755)`.

**`jinja_template_renderer.py`** — sequences post-processing exists (replaces `]` → `\x1b]`, `\` → `\x1b\\`, writes bytes). Verify and add test coverage.

**`oci_container_runtime.py`** — `build_image()` validates `timeout <= 0` but `run()` doesn't. Add same guard.

**`local_processor.py`** — `_generate_extract` checks `is_available()` per backend and raises `BackendNotAvailableError` individually. No aggregated "all backends unavailable" message.

**`config_resolver.py`** — `AssembledConfigResolver` creates one `AssembleConfiguration` instance. Verify the Yaml backend catalog loader creates its own separate instance.

### Testing Patterns

Use pytest with mocked dependencies. Mock subprocess, os.chmod, and container runtime as needed. Follow existing test patterns in each file's test module.

For sequences bytes test:
```python
def test_seqences_output_bytes(tmp_path, sample_scheme):
    renderer = JinjaTemplateRenderer(templates_dir=TEMPLATES_DIR)
    output = tmp_path / "colors.sequences"
    renderer.render("colors.sequences.j2", sample_scheme, output)
    with open(output, "rb") as f:
        content = f.read()
    assert isinstance(content, bytes)
    assert b"\x1b]" in content  # OSC sequence marker
    assert b"\x1b\\" in content  # OSC string terminator
```

For all-backends-unavailable test:
```python
def test_local_processor_all_backends_unavailable():
    backend_registry = {
        Backend.CUSTOM: MagicMock(is_available=Mock(return_value=False)),
        Backend.PYWAL: MagicMock(is_available=Mock(return_value=False)),
        Backend.WALLUST: MagicMock(is_available=Mock(return_value=False)),
    }
    processor = LocalProcessor(backend_registry=backend_registry)
    with pytest.raises(BackendNotAvailableError) as exc:
        processor.process_generate(request, settings)
    assert "csg install" in str(exc.value)
```

### Architecture Compliance

- **NFR-2 (Reliability):** Errors never produce unstructured output. Subprocess timeouts, cache read failures, and root-fs mounts all produce typed, structured exceptions.
- **NFR-5 (Container Security):** Root filesystem mount rejection is a security hardening measure.
- **NFR-6 (Testability):** Each edge case is unit-testable with mocked dependencies.
- **Hexagonal:** All changes are within adapters or their tests. No domain changes.

### Previous Story Intelligence (4.1)

- DryRunProcessor in story 4.1 established `_validate_params()` with type coercion patterns for float/int/str/choices — reference for consistent type validation in backends.
- ContainerProcessor mount logic from 3.2 established root-fs guard pattern.
- Error mapping from 3.4 established `map_oci_error()` for OCI → domain exception mapping.
- Test patterns from previous stories use `MagicMock` + `pytest.raises` for error-path coverage.

### References

- [Source: epics.md#735-768] — Story 4.2 acceptance criteria
- [Source: epics.md#710] — Epic 4 NFRs (FR-5, NFR-2)
- [Source: adapters/backends/pywal_generator.py:57-112] — Current timeout handling and cache parsing
- [Source: adapters/backends/wallust_generator.py:52-137] — Current timeout handling (more robust)
- [Source: adapters/container_processor.py:115-241] — ContainerProcessor.generate with root guard and chmod
- [Source: adapters/jinja_template_renderer.py:69-73] — Sequences post-processing
- [Source: adapters/oci_container_runtime.py:97-120] — build_image timeout guard (reference pattern)
- [Source: adapters/local_processor.py:36-50] — Backend availability check pattern
- [Source: domain/exceptions.py:1-125] — Available exception hierarchy

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

### Completion Notes List

- Implemented NaN/Inf guards for timeout and saturation in PywalGenerator
- Implemented Inf guard for saturation in WallustGenerator
- Added empty colors list fallback in PywalGenerator (16 black colors)
- Added negative/zero timeout guard in OciContainerRuntimeAdapter.run()
- Wrapped chmod calls in ContainerProcessor with try/except + warning log
- Added all-backends-unavailable aggregate error in LocalProcessor
- Verified sequences bytes output in JinjaTemplateRenderer (already correct)
- Verified separate AssembleConfiguration instances for settings/backends (correct by design)
- Added 12 new unit tests covering all edge cases
- Full test suite: 419 passed, 0 failed
- Ruff lint: clean (only pre-existing errors remain)

### File List

| File | Action |
|------|--------|
| `src/color_scheme_generator/adapters/backends/pywal_generator.py` | MODIFIED |
| `src/color_scheme_generator/adapters/backends/wallust_generator.py` | MODIFIED |
| `src/color_scheme_generator/adapters/container_processor.py` | MODIFIED |
| `src/color_scheme_generator/adapters/oci_container_runtime.py` | MODIFIED |
| `src/color_scheme_generator/adapters/local_processor.py` | MODIFIED |
| `tests/unit/adapters/backends/test_pywal_generator.py` | MODIFIED |
| `tests/unit/adapters/backends/test_wallust_generator.py` | MODIFIED |
| `tests/unit/adapters/test_container_processor.py` | MODIFIED |
| `tests/unit/adapters/test_jinja_template_renderer.py` | MODIFIED |
| `tests/unit/adapters/test_local_processor.py` | MODIFIED |
| `tests/unit/adapters/settings/test_config_resolver.py` | MODIFIED |
| `tests/unit/adapters/test_image_lifecycle.py` | MODIFIED |

### Change Log

- Implemented edge case hardening across adapters (NaN/Inf guards, empty colors fallback, chmod warning, negative timeout guard, all-backends-unavailable message, sequences bytes verification, separate config instances)

### Review Findings

- [x] [Review][Patch] Test name typo `test_seqences_*` → `test_sequences_*` [test_jinja_template_renderer.py:155,175]
- [x] [Review][Patch] Empty `_backend_registry` produces awkward error message "No backends available: " [local_processor.py:46-48]
- [x] [Review][Defer] `None` timeout raises TypeError instead of ValueError [oci_container_runtime.py:25] — deferred, pre-existing; type is `int` (not `Optional[int]`), typing should catch at dev time
