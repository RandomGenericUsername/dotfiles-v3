## MODIFIED Requirements

### Requirement: PipeReader port abstracts fd-based subprocess/PTY output reading

The `PipeReader` port in `ports/pipe_reader.py` defines the interface for reading output from subprocess pipes and PTY master fds without blocking on partial reads. The `read()` ABC declares `on_stdout` and `on_stderr` callback parameters (not `on_primary`/`on_secondary`), matching the keyword names callers use. There is no `**kwargs` shim — the port is substitutable: any `PipeReader` implementation honoring the ABC signature can replace `ProcessPipeReader`.

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
        on_stdout: Callable[[bytes], None] | None = None,
        on_stderr: Callable[[bytes], None] | None = None,
        cancel_token: CancellationToken | None = None,
    ) -> tuple[list[bytes], list[bytes]]: ...
```

#### Scenario: Callers use on_stdout/on_stderr keyword names
- **WHEN** `CliContainerManager.logs(follow=True)` and `CliStreamingTransport.stream()` call `reader.read(...)`
- **THEN** they pass `on_stdout=` and `on_stderr=` keyword arguments that exist on the ABC

#### Scenario: A substitute PipeReader impl works without a kwargs shim
- **WHEN** a test double implements `read(self, on_stdout=None, on_stderr=None, cancel_token=None)` (no `**kwargs`) is passed where `ProcessPipeReader` was used
- **THEN** callers invoking `reader.read(on_stdout=cb, on_stderr=cb2)` succeed with no `TypeError`

### Requirement: ProcessPipeReader is the production adapter; strict mode rejects non-fd inputs

`ProcessPipeReader` in `ports/pipe_reader.py` implements `PipeReader`. Its `from_process()` method validates **both** `process.stdout.fileno()` and `process.stderr.fileno()` and raises `TypeError` (the documented contract) if either is unavailable — including when `process.stderr is None` (e.g. `stderr=DEVNULL`/`stderr=None`), which previously raised `AttributeError`. The `isinstance(fd, int)` check in `_read_fd` and the `fileobj.read()` fallback branch remain deleted — only `os.read(fd, n)` is used. `_read_fd` narrows its `except OSError` to treat only `errno.EIO` (PTY master drained) as EOF; any other `OSError` (e.g. `EBADF`, `ECONNRESET`) is re-raised so real I/O errors are not silently swallowed as clean EOF.

#### Scenario: Real subprocess pipes succeed
- **WHEN** `PipeReader.from_process(subprocess.Popen(..., stdout=PIPE, stderr=PIPE))` is called
- **THEN** it returns a `ProcessPipeReader` with valid integer fds; `read()` returns accumulated output

#### Scenario: stderr=None raises TypeError (not AttributeError)
- **WHEN** `ProcessPipeReader.from_process()` is called with a process whose `stderr` is `None`
- **THEN** `TypeError` is raised (matching the documented contract), not `AttributeError: 'NoneType' object has no attribute 'fileno'`

#### Scenario: Non-fd stdout raises TypeError
- **WHEN** a test passes a `BytesIO` or `MagicMock` where `stdout.fileno()` is unavailable
- **THEN** `ProcessPipeReader.from_process()` raises `TypeError("ProcessPipeReader requires real fds...")`

#### Scenario: EIO on PTY master is treated as EOF
- **WHEN** `_read_fd` on a PTY master fd raises `OSError(errno.EIO)`
- **THEN** it returns `b""` (clean EOF), matching the documented PTY-drain behavior

#### Scenario: Non-EIO OSError is re-raised
- **WHEN** `_read_fd` raises `OSError(errno.EBADF)` (closed fd) after `select` fires
- **THEN** the `OSError` propagates (it is NOT silently treated as EOF)
