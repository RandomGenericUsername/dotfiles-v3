# oci-runtime — Architecture

Runtime-agnostic OCI container management built on hexagonal architecture. The module wraps the `docker` and `podman` CLIs behind ports so application code depends on abstractions, not on a specific runtime.

## Module Structure

```
oci-runtime/
├── pyproject.toml
├── docs/ARCHITECTURE.md           # This file
├── src/oci_runtime/
│   ├── __init__.py                # Public API re-exports (domain + ports + factory)
│   ├── factory.py                 # RuntimeFactory + RuntimeFactoryConfig (composition root)
│   ├── domain/                    # Pure domain layer — no I/O, no adapter imports
│   │   ├── __init__.py
│   │   ├── build_tar.py           # (new) create_build_tar, _validate_tar_path
│   │   ├── encoding.py            # (new) safe_decode
│   │   ├── error_matching.py      # (new) matches_any_pattern
│   │   ├── enums.py               # RuntimeKind, ContainerState, RestartPolicy, NetworkMode, VolumeMountType
│   │   ├── exceptions.py          # OciError hierarchy + ParsingError + ImagePullAccessDeniedError
│   │   ├── json_parsing.py        # (new) parse_json_item (scalar-guarded), parse_json_list
│   │   ├── list_command.py        # (new) build_list_command
│   │   ├── prune_parsing.py       # (new) parse_prune_result
│   │   ├── result_checking.py     # (new) check_cli_result
│   │   ├── size_parsing.py        # (new) parse_size_to_bytes, coerce_size, safe_int
│   │   └── types.py               # RunConfig, ContainerInfo, ExecResult, RawExecResult,
│   │                              #   PruneResult, VolumeMount, PortMapping, etc.
│   ├── ports/                     # Port interfaces (ABCs) + concrete implementations of infrastructure concerns
│   │   ├── __init__.py
│   │   ├── aggregates.py          # Parsers (port-level aggregate types)
│   │   ├── binary_resolver.py     # BinaryResolver ABC
│   │   ├── cancellation.py        # CancellationToken ABC + ThreadCancellationToken,
│   │   │                          #   DeadlineCancellationToken, CompositeCancellationToken, compose_tokens
│   │   ├── capabilities.py        # RuntimeCapabilities (frozen dataclass)
│   │   ├── discovery.py           # RuntimeDiscovery ABC
│   │   ├── engine.py              # ContainerEngine ABC
│   │   ├── managers.py            # ImageManager, ContainerManager, VolumeManager, NetworkManager ABCs
│   │   ├── output_stream.py       # OutputStream ABC
│   │   ├── parsers.py             # ContainerParser, ImageParser, VolumeParser, NetworkParser ABCs
│   │   │                          #   (re-exports ParsingError from domain)
│   │   ├── pipe_reader.py         # PipeReader ABC + ProcessPipeReader
│   │   ├── provider.py            # RuntimeProvider ABC
│   │   ├── pty_transport.py       # PtyTransport ABC
│   │   ├── streaming.py           # StreamingTransport ABC (real-time output streaming)
│   │   ├── transport.py           # Transport ABC (batch subprocess execution)
│   │   └── tty.py                 # TtyDetector ABC
│   └── adapters/
│       ├── helpers/
│       │   ├── list_executor.py    # CliListExecutor[T]
│       │   └── result_checker.py   # CliResultChecker
│       ├── parser/
│       │   ├── docker.py           # implements port ABCs directly
│       │   └── podman.py           # implements port ABCs directly
│       ├── provider/
│       │   ├── docker.py           # implements RuntimeProvider directly
│       │   └── podman.py           # implements RuntimeProvider directly
│       └── managers/
│           ├── container.py        # injects ResultChecker + ListExecutor
│           ├── image.py            # injects ResultChecker + ListExecutor
│           ├── volume.py           # injects ResultChecker + ListExecutor
│           └── network.py          # injects ResultChecker + ListExecutor
└── tests/
    ├── unit/                      # Domain, port, adapter, contract, wiring, boundary tests
    │   ├── domain/
    │   ├── ports/                 # Includes test_cancellation, test_capabilities
    │   ├── adapters/
    │   ├── contract/
    │   ├── wiring/                # Mock-based workflow + command-shape tests
    │   └── boundary/              # Empty/malformed/concurrency edge cases
    ├── integration/
    │   └── smoke/                 # Real-runtime tests (skip when no docker/podman present)
    └── helpers/                   # RecordingTransport, FakeTtyDetector, Mock*Parser
```

## Layering Rules

The dependency direction is strictly **domain ← ports ← adapters**, with the factory as the single composition root that wires adapters to ports.

The AST-based layering linter (`tests/architecture/test_layering.py`) enforces strict dependency direction with no intra-layer imports in the adapter layer:

- **domain/** contains value objects, enums, and exceptions. It imports only the standard library (`re`, `abc`, `dataclasses`, `pathlib`, `enum`). It never imports `ports` or `adapters`.
- **ports/** contains ABCs, aggregate dataclasses (`Parsers`), and port-level value objects (`RuntimeCapabilities`, `CancellationToken`). It imports from `domain` and defines the contracts the adapters implement. The only non-ABC artifact is the `ParsingError` re-export in `ports/parsers.py`, sourced from `domain/exceptions.py`.
- **adapters/** contains the concrete implementations. It imports from `ports` and `domain` only — the layering linter blocks intra-adapter imports (`adapters` → `adapters`), enforcing that adapters share no dependencies between themselves; all sharing goes through `ports`. Adapters are not re-exported by `oci_runtime/__init__.py` — they are implementation details reachable via their submodules.
- **factory.py** is the only place manager, transport, engine, discovery, and infrastructure adapter classes are referenced. `RuntimeFactoryConfig` exposes factory callables for every adapter so the entire object graph is injectable for testing.

## Domain Layer

The domain layer is pure and I/O-free.

- **`RuntimeCapabilities`** lives in `ports/capabilities.py` — it carries runtime-specific configuration (CLI format flags, default run/build flags, tar entry name, feature toggles). It is consumed by adapters and providers, never by the domain itself. All list-typed fields are `tuple[str, ...]` with `default=()`, ensuring the frozen dataclass is truly immutable.
- **`PruneResult`** — all `prune()` methods return `PruneResult(deleted=..., reclaimed_bytes=...)` rather than a magic-key dict.
- **All domain value objects use `frozen=True` AND hold only immutable containers** — every domain dataclass (`PruneResult`, `RunConfig`, `BuildContext`, `VolumeMount`, `PortMapping`, `ContainerInfo`, `ImageInfo`, `VolumeInfo`, `NetworkInfo`, `ExecResult`, `RawExecResult`, `RuntimePreference`, `RuntimeCapabilities`) is frozen with mutable fields (`dict` → `MappingProxyType`, `list` → `tuple`), ensuring deep immutability — instances and their contents cannot be mutated after creation, preventing accidental side effects.
- **`VolumeMountType(StrEnum)`** — `VolumeMount.type` is a typed enum with `BIND`, `VOLUME`, `TMPFS` members. `__post_init__` enforces the type at runtime: passing a non-`VolumeMountType` value raises `TypeError`. `VolumeMount.source` is `str | Path | None` — `None` is valid only for `TMPFS` mounts; `__post_init__` raises `ValueError` if `source is None` and `type != TMPFS`.
- **`PortMapping.host_ip`** is required (no default) — callers must pass `None` for unbound ports or a specific IP for bound ports. This prevents a misleading `0.0.0.0` default on ports with no host binding.
- **`RunConfig` validates limits** — `memory_limit` and `cpu_limit` are validated in `__post_init__` against regex patterns (`^\d+(\.\d+)?[bkmg]?$` and `^\d+(\.\d+)?$` respectively). `timeout` (if set) must be positive. `detach=True` is mutually exclusive with `tty`/`auto_tty`.
- **`BuildContext` forbids impossible combinations** — `__post_init__` raises `ValueError` when both `build_file_content` and `build_file_path` are set, when neither is set, and when both `context_path` and `files` are set.

## Exception Hierarchy

All module exceptions descend from `OciError`, so `except OciError:` catches every error this module raises. `ParsingError` lives in `domain/exceptions.py` alongside the rest of the hierarchy and is re-exported by `ports/parsers.py`.

```
OciError (base)
├── ParsingError
├── OperationTimeoutError
├── ContainerError
│   ├── ContainerNotFoundError
│   └── ContainerRuntimeError
├── ImageError
│   ├── ImageNotFoundError
│   ├── ImagePullAccessDeniedError
│   └── ImageRuntimeError
├── VolumeError
│   ├── VolumeNotFoundError
│   └── VolumeRuntimeError
├── NetworkError
│   ├── NetworkNotFoundError
│   └── NetworkRuntimeError
└── RuntimeNotAvailableError
```

`OciError` carries optional `command`, `exit_code`, and `stderr` fields and formats them into the exception message. The not-found subclasses attach the entity name as an attribute (`image_name`, `container_id`, `volume_name`, `network_name`). `ImagePullAccessDeniedError` attaches `image_name` and optional `registry`, distinguishing registry permission failures from missing images.

## Port Layer

The port layer defines the ABCs that adapters implement.

**`ContainerEngine`** — the top-level engine facade. Exposes `images`, `containers`, `volumes`, `networks` (the four manager ABCs) and `capabilities` as abstract properties, plus `is_available() -> bool` and `version() -> str`.

**`Transport`** — batch subprocess execution. `execute(command, *, timeout, input_data, cancel_token) -> RawExecResult` runs a command to completion and returns raw bytes. `probe() -> bool` checks whether the runtime binary is resolvable. `get_runtime_binary() -> str` returns the resolved binary path.

**`StreamingTransport`** — real-time streaming execution. `stream(command, *, timeout, input_data, on_stdout, on_stderr, cancel_token) -> RawExecResult` starts the process under `Popen`, reads stdout/stderr via a selector loop, and invokes callbacks as output arrives. On cancellation it returns partial data with `returncode=-1`; on timeout it raises `OperationTimeoutError(OciError)`.

**`PtyTransport`** — pseudo-terminal execution. `execute_pty(command, *, output_stream, timeout, cancel_token) -> RawExecResult` runs a command in a PTY for stdout (terminal rendering) with a separate pipe for stderr (error classification). This decouples output rendering from error detection — `_check_result` can inspect stderr for not-found patterns in both TTY and non-TTY modes. On timeout it raises `OperationTimeoutError(OciError)`.

**`BinaryResolver`** — resolves a runtime binary name to an executable path. `resolve(binary) -> str` raises `RuntimeNotAvailableError` if not found. `is_available(binary) -> bool` returns a boolean without raising. Caches results so repeated calls do not re-invoke `shutil.which`.

**`CancellationToken`** — signals cancellation across threads. `cancel() -> None` sets the cancelled state. `is_cancelled -> bool` is a property. Concrete implementations (`ThreadCancellationToken`, `DeadlineCancellationToken`, `CompositeCancellationToken`) and the `compose_tokens()` helper live alongside the ABC in `ports/cancellation.py`, eliminating the old adapter-level module.

**`RuntimeProvider`** — encapsulates all runtime-specific knowledge. `kind` returns the `RuntimeKind`. `capabilities()` returns `RuntimeCapabilities`. `create_parsers() -> Parsers` builds the four parser instances. Providers are constructed with parser classes and capabilities injected via keyword arguments.

**`ImageManager` / `ContainerManager` / `VolumeManager` / `NetworkManager`** — the four manager ABCs defining the lifecycle operations (build, pull, run, exec, inspect, list, prune, etc.). Each `prune()` returns `PruneResult`. Each `list()` returns `list[<entity info>]` — an empty result returns `[]`, not an error. `exec_container` accepts an optional `timeout: float | None`.

**`ContainerParser` / `ImageParser` / `VolumeParser` / `NetworkParser`** — parser ABCs that convert CLI JSON/text output into domain types. Each declares `parse_inspect`, `parse_list`, `parse_prune`, `is_not_found_error`, and `is_auth_error`. `ImageParser` adds `parse_build_output` and `parse_digest_from_pull`.

**`TtyDetector`** — single-method ABC: `is_tty() -> bool`. `CliContainerManager` requires a `TtyDetector` instance (no default) so TTY detection is injectable and testable without patching `sys.stdout`.

**`OutputStream`** — write-only byte stream ABC: `write(bytes) -> int` and `flush() -> None`. `PtyTransport.execute_pty()` accepts an `OutputStream | None` to decouple PTY output from `sys.stdout.buffer`.

**`RuntimeDiscovery`** — single-method ABC: `available() -> list[RuntimePreference]`. Enumerates which runtimes are reachable.

**`Parsers`** — frozen aggregate dataclass grouping the four parsers so providers can return them as a single value.

## Adapter Layer

### Binary Resolution

**`CliBinaryResolver`** implements `BinaryResolver` by caching `shutil.which` results per binary name in an internal dict. Both `CliTransport` and `CliStreamingTransport` receive a `BinaryResolver` instance via the factory, eliminating the duplicated `_ensure_binary` / `_which_cache` / `_NOT_PROBED` mechanism that previously existed in each transport independently. `probe()` calls `is_available()` on the resolver — consistent error contract with `execute()` / `get_runtime_binary()`.

### Transport

**`CliTransport`** implements `Transport.execute()` using `subprocess.Popen` + `ProcessPipeReader` + `DeadlineCancellationToken`. Receives `binary` and `BinaryResolver` via constructor injection (no default fallback — the factory provides the resolver). When `timeout` is set, a `DeadlineCancellationToken` is created and composed with any user-provided `cancel_token` via `compose_tokens()`. The reader loop polls `is_cancelled` each iteration; on deadline expiry the process is killed and `OperationTimeoutError(OciError)` is raised; on user cancellation it returns partial data with `returncode=-1`. Stdin (when `input_data` is provided) is written in a daemon thread to avoid pipe deadlock on large inputs. After the reader exits (pipes drained), a timeout-aware poll loop replaces bare `process.wait()` — it calls `process.wait(timeout=0.5)` in a loop, checking `effective_token.is_cancelled` each iteration, so that user cancellation or deadline expiry is detected even during the post-read wait phase. This replaces the previous `subprocess.run(timeout=...)` approach, unifying batch and streaming transports under the same `CancellationToken` framework and ensuring all timeouts raise `OperationTimeoutError` (never leaking `subprocess.TimeoutExpired`).

**`CliStreamingTransport`** wraps `subprocess.Popen` + `ProcessPipeReader`. Same `BinaryResolver` constructor injection, `DeadlineCancellationToken` + `compose_tokens()` pattern as `CliTransport`. After the reader exits on EOF, a timeout-aware poll loop replaces bare `process.wait()` — polling `process.wait(timeout=0.5)` with cancellation checks, matching `CliTransport` and `CliPtyTransport`. In the cancellation branch, `process.kill()` + `process.wait()` run BEFORE `_stdin_thread.join()` to break the pipe buffer deadlock. This avoids a double-timeout where `process.wait(timeout=timeout)` could raise `TimeoutExpired` after the deadline already passed.

**`PipeReader`** (ABC) / **`ProcessPipeReader`** (concrete) in `ports/pipe_reader.py` — reads from two file descriptors via `selectors.DefaultSelector` until both deliver EOF or cancellation. It uses `os.read(fd, n)` (not `fileobj.read(n)`) which returns available data immediately after `select` fires — `fileobj.read(n)` on `FileIO` blocks until `n` bytes or EOF, which would deadlock on processes that emit small chunks then wait. Works with both subprocess pipes AND PTY master fds; PTY `OSError(EIO)` on Linux (raised when the PTY master is drained) is caught and treated as EOF. The reader is constructed via `ProcessPipeReader.from_process(process)` (for subprocess pipes) or `ProcessPipeReader.from_fds(primary_fd, secondary_fd)` (for PTY + pipe). The port-level `PipeReader` ABC provides a seam for testing without real file descriptors.

### PTY

**`CliPtyTransport`** implements `PtyTransport.execute_pty()` using `pty.openpty()` + `subprocess.Popen`. The key architectural decision: stdout is connected to the PTY slave (terminal rendering for interactive container output) while stderr is connected to `subprocess.PIPE` (separate pipe for docker CLI error messages). This decouples output rendering from error classification — `_check_result` can inspect stderr for not-found patterns in PTY mode, just as it does in non-TTY mode. I/O is read via `ProcessPipeReader.from_fds(master_fd, stderr_fileno)`. After the reader exits, a timeout-aware poll loop replaces bare `process.wait()` — polling `process.wait(timeout=0.5)` with cancellation checks, matching `CliTransport` and `CliStreamingTransport`. Returns `RawExecResult(returncode, pty_stdout, stderr_bytes)`.

### ResultChecker + ListExecutor

Managers no longer inherit from a shared `CliBaseManager`. Instead, each manager
receives two injected dependencies via its constructor:
- **`ResultChecker`** (port: `ports/result_checker.py`, adapter: `helpers/result_checker.py`):
  `check(result, cmd, *, operation, entity, not_found_error) -> None` — inspects a
  `RawExecResult` and raises the appropriate `OciError` subclass. The `not_found_error`
  parameter is typed as `type[OciError] | None` (not bare `type`), improving type safety.
  1. On success (returncode 0): returns.
  2. If `is_auth` callback matches: raises `auth_error` with command/exit_code/stderr.
  3. If `is_not_found` callback matches: raises `not_found_error(entity)`.
  4. On any other non-zero exit: raises `generic_error` with full context.

  The checker is configured with `generic_error`, `not_found_error`, optional
  `auth_error`/`is_auth`, and `is_not_found` callbacks — all injected at construction
  time, making error behavior fully testable.

- **`ListExecutor[T]`** (port: `ports/list_executor.py`, adapter: `helpers/list_executor.py`):
  `execute_list(subcommand, entity_type, *, show_all, filters) -> list[T]` — builds
  the list command (binary + subcommand + format flags + optional -a/filters),
  executes it via transport, checks the result via its injected `ResultChecker`, and
  returns the parsed list via the injected `parse_list` callback.

Each manager's `list()` is a one-line delegate to `self._list_executor.execute_list(...)`.

### Parsers

Each parser (`Docker*Parser`, `Podman*Parser`) implements the port ABCs directly
(`ContainerParser`, `ImageParser`, etc.) without a shared base class. Parsing helpers
live in `domain/`:
- `parse_json_item(raw)` / `parse_json_list(raw)` from `domain/json_parsing.py` — JSON
  parsing with scalar guard (rejects non-dict/non-list JSON).
- `matches_any_pattern(text, patterns)` from `domain/error_matching.py` — word-boundary
  regex matching used by both `is_not_found_error` and `is_auth_error`.
- `parse_prune_result(raw)` from `domain/prune_parsing.py` — parses `prune` CLI output.
- `coerce_size(size)` / `safe_int(v)` from `domain/size_parsing.py` — size parsing.
- `parse_size_to_bytes(raw)` from the same module — converts human-readable sizes to int.

`parse_build_output` validates the result against `^sha256:[a-f0-9]{12,64}$`.
Image parsers also implement `is_auth_error` for pull-access-denied detection.

### Cancellation

`ports/cancellation.py` provides three `CancellationToken` implementations alongside the ABC:
- **`ThreadCancellationToken`** — backed by `threading.Event`; the production default.
- **`DeadlineCancellationToken(timeout)`** — starts a `threading.Timer` on construction that sets the event after `timeout` seconds. `cancel()` disarms the timer and sets the event immediately. `__del__` calls `self._timer.cancel()` to prevent the timer thread from lingering if the token is garbage-collected before firing.
- **`CompositeCancellationToken(*children)`** — cancelled when any child is cancelled; `cancel()` propagates to all children.

`compose_tokens(*tokens)` is a module-level helper that returns the effective token: `CompositeCancellationToken` if multiple tokens are passed, the single non-None one, or `None` if none are set.

### Provider

Each provider (`DockerRuntimeProvider`, `PodmanRuntimeProvider`) implements
`RuntimeProvider` directly with constructor injection of parser classes + capabilities.
The factory passes the classes explicitly in `_default_providers()`. There is no shared
base class — each provider declares its own `create_parsers() -> Parsers`.

## Composition Root

`RuntimeFactoryConfig` (frozen dataclass) is the single place where adapter selection is configured. Every field is a `Callable` or `type` that defaults to `None`; `_resolve_config()` fills in the production defaults lazily on first use:

```python
@dataclass(frozen=True)
class RuntimeFactoryConfig:
    transport_factory: Callable[[str, BinaryResolver], Transport] | None = None
    streaming_transport_factory: Callable[[str, BinaryResolver], StreamingTransport] | None = None
    runtime_cls: type[ContainerEngine] | None = None
    discovery_factory: Callable[[Callable[[str], Transport]], RuntimeDiscovery] | None = None
    tty_detector_factory: Callable[[], TtyDetector] | None = None
    output_stream_factory: Callable[[], OutputStream] | None = None
    cancellation_factory: Callable[[], CancellationToken] | None = None
    binary_resolver_factory: Callable[[], BinaryResolver] | None = None
    pty_transport_factory: Callable[[BinaryResolver], PtyTransport] | None = None
```

`RuntimeFactory.create(preference)` resolves the config, creates transports, asks the provider for caps + parsers, builds per-manager `CliResultChecker` and `CliListExecutor` instances, and wires them into each manager. `RuntimeFactoryConfig` has `result_checker_factory` and `list_executor_factory` fields (default `CliResultChecker` / `CliListExecutor`).

## Public API

`oci_runtime/__init__.py` re-exports the full set of public names so consumers never need to import from submodules:

- **Domain**: all enums (`RuntimeKind`, `ContainerState`, `RestartPolicy`, `NetworkMode`, `VolumeMountType`), all exceptions (`OciError` hierarchy including `ParsingError`, `ImagePullAccessDeniedError`), all types (`RunConfig`, `BuildContext`, `ContainerInfo`, `ImageInfo`, `VolumeInfo`, `NetworkInfo`, `PortMapping`, `VolumeMount`, `PruneResult`, `ExecResult`, `RawExecResult`, `RuntimePreference`).
- **Ports**: `ContainerEngine`, `ImageManager`, `ContainerManager`, `VolumeManager`, `NetworkManager`, `ContainerParser`, `ImageParser`, `VolumeParser`, `NetworkParser`, `Transport`, `StreamingTransport`, `PtyTransport`, `BinaryResolver`, `CancellationToken`, `TtyDetector`, `OutputStream`, `RuntimeDiscovery`, `RuntimeProvider`, `RuntimeCapabilities`.
- **Factory**: `RuntimeFactory`, `RuntimeFactoryConfig`.

Adapter classes (`CliTransport`, `CliRuntime`, `DockerRuntimeProvider`, etc.) are deliberately not exported — they are implementation details. The `__all__` list is the authoritative surface.

## Key Types

### `CancellationToken` (ports/cancellation.py)
```python
class CancellationToken(ABC):
    @abstractmethod
    def cancel(self) -> None: ...
    @property
    @abstractmethod
    def is_cancelled(self) -> bool: ...
```

### `ThreadCancellationToken` (ports/cancellation.py)
```python
class ThreadCancellationToken(CancellationToken):
    """Backed by threading.Event — thread-safe, no GIL dependency."""
```

### `DeadlineCancellationToken` (ports/cancellation.py)
```python
class DeadlineCancellationToken(CancellationToken):
    """Self-cancels after N seconds. Disarmed by cancel(). __del__ cancels the timer."""
```

### `CompositeCancellationToken` (ports/cancellation.py)
```python
class CompositeCancellationToken(CancellationToken):
    """Cancelled if ANY child token is cancelled."""
```

### `BinaryResolver` (ports/binary_resolver.py)
```python
class BinaryResolver(ABC):
    @abstractmethod
    def resolve(self, binary: str) -> str: ...
    @abstractmethod
    def is_available(self, binary: str) -> bool: ...
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
def execute(self, command, *, timeout=None, input_data=None,
            cancel_token: CancellationToken | None = None) -> RawExecResult: ...
```

### `StreamingTransport.stream()` (ports/streaming.py)
```python
def stream(self, command, *, timeout=None, input_data=None,
           on_stdout=None, on_stderr=None,
           cancel_token: CancellationToken | None = None) -> RawExecResult: ...
```

### `PtyTransport.execute_pty()` (ports/pty_transport.py)
```python
def execute_pty(self, command: list[str], *, output_stream: OutputStream,
                timeout: float | None = None,
                cancel_token: CancellationToken | None = None) -> RawExecResult: ...
```

### `ProcessPipeReader.read()` (ports/pipe_reader.py)
```python
def read(self, on_primary=None, on_secondary=None,
         cancel_token: CancellationToken | None = None) -> tuple[list[bytes], list[bytes]]: ...
```

### `PruneResult` (domain/types.py)
```python
@dataclass(frozen=True)
class PruneResult:
    deleted: int = 0
    reclaimed_bytes: int = 0
```

## Adding a New Runtime (e.g. nerdctl)

Create a provider implementing `RuntimeProvider` directly — it only needs `kind`,
`capabilities`, and `create_parsers`:

```python
class NerdctlRuntimeProvider(RuntimeProvider):
    def __init__(
        self,
        *,
        container_parser_cls: type[ContainerParser],
        image_parser_cls: type[ImageParser],
        volume_parser_cls: type[VolumeParser],
        network_parser_cls: type[NetworkParser],
        capabilities: RuntimeCapabilities | None = None,
    ):
        self._kind = RuntimeKind("nerdctl")
        self._container_parser_cls = container_parser_cls
        self._image_parser_cls = image_parser_cls
        self._volume_parser_cls = volume_parser_cls
        self._network_parser_cls = network_parser_cls
        self._capabilities = capabilities or _NERDCTL_CAPABILITIES

    @property
    def kind(self) -> RuntimeKind: ...
    def capabilities(self) -> RuntimeCapabilities: ...
    def create_parsers(self) -> Parsers: ...
```

Register it in the factory:
```python
from oci_runtime.adapters.parser.docker import DockerContainerParser, ...

_NERDCTL_CAPABILITIES = RuntimeCapabilities(...)

providers = {
    RuntimeKind.DOCKER: DockerRuntimeProvider(container_parser_cls=..., ...),
    RuntimeKind.PODMAN: PodmanRuntimeProvider(container_parser_cls=..., ...),
    RuntimeKind("nerdctl"): NerdctlRuntimeProvider(container_parser_cls=DockerContainerParser, ...),
}
factory = RuntimeFactory(providers=providers)
```

## Testing Strategy

- **`tests/unit/domain/`** — value-object construction, enum membership, exception attributes, frozen-semantics enforcement.
- **`tests/unit/ports/`** — ABC contract verification (abstract method sets, cannot-instantiate), `CancellationToken` interface, `RuntimeCapabilities` defaults.
- **`tests/unit/adapters/`** — parser JSON fixtures, transport/PTY/streaming behavior with mocked subprocess, manager command-shape and error-propagation tests.
- **`tests/unit/contract/`** — interface compliance (every adapter implements its port), public-API `__all__` membership.
- **`tests/unit/wiring/`** — full object-graph assembly via `RecordingTransport` and mock parsers; verifies the exact CLI command shape each manager method produces.
- **`tests/unit/boundary/`** — empty outputs, malformed JSON, error conditions, concurrent access.
- **`tests/integration/smoke/`** — real docker/podman lifecycle tests; skipped when no runtime is present.
- **`tests/helpers/`** — shared `RecordingTransport`, `RecordingStreamingTransport`, `FakeTtyDetector`, and `Mock*Parser` instances. The mocks conform to the port return types (`parse_prune` returns `PruneResult`, not `dict`).
- **`tests/architecture/`** — AST-based import-direction linter enforcing `domain ← ports ← adapters ← factory`. Runs on every `pytest` invocation.
- **`tests/audit/`** — regression tests for bugs found in the audit. All pass as regression guards — if a bug is reintroduced, the test fails.
- **`tests/conformance/`** — parser round-trip tests against real docker/podman CLI fixtures. No xfail mechanism; tests assert correctness directly.

## Remediation Log

| Date | Change | Summary |
|------|--------|---------|
| 2026-06-21 | `oci-runtime-guardrail-remediation` (`15f6238`) | **F1-F14**: silent-failure fixes (exec stderr, logs stderr, prune error propagation, build context fields, entity-typed errors, coerce_size, parse_size_to_bytes, get_runtime_binary, timeout→OperationTimeoutError). **F15-F42**: 28 additional fixes (cancellation_factory, RunConfig validation, tuple fields, cached which, conformance parser fixes, wiring test corrections). Bumped to 0.3.0. |
| 2026-06-22 | `oci-runtime-audit-remediation` | Full audit remediation: CancellationToken + RuntimeCapabilities relocated to ports/, BinaryResolver port + adapter, PtyTransport port + CliPtyTransport adapter (stderr=PIPE separation), ProcessPipeReader generalized (os.read, PTY EIO handling), CliTransport.execute() CancellationToken unification, all value objects frozen, PortMapping.host_ip required, VolumeMount.source Optional, ImagePullAccessDeniedError, parse_build_output hex validation, parse_digest_from_pull rename, Docker/Podman parser parity (RepoTags null, unbound ports, string Names), _parse_json_list scalar guard + empty NDJSON, tar path validation, DeadlineCancellationToken __del__, parse_size_to_bytes P/E units + regex fix, list() factored into base, _not_found_error required, collections.abc.Callable, conformance xfail removed, docs updated. 826 tests pass. |
| 2026-06-22 | `oci-runtime-audit-remediation-v2` | Full audit remediation v2: Podman pull digest fix (remove premature return), Podman null RepoTags handling, Podman auth-error patterns, ProcessPipeReader fd<1000 removal, CliTransport stdin thread ValueError catch, CliStreamingTransport cancellation ordering, logs(follow) GeneratorExit guard, timeout-aware poll loop in all 3 transports, factory type annotation fix (BinaryResolver param), timeout type unification (float), RuntimePreference docstring fix, build error contract (ParsingError→ImageRuntimeError wrapping), stream_output wiring with OutputStream callbacks, composition root consolidation (factory builds managers, provider create_managers removed), domain deep immutability (MappingProxyType + tuple), test fidelity improvements (timeout/cancellation/PTY/tar/logs tests, concurrency fix, build-command key ordering, test renames, mock parser fixes, sleep→deterministic cancellation tests). 840+ tests pass. |
| 2026-06-29 | `oci-runtime-audit-remediation-v3` | Full audit remediation v3: Domain extraction (8 new domain modules), parser rewire (BaseCliParser deleted, port ABCs implemented directly), manager rewire (CliBaseManager deleted, ResultChecker+ListExecutor injection), provider rewire (BaseCliRuntimeProvider deleted, constructor injection), factory DI (result_checker_factory+list_executor_factory), audit bug fixes A1-A8 (host_ip port flags, scalar guard, process reader strict, ImagePullAccessDeniedError context, PTY OciError, pull digest error, version OciError, Managers aggregate deleted), timeout params unified to float|None, hidden_tar_path norm fix, --network bridge explicit, LogDriverNotSupportedWarning, test cleanup. 861 tests pass. |
| 2026-06-29 | Post-v3 hardening (`1953540`) | CancellationToken implementations (`ThreadCancellationToken`, `DeadlineCancellationToken`, `CompositeCancellationToken`, `compose_tokens`) moved from `adapters/_cancellation.py` to `ports/cancellation.py`. ProcessPipeReader moved from `adapters/_process_reader.py` to `ports/pipe_reader.py` with new `PipeReader` ABC. `adapters/_tar.py` re-export shim deleted (logic already in `domain/build_tar.py`). All parser ABCs now require `is_auth_error(stderr) -> bool`. ResultChecker port `not_found_error` param typed as `type[OciError]`. `CliTransport`/`CliStreamingTransport` require `BinaryResolver` injection (no default fallback). Layering linter blocks `adapters` → `adapters` imports. Adapting tests updated. |
| 2026-06-30 | `oci-runtime-regression-fix` | Regression fixes R1-R3: PTY `output_stream` required (not `| None`), transport `binary_resolver` required (not `| None`), `exec_container` only suppresses `ContainerNotFoundError`. A1: `host_ip` port flag building fixed (handles `host_ip` without `host_port`, `None` vs truthy check). Dead code removal (`_NOT_PROBED`, `Managers` aggregate, `_execute_list` — already cleaned). Doc/type fixes (C4, E5). Test quality improvements (D2: Podman parser types; D5: dead `@patch` removed). New regression tests (T1-T4: PTY output_stream, transport binary_resolver, exec_container error propagation, host_ip port flags). 868 tests pass. |
