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
│   │   ├── exceptions.py          # OciError hierarchy + ParsingError + ImagePullAccessDeniedError
│   │   └── types.py               # RunConfig, ContainerInfo, ExecResult, RawExecResult,
│   │                              #   PruneResult, VolumeMount, PortMapping, etc.
│   ├── ports/                     # Port interfaces (ABCs only) + aggregate types
│   │   ├── __init__.py
│   │   ├── aggregates.py          # Parsers, Managers (port-level aggregate types)
│   │   ├── binary_resolver.py     # BinaryResolver ABC
│   │   ├── cancellation.py        # CancellationToken ABC
│   │   ├── capabilities.py        # RuntimeCapabilities (frozen dataclass)
│   │   ├── discovery.py           # RuntimeDiscovery ABC
│   │   ├── engine.py              # ContainerEngine ABC
│   │   ├── managers.py            # ImageManager, ContainerManager, VolumeManager, NetworkManager ABCs
│   │   ├── output_stream.py       # OutputStream ABC
│   │   ├── parsers.py             # ContainerParser, ImageParser, VolumeParser, NetworkParser ABCs
│   │   │                          #   (re-exports ParsingError from domain)
│   │   ├── provider.py            # RuntimeProvider ABC
│   │   ├── pty_transport.py       # PtyTransport ABC
│   │   ├── streaming.py           # StreamingTransport ABC (real-time output streaming)
│   │   ├── transport.py           # Transport ABC (batch subprocess execution)
│   │   └── tty.py                 # TtyDetector ABC
│   └── adapters/                  # Adapter implementations of the ports
│       ├── _cancellation.py       # ThreadCancellationToken, DeadlineCancellationToken, CompositeCancellationToken
│       ├── _process_reader.py     # ProcessPipeReader (selector-based fd reading, works with pipes AND PTY)
│       ├── _tar.py                # create_build_tar (tar archive builder for stdin context, path-validated)
│       ├── _utils.py              # parse_size_to_bytes (size string parser, B–E units)
│       ├── binary.py              # CliBinaryResolver (cached shutil.which)
│       ├── tty.py                 # StdoutTtyDetector
│       ├── output_stream.py       # StdoutBufferStream
│       ├── engine/cli.py          # CliRuntime
│       ├── transport/
│       │   ├── cli.py             # CliTransport (Popen + ProcessPipeReader + CancellationToken)
│       │   ├── streaming.py       # CliStreamingTransport (Popen + ProcessPipeReader)
│       │   └── pty.py             # CliPtyTransport (PTY stdout + stderr PIPE, returns RawExecResult)
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
│           ├── base.py            # CliBaseManager[P] (bounded generic, _check_result + _execute_list)
│           ├── container.py       # CliContainerManager
│           ├── image.py           # CliImageManager
│           ├── volume.py          # CliVolumeManager
│           └── network.py         # CliNetworkManager
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

- **domain/** contains value objects, enums, and exceptions. It imports only the standard library (`re`, `abc`, `dataclasses`, `pathlib`, `enum`). It never imports `ports` or `adapters`.
- **ports/** contains ABCs, aggregate dataclasses (`Parsers`, `Managers`), and port-level value objects (`RuntimeCapabilities`, `CancellationToken`). It imports from `domain` and defines the contracts the adapters implement. The only non-ABC artifact is the `ParsingError` re-export in `ports/parsers.py`, sourced from `domain/exceptions.py`.
- **adapters/** contains the concrete implementations. It imports from `ports` and `domain`. Adapters are not re-exported by `oci_runtime/__init__.py` — they are implementation details reachable via their submodules.
- **factory.py** is the only place manager, transport, engine, discovery, and infrastructure adapter classes are referenced. Provider subclasses reference only parser adapter classes. `RuntimeFactoryConfig` exposes factory callables for every adapter so the entire object graph is injectable for testing.

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

**`CancellationToken`** — signals cancellation across threads. `cancel() -> None` sets the cancelled state. `is_cancelled -> bool` is a property. This is a pure interface — concrete implementations live in `adapters/_cancellation.py`.

**`RuntimeProvider`** — encapsulates all runtime-specific knowledge. `create_parsers() -> Parsers` and `create_managers(transport, streaming, caps, *, tty_detector_factory, output_stream_factory, cancellation_factory, pty_transport) -> Managers` build the parser and manager instances for a given runtime. The factory hooks are keyword-only and required, so the composition root controls which `TtyDetector`, `OutputStream`, `CancellationToken`, and `PtyTransport` adapters are wired into the container manager.

**`ImageManager` / `ContainerManager` / `VolumeManager` / `NetworkManager`** — the four manager ABCs defining the lifecycle operations (build, pull, run, exec, inspect, list, prune, etc.). Each `prune()` returns `PruneResult`. Each `list()` returns `list[<entity info>]` — an empty result returns `[]`, not an error. `exec_container` accepts an optional `timeout: float | None`.

**`ContainerParser` / `ImageParser` / `VolumeParser` / `NetworkParser`** — parser ABCs that convert CLI JSON/text output into domain types. Each declares `parse_inspect`, `parse_list`, `parse_prune`, and `is_not_found_error`. `ImageParser` adds `parse_build_output` and `parse_digest_from_pull`.

**`TtyDetector`** — single-method ABC: `is_tty() -> bool`. `CliContainerManager` requires a `TtyDetector` instance (no default) so TTY detection is injectable and testable without patching `sys.stdout`.

**`OutputStream`** — write-only byte stream ABC: `write(bytes) -> int` and `flush() -> None`. `PtyTransport.execute_pty()` accepts an `OutputStream | None` to decouple PTY output from `sys.stdout.buffer`.

**`RuntimeDiscovery`** — single-method ABC: `available() -> list[RuntimePreference]`. Enumerates which runtimes are reachable.

**`Parsers` / `Managers`** — frozen aggregate dataclasses grouping the four parsers / four managers so providers can return them as a single value.

## Adapter Layer

### Binary Resolution

**`CliBinaryResolver`** implements `BinaryResolver` by caching `shutil.which` results per binary name in an internal dict. Both `CliTransport` and `CliStreamingTransport` receive a `BinaryResolver` instance via the factory, eliminating the duplicated `_ensure_binary` / `_which_cache` / `_NOT_PROBED` mechanism that previously existed in each transport independently. `probe()` calls `is_available()` on the resolver — consistent error contract with `execute()` / `get_runtime_binary()`.

### Transport

**`CliTransport`** implements `Transport.execute()` using `subprocess.Popen` + `ProcessPipeReader` + `DeadlineCancellationToken`. When `timeout` is set, a `DeadlineCancellationToken` is created and composed with any user-provided `cancel_token` via `compose_tokens()`. The reader loop polls `is_cancelled` each iteration; on deadline expiry the process is killed and `OperationTimeoutError(OciError)` is raised; on user cancellation it returns partial data with `returncode=-1`. Stdin (when `input_data` is provided) is written in a daemon thread to avoid pipe deadlock on large inputs. After the reader exits (pipes drained), a timeout-aware poll loop replaces bare `process.wait()` — it calls `process.wait(timeout=0.5)` in a loop, checking `effective_token.is_cancelled` each iteration, so that user cancellation or deadline expiry is detected even during the post-read wait phase. This replaces the previous `subprocess.run(timeout=...)` approach, unifying batch and streaming transports under the same `CancellationToken` framework and ensuring all timeouts raise `OperationTimeoutError` (never leaking `subprocess.TimeoutExpired`).

**`CliStreamingTransport`** wraps `subprocess.Popen` + `ProcessPipeReader`. Same `DeadlineCancellationToken` + `compose_tokens()` pattern as `CliTransport`. After the reader exits on EOF, a timeout-aware poll loop replaces bare `process.wait()` — polling `process.wait(timeout=0.5)` with cancellation checks, matching `CliTransport` and `CliPtyTransport`. In the cancellation branch, `process.kill()` + `process.wait()` run BEFORE `_stdin_thread.join()` to break the pipe buffer deadlock. This avoids a double-timeout where `process.wait(timeout=timeout)` could raise `TimeoutExpired` after the deadline already passed.

**`ProcessPipeReader`** reads from two file descriptors via `selectors.DefaultSelector` until both deliver EOF or cancellation. It uses `os.read(fd, n)` (not `fileobj.read(n)`) which returns available data immediately after `select` fires — `fileobj.read(n)` on `FileIO` blocks until `n` bytes or EOF, which would deadlock on processes that emit small chunks then wait. Works with both subprocess pipes AND PTY master fds; PTY `OSError(EIO)` on Linux (raised when the PTY master is drained) is caught and treated as EOF. The reader is constructed via `ProcessPipeReader.from_process(process)` (for subprocess pipes) or `ProcessPipeReader.from_fds(primary_fd, secondary_fd)` (for PTY + pipe).

### PTY

**`CliPtyTransport`** implements `PtyTransport.execute_pty()` using `pty.openpty()` + `subprocess.Popen`. The key architectural decision: stdout is connected to the PTY slave (terminal rendering for interactive container output) while stderr is connected to `subprocess.PIPE` (separate pipe for docker CLI error messages). This decouples output rendering from error classification — `_check_result` can inspect stderr for not-found patterns in PTY mode, just as it does in non-TTY mode. I/O is read via `ProcessPipeReader.from_fds(master_fd, stderr_fileno)`. After the reader exits, a timeout-aware poll loop replaces bare `process.wait()` — polling `process.wait(timeout=0.5)` with cancellation checks, matching `CliTransport` and `CliStreamingTransport`. Returns `RawExecResult(returncode, pty_stdout, stderr_bytes)`.

### Managers

**`CliBaseManager[P]`** is a `Generic[P]` base where `P` is bounded to `ContainerParser | ImageParser | VolumeParser | NetworkParser`. It holds the shared `transport`, `parser`, and `caps`. Class variables `_not_found_error` (required — no default) and `_generic_error` (defaults to `ContainerRuntimeError`) define the error types raised by `_check_result`. An optional `_auth_error` class variable (set only by `CliImageManager` to `ImagePullAccessDeniedError`) enables auth-error detection.

`_check_result(result, cmd, *, operation, entity, not_found=None)` inspects a `RawExecResult`:
1. On success (returncode 0): returns.
2. If `_auth_error` is set and `parser.is_auth_error(stderr)` matches: raises `_auth_error(entity)`.
3. If `parser.is_not_found_error(stderr)` matches: raises `_not_found_error(entity)` (or the `not_found` override if provided).
4. On any other non-zero exit: raises `_generic_error` with command, exit code, and stderr attached.

`_execute_list(entity_type, subcommand, show_all, filters)` is a shared helper that builds the list command (binary + subcommand + format flags + optional `-a`/filters), executes it, calls `_check_result`, and returns the parsed list. Each manager's `list()` delegates to this helper, eliminating the 4× copy-pasted list method.

**`CliContainerManager`** diverges from `_check_result` in one place:
- `exec_container()` does not call `_check_result`. It returns `ExecResult(returncode, stdout, stderr)` for any exit code, raising `ContainerNotFoundError` only when the container is missing. The exit code of the inner command is returned to the caller, not raised. Accepts an optional `timeout: float | None`.

`run()` builds the `docker run` / `podman run` command from `RunConfig`, dispatching TMPFS mounts to `--mount type=tmpfs,target=...` and BIND/VOLUME mounts to `-v src:tgt[:ro]`. When TTY is effective (`config.tty` or `config.auto_tty` + `tty_detector.is_tty()`) it calls `pty_transport.execute_pty()`; when `config.stream_output=True` and not TTY it calls `streaming.stream()` with `on_stdout`/`on_stderr` callbacks writing to `self._output_stream`; otherwise it calls `streaming.stream()` without callbacks. The routing matrix:

| Condition | Transport | Output | Return |
|-----------|-----------|--------|--------|
| `detach=True` | batch `execute()` (via `transport`) | captured | container ID |
| `effective_tty=True` | `pty_transport.execute_pty()` | → `output_stream` | `""` |
| `stream_output=True` | `streaming.stream()` with callbacks | → `output_stream` | `""` |
| neither | `streaming.stream()` no callbacks | captured | `stdout.strip()` |

**All branches call `_check_result` with `not_found=ImageNotFoundError`** — error classification is consistent regardless of TTY mode. `detach=True` and effective-TTY are mutually exclusive (a detached container has no terminal to attach a PTY to). Build flags are emitted before the positional context arg, ensuring `docker build [OPTIONS] PATH` grammar (runtime-agnostic, works with cobra and non-cobra CLIs).

`logs(follow=True)` runs the streaming transport in a daemon thread, feeding decoded chunks to a `Queue` that the generator drains. The thread catches `Exception` (not `BaseException`) so `KeyboardInterrupt`/`SystemExit` propagate. A `CancellationToken` cancels the stream when the consumer stops iterating. **Errors are checked in the `finally` block** — if the consumer breaks early, streaming errors are still propagated, not silently dropped. The thread join timeout is `_LOGS_JOIN_TIMEOUT = 5.0`.

**`CliImageManager`** builds images by sending the Dockerfile and extra files as a tar archive on stdin (`-f -`), or by pointing at a filesystem path (`-f <path> <context>`). `pull()` returns the parsed digest and raises `ImageError` if no digest can be extracted. Auth failures (pull access denied) raise `ImagePullAccessDeniedError`, not `ImageNotFoundError`. `parse_digest_from_pull` is the renamed method (was `parse_id_from_pull`).

**`CliVolumeManager`** and **`CliNetworkManager`** follow the same `_check_result` pattern for their respective CLI subcommands.

### Parsers

**`BaseCliParser`** provides shared JSON parsing and the prune parser:
- `_parse_json_item(raw)` — parses JSON that is either a list-with-one-item or a single dict. Raises `ParsingError` on malformed JSON or an empty result (inspect requires exactly one item).
- `_parse_json_list(raw)` — parses JSON that is a list, a single object, or NDJSON (newline-delimited JSON). An empty JSON array `[]` or empty NDJSON stream returns `[]` (a valid empty result). Non-list/non-dict JSON scalars (integers, strings, null, bool) raise `ParsingError` — they are not silently wrapped. Malformed input raises `ParsingError`.
- `is_not_found_error(stderr)` — word-boundary regex match against `_not_found_patterns` (lowercased).
- `is_auth_error(stderr)` — word-boundary regex match against `_auth_error_patterns` (only on `DockerImageParser`; checks for "pull access denied", "unauthorized", "authentication required").
- `parse_prune(raw)` — counts deleted IDs matching `^(?:deleted:\s*)?(?:sha256:)?([a-f0-9]{12,64})$` (covers both bare-hex and `deleted: sha256:` lines emitted by `prune --all`), and parses `Total reclaimed space:` via `parse_size_to_bytes`, defaulting to 0 on unparseable values.

`parse_build_output` validates the result against `^sha256:[a-f0-9]{12,64}$` after prefixing — if the output is not a valid image id (e.g. `--quiet` wasn't honored or build failed mid-output), it raises `ParsingError` rather than returning `sha256:<garbage>`.

`_coerce_size(size)` and `_safe_int(v)` are module-level helpers in `base.py` used by both Docker and Podman image/container parsers to coerce string sizes to int and guard against malformed port values.

The Docker and Podman parser classes (`Docker*Parser`, `Podman*Parser`) differ in their not-found/auth patterns and in how they normalize fields between the two runtimes' JSON shapes:
- Docker: `RepoTags: null` coerced to `[]` (not `None`); string `Names` coerced to `[string]`; `Repository`/`Tag` fallback when `RepoTags` is empty.
- Podman: `Names` fallback when `RepoTags` is null; string `Names` coerced to `[string]`; unbound ports (no host binding) kept in the port list, matching Docker behavior; `parse_digest_from_pull` returns `""` on no match (not the raw line), matching Docker's contract.

### Cancellation

`adapters/_cancellation.py` provides three `CancellationToken` implementations:
- **`ThreadCancellationToken`** — backed by `threading.Event`; the production default.
- **`DeadlineCancellationToken(timeout)`** — starts a `threading.Timer` on construction that sets the event after `timeout` seconds. `cancel()` disarms the timer and sets the event immediately. `__del__` calls `self._timer.cancel()` to prevent the timer thread from lingering if the token is garbage-collected before firing.
- **`CompositeCancellationToken(*children)`** — cancelled when any child is cancelled; `cancel()` propagates to all children.

`compose_tokens(user_token, deadline_token)` is a module-level helper that returns the effective token: `CompositeCancellationToken(user_token, deadline_token)` if both are set, the non-None one if only one is set, or `None` if neither is set.

### Provider

`BaseCliRuntimeProvider` implements `RuntimeProvider` by reading class-level attributes (`_kind`, `_capabilities`, `_container_parser_cls`, etc.) that concrete subclasses (`DockerRuntimeProvider`, `PodmanRuntimeProvider`) set. `create_managers` receives the `tty_detector_factory`, `output_stream_factory`, `cancellation_factory`, and `pty_transport` from the factory and invokes them to wire the `CliContainerManager`.

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

`RuntimeFactory.create(preference)` resolves the config, creates a `BinaryResolver`, builds the transport and streaming transport from `preference.binary` and the resolver, creates a `PtyTransport` from the resolver, and asks the provider to create the managers (passing the TTY, output-stream, cancellation, and PTY factories through). It does not probe availability — `is_available()` is the caller's responsibility. The `discovery` property caches the `RuntimeDiscovery` instance on first access.

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

### `ThreadCancellationToken` (adapters/_cancellation.py)
```python
class ThreadCancellationToken(CancellationToken):
    """Backed by threading.Event — thread-safe, no GIL dependency."""
```

### `DeadlineCancellationToken` (adapters/_cancellation.py)
```python
class DeadlineCancellationToken(CancellationToken):
    """Self-cancels after N seconds. Disarmed by cancel(). __del__ cancels the timer."""
```

### `CompositeCancellationToken` (adapters/_cancellation.py)
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
def execute_pty(self, command, *, output_stream=None, timeout=None,
                cancel_token: CancellationToken | None = None) -> RawExecResult: ...
```

### `ProcessPipeReader.read()` (adapters/_process_reader.py)
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

Create a provider inheriting from `BaseCliRuntimeProvider` (needs only `kind`, `capabilities`, `create_parsers`; no `create_managers`) and register it in the `providers` dict passed to `RuntimeFactory`:

```python
class NerdctlRuntimeProvider(BaseCliRuntimeProvider):
    _kind = RuntimeKind("nerdctl")
    _container_parser_cls = DockerContainerParser
    _image_parser_cls = DockerImageParser
    _volume_parser_cls = DockerVolumeParser
    _network_parser_cls = DockerNetworkParser
    _capabilities = RuntimeCapabilities(
        list_format_flags=("--format", "{{json .}}"),
        tar_entry_name="Dockerfile",
        default_build_flags=("--quiet",),
    )

providers = {
    RuntimeKind.DOCKER: DockerRuntimeProvider(),
    RuntimeKind.PODMAN: PodmanRuntimeProvider(),
    RuntimeKind("nerdctl"): NerdctlRuntimeProvider(),
}
factory = RuntimeFactory(providers=providers)
```

The factory builds managers directly from the provider's parsers, wiring transports and factories without requiring a `create_managers` method on the provider. The new provider only needs `kind`, `capabilities`, and `create_parsers`.

`RuntimeCapabilities` list fields (`list_format_flags`, `default_run_flags`, `default_build_flags`) are `tuple[str, ...]` with `default=()`, not `list[str]`. This ensures the frozen dataclass is truly immutable.

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
