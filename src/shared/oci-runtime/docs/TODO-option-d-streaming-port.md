# Option D: Split Streaming Into a Separate Port

## Motivation

The `Transport` port currently conflates two concerns: batch command execution and streaming output. The `execute()` method has `stream` and `on_output` flags that toggle between `subprocess.run` (simple, blocking) and a Popen-based streaming loop (complex, threaded). This violates the **Interface Segregation Principle** — callers that only need batch execution should not depend on a method with streaming concerns.

Status quo in `ports/transport.py`:

```python
class Transport(ABC):
    @abstractmethod
    def execute(
        self,
        command: list[str],
        *,
        timeout: int | None = None,
        input_data: bytes | None = None,
        stream: bool = False,           # <-- streaming concern
        on_output: Callable[[bytes, str], None] | None = None,  # <-- streaming concern
    ) -> ExecResult: ...

    @abstractmethod
    def execute_pty(
        self,
        command: list[str],
        on_output: Callable[[bytes], None] | None = None,
    ) -> subprocess.CompletedProcess: ...
```

## Proposed Port Separation

### New port: `ports/streaming.py`

```python
from abc import ABC, abstractmethod
from typing import Callable


class StreamingTransport(ABC):
    """Execute a command and stream its output in real-time."""

    @abstractmethod
    def stream(
        self,
        command: list[str],
        *,
        timeout: int | None = None,
        input_data: bytes | None = None,
        on_stdout: Callable[[bytes], None] | None = None,
        on_stderr: Callable[[bytes], None] | None = None,
    ) -> int:
        """Execute command, call callbacks as output arrives.
        Returns the process exit code.
        """
```

### Simplified `Transport` port

```python
class Transport(ABC):
    @abstractmethod
    def execute(
        self,
        command: list[str],
        *,
        timeout: int | None = None,
        input_data: bytes | None = None,
    ) -> ExecResult: ...

    @abstractmethod
    def get_runtime_binary(self) -> str: ...

    @abstractmethod
    def probe(self) -> bool: ...
```

The PTY concern also moves to its own port (`PtyTransport` or is merged into `StreamingTransport` with a `use_pty: bool` flag).

## Implementation Steps

### Phase 1: Define the new port

1. Create `ports/streaming.py` with `StreamingTransport` ABC.
2. Remove `stream`, `on_output` parameters from `Transport.execute()`.
3. Remove `execute_pty` from `Transport` ABC.
4. Update all imports and references across the codebase.

### Phase 2: Adapter implementations

1. **`CliTransport`** — simplifies to only batch `subprocess.run`. No more `Popen`, threading, or `ProcessPipeReader`. Becomes a ~50-line adapter.
2. **`CliStreamingTransport`** — new adapter in `adapters/transport/streaming.py`. Uses `ProcessPipeReader` and handles stdin threading. Has the PTY path as a private method or delegates to `run_pty`.
3. **`execute_pty`** — either becomes part of `CliStreamingTransport` (with a `pty: bool = False` parameter) or stays as its own adapter.

### Phase 3: Update consumers

| Consumer | Current call | New call |
|---|---|---|
| `CliContainerManager.run()` (tty) | `transport.execute_pty(cmd)` | `streaming.stream(cmd, use_pty=True)` |
| `CliContainerManager.run()` (stream) | `transport.execute(cmd, stream=True)` | `streaming.stream(cmd)` |
| `CliContainerManager.run()` (batch) | `transport.execute(cmd)` | `transport.execute(cmd)` |
| `CliContainerManager.logs()` | `transport.execute(cmd, on_output=...)` | `streaming.stream(cmd, on_stdout=...)` |
| `CliImageManager.build()` | `transport.execute(cmd, input_data=...)` | `transport.execute(cmd, input_data=...)` |
| `CliBaseManager._check_result()` | `result.returncode` | unchanged |
| `CliRuntime.version()` | `transport.execute(cmd)` | `transport.execute(cmd)` |
| All `*Manager.list()`, `inspect()`, etc. | `transport.execute(cmd)` | `transport.execute(cmd)` |

### Phase 4: Update factory wiring

`RuntimeFactoryConfig` gains:
```python
streaming_transport_cls: type[StreamingTransport] | None = None
```

`RuntimeFactory.create()` constructs both a `Transport` and a `StreamingTransport` from the same Popen lifecycle.

`CliRuntime.__init__` gains:
```python
self._streamer = streaming_transport  # injected alongside transport
```

`CliContainerManager.__init__` gains a `StreamingTransport` reference:
```python
class CliContainerManager(CliBaseManager[ContainerParser], ContainerManager):
    def __init__(
        self,
        transport: Transport,
        parser: ContainerParser,
        caps: RuntimeCapabilities,
        streaming: StreamingTransport,  # new
    ):
        super().__init__(transport, parser, caps)
        self._streaming = streaming

    def run(self, config: RunConfig) -> str:
        if config.effective_tty:
            result = self._streaming.stream(cmd, use_pty=True)
            ...
        if config.stream_output:
            result = self._streaming.stream(cmd)
            ...
```

`DockerRuntimeProvider` and `PodmanRuntimeProvider` construct both managers:
```python
def create_managers(self, transport, streaming, caps) -> Managers:
    return Managers(
        image_manager=CliImageManager(transport, parsers.image_parser, caps),
        container_manager=CliContainerManager(
            transport, parsers.container_parser, caps, streaming=streaming,
        ),
        volume_manager=CliVolumeManager(transport, parsers.volume_parser, caps),
        network_manager=CliNetworkManager(transport, parsers.network_parser, caps),
    )
```

### Phase 5: Clean up

1. Remove `stream`, `on_output` from `Transport.execute()`.
2. Remove `execute_pty` from `Transport`.
3. Remove the `_process_reader.py` import from `cli.py`.
4. Update tests:
   - `TestCliTransport` — removes streaming-specific test cases (move to `TestCliStreamingTransport`)
   - `TestExecuteStreaming` — becomes `TestCliStreamingTransport`
   - `TestProcessPipeReader` — stays, tests the reader independently

## Questions to Resolve

1. **Should PTY be a flag on `StreamingTransport` or its own port?**
   - Flag: simpler API, but `stream(use_pty=True)` has different semantics (merges stdout/stderr, uses PTY fd instead of pipes)
   - Own port: `PtyTransport.execute_pty()` — cleaner separation, but adds another injection point
   - Recommended: flag on `StreamingTransport` for now (`use_pty: bool = False`), extract later if complexity grows

2. **Does `ProcessPipeReader` stay or move into `StreamingTransport`?**
   - It should move into the `StreamingTransport` adapter as a private detail — no external consumer needs it directly

3. **Who owns the process lifecycle (Popen acquire/reap)?**
   - Currently `Transport.execute()` owns it for streaming
   - After separation, `StreamingTransport.stream()` owns it — Popen creation, reaping, and pipe cleanup
   - `Transport.execute()` uses `subprocess.run()` — no Popen needed

## Risks

- **Breaking change**: consumers that pass `stream=True` or `on_output=` must switch to the new port
- **Complexity**: more moving parts in the composition root (factory now wires two transports)
- **Over-engineering**: if the only streaming consumer is `logs()` and `run()`, a separate port may be excessive — consider a simpler `StreamingTransport` that lives entirely inside `CliContainerManager` instead of being a standalone port

## Decision Gate

Before starting, answer:

- [ ] Are there (or will there be) non-CLI streaming implementations (e.g., HTTP API, WebSocket, gRPC)?
  - **Yes** → full port separation is justified
  - **No** → keep streaming as a private concern of `CliContainerManager` instead of a public port

If the answer is "No", a lighter alternative: move the streaming logic entirely into `CliContainerManager` (it already has the PTY path) and keep `Transport` purely batch. This halves the refactor scope.
