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
│   │   ├── enums.py               # RuntimeKind, ContainerState, RestartPolicy, NetworkMode, VolumeMountType
│   │   ├── exceptions.py          # OciError hierarchy + ParsingError
│   │   ├── capabilities.py        # RuntimeCapabilities (frozen value object)
│   │   └── types.py               # RunConfig, ContainerInfo, ExecResult, RawExecResult,
│   │                              #   CancellationToken (ABC), PruneResult, VolumeMount, PortMapping, etc.
│   ├── ports/                     # Port interfaces (ABCs only) + aggregate types
│   │   ├── __init__.py
│   │   ├── engine.py              # ContainerEngine ABC
│   │   ├── transport.py           # Transport ABC (batch subprocess execution)
│   │   ├── streaming.py           # StreamingTransport ABC (real-time output streaming)
│   │   ├── discovery.py           # RuntimeDiscovery ABC
│   │   ├── provider.py            # RuntimeProvider ABC
│   │   ├── managers.py            # ImageManager, ContainerManager, VolumeManager, NetworkManager ABCs
│   │   ├── parsers.py             # ContainerParser, ImageParser, VolumeParser, NetworkParser ABCs
│   │   │                          #   (re-exports ParsingError from domain)
│   │   ├── tty.py                 # TtyDetector ABC
│   │   ├── output_stream.py       # OutputStream ABC
│   │   └── aggregates.py          # Parsers, Managers (port-level aggregate types)
│   └── adapters/                  # Adapter implementations of the ports
│       ├── _cancellation.py       # ThreadCancellationToken, DeadlineCancellationToken, CompositeCancellationToken
│       ├── _process_reader.py     # ProcessPipeReader (selector-based pipe reading)
│       ├── _tar.py                # create_build_tar (tar archive builder for stdin context)
│       ├── _utils.py              # parse_size_to_bytes (size string parser)
│       ├── tty.py                 # StdoutTtyDetector
│       ├── output_stream.py       # StdoutBufferStream
│       ├── engine/cli.py          # CliRuntime
│       ├── transport/
│       │   ├── cli.py             # CliTransport (batch subprocess.run, cached binary lookup)
│       │   └── streaming.py       # CliStreamingTransport (Popen + ProcessPipeReader)
│       ├── discovery/cli.py       # CliRuntimeDiscovery
│       ├── provider/
│       │   ├── _base.py           # BaseCliRuntimeProvider
│       │   ├── docker.py          # DockerRuntimeProvider
│       │   └── podman.py          # PodmanRuntimeProvider
│       ├── parser/
│       │   ├── base.py            # BaseCliParser + _coerce_size / _safe_int helpers
│       │   ├── docker.py          # Docker*Parser classes
│       │   └── podman.py          # Podman*Parser classes
│       └── managers/
│           ├── base.py            # CliBaseManager[P] (bounded generic)
│           ├── container.py       # CliContainerManager
│           ├── image.py           # CliImageManager
│           ├── volume.py          # CliVolumeManager
│           ├── network.py         # CliNetworkManager
│           └── pty.py             # run_pty (PTY process execution with optional timeout)
└── tests/
    ├── unit/                      # Domain, port, adapter, contract, wiring, boundary tests
    │   ├── domain/
    │   ├── ports/
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

- **domain/** contains value objects, enums, exceptions, and the `CancellationToken` ABC. It imports only the standard library (`re`, `abc`, `dataclasses`, `pathlib`, `enum`). It never imports `ports` or `adapters`.
- **ports/** contains only ABCs and aggregate dataclasses (`Parsers`, `Managers`). It imports from `domain` and defines the contracts the adapters implement. The only non-ABC artifact is the `ParsingError` re-export in `ports/parsers.py`, sourced from `domain/exceptions.py`.
- **adapters/** contains the concrete implementations. It imports from `ports` and `domain`. Adapters are not re-exported by `oci_runtime/__init__.py` — they are implementation details reachable via their submodules.
- **factory.py** is the only place adapter classes are referenced. `RuntimeFactoryConfig` exposes factory callables for every adapter so the entire object graph is injectable for testing.

## Domain Layer

The domain layer is pure and I/O-free.

- **`CancellationToken` is an ABC** — the domain defines only the interface. Concrete `ThreadCancellationToken` (backed by `threading.Event`) lives in `adapters/_cancellation.py`. This keeps thread-safety concerns out of the domain and avoids relying on CPython GIL atomicity.
- **`RuntimeCapabilities` is a frozen value object** — declared in `domain/capabilities.py`, it carries runtime-specific configuration (CLI format flags, default run/build flags, tar entry name, feature toggles). It is consumed by adapters and providers, never by the domain itself.
- **`PruneResult` is a frozen dataclass** — all `prune()` methods return `PruneResult(deleted=..., reclaimed_bytes=...)` rather than a magic-key dict.
- **`VolumeMountType(StrEnum)`** — `VolumeMount.type` is a typed enum with `BIND`, `VOLUME`, `TMPFS` members. `__post_init__` coerces string values to the enum.
- **`RunConfig` validates limits** — `memory_limit` and `cpu_limit` are validated in `__post_init__` against regex patterns (`^\d+(\.\d+)?[bkmg]?$` and `^\d+(\.\d+)?$` respectively).
- **`BuildContext` forbids impossible combinations** — `__post_init__` raises `ValueError` when both `build_file_content` and `build_file_path` are set, when neither is set, and when both `context_path` and `files` are set (the latter two cannot be combined in a single `docker build` invocation: context comes from either a filesystem PATH or a stdin tar, not both).

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
│   └── ImageRuntimeError
├── VolumeError
│   ├── VolumeNotFoundError
│   └── VolumeRuntimeError
├── NetworkError
│   ├── NetworkNotFoundError
│   └── NetworkRuntimeError
└── RuntimeNotAvailableError
```

`OciError` carries optional `command`, `exit_code`, and `stderr` fields and formats them into the exception message. The not-found subclasses attach the entity name as an attribute (`image_name`, `container_id`, `volume_name`, `network_name`).

## Port Layer

The port layer defines the ABCs that adapters implement.

**`ContainerEngine`** — the top-level engine facade. Exposes `images`, `containers`, `volumes`, `networks` (the four manager ABCs) and `capabilities` as abstract properties, plus `is_available() -> bool` and `version() -> str`.

**`Transport`** — batch subprocess execution. `execute(command, *, timeout, input_data) -> RawExecResult` runs a command to completion and returns raw bytes. `probe() -> bool` checks whether the runtime responds to `--version`. `get_runtime_binary() -> str` returns the resolved binary path.

**`StreamingTransport`** — real-time streaming execution. `stream(command, *, timeout, input_data, on_stdout, on_stderr, cancel_token) -> RawExecResult` starts the process under `Popen`, reads stdout/stderr via a selector loop, and invokes callbacks as output arrives. On cancellation it returns partial data with `returncode=-1`; on timeout it raises `OperationTimeoutError(OciError)`.

**`RuntimeProvider`** — encapsulates all runtime-specific knowledge. `create_parsers() -> Parsers` and `create_managers(transport, streaming, caps, *, tty_detector_factory, output_stream_factory) -> Managers` build the parser and manager instances for a given runtime. The factory hooks are keyword-only and required, so the composition root controls which `TtyDetector` and `OutputStream` adapters are wired into the container manager.

**`ImageManager` / `ContainerManager` / `VolumeManager` / `NetworkManager`** — the four manager ABCs defining the lifecycle operations (build, pull, run, exec, inspect, list, prune, etc.). Each `prune()` returns `PruneResult`. Each `list()` returns `list[<entity info>]` — an empty result returns `[]`, not an error.

**`ContainerParser` / `ImageParser` / `VolumeParser` / `NetworkParser`** — parser ABCs that convert CLI JSON/text output into domain types. Each declares `parse_inspect`, `parse_list`, `parse_prune`, and `is_not_found_error`. `ImageParser` adds `parse_build_output` and `parse_id_from_pull`.

**`TtyDetector`** — single-method ABC: `is_tty() -> bool`. `CliContainerManager` requires a `TtyDetector` instance (no default) so TTY detection is injectable and testable without patching `sys.stdout`.

**`OutputStream`** — write-only byte stream ABC: `write(bytes) -> int` and `flush() -> None`. `run_pty()` accepts an `OutputStream | None` to decouple PTY output from `sys.stdout.buffer`.

**`RuntimeDiscovery`** — single-method ABC: `available() -> list[RuntimePreference]`. Enumerates which runtimes are reachable.

**`Parsers` / `Managers`** — frozen aggregate dataclasses grouping the four parsers / four managers so providers can return them as a single value.

## Adapter Layer

### Transport

**`CliTransport`** wraps `subprocess.run`. It caches the `shutil.which` result on first probe (via a `_NOT_PROBED` sentinel) so repeated `get_runtime_binary()` / `execute()` calls do not re-invoke the syscall. If the binary is missing it raises `RuntimeNotAvailableError`.

**`CliStreamingTransport`** wraps `subprocess.Popen` + `ProcessPipeReader`. When `timeout` is set it constructs a `DeadlineCancellationToken` and composes it with any user-provided `cancel_token` via `CompositeCancellationToken`. The reader loop polls `is_cancelled` each iteration; on deadline expiry the process is killed and `subprocess.TimeoutExpired` is raised; on user cancellation it returns partial data with `returncode=-1`. Stdin (when `input_data` is provided) is written in a daemon thread to avoid pipe deadlock on large inputs.

**`ProcessPipeReader`** reads stdout/stderr via `selectors.DefaultSelector` until both pipes deliver EOF, not until process exit — this guarantees no data is lost when a process exits before the reader drains the pipes.

### Managers

**`CliBaseManager[P]`** is a `Generic[P]` base where `P` is bounded to `ContainerParser | ImageParser | VolumeParser | NetworkParser`. It holds the shared `transport`, `parser`, and `caps`, and provides `_check_result()` which inspects a `RawExecResult`: on success it returns; on a not-found stderr pattern it raises the manager's `_not_found_error` (a class variable); on any other non-zero exit it raises `ContainerRuntimeError` with the command, exit code, and stderr attached.

**`CliContainerManager`** is the one manager that diverges from `_check_result` in two places:
- `run()` calls `_check_result` with an explicit `not_found=ImageNotFoundError` override (a failed `run` of a missing image raises `ImageNotFoundError`, not `ContainerNotFoundError`).
- `exec_container()` does not call `_check_result` at all. It returns `ExecResult(returncode, stdout, stderr)` for any exit code, raising `ContainerNotFoundError` only when the container is missing. The exit code of the inner command is returned to the caller, not raised.

`run()` builds the `docker run` / `podman run` command from `RunConfig`, dispatching TMPFS mounts to `--mount type=tmpfs,target=...` and BIND/VOLUME mounts to `-v src:tgt[:ro]`. When TTY is effective (`config.tty` or `config.auto_tty` + `tty_detector.is_tty()`) it calls `run_pty()`; otherwise it calls `streaming.stream()`. `detach=True` and effective-TTY are mutually exclusive (a detached container has no terminal to attach a PTY to).

`logs(follow=True)` runs the streaming transport in a daemon thread, feeding decoded chunks to a `Queue` that the generator drains. The thread catches `Exception` (not `BaseException`) so `KeyboardInterrupt`/`SystemExit` propagate. A `CancellationToken` cancels the stream when the consumer stops iterating.

**`CliImageManager`** builds images by sending the Dockerfile and extra files as a tar archive on stdin (`-f -`), or by pointing at a filesystem path (`-f <path> <context>`). `pull()` returns the parsed image id and raises `ImageError` if no id can be extracted from the output (it never silently returns `""`).

**`CliVolumeManager`** and **`CliNetworkManager`** follow the same `_check_result` pattern for their respective CLI subcommands.

### Parsers

**`BaseCliParser`** provides shared JSON parsing and the prune parser:
- `_parse_json_item(raw)` — parses JSON that is either a list-with-one-item or a single dict. Raises `ParsingError` on malformed JSON or an empty result (inspect requires exactly one item).
- `_parse_json_list(raw)` — parses JSON that is a list, a single object, or NDJSON (newline-delimited JSON). An empty JSON array `[]` returns `[]` (a valid empty result). Malformed input raises `ParsingError`.
- `is_not_found_error(stderr)` — word-boundary regex match against `_not_found_patterns` (lowercased).
- `parse_prune(raw)` — counts deleted IDs matching `^(?:deleted:\s*)?(?:sha256:)?([a-f0-9]{12,64})$` (covers both bare-hex and `deleted: sha256:` lines emitted by `prune --all`), and parses `Total reclaimed space:` via `parse_size_to_bytes`, defaulting to 0 on unparseable values.

`_coerce_size(size)` and `_safe_int(v)` are module-level helpers in `base.py` used by both Docker and Podman image/container parsers to coerce string sizes to int and guard against malformed port values.

The Docker and Podman parser classes (`Docker*Parser`, `Podman*Parser`) differ in their not-found patterns and in how they normalize fields between the two runtimes' JSON shapes (e.g. Podman uses `Names` fallback when `RepoTags` is null; Docker uses `Repository`/`Tag` fallback).

### Cancellation

`adapters/_cancellation.py` provides three `CancellationToken` implementations:
- **`ThreadCancellationToken`** — backed by `threading.Event`; the production default.
- **`DeadlineCancellationToken(timeout)`** — starts a `threading.Timer` on construction that sets the event after `timeout` seconds. `cancel()` disarms the timer and sets the event immediately.
- **`CompositeCancellationToken(*children)`** — cancelled when any child is cancelled; `cancel()` propagates to all children.

### PTY

`run_pty(command, output_stream=None, timeout=None)` runs a command in a pseudo-terminal via `pty.openpty`, streaming output to the `OutputStream` as it arrives. When `timeout` is set it enforces a wall-clock deadline: the `select` timeout shrinks as the deadline approaches; on expiry the process is killed and reaped, then `subprocess.TimeoutExpired` is raised. When `output_stream` is `None` it defaults to `StdoutBufferStream`.

### Provider

`BaseCliRuntimeProvider` implements `RuntimeProvider` by reading class-level attributes (`_kind`, `_capabilities`, `_container_parser_cls`, etc.) that concrete subclasses (`DockerRuntimeProvider`, `PodmanRuntimeProvider`) set. `create_managers` receives the `tty_detector_factory` and `output_stream_factory` callables from the factory and invokes them to wire the `CliContainerManager`.

## Composition Root

`RuntimeFactoryConfig` (frozen dataclass) is the single place where adapter selection is configured. Every field is a `Callable` or `type` that defaults to `None`; `_resolve_config()` fills in the production defaults lazily on first use:

```python
@dataclass(frozen=True)
class RuntimeFactoryConfig:
    transport_factory: Callable[[str], Transport] | None = None
    streaming_transport_factory: Callable[[str], StreamingTransport] | None = None
    runtime_cls: type[ContainerEngine] | None = None
    discovery_factory: Callable[[Callable[[str], Transport]], RuntimeDiscovery] | None = None
    tty_detector_factory: Callable[[], TtyDetector] | None = None
    output_stream_factory: Callable[[], OutputStream] | None = None
```

`RuntimeFactory.create(preference)` resolves the config, looks up the registered `RuntimeProvider` for `preference.kind`, builds the transport and streaming transport from `preference.binary`, and asks the provider to create the managers (passing the TTY and output-stream factories through). It does not probe availability — `is_available()` is the caller's responsibility. The `discovery` property caches the `RuntimeDiscovery` instance on first access.

## Public API

`oci_runtime/__init__.py` re-exports the full set of public names so consumers never need to import from submodules:

- **Domain**: all enums (`RuntimeKind`, `ContainerState`, `RestartPolicy`, `NetworkMode`, `VolumeMountType`), all exceptions (`OciError` hierarchy including `ParsingError`), all types (`RunConfig`, `BuildContext`, `ContainerInfo`, `ImageInfo`, `VolumeInfo`, `NetworkInfo`, `PortMapping`, `VolumeMount`, `PruneResult`, `ExecResult`, `RawExecResult`, `RuntimePreference`, `CancellationToken`), and `RuntimeCapabilities`.
- **Ports**: `ContainerEngine`, `ImageManager`, `ContainerManager`, `VolumeManager`, `NetworkManager`, `ContainerParser`, `ImageParser`, `VolumeParser`, `NetworkParser`, `Transport`, `StreamingTransport`, `TtyDetector`, `OutputStream`, `RuntimeDiscovery`, `RuntimeProvider`.
- **Factory**: `RuntimeFactory`, `RuntimeFactoryConfig`.

Adapter classes (`CliTransport`, `CliRuntime`, `DockerRuntimeProvider`, etc.) are deliberately not exported — they are implementation details. The `__all__` list is the authoritative surface.

## Key Types

### `CancellationToken` (domain/types.py)
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
            output_stream: OutputStream | None = None,
            timeout: float | None = None) -> subprocess.CompletedProcess: ...
```

### `PruneResult` (domain/types.py)
```python
@dataclass(frozen=True)
class PruneResult:
    deleted: int = 0
    reclaimed_bytes: int = 0
```

### `RuntimeProvider.create_managers()` (ports/provider.py)
```python
def create_managers(
    self,
    transport: Transport,
    streaming_transport: StreamingTransport,
    caps: RuntimeCapabilities,
    *,
    tty_detector_factory: Callable[[], TtyDetector],
    output_stream_factory: Callable[[], OutputStream],
) -> Managers: ...
```

## Adding a New Runtime (e.g. nerdctl)

Create a provider inheriting from `BaseCliRuntimeProvider` and register it in the `providers` dict passed to `RuntimeFactory`:

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

providers = {
    RuntimeKind.DOCKER: DockerRuntimeProvider(),
    RuntimeKind.PODMAN: PodmanRuntimeProvider(),
    RuntimeKind("nerdctl"): NerdctlRuntimeProvider(),
}
factory = RuntimeFactory(providers=providers)
```

The factory passes `tty_detector_factory`, `output_stream_factory`, and `cancellation_factory` to `provider.create_managers()` automatically; the new provider does not need to handle them directly — `BaseCliRuntimeProvider` wires them into `CliContainerManager`.

`RuntimeCapabilities` list fields (`list_format_flags`, `default_run_flags`, `default_build_flags`) are `tuple[str, ...]`, not `list[str]`. This ensures the frozen dataclass is truly immutable.

## Testing Strategy

- **`tests/unit/domain/`** — value-object construction, enum membership, exception attributes.
- **`tests/unit/ports/`** — ABC contract verification (abstract method sets, cannot-instantiate).
- **`tests/unit/adapters/`** — parser JSON fixtures, transport/PTY/streaming behavior with mocked subprocess, manager command-shape and error-propagation tests.
- **`tests/unit/contract/`** — interface compliance (every adapter implements its port), public-API `__all__` membership.
- **`tests/unit/wiring/`** — full object-graph assembly via `RecordingTransport` and mock parsers; verifies the exact CLI command shape each manager method produces.
- **`tests/unit/boundary/`** — empty outputs, malformed JSON, error conditions, concurrent access.
- **`tests/integration/smoke/`** — real docker/podman lifecycle tests; skipped when no runtime is present.
- **`tests/helpers/`** — shared `RecordingTransport`, `RecordingStreamingTransport`, `FakeTtyDetector`, and `Mock*Parser` instances. The mocks conform to the port return types (`parse_prune` returns `PruneResult`, not `dict`).

## Remediation Log

| Date | Change | Summary |
|------|--------|---------|
| 2026-06-21 | `oci-runtime-guardrail-remediation` | F1-F42 fixes: `OperationTimeoutError`, entity-typed runtime errors, prune error propagation, tuple fields, cached which, RunConfig domain validation, null label/size/port edge cases, conformance parser fixes, wiring test corrections. Bumped to 0.3.0. |
