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
│   │   ├── enums.py            # RuntimeKind, ContainerState, RestartPolicy, NetworkMode
│   │   ├── exceptions.py       # OciError hierarchy (ImageError siblings to ContainerError)
│   │   └── types.py            # Value objects: RunConfig, ContainerInfo, ExecResult, CancellationToken, etc.
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
│   │   └── aggregates.py       # Parsers, Managers (port-level return types)
│   └── adapters/               # Adapter implementations
│       ├── _process_reader.py  # ProcessPipeReader (selector-based pipe reading)
│       ├── _tar.py             # create_build_tar (tar archive builder)
│       ├── _utils.py           # parse_size_to_bytes (size string parser)
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
└── tests/                      # Unit + integration + contract tests
```

## Architecture Decisions

### Domain Layer — Pure, I/O-Free

The domain layer contains no imports of `sys`, `io`, `threading`, or any adapter-level module.

- **`RunConfig.effective_tty` removed** — the TTY resolution (`sys.stdout.isatty()`) was moved to `CliContainerManager._resolve_tty()` in the adapter layer. The domain only holds the `tty` and `auto_tty` configuration flags. (#26)

### Exception Hierarchy

Exception hierarchy corrected to model the domain properly: (#2)

```
OciError (base)
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

`ImageError`, `VolumeError`, `NetworkError`, and `RuntimeNotAvailableError` inherit from `OciError` directly (not `ContainerError`). This prevents `except ContainerError` from inadvertently catching image/volume/network/runtime errors.

### Port Layer

**Transport port simplified to batch-only:** `execute()` no longer has `stream`, `on_output`, or `cancel_token` parameters. Streaming is now a separate `StreamingTransport` port. (#8, #27)

**StreamingTransport port extracted:** real-time output streaming (Popen + selector loop) moved from `Transport.execute()` to `StreamingTransport.stream()`. Callbacks use `on_stdout`/`on_stderr` instead of `on_output(data, stream_name)`. (#27)

**`ProcessPipeReader` callback signature updated:** `on_output(data, stream_name)` replaced with separate `on_stdout` and `on_stderr` callbacks. (#27)

**`execute_pty()` removed (earlier):** PTY execution is a concern of the container manager, not the transport. (#8)

**Transport accepts optional `CancellationToken`:** allows callers to cancel long-running streaming operations (e.g. `logs --follow`). (#21)

**`ParsingError` moved to `ports/parsers.py`:** it's a contract exception of the parser port, not an adapter implementation detail. (#14)

**`Parsers` and `Managers` kept in ports as `ports/aggregates.py`:** they are port-level return types used by `RuntimeProvider`. Moving them to domain or factory would create circular dependencies. (#12)

**`RuntimeFactoryConfig` moved to `factory.py`:** composition root config belongs in the composition root, not in the ports layer. (#13)

**`RuntimeCapabilities` defaults neutralized:** `supports_log_drivers` defaults to `False` (was `True` — Docker-centric), `tar_entry_name` defaults to `""` (was `"Dockerfile"`). Both providers set these explicitly. (#11)

**`ports/__init__.py` populated:** all 16 port types are re-exported from the package, making the public API explicit. (#15)

### Adapter Layer

**`ProcessPipeReader` extracted:** shared utility for selector-based pipe reading, used by `CliTransport`. Accepts optional `CancellationToken` for cooperative cancellation. (#4)

**`create_build_tar` extracted:** tar archive creation moved to `adapters/_tar.py`. (#17)

**`parse_size_to_bytes` extracted:** utility function moved to `adapters/_utils.py`. (#18)

**`BaseCliRuntimeProvider` extracted:** eliminates boilerplate between `DockerRuntimeProvider` and `PodmanRuntimeProvider` (both were 45 lines of identical structure, now ~12 lines each). (#25)

**`_parse_json_list` fail-fast:** invalid NDJSON lines now raise `ParsingError` instead of being silently skipped. (#19)

**`run_pty` accepts `output_stream` instead of `on_output` callback:** cleaner I/O abstraction — callers pass `io.IOBase` (defaults to `sys.stdout.buffer`). No more hidden stdout side effects. (#23)

**`RunConfig.entrypoint` changed from `list[str]` to `str`:** `--entrypoint` is a single-value CLI flag. The old code split `entrypoint[0]` → `--entrypoint`, `entrypoint[1:]` → CMD args, which was incorrect Docker/Podman semantics and dead code (never exercised). (#22)

**`CancellationToken` in domain, threaded through `Transport`:** enables clean cancellation of `logs --follow` when the caller stops iterating. The generator's `finally` block cancels the token, the selector loop exits, the process is killed, and the thread joins. No thread leakage or orphan subprocesses. (#21)

**Podman `parse_list` now extracts ports:** Podman's list format JSON includes a `Ports` array that was being silently discarded. Added `_parse_ports_from_list` to match Docker's equivalent. (#6)

**`parse_list` raises `ParsingError` on missing `Names`:** both Docker and Podman `parse_list` now validate that the `Names` field is present and non-empty, rather than silently producing an empty string. (#7)

**`RuntimeFactory._providers` defensively copied:** prevents external mutation of the provider dictionary. (#20)

## Key Types

### `CancellationToken` (domain/types.py)
```python
class CancellationToken:
    """Pure domain value — no I/O, no threading primitives.
    The flag is set by one thread and observed by another."""
    def cancel(self) -> None: ...
    @property
    def is_cancelled(self) -> bool: ...
```

### `Transport.execute()` (ports/transport.py)
```python
def execute(
    self, command, *,
    timeout=None, input_data=None,
) -> ExecResult: ...
```

### `StreamingTransport.stream()` (ports/streaming.py)
```python
def stream(
    self, command, *,
    timeout=None, input_data=None,
    on_stdout=None, on_stderr=None,
    cancel_token: CancellationToken | None = None,
) -> ExecResult: ...
```

### `ProcessPipeReader.read()` (adapters/_process_reader.py)
```python
def read(
    self, on_stdout=None, on_stderr=None,
    cancel_token: CancellationToken | None = None,
) -> tuple[list[bytes], list[bytes]]: ...
```

### `run_pty()` (adapters/managers/pty.py)
```python
def run_pty(
    command: list[str],
    output_stream: io.IOBase | None = None,  # defaults to sys.stdout.buffer
) -> subprocess.CompletedProcess: ...
```

## Future Consideration

### Add a new runtime (e.g. nerdctl)

Create a new provider class inheriting from `BaseCliRuntimeProvider`:
```python
class NerdctlRuntimeProvider(BaseCliRuntimeProvider):
    _kind = RuntimeKind("nerdctl")
    _container_parser_cls = DockerContainerParser  # nerdctl uses Docker-compatible JSON
    _image_parser_cls = DockerImageParser
    _volume_parser_cls = DockerVolumeParser
    _network_parser_cls = DockerNetworkParser
    _capabilities = RuntimeCapabilities(
        list_format_flags=["--format", "{{json .}}"],
        tar_entry_name="Dockerfile",
        default_build_flags=["--quiet"],
    )
```

Register it in `factory.py:_default_providers()`.
