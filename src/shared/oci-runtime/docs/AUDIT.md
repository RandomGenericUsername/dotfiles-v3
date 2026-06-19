# oci-runtime — Full Module Audit

**Date:** 2026-06-17  
**Scope:** `src/shared/oci-runtime/` — domain, ports, adapters, factory, and all tests  
**Stats:** 2,484 lines of source across 27 files, 460 unit tests (all passing), 2 lint errors  
**Architecture:** Hexagonal (ports & adapters) as documented in `docs/ARCHITECTURE.md`

---

## Table of Contents

1. [Architecture Drifts from Hexagonal/Clean](#1-architecture-drifts-from-hexagonalclean)
2. [Bugs](#2-bugs)
3. [Bad Implementations](#3-bad-implementations)
4. [Test Quality Issues](#4-test-quality-issues)
5. [Severity Summary](#5-severity-summary)

---

## 1. Architecture Drifts from Hexagonal/Clean

### 1.1 CancellationToken claims cross-thread use but has no thread-safety mechanism

**File:** `domain/types.py:197-208`

The `CancellationToken` class uses a plain `bool` (`self._cancelled = False`) with no memory barrier, no `threading.Event`, and no `@property` with volatile semantics. The docstring explicitly states:

> *"The flag is set by one thread and observed by another"*

This contradicts `ARCHITECTURE.md` which declares the domain layer is *"Pure, I/O-Free"* and contains *"no imports of `sys`, `io`, `threading`, or any adapter-level module."* A type explicitly designed for cross-thread communication IS a concurrency primitive. Under CPython's GIL the plain bool works, but this is an implementation detail of CPython, not a language guarantee.

**Recommendation:** Either:
- Move `CancellationToken` to the adapter layer and use `threading.Event` internally (domain keeps a Protocol/ABC), or
- Document the CPython GIL reliance explicitly and add a `threading.Event`-based adapter version for non-GIL runtimes.

---

### 1.2 sys.stdout.isatty() is a hidden I/O dependency in the adapter layer

**File:** `adapters/managers/container.py:4,30`

```python
import sys

@staticmethod
def _resolve_tty(config: RunConfig) -> bool:
    return config.tty or (config.auto_tty and sys.stdout.isatty())
```

While correctly placed in the adapter layer (not domain), `sys.stdout.isatty()` is a direct reference to the process's stdout that cannot be injected, overridden in tests without `patch("sys.stdout")`, or redirected for facilities like logging. In a strict hexagonal architecture, the *"is a TTY available?"* decision should be provided through a port (injectable callback or interface).

**Recommendation:** Add a `tty_detector: Callable[[], bool]` parameter to `CliContainerManager.__init__()` defaulting to `lambda: sys.stdout.isatty()`, and `_resolve_tty()` calls that instead of touching `sys.stdout` directly.

---

### 1.3 ParsingError inherits from Exception, not OciError

**File:** `ports/parsers.py:10-17`

All other domain/contract exceptions derive from `OciError`, creating a unified catch point. `ParsingError` derives directly from `Exception`, which means:

```python
try:
    engine.containers.inspect("ctr1")
except OciError as e:
    # This will NOT catch ParsingError
    handle_error(e)
```

This creates a gap in the exception hierarchy. If parsing fails during a manager operation, the caller must catch both `OciError` and `ParsingError`.

The `ARCHITECTURE.md` documents this as intentional: *"ParsingError lives in ports/parsers.py — it's a contract exception"* — but this creates an inconsistent exception boundary. A port's contract exception should still be catchable alongside domain errors.

**Recommendation:** Make `ParsingError` a subclass of `OciError`, or introduce an `OciPortError` base that both inherit from, so callers have a single catch point for all module errors.

---

### 1.4 ExecResult vs ExecOutput naming inversion

**File:** `domain/types.py`

| Type | Fields | Actual Role |
|------|--------|-------------|
| `ExecResult` | `returncode: int`, `stdout: bytes`, `stderr: bytes` | Transport-level raw output |
| `ExecOutput` | `returncode: int`, `stdout: str`, `stderr: str` | Domain-level decoded output |

The names are inverted relative to standard conventions. "Result" sounds like a domain concept (the business result of an operation), while "Output" sounds like raw data (what came out of a pipe). This creates confusion when reading code — `ExecResult` is the transport-level type but the name suggests it's the final business result.

**Recommendation:** Rename to `TransportResult` / `CommandResult` for the bytes version, and keep `ExecResult` / `ExecOutput` for the decoded domain version, or swap them so `ExecResult` is the decoded (str) version.

---

### 1.5 Primitive obsession: prune() returns dict[str, int]

**Files:** `ports/managers.py` — `ImageManager.prune()`, `ContainerManager.prune()`, `VolumeManager.prune()`, `NetworkManager.prune()`

All `prune()` methods return `dict[str, int]` with undocumented magic keys `"deleted"` and `"reclaimed_bytes"`. This is primitive obsession — the keys are not discoverable from the type signature and can be misspelled without any static checking.

**Recommendation:** Create a `PruneResult` value object in `domain/types.py`:

```python
@dataclass(frozen=True)
class PruneResult:
    deleted: int
    reclaimed_bytes: int
```

---

### 1.6 VolumeMount.type is a bare str, not an enum

**File:** `domain/types.py:8-11`

```python
@dataclass
class VolumeMount:
    source: str | Path
    target: str | Path
    type: str
    read_only: bool = False
```

The `type` field accepts any string, but Docker/Podman only support `"bind"`, `"volume"`, and `"tmpfs"`. This is a missing domain value object that should be an enum.

**Recommendation:** Create `VolumeMountType(StrEnum)` with `BIND`, `VOLUME`, `TMPFS` members, and type `type` as `VolumeMountType`.

---

### 1.7 RunConfig.memory_limit and cpu_limit are bare str with no validation

**File:** `domain/types.py`

```python
memory_limit: str | None = None
cpu_limit: str | None = None
```

No validation or documentation of accepted formats. `"512m"`, `"1g"`, and `"bananas"` are equally valid at the type level. Invalid values are silently passed to the CLI which produces unclear error messages.

**Recommendation:** Add a `__post_init__` validator or use `Annotated[str, ...]` with runtime pattern checking. At minimum, document the expected format (`<number><unit>` where unit = `b`, `k`, `m`, `g`).

---

### 1.8 No application/use-case layer

The module goes directly from ports to adapters with no use-case orchestration layer. The sibling module `config-assembler-engine` has a documented application layer (`AssembleConfiguration` use case). For complex operations like `ContainerManager.run()` which orchestrate transport, parser, error checking, PTY dispatch, and streaming, a use-case layer would make the flow clearer and more testable.

**Recommendation:** Consider extracting complex orchestrations (especially `run()` and `logs()`) into explicit use-case functions or classes in an `application/` layer, keeping managers as thin command builders.

---

## 2. Bugs

### 2.1 parse_size_to_bytes() silently returns 0 for unrecognized units (CRITICAL)

**File:** `adapters/_utils.py:15-18`

```python
units = {
    'B': 1, 'KB': 1024, 'MB': 1024**2, 'GB': 1024**3, 'TB': 1024**4,
    'KIB': 1024, 'MIB': 1024**2, 'GIB': 1024**3,
}
match = re.search(r"(\d+\.?\d*)\s*([a-zA-Z]+)", size_str.upper())
if not match:
    raise ValueError(f"Cannot parse size string: {size_str!r}")
number, unit = match.groups()
return int(float(number) * units.get(unit, 0))  # <-- BUG: falls back to 0
```

When the regex matches a number+unit pair but the unit is not in the dict (e.g., `"1PB"`, `"5EB"`, `"100XB"`), `units.get(unit, 0)` returns 0, making:

- `parse_size_to_bytes("1PB")` → `0` (should raise `ValueError`)
- `parse_size_to_bytes("100UNKNOWN")` → `0` (should raise `ValueError`)

This means image/volume size parsing silently produces 0 for any unrecognized unit, which propagates to `ImageInfo.size = 0` and `PruneResult.reclaimed_bytes = 0`.

**Fix:** Replace `units.get(unit, 0)` with `units[unit]` (raises `KeyError`), or add an explicit `if unit not in units: raise ValueError(...)`.

---

### 2.2 _resolve_tty() called 3 times in single run() execution (MEDIUM)

**File:** `adapters/managers/container.py:33,48,113`

```python
if config.detach and self._resolve_tty(config):   # call 1
    ...
if self._resolve_tty(config):                      # call 2
    cmd.append("-t")
...
if self._resolve_tty(config):                      # call 3
    result = run_pty(cmd)
```

`sys.stdout.isatty()` is evaluated three times. While unlikely in practice, the TTY state could theoretically change between calls (e.g., if stdout was redirected between checks). More importantly, this is a performance issue and a correctness risk — the method should be called once and cached.

**Fix:** Compute `effective_tty = self._resolve_tty(config)` once at the top of `run()` and reuse the local variable.

---

### 2.3 Manager list() methods skip error checking (HIGH)

**Files:** All four manager `list()` methods

```python
def list(self, ...) -> list[ContainerInfo]:
    cmd = [...]
    result = self._transport.execute(cmd)
    return self._parser.parse_list(self._decode_stdout(result.stdout))
    #   ^^^ No _check_result() call!
```

Every other manager method (`inspect`, `remove`, `start`, `stop`, etc.) calls `_check_result()` to translate non-zero exit codes into domain-specific exceptions. The `list()` methods skip this entirely. If the CLI returns a non-zero exit code with an error message, the parser receives raw error text and raises `ParsingError` instead of the appropriate `XxxError`.

**Fix:** Add `self._check_result(result, cmd, operation="list containers", entity="", not_found=ContainerNotFoundError)` before the parse call.

---

### 2.4 Manager create() methods skip error checking (HIGH)

**Files:** `CliVolumeManager.create()`, `CliNetworkManager.create()`

```python
def create(self, name: str, ...) -> str:
    cmd = [...]
    result = self._transport.execute(cmd)
    return self._decode_stdout(result.stdout).strip()
    #   ^^^ No _check_result() call!
```

A failed `volume create` or `network create` will return truncated stdout (possibly empty string) instead of raising a proper error. The user gets an empty string as a "volume name" with no indication of failure.

**Fix:** Add `_check_result()` before the return, with appropriate error types (`VolumeNotFoundError` / `NetworkNotFoundError` or a generic runtime error).

---

### 2.5 DockerImageParser.parse_list() silently swallows size parsing failures (LOW)

**File:** `adapters/parser/docker.py:70-83`

```python
size = item.get("Size", 0)
if isinstance(size, str):
    try:
        size = parse_size_to_bytes(size)
    except ValueError:
        size = 0                    # <-- silently set to 0
if not size:
    virtual = item.get("VirtualSize", 0)
    if isinstance(virtual, str):
        try:
            size = parse_size_to_bytes(virtual)
        except ValueError:
            size = 0                # <-- silently set to 0 again
```

Both `ValueError` catches set `size = 0` silently. If a Docker API version returns an unfamiliar size format, the user receives `ImageInfo(size=0)` with no warning or error.

**Fix:** At minimum, log a warning. Preferably raise `ParsingError` with the offending raw value.

---

### 2.6 BaseCliParser.is_not_found_error() uses substring matching (LOW)

**File:** `adapters/parser/base.py:43-44`

```python
def is_not_found_error(self, stderr: str) -> bool:
    lower = stderr.lower()
    return any(p in lower for p in self._not_found_patterns)
```

Pattern `"no such container"` matches `"no such containerxyz"`. This could cause false positives in error detection.

**Fix:** Use word boundary matching (`\b`) or exact substring matching with delimiters (e.g., `"no such container: "`).

---

### 2.7 CliStreamingTransport.stream() — stdin pipe not closed when input_data is None (LOW)

**File:** `adapters/transport/streaming.py:27-28`

When `Popen` is created with `stdin=subprocess.PIPE` but no `input_data` is provided, the stdin pipe is opened but never closed. The child process may block waiting for stdin input.

```python
process = subprocess.Popen(
    command,
    stdin=subprocess.PIPE if input_data else None,  # pipe created only when input_data truthy
    ...
)
```

This is actually correct — `stdin=subprocess.PIPE if input_data else None` means the pipe is only created when there's data to write. However, the condition `if input_data` means that `input_data=b""` (empty bytes) will NOT create a pipe, which differs from `CliTransport.execute()` where `input_data=b""` IS passed to `subprocess.run()`. This inconsistency could cause subtle bugs.

---

### 2.8 Unused imports (confirmed by lint)

**Files:** `domain/__init__.py:4` (unused `ContainerNotFoundError`), `domain/enums.py:1` (unused `Enum`)

```
F401 `ContainerNotFoundError` imported but unused
F401 `enum.Enum` imported but unused
```

**Fix:** Remove unused imports or add to `__all__`.

---

## 3. Bad Implementations

### 3.1 CancellationToken is not truly thread-safe

**File:** `domain/types.py:197-208`

See [1.1](#11-cancellationtoken-claims-cross-thread-use-but-has-no-thread-safety-mechanism) for the architectural concern. The implementation concern is that `self._cancelled = True` is a plain Python attribute assignment. While CPython's GIL ensures visibility, this is an implementation detail, not a language guarantee. Python 3.13+ free-threaded builds (PEP 703) will NOT provide this guarantee.

---

### 3.2 RecordingTransport is not thread-safe but used in concurrency tests

**File:** `tests/helpers/mock_transport.py:10-14`

```python
self.calls: list[RecordedCall] = []
```

`test_concurrency.py` fires 50 concurrent calls at `RecordingTransport` and asserts `len(t.calls) == n`. Python lists are not thread-safe for concurrent appends. Under CPython's GIL, `list.append()` is atomic, but this is an implementation detail, not a guarantee.

---

### 3.3 _check_result() over-engineered with Type[OciError] parameter

**File:** `adapters/managers/base.py:24-43`

```python
def _check_result(
    self, result, cmd, *, operation, entity, not_found: Type[OciError],
) -> None:
```

Every call site must pass `not_found=ContainerNotFoundError`, `not_found=ImageNotFoundError`, etc. This is an unusual pattern that pushes error-type selection to callers. A simpler approach would be a template method where each manager subclass declares its own `_not_found_error_class`.

---

### 3.4 RuntimeFactory.create() eagerly probes availability

**File:** `factory.py:79-81`

```python
if not runtime.is_available():
    raise RuntimeNotAvailableError(...)
```

`create()` always calls `runtime.is_available()` which calls `transport.probe()` which runs `subprocess.run([binary, "--version"])`. This spawns a subprocess on every `create()` call, even if the user is about to use the engine immediately (and would discover unavailability naturally). This adds ~100ms latency to every factory creation.

**Recommendation:** Make availability checking optional (e.g., `create(preference, check_available=False)`), or cache the probe result for a configurable TTL.

---

### 3.5 ProcessPipeReader has no read timeout

**File:** `adapters/_process_reader.py`

`reader.select(timeout=0.1)` uses a 100ms polling loop with no overall timeout. If the subprocess hangs and no `cancel_token` is provided, this spins forever. The outer `StreamingTransport.stream()` has a `timeout` parameter, but it only applies to `process.wait()`, not to the pipe-reading loop.

**Recommendation:** Add an optional `read_timeout` parameter to `ProcessPipeReader.read()` that raises `TimeoutError` if no data is received within the specified window.

---

### 3.6 Manager command construction uses string formatting without escaping

**File:** `adapters/managers/container.py:87-105`

```python
for env_key, env_val in config.environment.items():
    cmd.extend(["-e", f"{env_key}={env_val}"])    # no escaping
for k, v in config.labels.items():
    cmd.extend(["-l", f"{k}={v}"])                  # no escaping
for vol in config.volumes:
    spec = f"{src}:{tgt}"                            # no escaping
```

While `subprocess.run()` / `Popen` don't use a shell (so injection isn't a security risk), special characters in values (spaces, newlines, `=`) could produce malformed CLI arguments. Docker/Podman interpret these differently.

---

### 3.7 run_pty() output_stream type hint is overly broad

**File:** `adapters/managers/pty.py:14`

```python
def run_pty(command: list[str], output_stream: io.IOBase | None = None)
```

`io.IOBase` is the abstract base class. The method calls `output_stream.write(data)` and `output_stream.flush()`, which require `io.BufferedWriter` or `io.RawIOBase`. The type hint should be `io.BufferedWriter | io.RawIOBase` or a Protocol with `write()` and `flush()` methods.

---

## 4. Test Quality Issues

### 4.1 Excessive structural/reflective tests (~30+ tests)

The following tests verify Python language behavior, not module behavior. They would pass even if the entire module was broken:

| File | Tests | What they test |
|------|-------|-----------------|
| `test_enums.py` | `test_is_strenum`, `test_is_enum`, `test_strenum_is_str`, `test_strenum_equality_with_str`, `test_strenum_not_equal_to_wrong_str`, `test_strenum_fstring` | That StrEnum works as documented |
| `test_types.py` | `test_is_dataclass` (7 occurrences) | That dataclasses are dataclasses |
| `test_engine.py` | `test_is_abc`, `test_cannot_instantiate` | That ABCs can't be instantiated |
| `test_transport.py` | `test_is_abc`, `test_cannot_instantiate` | Same |
| `test_parsers.py` | `test_is_abc`, `test_cannot_instantiate` (4 parsers) | Same, 4 times |
| `test_managers.py` | `test_is_abc` (4 managers) | Same |
| `test_exceptions.py` | `test_is_exception` | That exceptions subclass Exception |
| `test_capabilities.py` | `test_has_no_get_binary_method` | That a method doesn't exist |

**Recommendation:** Remove these tests or consolidate into a single `test_structure.py` that verifies the module's ABC hierarchy in one pass. Replace with behavioral tests.

---

### 4.2 Integration tests are actually unit tests using mocks

The following directories use `RecordingTransport` (an in-memory mock), not real CLI tools:

- `tests/integration/boundary/` — All tests use mocks
- `tests/integration/integration/` — All tests use mocks  
- `tests/integration/contract/` — All tests use mocks
- `tests/integration/capability/` — All tests use mocks

Only `tests/integration/smoke/` uses real runtimes, but those tests are gated behind `@pytest.mark.docker_required`.

**Recommendation:** Rename mock-based integration tests to `tests/unit/adapters/` or `tests/unit/wiring/`. Reserve `tests/integration/` for tests that exercise real CLI tools against real runtimes.

---

### 4.3 Missing unit test coverage for critical paths

| Untested Code | Impact |
|---|---|
| `CancellationToken` (domain) | No tests at all for the cross-thread core type |
| `create_build_tar()` (adapter) | No tests for tar generation, a security-sensitive operation |
| `parse_size_to_bytes()` | Only tested indirectly via `BaseCliParser.parse_prune()` |
| `_parse_json_item()` / `_parse_json_list()` | Only tested indirectly via parser subclasses |
| `BaseCliParser.parse_prune()` | No direct unit test |
| `CliRuntimeDiscovery.available()` | No direct unit test (only via factory wiring) |
| `_resolve_tty()` | No test (mocking `sys.stdout.isatty()` is untested) |
| `ContainerManager.logs()` follow-mode threading | No test for the thread-based streaming path |
| `CliContainerManager.run()` PTY path | Only tested via `run_pty` directly, not through the manager |

---

### 4.4 Contract tests are shallow

**File:** `tests/unit/ports/test_container_manager_contract.py` (and similar)

Contract tests only verify return types using `MockContainerParser` that returns hardcoded values:

```python
def test_inspect_returns_container_info(self):
    mgr, t, st = self._defaults()
    t._responses["docker container inspect --format json c1"] = ExecResult(0, b"dummy", b"")
    result = mgr.inspect("c1")
    assert isinstance(result, ContainerInfo)   # Only checks type, not values
```

This doesn't verify that the parser was called with the correct data, or that error paths work correctly. The contract is "inspect returns a ContainerInfo" — but the mock parser returns a `ContainerInfo` regardless of input.

**Recommendation:** Add contract tests that verify:
1. The transport is called with the correct command
2. Error responses map to the correct exception types
3. The parser receives the transport's output verbatim

---

### 4.5 Duplicate mock/parser implementations across test files

Three separate implementations of mock parsers exist:

1. `tests/helpers/mock_parsers.py` — `MockContainerParser`, `MockImageParser`, `MockVolumeParser`, `MockNetworkParser`
2. `tests/unit/adapters/test_cli_container_manager.py:16-24` — `_MockParser(ContainerParser)` (incomplete, only 4 methods)
3. `tests/unit/ports/test_managers.py` — `_Parser(ImageParser)` (different, even more minimal)

Each has different behavior and different `is_not_found_error()` implementations.

**Recommendation:** Consolidate into a single `tests/helpers/mock_parsers.py` and import everywhere.

---

### 4.6 FailingTransport.probe() always returns True

**File:** `tests/helpers/mock_transport.py:53-62`

```python
class FailingTransport(Transport):
    def probe(self) -> bool:
        return True   # Should be False or configurable
```

A transport named "Failing" that always says it's available is semantically misleading.

**Fix:** Add `_probe_result: bool` parameter defaulting to `False`, or at minimum document the intent.

---

### 4.7 RecordingTransport matches commands by space-joined string

**File:** `tests/helpers/mock_transport.py:11`

```python
def execute(self, command, *, timeout=None, input_data=None):
    key = " ".join(command)
    if key in self._responses:
        return self._responses[key]
```

This breaks when command arguments contain spaces (e.g., `docker run -e "MY_VAR=hello world"`). The key `"docker run -e MY_VAR=hello world"` won't match the stored `"docker run -e MY_VAR=hello world"` if the argument was a single list element.

**Fix:** Use a `tuple(command)` as the key instead of `" ".join(command)`.

---

### 4.8 Tests don't verify exception attributes consistently

The `OciError` hierarchy stores `message`, `command`, `exit_code`, and `stderr` attributes, but most tests only check `with pytest.raises(XxxError)` without verifying the attributes contain meaningful values. Only `test_exceptions.py` checks `str(err)` formatting.

**Recommendation:** Add attribute assertions to manager error-path tests:

```python
with pytest.raises(ContainerRuntimeError) as exc_info:
    mgr.run(config)
assert exc_info.value.command == expected_command
assert exc_info.value.exit_code == 1
assert "expected substring" in exc_info.value.stderr
```

---

### 4.9 No negative path tests for domain types

Missing test cases:
- `BuildContext` with `context_path` + files (only `build_file_content` vs `build_file_path` mutual exclusion is tested)
- `RunConfig` with `NetworkMode.CONTAINER` but no `network_container` (only tested at adapter level, not domain level)
- `CancellationToken` being cancelled multiple times (idempotency)
- `CancellationToken.is_cancelled` default value
- `VolumeMount.type` with invalid string values
- `PortMapping` with `host_port=0` vs `host_port=None` semantics

---

### 4.10 Test file organization doesn't match source structure

- `test_capabilities.py` is in `unit/ports/` but `RuntimeCapabilities` is a data class, not an ABC — it's used across layers, not just ports.
- `ParsingError` tests are in `test_exceptions.py` (domain tests) but `ParsingError` is defined in `ports/parsers.py`.
- `test_domain_init.py` only tests that `__all__` contains specific names — a structural test with no behavioral value.

---

## 5. Severity Summary

| # | Issue | Severity | Category |
|---|-------|----------|----------|
| 2.1 | `parse_size_to_bytes()` silently returns 0 for unrecognized units | **Critical** | Bug |
| 2.3 | `list()` methods skip error checking | **High** | Bug |
| 2.4 | `create()` methods skip error checking | **High** | Bug |
| 1.1 | `CancellationToken` thread-safety gap | **High** | Architecture |
| 2.2 | `_resolve_tty()` called 3x in one method | **Medium** | Bug |
| 2.5 | Image parser size fallback silent failures | **Medium** | Bug |
| 1.2 | `sys.stdout.isatty()` not injectable | **Medium** | Architecture |
| 1.4 | `ExecResult`/`ExecOutput` naming inversion | **Medium** | Architecture |
| 1.5 | `prune()` returns `dict[str, int]` (primitive obsession) | **Medium** | Architecture |
| 1.6 | `VolumeMount.type` is bare `str` | **Medium** | Architecture |
| 1.7 | `RunConfig.memory_limit`/`cpu_limit` unvalidated | **Medium** | Architecture |
| 3.4 | Factory eagerly probes availability on every `create()` | **Low** | Implementation |
| 3.5 | `ProcessPipeReader` no read timeout | **Low** | Implementation |
| 2.6 | Substring match in `is_not_found_error` | **Low** | Bug |
| 2.7 | Inconsistent `input_data=b""` handling between transport types | **Low** | Bug |
| 3.3 | `_check_result()` over-engineered with `Type[OciError]` parameter | **Low** | Implementation |
| 3.6 | Command construction without escaping | **Low** | Implementation |
| 3.7 | `run_pty()` output_stream type hint overly broad | **Low** | Implementation |
| 4.1 | ~30+ structural/reflective tests with no behavioral value | **Medium** | Test Quality |
| 4.2 | Integration test directories contain mock-based unit tests | **Medium** | Test Quality |
| 4.3 | Missing coverage for 9 critical code paths | **Medium** | Test Quality |
| 4.4 | Contract tests only verify return types, not values or error paths | **Medium** | Test Quality |
| 4.5 | 3 separate mock parser implementations with different behavior | **Medium** | Test Quality |
| 4.6 | `FailingTransport.probe()` always returns `True` | **Low** | Test Quality |
| 4.7 | `RecordingTransport` key matching breaks with spaced args | **Low** | Test Quality |
| 4.8 | Exception attributes rarely verified in error-path tests | **Low** | Test Quality |
| 4.9 | No negative path tests for domain value objects | **Low** | Test Quality |
| 4.10 | Test file organization mismatches source structure | **Low** | Test Quality |
| 1.3 | `ParsingError` not catchable via `OciError` | **Low** | Architecture |
| 1.8 | No application/use-case layer | **Low** | Architecture |
| 2.8 | Unused imports (2 lint errors) | **Trivial** | Bug |
| 3.1 | `CancellationToken` not truly thread-safe (CPython GIL reliance) | **Info** | Implementation |
| 3.2 | `RecordingTransport` not thread-safe in concurrency tests | **Info** | Test Quality |