## ADDED Requirements

### Requirement: PipeReader port abstracts fd-based subprocess/PTY output reading

The `PipeReader` port in `ports/pipe_reader.py` defines the interface for reading output from subprocess pipes and PTY master fds without blocking on partial reads.

```python
class PipeReader(ABC):
    @abstractmethod
    @classmethod
    def from_process(cls, process) -> "PipeReader": ...
    
    @abstractmethod
    @classmethod
    def from_fds(cls, primary_fd: int, secondary_fd: int) -> "PipeReader": ...
    
    @abstractmethod
    def read(
        self,
        on_primary: Callable[[bytes], None] | None = None,
        on_secondary: Callable[[bytes], None] | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> tuple[list[bytes], list[bytes]]: ...
```

### Requirement: ProcessPipeReader is the production adapter; strict mode rejects non-fd inputs

`ProcessPipeReader` in `adapters/_process_reader.py` implements `PipeReader`. Its `from_process()` method **raises `TypeError`** if `process.stdout.fileno()` is unavailable (e.g. mocks using `BytesIO`). The `isinstance(fd, int)` check in `_read_fd` and the `fileobj.read()` fallback branch are deleted — only `os.read(fd, n)` is used.

#### Scenario: Real subprocess pipes succeed
- **WHEN** `PipeReader.from_process(subprocess.Popen(..., stdout=PIPE, stderr=PIPE))` is called
- **THEN** it returns a `ProcessPipeReader` with valid integer fds; `read()` returns accumulated output

#### Scenario: PTY master fd + stderr pipe succeeds
- **WHEN** `PipeReader.from_fds(master_fd, stderr_fd)` is called with integer fds from `pty.openpty()` and `process.stderr.fileno()`
- **THEN** it returns a `ProcessPipeReader` that reads both fds via `os.read`

#### Scenario: Non-fd input raises TypeError (strict)
- **WHEN** a test passes a `BytesIO` or `MagicMock` where `fileno()` is unavailable
- **THEN** `ProcessPipeReader.from_process()` raises `TypeError("ProcessPipeReader requires real fds...")`

#### Scenario: Transport receives PipeReader via factory injection
- **WHEN** `RuntimeFactory` creates a transport
- **THEN** it provides a `pipe_reader_factory` that produces `ProcessPipeReader` instances; the transport only imports `ports.pipe_reader.PipeReader`