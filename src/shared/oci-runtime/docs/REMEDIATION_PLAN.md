# oci-runtime — Remediation Plan

**Created:** 2026-06-17  
**Source:** `docs/AUDIT.md`  
**Status:** Planning  

This document is the single source of truth for addressing all issues identified in the audit. Each item has a unique ID, a description referencing the audit, a concrete fix path, affected files, acceptance criteria, and a progress tracker.

---

## Phase Structure

Items are organized into 5 phases. Phases are sequential — later phases may depend on fixes from earlier phases. Within a phase, items are ordered by dependency (earlier items unblock later ones).

| Phase | Focus | Items |
|-------|-------|-------|
| 0 | Critical & High Bugs | Fixes that produce incorrect behavior right now |
| 1 | Low Bugs & Implementation Issues | Fixes that produce subtle/wrong behavior or degrade quality |
| 2 | Architecture Alignment | Changes that realign the module with hexagonal/clean principles |
| 3 | Test Quality Overhaul | Restructure, consolidate, and add missing tests |
| 4 | Low-Priority Polish | Nice-to-haves, info-level items, documentation |

---

## Phase 0 — Critical & High Bugs

### 0.1 `parse_size_to_bytes()` silently returns 0 for unrecognized units

**Audit ref:** 2.1  
**Severity:** Critical  
**Progress:** [x] Done

**Fix applied:** Replaced `units.get(unit, 0)` with explicit check: `if unit not in units: raise ValueError(...)` then `return int(float(number) * units[unit])`. Unknown units like `"1PB"` or `"5EB"` now raise `ValueError`.

**Affected files:**
- `src/oci_runtime/adapters/_utils.py`

---

### 0.2 Manager `list()` methods skip error checking

**Audit ref:** 2.3  
**Severity:** High  
**Progress:** [x] Done

**Fix applied:** Added `self._check_result(result, cmd, ...)` before the parse call in all four `list()` methods:
- `CliContainerManager.list()` — `ContainerNotFoundError`
- `CliImageManager.list()` — `ImageNotFoundError`
- `CliVolumeManager.list()` — `VolumeNotFoundError`
- `CliNetworkManager.list()` — `NetworkNotFoundError`

**Affected files:**
- `src/oci_runtime/adapters/managers/container.py`
- `src/oci_runtime/adapters/managers/image.py`
- `src/oci_runtime/adapters/managers/volume.py`
- `src/oci_runtime/adapters/managers/network.py`

---

### 0.3 Manager `create()` methods skip error checking

**Audit ref:** 2.4  
**Severity:** High  
**Progress:** [x] Verified — no change needed

**Original concern:** `CliVolumeManager.create()` and `CliNetworkManager.create()` might skip error checking. Upon review, both methods already call `self._check_result()` before returning. The original audit was based on a misreading of the source code.

**Affected files:** None

---

## Phase 1 — Low Bugs & Implementation Improvements

### 1.1 `_resolve_tty()` called 3 times in `run()`

**Audit ref:** 2.2  
**Severity:** Medium  
**Progress:** [x] Done (combined with 2.2 — see below)

**Fix applied:** Combined with 2.2. `_resolve_tty()` is no longer a `@staticmethod` referencing `sys.stdout`. It's now an instance method that calls `self._tty_detector.is_tty()`, and the result is cached once in `effective_tty` at the top of `run()`.

**Affected files:**
- `src/oci_runtime/adapters/managers/container.py`
- `src/oci_runtime/ports/tty.py` (new)
- `src/oci_runtime/adapters/tty.py` (new)
- `src/oci_runtime/adapters/provider/_base.py`
- All test files constructing `CliContainerManager`

**Acceptance criteria:**
- `_resolve_tty()` is called exactly once per `run()` invocation
- All 717 tests pass

---

### 1.2 Docker image parser silent size fallback

**Audit ref:** 2.5  
**Severity:** Medium  
**Progress:** [ ] Not started

**Problem:** `DockerImageParser.parse_list()` swallows `ValueError` from `parse_size_to_bytes()` and sets `size = 0`. This hides data corruption.

**Fix path:**
1. Open `adapters/parser/docker.py`
2. Replace the `try/except ValueError: size = 0` pattern with `try/except ValueError` that raises `ParsingError`:
   ```python
   try:
       size = parse_size_to_bytes(size)
   except ValueError as e:
       raise ParsingError(raw=raw, message=f"Cannot parse image size: {size!r}") from e
   ```
3. Same for the `VirtualSize` fallback
4. Update tests to expect `ParsingError` instead of silent `size=0`

**Affected files:**
- `src/oci_runtime/adapters/parser/docker.py`
- `tests/unit/adapters/test_docker_parser.py`

**Acceptance criteria:**
- `parse_list()` raises `ParsingError` when `Size` is an unparseable string
- `parse_list()` still works with valid integer/absent `Size`
- Existing parser tests pass

---

### 1.3 Substring matching in `is_not_found_error()`

**Audit ref:** 2.6  
**Severity:** Low  
**Progress:** [ ] Not started

**Problem:** `any(p in lower for p in self._not_found_patterns)` matches `"no such containerxyz"` as "not found". Should use word-boundary matching.

**Fix path:**
1. Open `adapters/parser/base.py`
2. Change `is_not_found_error()` to use regex word boundaries:
   ```python
   import re
   def is_not_found_error(self, stderr: str) -> bool:
       lower = stderr.lower()
       return any(
           re.search(rf'\b{re.escape(p)}\b', lower)
           for p in self._not_found_patterns
       )
   ```
3. Update test patterns to include edge cases

**Affected files:**
- `src/oci_runtime/adapters/parser/base.py`
- `tests/unit/adapters/test_parser_base.py`
- `tests/integration/boundary/test_error_conditions.py`

**Acceptance criteria:**
- `"No such container: abc"` matches → `True`
- `"No such containerxyz"` does not match → `False`
- `"no such image: myimage pull access denied"` matches both patterns → `True`

---

### 1.4 Unused imports

**Audit ref:** 2.8  
**Severity:** Trivial  
**Progress:** [x] Done

**Fix applied:** Removed `ContainerNotFoundError` from the import in `src/oci_runtime/domain/__init__.py` and removed `Enum` from the `from enum import Enum, StrEnum` import in `src/oci_runtime/domain/enums.py`. `ruff check src/oci_runtime/` now reports zero errors.

---

### 1.5 Eager availability probing on `create()`

**Audit ref:** 3.4  
**Severity:** Low  
**Progress:** [ ] Not started

**Problem:** `RuntimeFactory.create()` calls `runtime.is_available()` every time, spawning a `subprocess.run([binary, "--version"])`. This adds ~100ms per factory creation.

**Fix path:**
1. Open `src/oci_runtime/factory.py`
2. Add `check_available: bool = True` parameter to `RuntimeFactory.create()`
3. Only call `runtime.is_available()` when `check_available is True`
4. Update `RuntimeFactory.available()` documentation to note that it also probes
5. Add test for `create(preference, check_available=False)` skipping the probe

**Affected files:**
- `src/oci_runtime/factory.py`
- `tests/unit/adapters/test_factory.py`

**Acceptance criteria:**
- `RuntimeFactory().create(pref, check_available=False)` does not call `transport.probe()`
- `RuntimeFactory().create(pref, check_available=True)` (default) still calls `transport.probe()`
- `RuntimeFactory().create(pref)` behavior is backward-compatible

---

### 1.6 `ProcessPipeReader` read timeout

**Audit ref:** 3.5  
**Severity:** Low  
**Progress:** [ ] Not started

**Problem:** If a subprocess hangs and no `cancel_token` is provided, `ProcessPipeReader.read()` polls forever with 100ms intervals. The `timeout` parameter on `StreamingTransport.stream()` only applies to `process.wait()`, not to the reading loop.

**Fix path:**
1. Add `read_timeout: float | None = None` parameter to `ProcessPipeReader.read()`
2. Track total elapsed time in the read loop. If `read_timeout` is set and elapsed time exceeds it, break the loop and return partial data with a `TimedOut` flag
3. Propagate `timeout` from `CliStreamingTransport.stream()` through to `ProcessPipeReader.read()` as a total read deadline
4. Add tests for timeout behavior

**Affected files:**
- `src/oci_runtime/adapters/_process_reader.py`
- `src/oci_runtime/adapters/transport/streaming.py`
- `tests/unit/adapters/test_cli_streaming_transport.py`

**Acceptance criteria:**
- If `read_timeout=5.0` is set and no data arrives for 5 seconds, `ProcessPipeReader.read()` returns partial data
- Default behavior (no timeout) is unchanged
- Existing streaming transport tests pass

---

### 1.7 `_check_result()` over-engineering simplification

**Audit ref:** 3.3  
**Severity:** Low  
**Progress:** [ ] Not started

**Problem:** Every call site passes `not_found=ContainerNotFoundError`, `not_found=ImageNotFoundError`, etc. This is repetitive — each manager always raises the same "not found" class. A template method pattern would be cleaner.

**Fix path:**
1. Open `src/oci_runtime/adapters/managers/base.py`
2. Add an abstract class variable `_not_found_error: Type[OciError]` to `CliBaseManager`
3. Change `_check_result()` to use `self._not_found_error` as the default for the `not_found` parameter
4. Each concrete manager sets `_not_found_error = ContainerNotFoundError` etc.
5. Remove explicit `not_found=` from all call sites in concrete managers (keep the parameter for rare override cases)

**Affected files:**
- `src/oci_runtime/adapters/managers/base.py`
- `src/oci_runtime/adapters/managers/container.py`
- `src/oci_runtime/adapters/managers/image.py`
- `src/oci_runtime/adapters/managers/volume.py`
- `src/oci_runtime/adapters/managers/network.py`

**Acceptance criteria:**
- All managers still raise the correct "not found" error type
- `_check_result()` can still accept an explicit `not_found` for override cases
- All existing error-path tests pass

---

### 1.8 `run_pty()` output_stream type hint

**Audit ref:** 3.7  
**Severity:** Low  
**Progress:** [ ] Not started

**Problem:** `output_stream: io.IOBase | None` is overly broad. The method calls `write(bytes)` and `flush()`.

**Fix path:**
1. Define a `Protocol` type in `adapters/managers/pty.py`:
   ```python
   from typing import Protocol

   class OutputStream(Protocol):
       def write(self, data: bytes) -> int: ...
       def flush(self) -> None: ...
   ```
2. Change the type hint to `OutputStream | None`
3. Update tests accordingly

**Affected files:**
- `src/oci_runtime/adapters/managers/pty.py`
- `tests/unit/adapters/test_cli_pty.py`

**Acceptance criteria:**
- `io.BytesIO` and `sys.stdout.buffer` both satisfy `OutputStream`
- Existing tests pass

---

### 1.9 Command string formatting without escaping

**Audit ref:** 3.6  
**Severity:** Low  
**Progress:** [ ] Not started

**Problem:** Environment variables, labels, and volume mounts are built via f-strings without escaping. While not a security risk (no shell), special characters can produce malformed CLI args.

**Fix path:**
1. Open `src/oci_runtime/adapters/managers/container.py`
2. Add a private helper `_shell_escape(value: str) -> str` or use `shlex.quote()` for values that may contain special characters
3. Apply selectively to `-e`, `-l`, and `-v` arguments where user-controlled values are interpolated
4. Add tests with values containing spaces, quotes, and newlines

**Affected files:**
- `src/oci_runtime/adapters/managers/container.py`
- `tests/unit/adapters/test_cli_container_manager.py`

**Acceptance criteria:**
- `RunConfig(environment={"KEY": "hello world"})` produces `-e KEY=hello world` (quoted if needed by the runtime)
- Values with `=` signs are handled correctly
- Existing tests pass

---

### 1.10 input_data None sentinel in CliStreamingTransport

**Audit ref:** 2.7 (revised)  
**Severity:** Low  
**Progress:** [x] Done

**Original problem:** `CliStreamingTransport.stream()` used falsy checks (`if input_data`) for both stdin pipe creation and stdin write/close. This meant `input_data=b""` created no pipe and never closed stdin, inconsistent with `CliTransport.execute()`.

**Fix applied:** Changed both conditions to `is not None`:
- Line 35: `stdin=subprocess.PIPE if input_data is not None else None`
- Line 41: `if input_data is not None:`

Now `None` is the sole sentinel meaning "no stdin pipe". Any `bytes` value (including `b""`) creates a pipe, writes data, and closes it to send EOF — matching `CliTransport.execute()` semantics.

**Affected files:**
- `src/oci_runtime/adapters/transport/streaming.py`

---

## Phase 2 — Architecture Alignment

### 2.1 CancellationToken: move thread-safe impl to adapter, keep protocol in domain

**Audit ref:** 1.1, 3.1  
**Severity:** High  
**Progress:** [ ] Not started

**Problem:** `CancellationToken` is in `domain/types.py` but claims cross-thread use. The domain layer is documented as I/O-free with no threading primitives. The current `bool`-based impl relies on CPython's GIL.

**Fix path:**
1. In `domain/types.py`, convert `CancellationToken` to an ABC (or Protocol):
   ```python
   class CancellationToken(Protocol):
       @property
       def is_cancelled(self) -> bool: ...
       def cancel(self) -> None: ...
   ```
2. Move current implementation to `adapters/_process_reader.py` or a new `adapters/_cancellation.py` as `ThreadCancellationToken` using `threading.Event`:
   ```python
   class ThreadCancellationToken:
       def __init__(self):
           self._event = threading.Event()
       def cancel(self) -> None:
           self._event.set()
       @property
       def is_cancelled(self) -> bool:
           return self._event.is_set()
   ```
3. Update `RuntimeFactoryConfig` to include `cancellation_factory: Callable[[], CancellationToken]` defaulting to `ThreadCancellationToken`
4. Update `RuntimeFactory.create()` and `ContainerManager.logs()` to use the factory
5. Add tests for `ThreadCancellationToken` (cancel, is_cancelled, idempotent cancel)
6. Add domain-level tests for the `CancellationToken` Protocol

**Affected files:**
- `src/oci_runtime/domain/types.py`
- `src/oci_runtime/adapters/_process_reader.py` (or new `_cancellation.py`)
- `src/oci_runtime/factory.py`
- `src/oci_runtime/adapters/managers/container.py`
- `src/oci_runtime/ports/streaming.py`
- `tests/unit/domain/test_types.py`
- `tests/unit/adapters/` (new: `test_cancellation.py`)

**Acceptance criteria:**
- `domain/types.py` has no `threading` import
- `ThreadCancellationToken` uses `threading.Event` internally
- `CancellationToken` is a Protocol/ABC in domain
- All existing tests pass
- New tests verify `ThreadCancellationToken` works across threads

**Dependencies:** None (independent of other phase items)

---

### 2.2 Inject `sys.stdout.isatty()` via `tty_detector` parameter

**Audit ref:** 1.2  
**Severity:** Medium  
**Progress:** [x] Done (combined with 1.1)

**Fix applied:**
Extracted TTY detection behind a named `TtyDetector` ABC port (hexagonal clean architecture), eliminating `sys.stdout` references from the container adapter:

1. Created `ports/tty.py` — `TtyDetector` ABC with abstract `is_tty() -> bool`
2. Created `adapters/tty.py` — `StdoutTtyDetector` adapter implementing `is_tty()` via `sys.stdout.isatty()`
3. Added `tty_detector: TtyDetector` (required, no `Optional`, no default) to `CliContainerManager.__init__()`
4. `_resolve_tty()` is now an instance method calling `self._tty_detector.is_tty()`; result cached in `effective_tty` at the top of `run()`
5. Wired `StdoutTtyDetector()` in `BaseCliRuntimeProvider.create_managers()` (composition root)
6. Created `FakeTtyDetector` test double in `tests/helpers/mock_transport.py` (supports `is_tty=True/False`)
7. Updated all 12 test files that construct `CliContainerManager` to pass `tty_detector=FakeTtyDetector()`
8. Removed `import sys` from `adapters/managers/container.py`

This approach was chosen over the simpler `Callable[[], bool] | None` default because:
- **Discoverability:** A named ABC appears in the type hierarchy and `__init__` signature with clear intent
- **No hidden I/O:** No fallback to `sys.stdout.isatty()` in the adapter — the production adapter (`StdoutTtyDetector`) owns the I/O dependency
- **Testability:** Tests inject `FakeTtyDetector()` without `patch()` or mocking `sys.stdout`
- **Single composition root:** `_base.py` is the only place that wires the production `StdoutTtyDetector()`

**Affected files:**
- `src/oci_runtime/ports/tty.py` (new)
- `src/oci_runtime/adapters/tty.py` (new)
- `src/oci_runtime/adapters/managers/container.py`
- `src/oci_runtime/adapters/provider/_base.py`
- `src/oci_runtime/ports/__init__.py`
- `tests/helpers/mock_transport.py`
- 12 test files updated

**Acceptance criteria:**
- `_resolve_tty` uses the injected `TtyDetector`, not `sys.stdout` directly
- Tests pass `FakeTtyDetector(is_tty=True)` / `FakeTtyDetector(is_tty=False)` without mocking `sys`
- All 717 tests pass, zero lint errors on source code)

---

### 2.3 ParsingError hierarchy alignment

**Audit ref:** 1.3  
**Severity:** Low  
**Progress:** [ ] Not started

**Problem:** `ParsingError` inherits from `Exception`, not `OciError`. Callers must catch both separately, breaking the unified exception hierarchy.

**Fix path:**
1. Decide on approach:
   - **Option A:** Make `ParsingError` inherit from `OciError` — simplest, preserves single catch point
   - **Option B:** Create `OciPortError(OciError)` and make `ParsingError` inherit from it — preserves semantic distinction between domain errors and port contract errors
2. Implement the chosen approach
3. Update `test_exceptions.py` to verify `ParsingError` is catchable via `OciError`
4. Update `ARCHITECTURE.md` if needed

**Affected files:**
- `src/oci_runtime/ports/parsers.py`
- `src/oci_runtime/domain/exceptions.py` (Option B only)
- `tests/unit/domain/test_exceptions.py`
- `docs/ARCHITECTURE.md`

**Acceptance criteria:**
- `except OciError:` catches `ParsingError` (Option A) or `except OciPortError:` catches it (Option B)
- All existing tests pass
- Exception hierarchy docs updated

---

### 2.4 ExecResult / ExecOutput naming alignment

**Audit ref:** 1.4  
**Severity:** Medium  
**Progress:** [ ] Not started

**Problem:** `ExecResult` (bytes) is the transport type but sounds like a domain type. `ExecOutput` (str) is the domain type but sounds like raw output.

**Fix path:**
1. Rename `ExecResult` → `RawExecResult` in `domain/types.py` and all references
2. Rename `ExecOutput` → `ExecResult` in `domain/types.py` and all references
3. Update `__init__.py` exports
4. Update `ARCHITECTURE.md` type signatures

**Affected files:**
- `src/oci_runtime/domain/types.py`
- `src/oci_runtime/domain/__init__.py`
- `src/oci_runtime/__init__.py`
- `src/oci_runtime/ports/transport.py`
- `src/oci_runtime/ports/streaming.py`
- `src/oci_runtime/adapters/transport/cli.py`
- `src/oci_runtime/adapters/transport/streaming.py`
- `src/oci_runtime/adapters/managers/base.py` (and all manager files)
- All test files referencing `ExecResult` / `ExecOutput`
- `docs/ARCHITECTURE.md`

**Acceptance criteria:**
- `RawExecResult` contains `bytes` fields (`stdout: bytes`, `stderr: bytes`)
- `ExecResult` contains `str` fields (`stdout: str`, `stderr: str`)
- All references updated
- All existing tests pass

---

### 2.5 PruneResult value object (replace `dict[str, int]`)

**Audit ref:** 1.5  
**Severity:** Medium  
**Progress:** [ ] Not started

**Problem:** All `prune()` methods return `dict[str, int]` with magic keys `"deleted"` and `"reclaimed_bytes"`.

**Fix path:**
1. Create `PruneResult` in `domain/types.py`:
   ```python
   @dataclass(frozen=True)
   class PruneResult:
       deleted: int
       reclaimed_bytes: int
   ```
2. Update all 4 manager port interfaces in `ports/managers.py` to return `PruneResult`
3. Update all 4 adapter implementations to return `PruneResult`
4. Update parser `parse_prune()` return types to `PruneResult`
5. Update all tests

**Affected files:**
- `src/oci_runtime/domain/types.py`
- `src/oci_runtime/domain/__init__.py`
- `src/oci_runtime/__init__.py`
- `src/oci_runtime/ports/managers.py`
- `src/oci_runtime/adapters/managers/container.py`
- `src/oci_runtime/adapters/managers/image.py`
- `src/oci_runtime/adapters/managers/volume.py`
- `src/oci_runtime/adapters/managers/network.py`
- `src/oci_runtime/adapters/parser/base.py`
- `src/oci_runtime/ports/parsers.py`
- All test files referencing prune results
- `tests/helpers/mock_parsers.py`

**Acceptance criteria:**
- All `prune()` methods return `PruneResult` instead of `dict[str, int]`
- `PruneResult` instances support `.deleted` and `.reclaimed_bytes` attribute access
- All existing tests pass

---

### 2.6 VolumeMountType enum

**Audit ref:** 1.6  
**Severity:** Medium  
**Progress:** [ ] Not started

**Problem:** `VolumeMount.type` is a bare `str` that should be an enum.

**Fix path:**
1. Add `VolumeMountType` to `domain/enums.py`:
   ```python
   class VolumeMountType(StrEnum):
       BIND = "bind"
       VOLUME = "volume"
       TMPFS = "tmpfs"
   ```
2. Change `VolumeMount.type` from `str` to `VolumeMountType` in `domain/types.py`
3. Update `adapters/managers/container.py` to use `VolumeMountType` in the `-v` spec generation
4. Update `__init__.py` exports
5. Update tests

**Affected files:**
- `src/oci_runtime/domain/enums.py`
- `src/oci_runtime/domain/types.py`
- `src/oci_runtime/domain/__init__.py`
- `src/oci_runtime/__init__.py`
- `src/oci_runtime/adapters/managers/container.py`
- `tests/unit/domain/test_enums.py`
- `tests/unit/domain/test_types.py`
- `tests/unit/adapters/test_cli_container_manager.py`

**Acceptance criteria:**
- `VolumeMount(type="bind")` works via StrEnum coercion
- `VolumeMount(type="invalid")` raises `ValueError` or maps to UNKNOWN
- Enum values serialize to correct CLI strings
- Existing tests pass

---

### 2.7 RunConfig memory_limit / cpu_limit validation

**Audit ref:** 1.7  
**Severity:** Medium  
**Progress:** [ ] Not started

**Problem:** `memory_limit` and `cpu_limit` accept arbitrary strings with no validation.

**Fix path:**
1. Add `__post_init__` validation to `RunConfig`:
   ```python
   import re
   _SIZE_PATTERN = re.compile(r'^\d+[bkmg]?$', re.IGNORECASE)
   _CPU_PATTERN = re.compile(r'^\d+\.?\d*$')

   def __post_init__(self):
       if self.memory_limit is not None and not self._SIZE_PATTERN.match(self.memory_limit):
           raise ValueError(f"Invalid memory_limit: {self.memory_limit!r}")
       if self.cpu_limit is not None and not self._CPU_PATTERN.match(self.cpu_limit):
           raise ValueError(f"Invalid cpu_limit: {self.cpu_limit!r}")
   ```
2. Alternatively, document the expected format without enforcement (less safe, less code)
3. Add tests for valid and invalid values

**Affected files:**
- `src/oci_runtime/domain/types.py`
- `tests/unit/domain/test_types.py`

**Acceptance criteria:**
- `RunConfig(image="alpine", memory_limit="512m")` works
- `RunConfig(image="alpine", memory_limit="bananas")` raises `ValueError`
- `RunConfig(image="alpine", memory_limit=None)` works (default)

---

## Phase 3 — Test Quality Overhaul

### 3.1 Remove/consolidate structural/reflective tests

**Audit ref:** 4.1  
**Severity:** Medium  
**Progress:** [ ] Not started

**Problem:** ~30 tests verify Python language features, not module behavior.

**Fix path:**
1. Create `tests/unit/structure/test_abc_hierarchy.py` — single file that verifies all ABCs can't be instantiated, all required abstract methods exist. This replaces the scattered `test_is_abc`, `test_cannot_instantiate` tests.
2. Delete individual structural tests from:
   - `test_enums.py`: Remove `test_is_strenum`, `test_is_enum`, `test_strenum_is_str`, `test_strenum_equality_with_str`, `test_strenum_not_equal_to_wrong_str`, `test_strenum_fstring`
   - `test_types.py`: Remove all `test_is_dataclass` assertions (7 occurrences)
   - `test_engine.py`: Remove `test_is_abc`, `test_cannot_instantiate`
   - `test_transport.py`: Remove `test_is_abc`, `test_cannot_instantiate`, `test_concrete_subclass_must_implement_all_abstract`
   - `test_parsers.py`: Remove `test_is_abc`, `test_cannot_instantiate` (4 parsers)
   - `test_managers.py`: Remove `test_is_abc` (4 managers)
   - `test_exceptions.py`: Remove `test_is_exception`
   - `test_capabilities.py`: Remove `test_has_no_get_binary_method`
3. Keep behavioral tests (e.g., `test_unknown_state_falls_back_to_unknown`, `test_both_set_raises_value_error`)

**Affected files:**
- Multiple test files (see list above)
- New: `tests/unit/structure/test_abc_hierarchy.py`

**Acceptance criteria:**
- Total test count reduced by ~30
- All behavioral tests still pass
- New structural test file handles all ABC/instantiation checks in one place

---

### 3.2 Reorganize mock-based "integration" tests

**Audit ref:** 4.2  
**Severity:** Medium  
**Progress:** [ ] Not started

**Problem:** `tests/integration/boundary/`, `integration/integration/`, `integration/contract/`, and `integration/capability/` all use `RecordingTransport` (a mock), not real CLI tools.

**Fix path:**
1. Move mock-based test directories to `tests/unit/`:
   - `tests/integration/boundary/` → `tests/unit/boundary/`
   - `tests/integration/contract/` → `tests/unit/contract/`
   - `tests/integration/capability/` → `tests/unit/capability/`
   - `tests/integration/integration/` → `tests/unit/wiring/`
2. Keep `tests/integration/smoke/` and `tests/integration/functional/` as real runtime tests
3. Keep `tests/integration/container/` as real runtime test (test_tty_dispatch.py)
4. Update `conftest.py` and `pytest.ini`/`pyproject.toml` if needed
5. Update `Makefile` test commands if they reference specific paths

**Affected files:**
- Directory restructuring (no source code changes)
- `pyproject.toml` or `pytest.ini` (if test paths are configured)
- `Makefile`

**Acceptance criteria:**
- `uv run pytest tests/unit/` runs all unit tests including moved ones
- `uv run pytest tests/integration/` only runs real-runtime tests
- All tests pass

---

### 3.3 Add missing unit test coverage

**Audit ref:** 4.3  
**Severity:** Medium  
**Progress:** [ ] Not started

**Problem:** 9 critical code paths have no direct unit tests.

**Fix path — create new test files:**

| New Test File | What It Tests |
|---------------|---------------|
| `tests/unit/adapters/test_utils.py` | `parse_size_to_bytes()` — valid units, unknown units, no-match strings, edge cases |
| `tests/unit/adapters/test_tar.py` | `create_build_tar()` — tar structure, file entries, Dockerfile entry name |
| `tests/unit/adapters/test_process_reader.py` | `ProcessPipeReader.read()` — EOF, callbacks, cancellation, timeout |
| `tests/unit/adapters/test_discovery.py` | `CliRuntimeDiscovery.available()` — mock transport, probe results |
| `tests/unit/domain/test_cancellation_token.py` | `CancellationToken` — cancel, is_cancelled, idempotent cancel, default state |
| `tests/unit/adapters/test_resolve_tty.py` | `_resolve_tty()` — tty=True, auto_tty+tty_detector, neither |

**Augment existing test files:**

| Test File | New Tests |
|-----------|-----------|
| `test_docker_parser.py` | `BaseCliParser.parse_prune()` — line-based counting, size parsing |
| `test_cli_container_manager.py` | `logs()` follow-mode threading, `run()` PTY path through manager |

**Affected files:**
- 6 new test files
- 2 augmented test files

**Acceptance criteria:**
- Each untested code path has at least 3 test cases (happy path, edge case, error case)
- `pytest --cov=oci_runtime tests/unit/` shows improved coverage

---

### 3.4 Deepen contract tests

**Audit ref:** 4.4  
**Severity:** Medium  
**Progress:** [ ] Not started

**Problem:** Contract tests only verify return types, not values or error paths.

**Fix path:**
1. For each contract test file (`test_container_manager_contract.py`, `test_image_manager_contract.py`, `test_volume_manager_contract.py`, `test_network_manager_contract.py`):
   - Add error-path tests: non-zero exit code → correct exception type and attributes
   - Add command assertion tests: verify the correct CLI command is built
   - Add parser delegation tests: verify parser methods receive the transport's output
2. Example improvement for `test_container_manager_contract.py`:
   ```python
   def test_inspect_nonexistent_raises_not_found_with_attributes(self):
       mgr, _ = self._failing(stderr="No such container: xyz")
       with pytest.raises(ContainerNotFoundError) as exc_info:
           mgr.inspect("xyz")
       assert "xyz" in exc_info.value.container_id
   ```

**Affected files:**
- `tests/unit/ports/test_container_manager_contract.py`
- `tests/unit/ports/test_image_manager_contract.py`
- `tests/unit/ports/test_volume_manager_contract.py`
- `tests/unit/ports/test_network_manager_contract.py`

**Acceptance criteria:**
- Each contract test file has at least 3 error-path tests with attribute assertions
- Each contract test verifies at least 2 command constructions

---

### 3.5 Consolidate mock implementations

**Audit ref:** 4.5  
**Severity:** Medium  
**Progress:** [ ] Not started

**Problem:** Three separate implementations of mock parsers with different behavior.

**Fix path:**
1. Delete `_MockParser` from `test_cli_container_manager.py:16-24`
2. Delete `_Parser` from `test_managers.py`
3. Delete `_make_transport()` from `test_managers.py`
4. Import `MockContainerParser`, `MockImageParser`, etc. from `tests/helpers/mock_parsers.py` everywhere
5. Ensure `tests/helpers/mock_parsers.py` has complete, consistent implementations for all 4 parser types

**Affected files:**
- `tests/unit/adapters/test_cli_container_manager.py` (remove local mock)
- `tests/unit/ports/test_managers.py` (remove local mock)
- `tests/helpers/mock_parsers.py` (verify completeness)

**Acceptance criteria:**
- Only one mock parser implementation exists (in `tests/helpers/`)
- All test files import from `tests.helpers.mock_parsers`
- All tests pass

---

### 3.6 Remove FailingTransport (replaced by RecordingTransport with error responses)

**Audit ref:** 4.6  
**Severity:** Low  
**Progress:** [x] Done

**Problem:** `FailingTransport` was semantically misleading — `probe()` always returned `True` while `execute()` always returned exit code 1. The name implied "failing" but it claimed to be available. Its only use was in 4 contract tests that needed a transport returning errors.

**Fix applied:**
- Deleted `FailingTransport` class from `tests/helpers/mock_transport.py`
- Replaced all 4 usages with `RecordingTransport` configured with specific error `ExecResult` responses keyed to the exact command being tested
- `RecordingTransport` returns exit code 0 for unmatched commands, so tests now explicitly configure which command fails — making the test more precise

**Affected files:**
- `tests/helpers/mock_transport.py` — deleted `FailingTransport` class
- `tests/unit/ports/test_container_manager_contract.py` — `_failing()` now uses `RecordingTransport`
- `tests/unit/ports/test_image_manager_contract.py` — `_failing()` now uses `RecordingTransport`
- `tests/unit/ports/test_volume_manager_contract.py` — `_failing()` now uses `RecordingTransport`
- `tests/unit/ports/test_network_manager_contract.py` — `_failing()` now uses `RecordingTransport`

---

### 3.7 Fix RecordingTransport key matching

**Audit ref:** 4.7  
**Severity:** Low  
**Progress:** [ ] Not started

**Problem:** `" ".join(command)` breaks when arguments contain spaces.

**Fix path:**
1. Open `tests/helpers/mock_transport.py`
2. Change `key = " ".join(command)` to `key = tuple(command)` in both `RecordingTransport` and `RecordingStreamingTransport`
3. Change `self._responses: dict[str, ExecResult]` to `self._responses: dict[tuple[str, ...], ExecResult]`
4. Update all test files that set response keys to use tuples:
   - `test_manager_commands.py`: `{"docker", "image", "inspect", ...}` → `("docker", "image", "inspect", ...)`
   - All other test files using `RecordingTransport`
5. Add a helper method `response_for(*args)` to make key creation cleaner

**Affected files:**
- `tests/helpers/mock_transport.py`
- All test files using `RecordingTransport._responses`

**Acceptance criteria:**
- `RecordingTransport.execute(["docker", "run", "-e", "MY_VAR=hello world"])` correctly matches responses
- All existing tests pass

---

### 3.8 Add exception attribute assertions to error-path tests

**Audit ref:** 4.8  
**Severity:** Low  
**Progress:** [ ] Not started

**Problem:** Most error-path tests only check exception type, not attributes.

**Fix path:**
1. Audit all `pytest.raises(XxxError)` calls in test files
2. For each, add assertions on `exc_info.value.command`, `exc_info.value.exit_code`, `exc_info.value.stderr`, `exc_info.value.message` as appropriate
3. Focus on `test_error_conditions.py` and `test_cli_container_manager.py` first

**Affected files:**
- `tests/integration/boundary/test_error_conditions.py`
- `tests/unit/adapters/test_cli_container_manager.py`
- `tests/unit/adapters/test_cli_image_manager.py`
- `tests/unit/adapters/test_cli_volume_manager.py`
- `tests/unit/adapters/test_cli_network_manager.py`

**Acceptance criteria:**
- Every `pytest.raises` that catches an `OciError` subclass also checks at least one attribute

---

### 3.9 Add negative path tests for domain types

**Audit ref:** 4.9  
**Severity:** Low  
**Progress:** [ ] Not started

**Problem:** Domain value objects lack negative/edge case tests.

**Fix path — add tests to `tests/unit/domain/test_types.py`:**

| Test Case | Description |
|-----------|-------------|
| `BuildContext` with `context_path` + files | Verify files dict works with path |
| `RunConfig` with `NetworkMode.CONTAINER` and `network_container` | Valid combination |
| `RunConfig` with `NetworkMode.CONTAINER` and no `network_container` | Should this validate? (currently only validated in adapter) |
| `CancellationToken` default state | `is_cancelled` returns `False` |
| `CancellationToken` cancel once | `is_cancelled` returns `True` |
| `CancellationToken` cancel twice | Idempotent |
| `CancellationToken` cancel from different thread | Works correctly |
| `VolumeMount` with `type="bind"` | Works |
| `VolumeMount` with `type="invalid"` | Accepted (str field) — document this |
| `PortMapping` with `host_port=0` | Different from `None` |
| `PortMapping` with `host_port=None` | Random port assignment |

**Affected files:**
- `tests/unit/domain/test_types.py`

**Acceptance criteria:**
- Each domain type has at least 2 negative/edge case tests
- All tests pass

---

### 3.10 Reorganize misplaced test files

**Audit ref:** 4.10  
**Severity:** Low  
**Progress:** [ ] Not started

**Problem:** Test organization doesn't match source structure.

**Fix path:**
1. Move `tests/unit/ports/test_capabilities.py` → `tests/unit/domain/test_capabilities.py` (or `tests/unit/test_capabilities.py`)
   - `RuntimeCapabilities` is a domain data class, not a port ABC
   - `RuntimePreference` is a domain value object
2. Move `ParsingError` tests from `test_exceptions.py` to `test_parsers.py` (or a new `tests/unit/ports/test_parsing_error.py`)
3. Delete `test_domain_init.py` — its only assertion is that `__all__` contains names, which is a structural test with no behavioral value

**Affected files:**
- Test file moves (no source changes)

**Acceptance criteria:**
- Tests are in directories matching their source module
- All tests pass

---

## Phase 4 — Low-Priority Polish

### 4.1 Application/use-case layer (deferred)

**Audit ref:** 1.8  
**Severity:** Low  
**Progress:** [ ] Not started — Deferred

This is a design-level change that requires broader agreement. Document it as a future consideration but do not implement in this remediation cycle. The current manager-level orchestration works; an application layer would be added when:
- Multiple consumers need the same orchestration logic
- The `run()` or `logs()` methods become too complex to maintain in the manager

**Action:** Add a note to `ARCHITECTURE.md` under "Future Consideration" documenting this opportunity.

---

### 4.2 CancellationToken CPython GIL documentation

**Audit ref:** 3.1, 3.2  
**Severity:** Info  
**Progress:** [ ] Not started

**Fix path:**
1. Add a docstring note to `CancellationToken` in `domain/types.py` (or the Protocol, after 2.1):
   ```
   Note: Under CPython, plain attribute reads/writes are atomic due to the GIL.
   For free-threaded Python (3.13+ PEP 703), use the ThreadCancellationToken adapter
   which uses threading.Event for guaranteed visibility.
   ```
2. Add a note to `RecordingTransport` class docstring about thread-safety:
   ```
   Note: This class is not thread-safe. For concurrent test scenarios,
   wrap `self.calls` with a threading.Lock or use queue.Queue.
   ```

**Affected files:**
- `src/oci_runtime/domain/types.py` (or Protocol location after 2.1)
- `tests/helpers/mock_transport.py`

**Acceptance criteria:**
- Docstrings document threading limitations

---

## Dependency Graph

```
Phase 0 (Critical Bugs) — COMPLETED
  0.1 parse_size_to_bytes          ── DONE
  0.2 list() error checking        ── DONE
  0.3 create() error checking      ── VERIFIED (already had _check_result)

Phase 1 (Low Bugs & Implementation)
  1.1 _resolve_tty caching         ── DONE (combined with 2.2)
  1.2 Image parser size fallback   ── depends on 0.1 (parse_size_to_bytes fix)
  1.3 is_not_found_error fix       ── standalone
  1.4 Unused imports               ── DONE
  1.5 Eager probing                ── standalone
  1.6 ProcessPipeReader timeout    ── standalone
  1.7 _check_result simplification ── depends on 0.2 (done)
  1.8 run_pty type hint            ── standalone
  1.9 Command string escaping      ── standalone
  1.10 input_data None sentinel    ── DONE

Phase 2 (Architecture Alignment)
  2.1 CancellationToken Protocol   ── standalone
  2.2 Inject tty_detector          ── DONE (combined with 1.1)
  2.3 ParsingError hierarchy       ── standalone
  2.4 ExecResult rename            ── standalone (large rename, do last in phase)
  2.5 PruneResult value object     ── standalone
  2.6 VolumeMountType enum         ── standalone
  2.7 RunConfig validation         ── standalone

Phase 3 (Test Quality)
  3.1 Remove structural tests      ── standalone
  3.2 Reorganize integration tests  ── standalone
  3.3 Add missing coverage          ── can proceed (0.1, 0.2, 0.3 done)
  3.4 Deepen contract tests         ── can proceed (0.2, 0.3 done)
  3.5 Consolidate mocks             ── standalone
  3.6 Remove FailingTransport       ── DONE
  3.7 Fix RecordingTransport keys   ── standalone
  3.8 Exception attribute assertions ── can proceed (0.2, 0.3 done)
  3.9 Negative domain type tests     ── standalone
  3.10 Reorganize test files          ── standalone

Phase 4 (Polish)
  4.1 Application layer note        ── standalone
  4.2 Threading documentation        ── depends on 2.1 (after CancellationToken refactoring)
```

---

## Progress Tracker

| ID | Description | Phase | Status | Commit |
|----|-------------|-------|--------|--------|
| 0.1 | parse_size_to_bytes silent 0 | 0 | [x] | Done — raise ValueError on unknown units |
| 0.2 | list() error checking | 0 | [x] | Done — _check_result() added to all 4 list() methods |
| 0.3 | create() error checking | 0 | [x] | Verified — already had _check_result(), no change needed |
| 1.1 | _resolve_tty 3x call | 1 | [x] | Done — cached once via `TtyDetector` port (combined with 2.2) |
| 1.2 | Image parser size fallback | 1 | [ ] | |
| 1.3 | is_not_found_error substring | 1 | [ ] | |
| 1.4 | Unused imports | 1 | [x] | Done — removed `ContainerNotFoundError` from `domain/__init__.py` and `Enum` from `domain/enums.py`; `ruff check` now passes with zero errors |
| 1.5 | Eager probing | 1 | [ ] | |
| 1.6 | ProcessPipeReader timeout | 1 | [ ] | |
| 1.7 | _check_result simplification | 1 | [ ] | |
| 1.8 | run_pty type hint | 1 | [ ] | |
| 1.9 | Command string escaping | 1 | [ ] | |
| 1.10 | input_data None sentinel | 1 | [x] | Done — both conditions use `is not None` |
| 2.1 | CancellationToken Protocol | 2 | [ ] | |
| 2.2 | Inject tty_detector | 2 | [x] | Done — `TtyDetector` ABC port + `StdoutTtyDetector` adapter + wiring (combined with 1.1) |
| 2.3 | ParsingError hierarchy | 2 | [ ] | |
| 2.4 | ExecResult rename | 2 | [ ] | |
| 2.5 | PruneResult value object | 2 | [ ] | |
| 2.6 | VolumeMountType enum | 2 | [ ] | |
| 2.7 | RunConfig validation | 2 | [ ] | |
| 3.1 | Remove structural tests | 3 | [ ] | |
| 3.2 | Reorganize integration tests | 3 | [ ] | |
| 3.3 | Add missing coverage | 3 | [ ] | |
| 3.4 | Deepen contract tests | 3 | [ ] | |
| 3.5 | Consolidate mocks | 3 | [ ] | |
| 3.6 | Remove FailingTransport | 3 | [x] | Done — deleted, contract tests use RecordingTransport with error responses |
| 3.7 | Fix RecordingTransport keys | 3 | [ ] | |
| 3.8 | Exception attribute assertions | 3 | [ ] | |
| 3.9 | Negative domain type tests | 3 | [ ] | |
| 3.10 | Reorganize test files | 3 | [ ] | |
| 4.1 | Application layer note | 4 | [ ] | |
| 4.2 | Threading documentation | 4 | [ ] | |