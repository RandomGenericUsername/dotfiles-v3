# oci-runtime — Architecture & Decisions

## Module Structure

```
oci-runtime/                    # Runtime-agnostic OCI container management
├── pyproject.toml
├── docs/ARCHITECTURE.md        # This file
├── src/oci_runtime/
│   ├── __init__.py             # Public API re-exports
│   ├── factory.py              # RuntimeFactory + RuntimeFactoryConfig
│   ├── domain/                 # Pure domain layer (no I/O, no adapter imports)
│   │   ├── __init__.py
│   │   ├── enums.py            # RuntimeKind, ContainerState, RestartPolicy, NetworkMode, VolumeMountType
│   │   ├── exceptions.py       # OciError hierarchy (ImageError siblings to ContainerError)
│   │   └── types.py            # Value objects: RunConfig, ContainerInfo, ExecResult, RawExecResult,
│   │                           #   CancellationToken (ABC), PruneResult, VolumeMount, PortMapping, etc.
│   ├── ports/                  # Port interfaces + contract exceptions + aggregate types
│   │   ├── __init__.py         # Re-exports all public port types
│   │   ├── engine.py           # ContainerEngine ABC
│   │   ├── transport.py        # Transport ABC (batch execution only)
│   │   ├── streaming.py        # StreamingTransport ABC (real-time output streaming)
│   │   ├── capabilities.py     # RuntimeCapabilities
│   │   ├── discovery.py        # RuntimeDiscovery ABC
│   │   ├── provider.py         # RuntimeProvider ABC
│   │   ├── managers.py         # ImageManager, ContainerManager, VolumeManager, NetworkManager ABCs
│   │   ├── parsers.py          # ContainerParser, ImageParser, VolumeParser, NetworkParser ABCs + ParsingError
│   │   ├── tty.py              # TtyDetector ABC
│   │   ├── output_stream.py    # OutputStream ABC
│   │   └── aggregates.py       # Parsers, Managers (port-level return types)
│   └── adapters/               # Adapter implementations
│       ├── _cancellation.py    # ThreadCancellationToken, DeadlineCancellationToken, CompositeCancellationToken
│       ├── _process_reader.py  # ProcessPipeReader (selector-based pipe reading)
│       ├── _tar.py             # create_build_tar (tar archive builder)
│       ├── _utils.py           # parse_size_to_bytes (size string parser)
│       ├── tty.py              # StdoutTtyDetector
│       ├── output_stream.py    # StdoutBufferStream
│       ├── engine/cli.py       # CliRuntime
│       ├── transport/
│       │   ├── cli.py          # CliTransport (batch subprocess.run)
│       │   └── streaming.py    # CliStreamingTransport (Popen + ProcessPipeReader)
│       ├── discovery/cli.py    # CliRuntimeDiscovery
│       ├── provider/
│       │   ├── _base.py        # BaseCliRuntimeProvider
│       │   ├── docker.py       # DockerRuntimeProvider
│       │   └── podman.py       # PodmanRuntimeProvider
│       ├── parser/
│       │   ├── base.py         # BaseCliParser
│       │   ├── docker.py       # Docker*Parser classes
│       │   └── podman.py       # Podman*Parser classes
│       └── managers/
│           ├── base.py         # CliBaseManager[P]
│           ├── container.py    # CliContainerManager
│           ├── image.py        # CliImageManager
│           ├── volume.py       # CliVolumeManager
│           ├── network.py      # CliNetworkManager
│           └── pty.py          # run_pty (PTY process execution)
└── tests/                      # Unit + contract + wiring + integration tests
```

## Architecture Decisions

### Domain Layer — Pure, I/O-Free

The domain layer contains no imports of `sys`, `io`, `threading`, or any adapter-level module.

- **`CancellationToken` is an ABC, not a concrete class** — the domain only defines the interface. The concrete `ThreadCancellationToken` (backed by `threading.Event`) lives in `adapters/_cancellation.py`. This guarantees thread-safety without requiring GIL-dependent behavior. (#2.1)

- **`PruneResult` replaces `dict[str, int]`** — all `prune()` methods now return a `PruneResult(deleted=..., reclaimed_bytes=...)` frozen dataclass instead of a magic-key dict. (#2.5)

- **`VolumeMountType(StrEnum)` replaces `str`** — `VolumeMount.type` is now a `StrEnum` with `BIND`, `VOLUME`, `TMPFS` members. `__post_init__` coerces string values. (#2.6)

- **`RunConfig` validates limits** — `memory_limit` and `cpu_limit` are validated in `__post_init__` against regex patterns. (#2.7)

### Exception Hierarchy

`ParsingError` now inherits from `OciError`, so `except OciError:` catches all module-level exceptions. (#2.3)

```
OciError (base)
├── ParsingError              ← formerly Exception
├── ContainerError
│   ├── ContainerNotFoundError
│   └── ContainerRuntimeError
├── ImageError
│   └── ImageNotFoundError
├── VolumeError
│   └── VolumeNotFoundError
├── NetworkError
│   └── NetworkNotFoundError
└── RuntimeNotAvailableError
```

### Port Layer

**`TtyDetector` port** — `ports/tty.py` defines an ABC with a single `is_tty() -> bool` method. `CliContainerManager` takes a `TtyDetector` (required, no default, no `Optional`). `StdoutTtyDetector` in `adapters/tty.py` implements it via `sys.stdout.isatty()`. Tests inject `FakeTtyDetector(is_tty=True/False)`. (#1.1, #2.2)

**`OutputStream` port** — `ports/output_stream.py` defines an ABC with `write(bytes) -> int` and `flush()`. `run_pty()` accepts `OutputStream | None`. `StdoutBufferStream` in `adapters/output_stream.py` wraps `sys.stdout.buffer`. Tests inject a `BytesOutputStream`. (#1.8)

### Adapter Layer

**Composable cancellation** — `CliStreamingTransport.stream()` creates a `DeadlineCancellationToken` when `timeout` is set, and composes it with any user-provided `cancel_token` via `CompositeCancellationToken`. The reader loop checks cancellation; on timeout, `subprocess.TimeoutExpired` is raised. ProcessPipeReader is untouched — it only checks `is_cancelled`. (#1.6)

**`_check_result` class variable** — each manager sets `_not_found_error` once at the class level (`ContainerNotFoundError`, `ImageNotFoundError`, etc.). The `not_found=` kwarg is dropped from 26/27 call sites; only `CliContainerManager.run()` keeps the explicit override (`ImageNotFoundError`). (#1.7)

**`RuntimeFactory.create()` no longer probes** — availability checking (`is_available()`) is the caller's responsibility. The factory purely composes the object graph. (#1.5)

**`VolumeMountType` dispatched in adapter** — `TMPFS` mounts produce `--mount type=tmpfs,target=...` instead of the broken `-v :/tmp`. `BIND` and `VOLUME` use the existing `-v` format. (#2.6)

**`RecordingTransport` uses tuple keys** — response keys are `tuple[str, ...]` instead of `" ".join(str)`, avoiding ambiguity with space-containing arguments. (#3.7)

### Type Renames

- `ExecResult` (bytes) → `RawExecResult` — transport-level, raw bytes
- `ExecOutput` (str) → `ExecResult` — domain-level, decoded strings

These names now accurately reflect their layer: `RawExecResult` signals "unprocessed bytes" (transport), `ExecResult` signals "processed result" (domain). (#2.4)

## Key Types

### `CancellationToken` (domain/types.py — ABC)
```python
class CancellationToken(ABC):
    @abstractmethod
    def cancel(self) -> None: ...
    @property
    @abstractmethod
    def is_cancelled(self) -> bool: ...
```

### `ThreadCancellationToken` (adapters/_cancellation.py)
```python
class ThreadCancellationToken(CancellationToken):
    """Backed by threading.Event — thread-safe, no GIL dependency."""
```

### `DeadlineCancellationToken` (adapters/_cancellation.py)
```python
class DeadlineCancellationToken(CancellationToken):
    """Self-cancels after N seconds. Disarmed by cancel()."""
```

### `CompositeCancellationToken` (adapters/_cancellation.py)
```python
class CompositeCancellationToken(CancellationToken):
    """Cancelled if ANY child token is cancelled."""
```

### `TtyDetector` (ports/tty.py)
```python
class TtyDetector(ABC):
    @abstractmethod
    def is_tty(self) -> bool: ...
```

### `OutputStream` (ports/output_stream.py)
```python
class OutputStream(ABC):
    @abstractmethod
    def write(self, data: bytes) -> int: ...
    @abstractmethod
    def flush(self) -> None: ...
```

### `Transport.execute()` (ports/transport.py)
```python
def execute(self, command, *, timeout=None, input_data=None) -> RawExecResult: ...
```

### `StreamingTransport.stream()` (ports/streaming.py)
```python
def stream(self, command, *, timeout=None, input_data=None,
           on_stdout=None, on_stderr=None,
           cancel_token: CancellationToken | None = None) -> RawExecResult: ...
```

### `ProcessPipeReader.read()` (adapters/_process_reader.py)
```python
def read(self, on_stdout=None, on_stderr=None,
         cancel_token: CancellationToken | None = None) -> tuple[list[bytes], list[bytes]]: ...
```

### `run_pty()` (adapters/managers/pty.py)
```python
def run_pty(command: list[str],
            output_stream: OutputStream | None = None) -> subprocess.CompletedProcess: ...
```

### `PruneResult` (domain/types.py)
```python
@dataclass(frozen=True)
class PruneResult:
    deleted: int = 0
    reclaimed_bytes: int = 0
```

## Adding a New Runtime (e.g. nerdctl)

Create a provider inheriting from `BaseCliRuntimeProvider` and register in `factory.py`:

```python
class NerdctlRuntimeProvider(BaseCliRuntimeProvider):
    _kind = RuntimeKind("nerdctl")
    _container_parser_cls = DockerContainerParser
    _image_parser_cls = DockerImageParser
    _volume_parser_cls = DockerVolumeParser
    _network_parser_cls = DockerNetworkParser
    _capabilities = RuntimeCapabilities(
        list_format_flags=["--format", "{{json .}}"],
        tar_entry_name="Dockerfile",
        default_build_flags=["--quiet"],
    )
```

## Remediation Log

| Date | ID | Change |
|------|----|--------|
| 2026-06-17 | 0.1 | `parse_size_to_bytes()` raises `ValueError` on unknown units |
| 2026-06-17 | 0.2 | `_check_result()` added to all 4 `list()` methods |
| 2026-06-17 | 0.3 | Verified `create()` already had `_check_result()` |
| 2026-06-17 | 1.1+2.2 | `TtyDetector` ABC port + `StdoutTtyDetector` adapter; `CliContainerManager` requires `tty_detector: TtyDetector`; `_resolve_tty()` cached once |
| 2026-06-17 | 1.2 | Image parser size raises `ParsingError` on unparseable sizes (int + parse_size_to_bytes) |
| 2026-06-17 | 1.3 | `is_not_found_error()` uses `\b` word-boundary regex |
| 2026-06-17 | 1.4 | Removed unused imports (`ContainerNotFoundError`, `Enum`) |
| 2026-06-17 | 1.5 | `RuntimeFactory.create()` no longer probes `is_available()` |
| 2026-06-17 | 1.6+2.1 | `CancellationToken` ABC + `ThreadCancellationToken`, `DeadlineCancellationToken`, `CompositeCancellationToken`; `stream()` enforces total timeout |
| 2026-06-17 | 1.7 | `_not_found_error` class variable eliminates 26/27 `not_found=` kwargs |
| 2026-06-17 | 1.8 | `OutputStream` ABC port for PTY output binding |
| 2026-06-17 | 1.10 | `input_data` sentinel uses `is not None` (both conditions) |
| 2026-06-17 | 2.3 | `ParsingError` inherits from `OciError` |
| 2026-06-17 | 2.4 | `ExecResult` (bytes) → `RawExecResult`; `ExecOutput` (str) → `ExecResult` |
| 2026-06-17 | 2.5 | `PruneResult` frozen dataclass replaces `dict[str, int]` |
| 2026-06-17 | 2.6 | `VolumeMountType(StrEnum)` with adapter dispatch (tmpfs → `--mount`) |
| 2026-06-17 | 2.7 | `RunConfig` validates `memory_limit`/`cpu_limit` in `__post_init__` |
| 2026-06-17 | 3.1 | ~40 structural language tests deleted |
| 2026-06-17 | 3.2 | Mock-based tests moved from `tests/integration/` to `tests/unit/` |
| 2026-06-17 | 3.3 | Coverage improved 95%→99% |
| 2026-06-17 | 3.4 | Contract tests deepened with `pytest.raises(...) as exc` + attribute assertions |
| 2026-06-17 | 3.5 | Local mock parsers replaced with shared `MockXxxParser` |
| 2026-06-17 | 3.6 | `FailingTransport` deleted; contract tests use `RecordingTransport` with error responses |
| 2026-06-17 | 3.7 | `RecordingTransport` uses `tuple(command)` keys (no space ambiguity) |
| 2026-06-17 | 3.8 | Exception attribute assertions added (`.container_id`, `.image_name`, etc.) |
| 2026-06-17 | 3.9 | Negative domain type tests added (invalid mount type, host_port=0, network_container) |
| 2026-06-17 | 3.10 | `test_capabilities.py`→`tests/unit/domain/`; `test_domain_init.py` deleted; `TestParsingError` moved to `test_parsers.py` |
| 2026-06-17 | 4.2 | Threading docstrings added to `CancellationToken` and `RecordingTransport` |
