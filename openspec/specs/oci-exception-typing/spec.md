## Purpose

Exception typing and error hierarchy requirements for OCI runtime operations.
## Requirements
### Requirement: Generic manager failures SHALL raise entity-typed errors

`CliBaseManager._check_result` SHALL raise the manager's own entity-typed error for generic (non-not-found) failures, not `ContainerRuntimeError`. This ensures `except ImageError`, `except VolumeError`, and `except NetworkError` catch the failures of their respective managers. The hierarchy SHALL be:

- `CliImageManager` generic failure → `ImageError` subclass
- `CliVolumeManager` generic failure → `VolumeError` subclass
- `CliNetworkManager` generic failure → `NetworkError` subclass
- `CliContainerManager` generic failure → `ContainerRuntimeError` (unchanged)

#### Scenario: Image manager generic error is ImageError
- **WHEN** `docker image inspect --format json alpine` returns exit 1 with stderr `"Error: something broke"` (not a not-found pattern)
- **THEN** `ImageManager.inspect()` raises `ImageError` (or subclass), and `except ImageError` catches it

#### Scenario: Volume manager generic error is VolumeError
- **WHEN** `docker volume inspect --format json myvol` returns exit 1 with stderr `"Error: something broke"`
- **THEN** `VolumeManager.inspect()` raises `VolumeError` (or subclass), and `except VolumeError` catches it

#### Scenario: Network manager generic error is NetworkError
- **WHEN** `docker network inspect --format json mynet` returns exit 1 with stderr `"Error: something broke"`
- **THEN** `NetworkManager.inspect()` raises `NetworkError` (or subclass), and `except NetworkError` catches it

#### Scenario: Container manager generic error stays ContainerRuntimeError
- **WHEN** `docker run -d alpine` returns exit 125 with stderr `"Error response from daemon"`
- **THEN** `ContainerManager.run()` raises `ContainerRuntimeError` (unchanged behavior)

### Requirement: Timeouts SHALL raise OperationTimeoutError

`CliStreamingTransport.stream()` and `run_pty()` SHALL raise `OperationTimeoutError(OciError)` on timeout, not bare `subprocess.TimeoutExpired`. `OperationTimeoutError` is a new `OciError` subclass that carries the command and timeout duration. This ensures `except OciError` catches every error the module raises, as the architecture promises.

#### Scenario: Stream timeout raises OciError subclass
- **WHEN** `stream(["docker", "ps"], timeout=0.01)` exceeds the deadline
- **THEN** `OperationTimeoutError` is raised, and `except OciError` catches it

#### Scenario: PTY timeout raises OciError subclass
- **WHEN** `run_pty(["/bin/sleep", "5"], timeout=0.3)` exceeds the deadline
- **THEN** `OperationTimeoutError` is raised, and `except OciError` catches it

### Requirement: parse_json_list produces informative error for pretty-printed JSON

`parse_json_list` SHALL produce an informative error message when line-by-line NDJSON parsing fails, suggesting the user invoke the runtime with `--format '{{json .}}'` if the output is pretty-printed (multi-line). The message SHALL include both the failing line number/content AND the format-flag guidance.

#### Scenario: Pretty-printed JSON raises informative error
- **WHEN** `parse_json_list` receives `'{"id":\n  "abc"\n}'` (pretty-printed single object)
- **THEN** the raised `ParsingError.message` contains both `"line 1"` and `"pretty-printed"` and `"--format"`

#### Scenario: Valid NDJSON still parses
- **WHEN** `parse_json_list` receives `'{"id":"a"}\n{"id":"b"}'`
- **THEN** it returns `[{"id":"a"}, {"id":"b"}]` with no error

