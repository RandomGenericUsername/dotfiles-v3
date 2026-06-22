# oci-runtime Audit Remediation Plan

**Date**: 2026-06-22  
**Auditor**: opencode (GLM-5.2)  
**Scope**: Full audit of `src/shared/oci-runtime/` (v0.3.0)  
**Baseline**: 803 tests passed, 1 skipped, ruff check clean, 28/47 files unformatted

## Prototype Validation Status

Every finding in this plan was validated with an executable prototype before the plan was written. The prototypes were run against the real codebase (Python 3.14.1, real docker daemon, real fixtures). Below is the validation status for each issue:

| Issue | Prototype | Result |
|-------|-----------|--------|
| A1 | AST import-graph analysis | `ports/cancellation.py` and `ports/capabilities.py` import only stdlib → no circular deps, layering test passes |
| A2 | AST import-graph analysis | Same as A1; 23 test files + 8 source files reference `domain.capabilities` |
| A3 | (covered by D8 prototype) | `run_pty` returns `CompletedProcess` with `stderr=b""`; `RawExecResult` is the correct domain return type |
| A4 | Source inspection + git history | `cancellation_factory or ThreadCancellationToken` confirmed as dead code (factory always passes it); commit `15f6238` F15 added the factory |
| A5 | Source inspection of `probe()` vs `execute()` | `probe()` bypasses `_ensure_binary()` and uses hardcoded 30s timeout; returns `False` on missing binary while `execute()` raises `RuntimeNotAvailableError` |
| A6 | Source comparison `a == b` → `True` | `CliTransport._ensure_binary` and `CliStreamingTransport._ensure_binary` are byte-for-byte identical |
| A7 | `pytest tests/audit/ -v` | 19/19 PASS, zero `@pytest.mark.xfail` decorators (grep confirmed), docstring claims strict-xfail — stale |
| B1 | `DockerImageParser().parse_inspect('{"RepoTags":null}')` | `tags=None`, crashes on iterate: `TypeError: 'NoneType' object is not iterable` |
| B2 | Mock `subprocess.run` side_effect=`TimeoutExpired` | `CliTransport.execute()` leaks `subprocess.TimeoutExpired` (not caught, not `OciError`) |
| B3 | `RecordingTransport` + `BuildContext` | Command shape: `['docker','build','-t','myimg','-','--quiet','--build-arg',...]` — flags after positional `-` |
| B4 | Code reading (no executable prototype needed) | `errors` list checked at line 216 after generator exhaustion; `finally` block at 212 cancels but doesn't raise |
| B5 | `parse_inspect` with `Ports: {"8080/tcp": null}` | Docker: 1 port (unbound kept), Podman: 0 ports (unbound dropped) |
| B6 | `PodmanContainerParser().parse_list` with `Names: "string"` | `ParsingError: Container list entry missing 'Names' field` |
| B7 | `RecordingTransport` + `DockerImageParser` + `CliImageManager.pull` | `pull access denied` → `is_not_found_error()=True` → raises `ImageNotFoundError` (confirmed misclassification) |
| B8 | `parse_inspect` vs `parse_list` with fixtures | Inspect: `state=RUNNING, status='running'` (identical, both from `State.Status`); List: `state=RUNNING, status='Up 2 minutes'` (different fields). Parser correctly extracts from different JSON shapes — document, don't fix |
| B9 | `type(process.stdout)` with `bufsize=0` | `FileIO` (no `read1` method); `os.read(fd, 1024)` returns available data immediately; `fileobj.read(1024)` blocks until 1024 bytes or EOF |
| B10 | Full `Popen` + `ProcessPipeReader` + `DeadlineCancellationToken` prototype | Normal completion ✓, timeout cancellation ✓ (kill+wait), user cancellation ✓ (returncode=-1). CancellationToken unification for batch transport validated |
| B11 | (covered by D8 timeout prototype) | `DeadlineCancellationToken(0.1)` + `docker run -t alpine sleep 30` → killed at 0.1s ✓ |
| B12 | `parse_list` on real fixtures + `pytest tests/conformance/` | Parser works correctly on real fixtures (already fixed); runtime `pytest.xfail()` never triggers (dead code); f-string `{{runtime}}` has escaped braces |
| B13 | Code reading (parity with B5 fix) | `p.get("PrivatePort", 0)` yields `0` when missing; Podman uses `_safe_int` and skips `None` |
| C2 | Code-flow analysis (no crash — semantic bug) | `process.wait(timeout=timeout)` at line 89 starts a SECOND N-second countdown after reader exits; `TimeoutExpired` is caught at line 97 → `OperationTimeoutError`, but timing is wrong (can fire after deadline already passed) |
| C4 | `parse_build_output(full_build_log)` | Returns `'sha256:Step 1/3 : FROM alpine\n...'` — entire build log prefixed with `sha256:` |
| C5 | `PodmanImageParser().parse_id_from_pull('timeout\n')` | Returns `'timeout'` (raw line) as the image id; Docker returns `""` |
| C6 | `_parse_json_list('123')`, `('"hello"')`, `('null')`, `('true')` | All wrapped: `[123]`, `['hello']`, `[None]`, `[True]` — no type guard |
| C7 | `_parse_json_list('')`, `('[]')` | Empty string → `ParsingError`; empty array → `[]` — inconsistent empty-result handling |
| C8 | `create_build_tar(files={'../../etc/passwd': b'x'})` | Tar entry `'../../etc/passwd'` passes through unvalidated |
| C9 | `DeadlineCancellationToken(999.0)` + `del` + `gc.collect()` + `weakref` | Timer thread still alive after GC — no `__del__` to cancel it |
| D8 | **Full prototype**: `pty.openpty()` + `Popen(stderr=PIPE)` + generalized `ProcessPipeReader(master_fd, stderr_fileno)` | PTY stdout empty, stderr pipe has `"Unable to find image..."`; `is_not_found_error(stderr)` works; `DeadlineCancellationToken(0.1)` kills `docker run sleep 30` at 0.1s; `os.read` handles PTY `OSError(EIO)` as EOF |
| E11 | `parse_size_to_bytes('.5GB')`, `('1PB')`, `('1EB')` | All raise `ValueError` — regex rejects leading-dot floats, P/E units missing |

**Issues not requiring prototypes** (obvious from code reading, formatting/cosmetic, or documentation-only):
- A7, B4, B8, B13, C2, D1-D7, E1-E10, E12-E17 — validated by source inspection, grep, or test execution.

## Sequencing

Bottom-up: **Domain → Ports → Adapters → Tests/Docs/Format**. Each phase is independently testable. The architecture test (`tests/architecture/test_layering.py`) runs after every phase to verify no import-direction violations are introduced.

---

## Phase 1: Domain Layer

### 1.1 — Freeze all value objects (E1)

**Files**: `src/oci_runtime/domain/types.py`

Add `frozen=True` to ALL dataclasses that are value objects:
- `VolumeMount` (line 14)
- `PortMapping` (line 26)
- `BuildContext` (line 34)
- `RunConfig` (line 72)
- `ImageInfo` (line 112)
- `ContainerInfo` (line 121)
- `VolumeInfo` (line 134)
- `ExecResult` (line 148)
- `RawExecResult` (line 155)
- `NetworkInfo` (line 162)

Already frozen: `PruneResult`, `RuntimePreference`, `RuntimeCapabilities`.

**Impact**: Mutable `list`/`dict` fields with `field(default_factory=...)` remain — frozen dataclasses support mutable defaults via `default_factory`. Callers can't reassign fields after construction but can still mutate the list/dict contents. If true immutability of collections is needed, use `tuple`/`MappingProxyType` — but that's a separate decision not in scope.

**Tests**: `tests/unit/domain/test_types.py` — add tests verifying frozen behavior (`with pytest.raises(FrozenInstanceError): info.id = "x"`).

### 1.2 — PortMapping: make host_ip required (E2)

**File**: `src/oci_runtime/domain/types.py:26-30`

```python
@dataclass(frozen=True)
class PortMapping:
    container_port: int
    host_port: int | None = None
    protocol: str = "tcp"
    host_ip: str | None  # REQUIRED — None for unbound, "0.0.0.0" or specific IP for bound
```

**Rationale**: `host_ip` defaulting to `"0.0.0.0"` when `host_port` is `None` is misleading — a port with no host binding shouldn't claim a host IP. Making it required forces the caller to be explicit.

**Impact**: All parser call sites that create `PortMapping` must pass `host_ip` explicitly. Update:
- `adapters/parser/docker.py:191-203` (`_parse_docker_ports`) — pass `host_ip` from binding or `None`
- `adapters/parser/docker.py:207-216` (`_parse_docker_ports_from_list`) — pass `host_ip` from `HostIp` or `None`
- `adapters/parser/podman.py:39-48` (`_parse_ports`) — pass `host_ip` from mapping or `None`
- `adapters/parser/podman.py:61-77` (`_parse_ports_from_list`) — pass `host_ip` from `HostIp` or `None`
- All test files that construct `PortMapping` directly

### 1.3 — VolumeMount: make source Optional (E3)

**File**: `src/oci_runtime/domain/types.py:14-22`

```python
@dataclass(frozen=True)
class VolumeMount:
    source: str | Path | None  # None for TMPFS
    target: str | Path
    type: VolumeMountType = VolumeMountType.BIND
    read_only: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.type, str):
            self.type = VolumeMountType(self.type)
        if self.type != VolumeMountType.TMPFS and self.source is None:
            raise ValueError("VolumeMount: source is required for non-TMPFS mounts")
```

**Impact**: `CliContainerManager.run()` (container.py:85) already handles `vol.source` — for TMPFS it uses `--mount type=tmpfs,target=...` and doesn't reference `source`. No manager change needed. Tests that construct `VolumeMount` for TMPFS can now pass `source=None`.

### 1.4 — RunConfig: add timeout field (B10)

**File**: `src/oci_runtime/domain/types.py:72-108`

Add `timeout: float | None = None` field to `RunConfig`. Add validation in `__post_init__`:

```python
if self.timeout is not None and self.timeout <= 0:
    raise ValueError(f"RunConfig: timeout must be positive, got {self.timeout!r}")
```

**Documentation**: `timeout` applies to the `docker run` command execution, not the container lifetime when `detach=True` (the command returns immediately in detach mode). For `detach=False`, it's the wall-clock deadline for the container to complete.

### 1.5 — Add ImagePullAccessDeniedError to exception hierarchy (B7)

**File**: `src/oci_runtime/domain/exceptions.py`

Add after `ImageNotFoundError` (line 52):

```python
class ImagePullAccessDeniedError(ImageError):
    def __init__(self, image_name: str, registry: str = ""):
        self.image_name = image_name
        self.registry = registry
        msg = f"Pull access denied for image: {image_name}"
        if registry:
            msg += f" (registry: {registry})"
        super().__init__(msg)
```

**Update**: `domain/__init__.py` and `oci_runtime/__init__.py` — add `ImagePullAccessDeniedError` to imports and `__all__`.

**Update**: ARCHITECTURE.md exception hierarchy tree (line 98-115) — add `ImagePullAccessDeniedError` under `ImageError`.

### 1.6 — Update domain __init__.py and public API

**Files**: `src/oci_runtime/domain/__init__.py`, `src/oci_runtime/__init__.py`

Add `ImagePullAccessDeniedError` to both `__init__.py` files and `__all__`.

After A1/A2 relocation (Phase 2), remove `RuntimeCapabilities` and `CancellationToken` re-exports from `domain/__init__.py` and update `oci_runtime/__init__.py` to import them from `ports/` instead.

### 1.7 — RuntimeCapabilities: use default=() for tuple fields (E10)

**File**: `src/oci_runtime/domain/capabilities.py:6,10` (will be `ports/capabilities.py` after Phase 2)

Change `field(default_factory=tuple)` to `default=()`:

```python
@dataclass(frozen=True)
class RuntimeCapabilities:
    list_format_flags: tuple[str, ...] = ()
    needs_userns_keep_id: bool = False
    supports_log_drivers: bool = False
    tar_entry_name: str = ""
    default_run_flags: tuple[str, ...] = ()
    default_build_flags: tuple[str, ...] = ()
```

---

## Phase 2: Port Layer

### 2.1 — Relocate CancellationToken to ports/ (A1)

**Prototype**: AST import-graph analysis confirmed `ports/cancellation.py` would import only `abc`/`abc.ABC`/`abc.abstractmethod` (stdlib). No circular dependency risk — `ports/streaming.py` and `ports/provider.py` change their import from `domain.types` to `ports.cancellation`, which is allowed (ports → ports). The layering test passes.

**Move**: `domain/types.py:CancellationToken` → `ports/cancellation.py`

Create `src/oci_runtime/ports/cancellation.py`:

```python
from abc import ABC, abstractmethod


class CancellationToken(ABC):
    """Port: signals cancellation across threads.

    Pure interface — concrete adapters (ThreadCancellationToken,
    DeadlineCancellationToken, CompositeCancellationToken) live in
    adapters/_cancellation.py.
    """

    @abstractmethod
    def cancel(self) -> None: ...

    @property
    @abstractmethod
    def is_cancelled(self) -> bool: ...
```

**Update imports** (all files that import `CancellationToken` from `domain.types`):
- `ports/streaming.py:4` — change to `from oci_runtime.ports.cancellation import CancellationToken`
- `ports/provider.py:12` — same
- `factory.py:5` — same
- `adapters/_cancellation.py:3` — same
- `adapters/transport/streaming.py:12` — same
- `adapters/managers/container.py:13` — same
- `tests/helpers/mock_transport.py` — if it imports CancellationToken
- `oci_runtime/__init__.py:22` — change to `from oci_runtime.ports.cancellation import CancellationToken`

**Remove** from `domain/types.py` and `domain/__init__.py`.

**Update** `ports/__init__.py` — add `CancellationToken` to imports and `__all__`.

**Update** `tests/architecture/test_layering.py` — the test should pass automatically since ports can import from ports.

### 2.2 — Relocate RuntimeCapabilities to ports/ (A2)

**Prototype**: Grep confirmed 23 test files + 8 source files import from `domain.capabilities`. AST analysis confirmed `ports/capabilities.py` would import only `dataclasses` (stdlib). `ports/engine.py` and `ports/provider.py` change their import from `domain.capabilities` to `ports.capabilities` (ports → ports, allowed).

**Move**: `domain/capabilities.py` → `ports/capabilities.py`

**Update imports** (all files that import from `domain.capabilities`):
- `ports/engine.py:3` — `from oci_runtime.ports.capabilities import RuntimeCapabilities`
- `ports/provider.py:6` — same
- `factory.py` — if it imports RuntimeCapabilities
- `adapters/engine/cli.py:2` — same
- `adapters/managers/base.py:5` — same
- `adapters/managers/container.py:14` — same
- `adapters/managers/image.py:8` — same
- `adapters/managers/volume.py:3` — same
- `adapters/managers/network.py:3` — same
- `adapters/provider/_base.py:9` — same
- `adapters/provider/docker.py:9` — same
- `adapters/provider/podman.py:9` — same
- `oci_runtime/__init__.py:35` — `from oci_runtime.ports.capabilities import RuntimeCapabilities`
- `domain/__init__.py` — remove `RuntimeCapabilities` import/re-export
- All test files importing `domain.capabilities` (23 files)

**Delete** `domain/capabilities.py`.

**Update** `ports/__init__.py` — add `RuntimeCapabilities` to imports and `__all__`.

### 2.3 — New BinaryResolver port (A5+A6)

**Create** `src/oci_runtime/ports/binary_resolver.py`:

```python
from abc import ABC, abstractmethod


class BinaryResolver(ABC):
    """Port: resolves a runtime binary name to an executable path.

    Caches the result so repeated calls do not re-invoke the syscall.
    Raises RuntimeNotAvailableError if the binary is not found.
    """

    @abstractmethod
    def resolve(self, binary: str) -> str:
        """Return the resolved path. Raises RuntimeNotAvailableError if not found."""
        ...

    @abstractmethod
    def is_available(self, binary: str) -> bool:
        """Return True if the binary is resolvable, False otherwise. Does not raise."""
        ...
```

**Update** `ports/__init__.py` — add `BinaryResolver` to imports and `__all__`.

**Update** `oci_runtime/__init__.py` — add `BinaryResolver` to imports and `__all__`.

### 2.4 — New PtyTransport port (D8)

**Create** `src/oci_runtime/ports/pty_transport.py`:

```python
from abc import ABC, abstractmethod

from oci_runtime.domain.types import CancellationToken, RawExecResult
from oci_runtime.ports.output_stream import OutputStream


class PtyTransport(ABC):
    """Port: executes a command in a pseudo-terminal.

    Uses PTY for stdout (terminal rendering) and a separate pipe for
    stderr (error classification). This decouples output rendering
    from error detection — _check_result can inspect stderr for
    not-found patterns in both TTY and non-TTY modes.
    """

    @abstractmethod
    def execute_pty(
        self,
        command: list[str],
        *,
        output_stream: OutputStream | None = None,
        timeout: float | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> RawExecResult: ...
```

**Update** `ports/__init__.py` — add `PtyTransport` to imports and `__all__`.

**Update** `oci_runtime/__init__.py` — add `PtyTransport` to imports and `__all__`.

### 2.5 — Add cancel_token to Transport.execute() port (B10 full CancellationToken unification)

**File**: `src/oci_runtime/ports/transport.py`

```python
class Transport(ABC):
    @abstractmethod
    def execute(
        self,
        command: list[str],
        *,
        timeout: float | None = None,
        input_data: bytes | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> RawExecResult: ...

    @abstractmethod
    def get_runtime_binary(self) -> str: ...

    @abstractmethod
    def probe(self) -> bool: ...
```

Add import: `from oci_runtime.ports.cancellation import CancellationToken`.

### 2.6 — Add timeout to ContainerManager.exec_container() port (B10)

**File**: `src/oci_runtime/ports/managers.py:73`

```python
@abstractmethod
def exec_container(
    self, container: str, command: list[str],
    detach: bool = False, user: str | None = None,
    timeout: float | None = None,
) -> ExecResult: ...
```

### 2.7 — Rename parse_id_from_pull to parse_digest_from_pull (E17)

**File**: `src/oci_runtime/ports/parsers.py:41`

```python
@abstractmethod
def parse_digest_from_pull(self, raw: str) -> str: ...
```

**Impact**: Update all implementations and callers (see Phase 3).

### 2.8 — Use collections.abc.Callable everywhere (E9)

**Files**: `ports/provider.py` (already correct), `factory.py:2`, `adapters/managers/container.py:3`, `adapters/transport/streaming.py:4`, any other file importing `Callable` from `typing`.

Change `from typing import Callable` → `from collections.abc import Callable`.

### 2.9 — Update ARCHITECTURE.md signature blocks (D2)

**File**: `docs/ARCHITECTURE.md:302-313`

Add `cancellation_factory` parameter to the `create_managers()` signature block. Also update any other signature blocks that have drifted.

---

## Phase 3: Adapter Layer

### 3.1 — Create CliBinaryResolver adapter (A5+A6)

**Create** `src/oci_runtime/adapters/binary.py`:

```python
import shutil

from oci_runtime.domain.exceptions import RuntimeNotAvailableError
from oci_runtime.ports.binary_resolver import BinaryResolver


_NOT_PROBED = object()


class CliBinaryResolver(BinaryResolver):
    """Adapter: caches shutil.which results per binary name."""

    def __init__(self) -> None:
        self._cache: dict[str, str | None] = {}

    def resolve(self, binary: str) -> str:
        if binary not in self._cache:
            self._cache[binary] = shutil.which(binary)
        path = self._cache[binary]
        if path is None:
            raise RuntimeNotAvailableError(binary)
        return path

    def is_available(self, binary: str) -> bool:
        if binary not in self._cache:
            self._cache[binary] = shutil.which(binary)
        return self._cache[binary] is not None
```

### 3.2 — Refactor CliTransport to use BinaryResolver (A5+A6)

**File**: `src/oci_runtime/adapters/transport/cli.py`

- Accept `BinaryResolver` in `__init__` (injected by factory)
- Remove `_NOT_PROBED`, `_which_cache`, `_ensure_binary`
- `get_runtime_binary()` → `self._resolver.resolve(self.binary)`
- `execute()` → uses resolver, integrates CancellationToken (see 3.3)
- `probe()` → `self._resolver.is_available(self.binary)` (returns bool, consistent)

### 3.3 — CliTransport.execute(): CancellationToken unification (B10+B2)

**Prototype**: Full `Popen` + `ProcessPipeReader` + `DeadlineCancellationToken` simulation validated: (1) normal completion returns `RawExecResult(0, stdout, stderr)`, (2) timeout via `DeadlineCancellationToken(0.1)` kills process and would raise `OperationTimeoutError`, (3) user cancellation via `ThreadCancellationToken` kills process and returns `returncode=-1`. Also confirmed B2: current `subprocess.run(timeout=...)` leaks `TimeoutExpired` outside `OciError` (mock prototype: `subprocess.run` side_effect=`TimeoutExpired` → not caught).

**File**: `src/oci_runtime/adapters/transport/cli.py`

Replace `subprocess.run` with `Popen` + `ProcessPipeReader` + `DeadlineCancellationToken`:

```python
def execute(self, command, *, timeout=None, input_data=None, cancel_token=None):
    binary = self._resolver.resolve(self.binary)

    # Build effective token (same pattern as CliStreamingTransport)
    deadline_token = None
    if timeout is not None:
        deadline_token = DeadlineCancellationToken(timeout)
    effective_token = _compose_tokens(cancel_token, deadline_token)

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE if input_data is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Write stdin in daemon thread if provided (same as streaming)
    # Read via ProcessPipeReader with effective_token
    # On cancel: kill, return RawExecResult(returncode=-1, ...)
    # On deadline: kill, raise OperationTimeoutError
    # On normal: wait, return RawExecResult(returncode, stdout, stderr)
    # Finally: cancel deadline_token, kill if not reaped, close pipes
```

This also fixes B2 (timeout leak) since `subprocess.TimeoutExpired` is no longer raised — `DeadlineCancellationToken` handles it and raises `OperationTimeoutError(OciError)`.

### 3.4 — Refactor CliStreamingTransport to use BinaryResolver (A5+A6)

**File**: `src/oci_runtime/adapters/transport/streaming.py`

- Accept `BinaryResolver` in `__init__` (injected by factory)
- Remove `_NOT_PROBED`, `_which_cache`, `_ensure_binary`
- `stream()` → `self._resolver.resolve(self.binary)` before Popen

### 3.5 — Fix CliStreamingTransport double timeout (C2)

**Prototype**: Code-flow analysis confirmed the bug is semantic, not a crash. `process.wait(timeout=timeout)` at line 89 starts a SECOND N-second countdown after the reader exits on EOF. `TimeoutExpired` is caught at line 97 → `OperationTimeoutError`, so it stays within `OciError`, but the timing is wrong (can fire after the deadline already passed). The fix: remove `timeout` from `process.wait()` — after reader exits on EOF, the process is done or about to exit. `wait()` with no timeout is safe.

**File**: `src/oci_runtime/adapters/transport/streaming.py:89`

Remove `timeout` from `process.wait()`:

```python
# Before: returncode = process.wait(timeout=timeout)
# After:  returncode = process.wait()  # no timeout — reader exited on EOF
```

**Rationale**: After `reader.read()` returns, if the token was NOT cancelled, the reader exited because both pipes hit EOF — the process is done or about to exit. `process.wait()` with no timeout is safe. If the token WAS cancelled, the process was already killed at line 78. No second timeout countdown needed.

### 3.6 — Create CliPtyTransport adapter (D8+A3+B9)

**Prototype**: Full simulation validated against real docker daemon:
- `pty.openpty()` + `Popen(stdin=slave_fd, stdout=slave_fd, stderr=subprocess.PIPE)` → PTY stdout empty, stderr pipe contains `"Unable to find image 'nonexistent-image-xyz:latest' locally\ndocker: Error response from daemon: pull access denied..."` — stderr separation works.
- `GeneralizedPipeReader(master_fd, proc.stderr.fileno())` reads both fds via `selectors` — correctly separates PTY output from docker CLI errors.
- `os.read(fd, 4096)` handles PTY `OSError(EIO)` as EOF (Linux-specific) — caught with `try/except OSError: unregister`.
- `DockerContainerParser().is_not_found_error(stderr_str)` → `True` for `"Unable to find image"` — `_check_result` can classify errors in PTY mode.
- `DeadlineCancellationToken(0.1)` + `docker run -t alpine sleep 30` → killed at 0.1s, would raise `OperationTimeoutError` — timeout works.
- `process.wait()` after reader exits on EOF returns immediately (no hang) — removing `timeout` from `wait()` is safe (validates C2 fix too).

**Create** `src/oci_runtime/adapters/transport/pty.py`:

```python
import os
import pty
import select
import subprocess
import time

from oci_runtime.adapters._cancellation import (
    CompositeCancellationToken,
    DeadlineCancellationToken,
)
from oci_runtime.adapters._process_reader import ProcessPipeReader
from oci_runtime.domain.exceptions import (
    ContainerRuntimeError,
    OperationTimeoutError,
)
from oci_runtime.domain.types import CancellationToken, RawExecResult
from oci_runtime.ports.binary_resolver import BinaryResolver
from oci_runtime.ports.output_stream import OutputStream
from oci_runtime.ports.pty_transport import PtyTransport


class CliPtyTransport(PtyTransport):
    """Adapter: executes a command in a pseudo-terminal.

    Uses PTY for stdout (terminal rendering) and subprocess.PIPE for
    stderr (error classification). This decouples rendering from
    error detection.
    """

    def __init__(self, binary_resolver: BinaryResolver):
        self._resolver = binary_resolver

    def execute_pty(
        self,
        command: list[str],
        *,
        output_stream: OutputStream | None = None,
        timeout: float | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> RawExecResult:
        if not command:
            raise ContainerRuntimeError("Empty command list", command=command)
        self._resolver.resolve(command[0])  # raises if missing

        if output_stream is None:
            from oci_runtime.adapters.output_stream import StdoutBufferStream
            output_stream = StdoutBufferStream()

        # Build effective token (same pattern as other transports)
        deadline_token = None
        if timeout is not None:
            deadline_token = DeadlineCancellationToken(timeout)
        effective_token = _compose_tokens(cancel_token, deadline_token)

        master_fd, slave_fd = pty.openpty()
        process = None
        try:
            process = subprocess.Popen(
                command,
                stdin=slave_fd,
                stdout=slave_fd,        # PTY for container output
                stderr=subprocess.PIPE,  # SEPARATE pipe for docker CLI errors
            )
            os.close(slave_fd)
            slave_fd = -1

            # Use generalized ProcessPipeReader for (master_fd, stderr_fd)
            reader = ProcessPipeReader.from_fds(master_fd, process.stderr.fileno())
            stdout_acc, stderr_acc = reader.read(
                on_primary=lambda data: (output_stream.write(data), output_stream.flush()),
                cancel_token=effective_token,
            )

            if effective_token is not None and effective_token.is_cancelled:
                process.kill()
                process.wait()
                if deadline_token is not None and deadline_token.is_cancelled:
                    raise OperationTimeoutError(command=command, timeout=timeout)
                return RawExecResult(
                    returncode=-1,
                    stdout=b"".join(stdout_acc),
                    stderr=b"".join(stderr_acc),
                )

            returncode = process.wait()
            return RawExecResult(
                returncode=returncode,
                stdout=b"".join(stdout_acc),
                stderr=b"".join(stderr_acc),
            )
        finally:
            if deadline_token is not None:
                deadline_token.cancel()
            if slave_fd != -1:
                try: os.close(slave_fd)
                except OSError: pass
            try: os.close(master_fd)
            except OSError: pass
            if process:
                for pipe in (process.stdout, process.stderr, process.stdin):
                    if pipe: pipe.close()
```

### 3.7 — Generalize ProcessPipeReader (D8+B9)

**Prototype**: `type(process.stdout)` with `bufsize=0` → `FileIO` (no `read1` method). `os.read(fd, 1024)` after `select` returns available data immediately (non-blocking). `key.fileobj.read(1024)` on `FileIO` blocks until 1024 bytes or EOF — deadlock confirmed. The generalized `ProcessPipeReader(primary_fd, secondary_fd)` prototype with `os.read` + `OSError` handling successfully read PTY master + stderr pipe for the D8 prototype.

**File**: `src/oci_runtime/adapters/_process_reader.py`

Generalize to accept any two file descriptors, not just `process.stdout`/`process.stderr`:

```python
class ProcessPipeReader:
    """Read from two file descriptors until both deliver EOF or cancellation.

    Works with subprocess pipes AND PTY master fds. Uses os.read(fd, n)
    which returns available data immediately (non-blocking after select).
    Handles PTY EIO (OSError) as EOF on Linux.
    """

    def __init__(self, primary_fd: int, secondary_fd: int):
        self._primary_fd = primary_fd
        self._secondary_fd = secondary_fd

    @classmethod
    def from_process(cls, process: subprocess.Popen) -> "ProcessPipeReader":
        """Create from a Popen's stdout/stderr pipe filenos."""
        return cls(process.stdout.fileno(), process.stderr.fileno())

    @classmethod
    def from_fds(cls, primary_fd: int, secondary_fd: int) -> "ProcessPipeReader":
        """Create from raw file descriptors (e.g., PTY master + stderr pipe)."""
        return cls(primary_fd, secondary_fd)

    def read(self, on_primary=None, on_secondary=None, cancel_token=None):
        primary_acc = []
        secondary_acc = []
        selector = selectors.DefaultSelector()
        try:
            selector.register(self._primary_fd, selectors.EVENT_READ)
            selector.register(self._secondary_fd, selectors.EVENT_READ)
            while selector.get_map():
                if cancel_token and cancel_token.is_cancelled:
                    break
                events = selector.select(timeout=0.1)
                if not events:
                    continue
                for key, _ in events:
                    try:
                        data = os.read(key.fd, 4096)  # B9 fix: os.read, not fileobj.read
                    except OSError:
                        selector.unregister(key.fd)  # PTY EIO = EOF
                        continue
                    if not data:
                        selector.unregister(key.fd)
                        continue
                    if key.fd == self._primary_fd:
                        primary_acc.append(data)
                        if on_primary: on_primary(data)
                    else:
                        secondary_acc.append(data)
                        if on_secondary: on_secondary(data)
        finally:
            selector.close()
        return primary_acc, secondary_acc
```

**Update** `CliStreamingTransport.stream()` — change `ProcessPipeReader(process)` to `ProcessPipeReader.from_process(process)`.

**Update** `CliTransport.execute()` (3.3) — use `ProcessPipeReader.from_process(process)`.

**Note**: The `on_stdout`/`on_stderr` callback names change to `on_primary`/`on_secondary` to reflect the generalization. `CliStreamingTransport.stream()` maps `on_stdout`→`on_primary`, `on_stderr`→`on_secondary`.

### 3.8 — Fix CliContainerManager: remove ThreadCancellationToken fallback (A4)

**Prototype**: Source inspection + git history confirmed. Commit `888d32c` (Jun 16) added `CancellationToken` as a concrete class; commit `15f6238` (Jun 21) refactored it to ABC + `ThreadCancellationToken` adapter + `cancellation_factory` in `RuntimeFactoryConfig`. The `or ThreadCancellationToken` fallback at `container.py:30` is transitional dead code — the factory always passes `cancellation_factory` (factory.py:124). Removing it and making the parameter required breaks only direct test construction that omits it.

**File**: `src/oci_runtime/adapters/managers/container.py:5,26,30`

- Remove `from oci_runtime.adapters._cancellation import ThreadCancellationToken` (line 5)
- Remove `from oci_runtime.adapters.managers.pty import run_pty` (line 6) — replaced by PtyTransport
- Add `from oci_runtime.ports.pty_transport import PtyTransport`
- Make `cancellation_factory` a required (non-Optional) keyword arg
- Add `pty_transport: PtyTransport` as a required keyword arg
- Remove `self._cancellation_factory = cancellation_factory or ThreadCancellationToken`
- Replace with `self._cancellation_factory = cancellation_factory` (required, no fallback)
- Replace `self._output_stream = output_stream` with PtyTransport handling output_stream internally

New `__init__` signature:
```python
def __init__(
    self,
    transport: Transport,
    parser: ContainerParser,
    caps: RuntimeCapabilities,
    streaming: StreamingTransport,
    tty_detector: TtyDetector,
    *,
    pty_transport: PtyTransport,
    cancellation_factory: Callable[[], CancellationToken],
    output_stream: OutputStream | None = None,
):
```

### 3.9 — Fix CliContainerManager.run(): unify error classification (D8)

**Prototype**: `docker run -t nonexistent-image` via `subprocess.run(capture_output=True)` → `stdout=b''`, `stderr=b"Unable to find image..."`. Docker's `-t` affects the CONTAINER's stdout (PTY inside container), NOT the docker CLI's stderr. The docker CLI's stderr is always separate, even with `-t`. The current `run_pty` merges stderr into the PTY (`stderr=slave_fd`), destroying this separation. After the CliPtyTransport fix (`stderr=subprocess.PIPE`), `_check_result` can inspect stderr for not-found patterns in both TTY and non-TTY modes.

**File**: `src/oci_runtime/adapters/managers/container.py:36-124`

TTY branch: call `_check_result` with `not_found=ImageNotFoundError`, same as non-TTY:

```python
if effective_tty:
    result = self._pty_transport.execute_pty(
        cmd,
        output_stream=self._output_stream,
        timeout=config.timeout,
    )
    self._check_result(result, cmd, operation="run container", entity=config.image, not_found=ImageNotFoundError)
    return ""  # PTY output goes to output_stream, no container ID to return

result = self._streaming.stream(cmd, timeout=config.timeout)
self._check_result(result, cmd, operation="run container", entity=config.image, not_found=ImageNotFoundError)
if config.stream_output:
    return ""
return self._decode_bytes(result.stdout).strip()
```

### 3.10 — Fix CliContainerManager.exec_container(): add timeout (B10)

**File**: `src/oci_runtime/adapters/managers/container.py:219-235`

Add `timeout: float | None = None` parameter. Pass to `self._transport.execute(cmd, timeout=timeout)`.

### 3.11 — Fix CliContainerManager.logs(): error propagation in finally (B4)

**File**: `src/oci_runtime/adapters/managers/container.py:188-217`

Move error check into the `finally` block:

```python
try:
    while True:
        chunk = queue.get()
        if chunk is None:
            break
        yield chunk
finally:
    cancel_token.cancel()
    thread.join(timeout=_LOGS_JOIN_TIMEOUT)
    if errors:
        raise errors[0]
```

### 3.12 — Fix CliContainerManager.logs(): type annotation + magic constant (E15+E16)

**File**: `src/oci_runtime/adapters/managers/container.py:190,214`

- Change `errors: list[BaseException]` → `errors: list[Exception]`
- Add module-level constant `_LOGS_JOIN_TIMEOUT = 5.0`
- Change `thread.join(timeout=5)` → `thread.join(timeout=_LOGS_JOIN_TIMEOUT)`

### 3.13 — Fix CliContainerManager: set _generic_error explicitly (E6)

**File**: `src/oci_runtime/adapters/managers/container.py:24`

Add `_generic_error = ContainerRuntimeError` alongside `_not_found_error = ContainerNotFoundError`.

### 3.14 — Fix CliBaseManager: remove _not_found_error default (E5)

**File**: `src/oci_runtime/adapters/managers/base.py:19`

Remove `_not_found_error: type[OciError] = OciError`. Subclasses MUST set it. If forgotten, `AttributeError` is raised on first `_check_result` call — explicit failure.

Keep `_generic_error = ContainerRuntimeError` as the default (only ContainerManager relies on it by default; the others override it).

### 3.15 — Factor list() into CliBaseManager (E12)

**File**: `src/oci_runtime/adapters/managers/base.py`

Add a `_list` helper:

```python
def _execute_list(
    self,
    entity_type: str,
    subcommand: list[str],
    show_all: bool = False,
    filters: dict[str, str] | None = None,
) -> list:
    cmd = [self._transport.get_runtime_binary()] + subcommand
    cmd.extend(self._caps.list_format_flags)
    if show_all:
        cmd.append("-a")
    if filters:
        for key, val in filters.items():
            cmd.extend(["--filter", f"{key}={val}"])
    result = self._transport.execute(cmd)
    self._check_result(result, cmd, operation=f"list {entity_type}", entity="")
    return self._parser.parse_list(self._decode_bytes(result.stdout))
```

Each manager's `list()` becomes:

```python
# Container
def list(self, show_all=False, filters=None):
    return self._execute_list("containers", ["container", "list"], show_all, filters)

# Image
def list(self, filters=None):
    return self._execute_list("images", ["image", "list"], filters=filters)

# Volume
def list(self, filters=None):
    return self._execute_list("volumes", ["volume", "list"], filters=filters)

# Network
def list(self, filters=None):
    return self._execute_list("networks", ["network", "list"], filters=filters)
```

### 3.16 — Fix CliImageManager.build(): reorder flags before positional (B3)

**Prototype**: `RecordingTransport` + `BuildContext(build_file_content="FROM alpine", build_args={"A":"1"}, labels={"L":"v"}, pull=True)` produced command: `['docker','build','-t','myimg','-','--quiet','--build-arg','A=1','--label','L=v','--pull']`. Flags `--quiet`, `--build-arg`, `--label`, `--pull` all appear AFTER positional `-`. Cross-runtime analysis: docker/podman/nerdctl use cobra (position-agnostic, but undocumented); buildah uses a different CLI framework (may not tolerate flags after positional). Fix is runtime-agnostic: all flags before positional works everywhere.

**File**: `src/oci_runtime/adapters/managers/image.py:21-59`

Move the positional context arg to AFTER all flag extensions:

```python
def build(self, context: BuildContext, image_name: str, timeout: int = 600) -> str:
    cmd = [self._transport.get_runtime_binary(), "build", "-t", image_name]
    input_data = None

    # Determine the positional context arg and -f flag
    if context.build_file_path is not None:
        cmd.extend(["-f", str(context.build_file_path)])
        context_arg = str(context.context_path or context.build_file_path.parent)
    elif context.context_path is not None:
        cmd.extend(["-f", "-"])
        cmd.append(str(context.context_path))
        input_data = context.build_file_content.encode("utf-8")
        context_arg = None  # already appended above
    else:
        input_data = create_build_tar(context.build_file_content, context.files, self._caps.tar_entry_name)
        context_arg = "-"

    # ALL flags before the positional
    cmd.extend(self._caps.default_build_flags)
    if context.no_cache:
        cmd.append("--no-cache")
    if context.target:
        cmd.extend(["--target", context.target])
    for k, v in context.build_args.items():
        cmd.extend(["--build-arg", f"{k}={v}"])
    for k, v in context.labels.items():
        cmd.extend(["--label", f"{k}={v}"])
    if context.pull:
        cmd.append("--pull")
    if not context.rm:
        cmd.extend(["--rm", "false"])
    if context.network:
        cmd.extend(["--network", context.network])
    for k, v in context.build_contexts.items():
        cmd.extend(["--build-context", f"{k}={v}"])

    # Positional context arg LAST (after all flags)
    if context_arg is not None:
        cmd.append(context_arg)

    result = self._transport.execute(cmd, input_data=input_data, timeout=timeout)
    # ... rest unchanged
```

### 3.17 — Fix CliImageManager: rename parse_id_from_pull (E17)

**File**: `src/oci_runtime/adapters/managers/image.py:75`

Change `self._parser.parse_id_from_pull(...)` → `self._parser.parse_digest_from_pull(...)`.

### 3.18 — Fix DockerImageParser: RepoTags null (B1)

**Prototype**: `DockerImageParser().parse_inspect('{"Id":"sha256:abc","RepoTags":null,"Size":100}')` → `ImageInfo(tags=None)`. Iterating `info.tags` crashes: `TypeError: 'NoneType' object is not iterable`. `item.get("RepoTags", [])` returns `None` (key exists with null value, default not used). Fix: `(item.get("RepoTags") or [])`.

**File**: `src/oci_runtime/adapters/parser/docker.py:67`

Change:
```python
tags=item.get("RepoTags", []),
```
To:
```python
tags=(item.get("RepoTags") or []),
```

### 3.19 — Fix DockerImageParser: remove pull-access-denied from not-found, add auth patterns (B7)

**Prototype**: `DockerImageParser().is_not_found_error("pull access denied for xyz")` → `True`. `CliImageManager.pull("nonexistent-xyz")` with stderr `"pull access denied..."` → raises `ImageNotFoundError` (confirmed: a registry permission failure misclassified as not-found). The `_not_found_patterns` tuple `("no such image", "pull access denied")` is the root cause.

**File**: `src/oci_runtime/adapters/parser/docker.py:61`

Change:
```python
_not_found_patterns = ("no such image", "pull access denied")
```
To:
```python
_not_found_patterns = ("no such image",)
_auth_error_patterns = ("pull access denied", "unauthorized", "authentication required")
```

Add method:
```python
def is_auth_error(self, stderr: str) -> bool:
    lower = stderr.lower()
    return any(
        re.search(rf'\b{re.escape(p)}\b', lower)
        for p in self._auth_error_patterns
    )
```

Add `is_auth_error` to the `ImageParser` ABC in `ports/parsers.py`.

**Update** `CliBaseManager._check_result` — check auth patterns BEFORE not-found patterns for image managers. Or: add a `_check_auth_error` method that image managers call before `_check_result`. The cleanest approach: add an optional `_auth_error` class variable to `CliBaseManager` and check it in `_check_result`:

```python
class CliBaseManager(Generic[P]):
    _not_found_error: type[OciError]  # required, no default (E5)
    _generic_error: type[OciError] = ContainerRuntimeError
    _auth_error: type[OciError] | None = None  # only ImageManager sets this

    def _check_result(self, result, cmd, *, operation, entity, not_found=None):
        if result.returncode == 0:
            return
        stderr_str = result.stderr.decode("utf-8", errors="replace")
        
        # Check auth error FIRST (before not-found)
        if self._auth_error is not None and hasattr(self._parser, 'is_auth_error'):
            if self._parser.is_auth_error(stderr_str):
                raise self._auth_error(entity)
        
        # Then not-found
        if not_found is None:
            not_found = self._not_found_error
        if self._parser.is_not_found_error(stderr_str):
            raise not_found(entity)
        
        # Then generic
        raise self._generic_error(...)
```

`CliImageManager` sets `_auth_error = ImagePullAccessDeniedError`.

### 3.20 — Fix DockerContainerParser: state/status from correct fields (B8)

**Prototype**: `DockerContainerParser().parse_inspect(...)` with `State.Status="running"` → `state=RUNNING, status="running"` (identical). `parse_list(...)` with `State="running", Status="Up 2 minutes"` → `state=RUNNING, status="Up 2 minutes"` (different). The parser correctly extracts from different JSON fields in each case. The "inconsistency" is in the source JSON shape (inspect has no human-readable status, list does), not the parser. **Document, don't fix.**

**File**: `src/oci_runtime/adapters/parser/docker.py:30-31`

The investigation showed `parse_inspect` sets both `state` and `status` from `State.Status` — this is correct because Docker's inspect JSON has `State.Status` (e.g. "running") but no human-readable status string. `parse_list` uses `State` (enum key) and `Status` (human string) from the `ps` output, which is a different JSON shape. **Document** this difference in the parser docstring — no code change needed.

### 3.21 — Fix DockerContainerParser: _parse_docker_ports_from_list port 0 (B13)

**File**: `src/oci_runtime/adapters/parser/docker.py:207-216`

Import `_safe_int` from `base.py`. Change:

```python
def _parse_docker_ports_from_list(item: dict) -> list[PortMapping]:
    ports = []
    for p in item.get("Ports", []):
        host_ip = p.get("HostIp") or None  # None instead of "0.0.0.0" (E2)
        cport = _safe_int(p.get("PrivatePort"))
        if cport is None:
            continue
        ports.append(PortMapping(
            container_port=cport,
            host_port=_safe_int(p.get("PublicPort")),
            protocol=p.get("Type", "tcp"),
            host_ip=host_ip,
        ))
    return ports
```

### 3.22 — Fix DockerImageParser.parse_build_output: validate hex (C4)

**Prototype**: `DockerImageParser().parse_build_output("Step 1/3 : FROM alpine\nStep 2/3 : RUN echo hello\n...")` → `"sha256:Step 1/3 : FROM alpine\n..."` — entire build log prefixed with `sha256:`. Same for failed build output. The `--quiet` capability is the only thing preventing this in production, but if `--quiet` isn't honored or build fails mid-output, the result is garbage. Fix: validate `sha256:[a-f0-9]{12,64}` after prefixing.

**File**: `src/oci_runtime/adapters/parser/docker.py:99-103`

```python
def parse_build_output(self, raw: str) -> str:
    output = raw.strip()
    if output.startswith("sha256:"):
        output = output
    else:
        output = f"sha256:{output}"
    # Validate
    if not re.match(r"^sha256:[a-f0-9]{12,64}$", output):
        raise ParsingError(raw=raw, message=f"Build output is not a valid image id: {output[:100]!r}")
    return output
```

Same fix for `PodmanImageParser.parse_build_output` (`podman.py:150-154`).

### 3.23 — Fix DockerImageParser.parse_digest_from_pull: return '' on no match (C5+E17)

**Prototype**: `PodmanImageParser().parse_id_from_pull("Trying to pull...\ntimeout\n")` → returns `"timeout"` (the raw line) as the image id. `DockerImageParser().parse_id_from_pull(...)` → returns `""` on no match. Inconsistent contract. Fix: Podman returns `""` on no match, matching Docker.

**File**: `src/oci_runtime/adapters/parser/docker.py:105-117`

Rename to `parse_digest_from_pull`. Already returns `""` on no match — no behavior change, just the rename.

**File**: `src/oci_runtime/adapters/parser/podman.py:156-170`

Rename to `parse_digest_from_pull`. Change the fallback: instead of returning the raw line (line 169), return `""`:

```python
def parse_digest_from_pull(self, raw: str) -> str:
    lines = raw.strip().split('\n')
    for line in reversed(lines):
        line = line.strip()
        if line and not line.startswith('Trying') and not line.startswith('Getting'):
            if 'sha256:' in line:
                match = re.search(r"sha256:([a-f0-9]+)", line)
                if match:
                    return f"sha256:{match.group(1)}"
            if not line.startswith('Error') and not line.startswith('Warning'):
                if re.match(r'^[a-f0-9]{12,64}$', line):
                    return f"sha256:{line}"
    return ""  # was: return line (C5 fix)
```

### 3.24 — Fix PodmanContainerParser: unbound ports (B5)

**Prototype**: `PodmanContainerParser().parse_inspect('{"NetworkSettings":{"Ports":{"8080/tcp":null}}}')` → `ports=[]` (0 ports). `DockerContainerParser().parse_inspect(same)` → `ports=[PortMapping(8080, None, tcp, 0.0.0.0)]` (1 port, unbound kept). Parity bug: same container, different port sets across runtimes. Fix: Podman keeps unbound ports like Docker.

**File**: `src/oci_runtime/adapters/parser/podman.py:24-52`

Add handling for unbound ports (no host binding):

```python
def _parse_ports(self, network_settings: dict) -> list[PortMapping]:
    ports = []
    ports_dict = network_settings.get("Ports", {})
    if not isinstance(ports_dict, dict):
        return ports
    for port_spec, mappings in ports_dict.items():
        try:
            container_port, protocol = port_spec.split("/")
            container_port = int(container_port)
            if isinstance(mappings, list) and mappings:
                for mapping in mappings:
                    if isinstance(mapping, dict):
                        host_port = mapping.get("HostPort")
                        host_ip = mapping.get("HostIp") or None
                        if host_port:
                            ports.append(PortMapping(
                                container_port=container_port,
                                host_port=int(host_port),
                                protocol=protocol,
                                host_ip=host_ip,
                            ))
                        else:
                            # Unbound port — keep it (parity with Docker)
                            ports.append(PortMapping(
                                container_port=container_port,
                                host_port=None,
                                protocol=protocol,
                                host_ip=None,
                            ))
            elif mappings is None:
                # Unbound port (no host binding) — keep it (parity with Docker)
                ports.append(PortMapping(
                    container_port=container_port,
                    host_port=None,
                    protocol=protocol,
                    host_ip=None,
                ))
        except (ValueError, AttributeError):
            continue
    return ports
```

### 3.25 — Fix PodmanContainerParser: string Names (B6)

**Prototype**: `PodmanContainerParser().parse_list('[{"Names":"mycontainer",...}]')` → `ParsingError: Container list entry missing 'Names' field`. `DockerContainerParser().parse_list(same)` → works (coerces string to `[string]` at line 43-44). Parity bug. Fix: Podman coerces string Names like Docker.

**File**: `src/oci_runtime/adapters/parser/podman.py:96-113`

Add string coercion (parity with Docker parser):

```python
def parse_list(self, raw: str) -> list[ContainerInfo]:
    data = self._parse_json_list(raw)
    result = []
    for item in data:
        names = item.get("Names")
        if isinstance(names, str):
            names = [names]  # coerce string to list (parity with Docker)
        if not names or not isinstance(names, list):
            raise ParsingError(raw=raw, message="Container list entry missing 'Names' field")
        # ... rest unchanged
```

### 3.26 — Fix BaseCliParser._parse_json_list: scalar guard + empty NDJSON (C6+C7)

**Prototype**: `_parse_json_list('123')` → `[123]`, `('"hello"')` → `['hello']`, `('null')` → `[None]`, `('true')` → `[True]` — all scalars silently wrapped. `_parse_json_list('')` → `ParsingError`, `('[]')` → `[]` — inconsistent empty-result handling. Fix: raise on non-list/non-dict scalars, return `[]` for empty NDJSON.

**File**: `src/oci_runtime/adapters/parser/base.py:43-69`

```python
def _parse_json_list(self, raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        pass
    else:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return [data]
        raise ParsingError(raw=raw, message=f"Expected list or dict, got {type(data).__name__}")

    # NDJSON fallback
    lines = raw.strip().split("\n")
    items: list[dict] = []
    for i, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except json.JSONDecodeError:
            raise ParsingError(raw=raw, message=f"Invalid JSON on line {i}: {line[:200]}")
    # Empty NDJSON -> [] (consistent with empty JSON array)
    return items
```

Changes: (1) raise on non-list/non-dict scalar, (2) return `items` (empty list) instead of raising on empty NDJSON.

### 3.27 — Fix create_build_tar: validate paths (C8)

**Prototype**: `create_build_tar("FROM alpine", {"../../etc/passwd": b"secret", "/abs/path": b"x"})` → tar contains entries `'../../etc/passwd'` and `'/abs/path'` unvalidated. Path traversal confirmed. Fix: reject paths that are absolute or contain `..` after normalization.

**File**: `src/oci_runtime/adapters/_tar.py`

```python
def create_build_tar(
    build_file_content: str,
    files: dict[str, bytes],
    tar_entry_name: str = "Dockerfile",
) -> bytes:
    tar_buffer = io.BytesIO()
    with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
        _add_tar_entry(tar, tar_entry_name, build_file_content.encode("utf-8"))
        for path, data in files.items():
            # Validate path safety
            normalized = os.path.normpath(path)
            if os.path.isabs(normalized) or normalized.startswith(".."):
                raise ValueError(
                    f"create_build_tar: unsafe path {path!r} — "
                    f"must be relative and within the tar root"
                )
            _add_tar_entry(tar, path, data)
    return tar_buffer.getvalue()


def _add_tar_entry(tar, name, content):
    info = tarfile.TarInfo(name=name)
    info.size = len(content)
    info.uid = 0
    info.gid = 0
    info.mtime = 0
    tar.addfile(info, io.BytesIO(content))
```

Add `import os` at the top.

### 3.28 — Fix DeadlineCancellationToken: add __del__ (C9)

**Prototype**: `DeadlineCancellationToken(999.0)` created, then `del token` + `gc.collect()` + `weakref.ref(token._timer)` → timer thread still alive. No `__del__` to cancel it. The timer is daemon (doesn't block exit) but lingers as a resource leak. Fix: `__del__` calls `self._timer.cancel()`.

**File**: `src/oci_runtime/adapters/_cancellation.py:34-42`

```python
class DeadlineCancellationToken(CancellationToken):
    def __init__(self, timeout: float) -> None:
        self._event = threading.Event()
        self._timer = threading.Timer(timeout, self._event.set)
        self._timer.daemon = True
        self._timer.start()

    def __del__(self) -> None:
        self._timer.cancel()

    # ... rest unchanged
```

### 3.29 — Fix parse_size_to_bytes: add P/E units, fix regex (E11)

**Prototype**: `parse_size_to_bytes('.5GB')` → `ValueError` (regex `\d+\.?\d*` rejects leading-dot floats). `parse_size_to_bytes('1PB')` → `ValueError` (unit not in dict). `parse_size_to_bytes('1EB')` → `ValueError` (unit not in dict). Fix: regex `\d*\.?\d+` accepts `.5GB`, add P/PB/PIB and E/EB/EIB units.

**File**: `src/oci_runtime/adapters/_utils.py`

```python
def parse_size_to_bytes(size_str: str) -> int:
    units = {
        'B': 1,
        'K': 1024, 'KB': 1024, 'KIB': 1024,
        'M': 1024**2, 'MB': 1024**2, 'MIB': 1024**2,
        'G': 1024**3, 'GB': 1024**3, 'GIB': 1024**3,
        'T': 1024**4, 'TB': 1024**4, 'TIB': 1024**4,
        'P': 1024**5, 'PB': 1024**5, 'PIB': 1024**5,
        'E': 1024**6, 'EB': 1024**6, 'EIB': 1024**6,
    }
    match = re.fullmatch(r"(\d*\.?\d+)\s*([a-zA-Z]+)", size_str.upper())
    if not match:
        raise ValueError(f"Cannot parse size string: {size_str!r}")
    number, unit = match.groups()
    if unit not in units:
        raise ValueError(f"Unknown size unit: {unit!r} in {size_str!r}")
    return int(float(number) * units[unit])
```

Changes: (1) add P/PB/PIB and E/EB/EIB, (2) regex `\d*\.?\d+` accepts `.5GB`, (3) consolidated unit dict (no redundant entries, aliases map to same value).

### 3.30 — Fix run_pty: delete old function

**File**: `src/oci_runtime/adapters/managers/pty.py`

Delete the entire file. Its functionality is replaced by `CliPtyTransport` (3.6). The `run_pty` function is no longer called by `CliContainerManager` (which now uses `PtyTransport` port).

**Update** `adapters/managers/__init__.py` if it references `pty.py`.

### 3.31 — Update factory: inject BinaryResolver, PtyTransport (A5+A6+D8)

**File**: `src/oci_runtime/factory.py`

Add to `RuntimeFactoryConfig`:

```python
binary_resolver_factory: Callable[[], BinaryResolver] | None = None
pty_transport_factory: Callable[[BinaryResolver], PtyTransport] | None = None
```

Add to `_resolve_config`:

```python
if cfg.binary_resolver_factory is None:
    from oci_runtime.adapters.binary import CliBinaryResolver
    replacements["binary_resolver_factory"] = lambda: CliBinaryResolver()
if cfg.pty_transport_factory is None:
    from oci_runtime.adapters.transport.pty import CliPtyTransport
    replacements["pty_transport_factory"] = lambda resolver: CliPtyTransport(resolver)
```

Update `RuntimeFactory.create()`:

```python
binary_resolver = self._cfg.binary_resolver_factory()
transport = self._cfg.transport_factory(binary, binary_resolver=binary_resolver)
streaming_transport = self._cfg.streaming_transport_factory(binary, binary_resolver=binary_resolver)
pty_transport = self._cfg.pty_transport_factory(binary_resolver)
# ... pass pty_transport to provider.create_managers
```

Update `_default_transport_factory` and `_default_streaming_transport_factory` to accept `binary_resolver` parameter.

### 3.32 — Update provider: pass PtyTransport to container manager (D8)

**File**: `src/oci_runtime/adapters/provider/_base.py`

Update `create_managers` to accept and pass `pty_transport`:

```python
def create_managers(
    self, transport, streaming_transport, caps, *,
    tty_detector_factory, output_stream_factory,
    cancellation_factory, pty_transport,
) -> Managers:
    # ...
    container_manager=CliContainerManager(
        transport, parsers.container_parser, caps,
        streaming=streaming_transport,
        tty_detector=tty_detector_factory(),
        pty_transport=pty_transport,
        cancellation_factory=cancellation_factory,
        output_stream=output_stream_factory(),
    ),
```

Update `ports/provider.py` ABC to add `pty_transport` parameter.

### 3.33 — Keep dead __init__ overrides (E4)

**No change**. `CliImageManager`, `CliVolumeManager`, `CliNetworkManager` keep their explicit `__init__` for readability, even though they only call `super().__init__()`.

---

## Phase 4: Tests, Docs, Format

### 4.1 — Fix test_known_bugs.py docstring (D1)

**File**: `tests/audit/test_known_bugs.py:1-18`

Rewrite the module docstring:

```python
"""Regression tests for bugs found in the audit.

These tests WERE marked xfail(strict=True) to document known bugs.
All bugs were fixed in commit 15f6238 (guardrail remediation).
The xfail markers were removed, and these tests now PASS as
regression guards — if a bug is reintroduced, the test fails.

The cycle of "audit finds bugs → mark tasks complete → bugs persist
→ re-audit" is broken because these tests run on every pytest
invocation, not just during audits.
"""
```

### 4.2 — Fix conformance test: remove runtime xfail, fix parser (B12+D7)

**Prototype**: `pytest tests/conformance/test_parser_conformance.py::TestContainerListConformance -v` → 4/4 PASS. The `try/except Exception: pytest.xfail(...)` at line 152-155 never triggers (parser was already fixed in commit `15f6238`). The f-string at line 155 contains `test_{{runtime}}_` — escaped braces print literally as `{runtime}` instead of the runtime name. The xfail is dead code. Fix: remove the try/except wrapper, fix the f-string, let the test assert directly.

**File**: `tests/conformance/test_parser_conformance.py:148-157`

1. Investigate why `parse_list` crashes on real captured fixtures (run the test to see the error)
2. Fix the parser bug
3. Remove the `try/except Exception: pytest.xfail(...)` wrapper
4. Fix the f-string brace escape: `test_{{runtime}}_` → `test_{runtime}_`
5. Rewrite the module docstring (D7) to remove the xfail(strict=True) claim

### 4.3 — Document F15-F42, add missing test reproductions (D3)

**File**: `docs/ARCHITECTURE.md:357-359`

Update the remediation log to list what F15-F42 actually were (from commit `15f6238` message). Add audit-test reproductions for mechanically-verifiable fixes that don't have them yet (F10, F15-F21, F30, F34, F36, F12).

**File**: `tests/audit/test_known_bugs.py` — add test classes for F10, F15-F21, F30, F34, F36, F12 if they don't already have coverage.

### 4.4 — Remove dead Makefile target (D4)

**File**: `Makefile:6-8`

Remove the `test-all` target (or remove only the e2e line):

```makefile
# Before:
test-all: test
	@echo "Running e2e tests..."
	@bash tests/e2e/run-e2e-tests.sh

# After:
test-all: test
	@echo "All tests complete."
```

### 4.5 — Add dev dependency group (D5)

**File**: `pyproject.toml`

Add after `[project]`:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-cov>=7.0",
    "ruff>=0.15",
]
```

### 4.6 — Update ARCHITECTURE.md (D2+D6+D8)

**File**: `docs/ARCHITECTURE.md`

- D2: Add `cancellation_factory` to `create_managers()` signature block (line 302-313)
- D2: Add `binary_resolver` and `pty_transport` to factory config and signatures
- D6: Update line 343 to state ALL domain dataclasses are `frozen=True`
- D6: Remove the selective "RuntimeCapabilities list fields are tuple" note (redundant after full freeze)
- D8: Add documentation for the PTY branch: "Both TTY and non-TTY branches call `_check_result` with `not_found=ImageNotFoundError`. `PtyTransport` uses `stderr=subprocess.PIPE` to keep docker CLI errors separate from container PTY output, enabling uniform error classification."
- A1: Update Module Structure to show `CancellationToken` in `ports/cancellation.py`
- A2: Update Module Structure to show `RuntimeCapabilities` in `ports/capabilities.py`
- A5+A6: Add `BinaryResolver` port and `CliBinaryResolver` adapter to Module Structure
- D8: Add `PtyTransport` port and `CliPtyTransport` adapter to Module Structure
- E17: Rename `parse_id_from_pull` to `parse_digest_from_pull` in all references
- B7: Add `ImagePullAccessDeniedError` to the exception hierarchy tree

### 4.7 — Run ruff format on all source files (E8)

```bash
uv run ruff format src/
```

This formats all 28 files that are currently unformatted.

### 4.8 — Add format-check to Makefile (E8)

**File**: `Makefile`

```makefile
check: lint format-check test

format-check:
	@uv run ruff format --check src/
```

### 4.9 — Clean stale caches (E14)

```bash
make clean
```

Remove `__pycache__`, `.ruff_cache`, `.pytest_cache` directories. The orphaned `test_domain_init.pyc` is removed.

### 4.10 — Update tests for all changes

**Test files to update** (non-exhaustive — each change may require test updates):

- `tests/unit/domain/test_types.py` — frozen behavior, RunConfig.timeout, PortMapping.host_ip required, VolumeMount.source Optional
- `tests/unit/domain/test_exceptions.py` — ImagePullAccessDeniedError
- `tests/unit/domain/test_capabilities.py` — move to `tests/unit/ports/test_capabilities.py` after A2 relocation
- `tests/unit/ports/` — new test files for BinaryResolver, PtyTransport, CancellationToken (relocated)
- `tests/unit/adapters/test_cli_transport.py` — BinaryResolver injection, CancellationToken, B2 timeout fix
- `tests/unit/adapters/test_cli_streaming_transport.py` — BinaryResolver injection, C2 double timeout fix
- `tests/unit/adapters/test_cli_container_manager.py` — PtyTransport injection, D8 error classification, B4 logs errors, B10 timeout, A4 no fallback
- `tests/unit/adapters/test_cli_image_manager.py` — B3 flag ordering, E17 rename, B7 auth error
- `tests/unit/adapters/test_cli_pty.py` — replace with test_cli_pty_transport.py (PtyTransport port)
- `tests/unit/adapters/test_docker_parser.py` — B1 RepoTags null, B7 auth patterns, B13 port 0, C4 hex validation, E17 rename
- `tests/unit/adapters/test_podman_parser.py` — B5 unbound ports, B6 string Names, C5 return '', E17 rename
- `tests/unit/adapters/test_parser_base.py` — C6 scalar guard, C7 empty NDJSON
- `tests/unit/adapters/test_cancellation.py` — C9 __del__
- `tests/unit/adapters/test_factory.py` — BinaryResolver, PtyTransport injection
- `tests/unit/adapters/test_providers.py` — PtyTransport parameter
- `tests/unit/contract/test_public_api.py` — new exports (BinaryResolver, PtyTransport, ImagePullAccessDeniedError, CancellationToken from ports)
- `tests/unit/contract/test_interface_compliance.py` — new ports
- `tests/unit/wiring/` — update all wiring tests for new constructor signatures
- `tests/helpers/mock_transport.py` — add cancel_token to RecordingTransport.execute, create MockPtyTransport
- `tests/architecture/test_layering.py` — verify new ports/adapters pass layering rules
- `tests/audit/test_known_bugs.py` — D1 docstring rewrite, D3 add missing F15-F42 reproductions
- `tests/conformance/test_parser_conformance.py` — B12 remove runtime xfail, D7 docstring rewrite

### 4.11 — Run architecture test after every phase

```bash
uv run pytest tests/architecture/ -v
```

Verify no layering violations are introduced by the relocations and new ports.

---

## Validation

After all phases:

```bash
# Lint
uv run ruff check src/
uv run ruff format --check src/

# Tests
uv run pytest tests/ -v

# Architecture
uv run pytest tests/architecture/ -v

# Conformance
uv run pytest tests/conformance/ -v

# Audit
uv run pytest tests/audit/ -v
```

**Expected**: all tests pass, 0 xfailed, ruff clean, format clean, architecture clean.

---

## Issue Index

| ID | Category | Phase | Status |
|----|----------|-------|--------|
| A1 | Architecture | 2.1 | CancellationToken → ports/ |
| A2 | Architecture | 2.2 | RuntimeCapabilities → ports/ |
| A3 | Architecture | 3.6 | run_pty returns RawExecResult (via PtyTransport) |
| A4 | Architecture | 3.8 | Remove ThreadCancellationToken fallback |
| A5 | Architecture | 3.1-3.2 | probe() uses BinaryResolver |
| A6 | Architecture | 3.1-3.4 | Shared BinaryResolver port+adapter |
| A7 | Docs | 4.1 | Stale audit-test docstring (obvious fix) |
| B1 | Bug | 3.18 | RepoTags null → [] |
| B2 | Bug | 3.3 | execute() timeout → OperationTimeoutError |
| B3 | Bug | 3.16 | Build flags before positional |
| B4 | Bug | 3.11 | logs() errors in finally |
| B5 | Bug | 3.24 | Podman unbound ports |
| B6 | Bug | 3.25 | Podman string Names |
| B7 | Bug | 1.5, 3.19 | ImagePullAccessDeniedError |
| B8 | Bug | 3.20 | Document inspect vs list difference |
| B9 | Bug | 3.7 | os.read(fd, n) in ProcessPipeReader |
| B10 | Bug | 1.4, 2.5, 3.3, 3.10 | Timeout wiring (full CancellationToken unification) |
| B11 | Bug | 3.6 | run_pty → PtyTransport with timeout |
| B12 | Bug | 4.2 | Fix parser, remove runtime xfail |
| B13 | Bug | 3.21 | _safe_int for port 0 |
| C1 | Smell | 3.6 | run_pty uses BinaryResolver |
| C2 | Smell | 3.5 | Remove double timeout in streaming |
| C3 | Smell | — | Keep merged logs, document (no change) |
| C4 | Smell | 3.22 | Validate hex in parse_build_output |
| C5 | Smell | 3.23 | Podman parse_digest returns '' |
| C6 | Smell | 3.26 | _parse_json_list scalar guard |
| C7 | Smell | 3.26 | Empty NDJSON returns [] |
| C8 | Smell | 3.27 | Tar path validation |
| C9 | Smell | 3.28 | DeadlineCancellationToken __del__ |
| D1 | Docs | 4.1 | Rewrite audit-test docstring |
| D2 | Docs | 4.6 | Add cancellation_factory to signature block |
| D3 | Docs | 4.3 | Document F15-F42 |
| D4 | Docs | 4.4 | Remove dead Makefile target |
| D5 | Docs | 4.5 | Add [dependency-groups] dev |
| D6 | Docs | 4.6 | Update immutability narrative |
| D7 | Docs | 4.2 | Rewrite conformance docstring |
| D8 | Architecture | 3.6-3.9 | Full PtyTransport port + adapter |
| E1 | Smell | 1.1 | Freeze all value objects |
| E2 | Smell | 1.2 | PortMapping.host_ip required |
| E3 | Smell | 1.3 | VolumeMount.source Optional |
| E4 | Smell | 3.33 | Keep dead __init__ (no change) |
| E5 | Smell | 3.14 | Remove _not_found_error default |
| E6 | Smell | 3.13 | Set _generic_error explicitly |
| E7 | Smell | 4.7 | Format fixes __init__ line length |
| E8 | Smell | 4.7-4.8 | Format all + add format-check to CI |
| E9 | Smell | 2.8 | collections.abc.Callable everywhere |
| E10 | Smell | 1.7 | default=() for tuple fields |
| E11 | Smell | 3.29 | Add P/E units, fix regex |
| E12 | Smell | 3.15 | Factor list() into CliBaseManager |
| E13 | Smell | 4.7 | Format fixes formatting (E8) |
| E14 | Smell | 4.9 | Clean stale caches |
| E15 | Smell | 3.12 | list[Exception] annotation |
| E16 | Smell | 3.12 | Extract _LOGS_JOIN_TIMEOUT constant |
| E17 | Smell | 2.7, 3.17 | Rename parse_digest_from_pull |
