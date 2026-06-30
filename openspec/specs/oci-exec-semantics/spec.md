## ADDED Requirements

### Requirement: exec_container semantics are documented, not changed

`ContainerManager.exec_container()` behavior remains as-is: returns `ExecResult(returncode, stdout, stderr)` for any exit code; raises `ContainerNotFoundError` only when `is_not_found_error(stderr)` matches. The routing doc (ARCHITECTURE.md) is updated to clarify that `exec_container` does not call `_check_result`.

#### Scenario: exec_container returns non-zero without raising
- **WHEN** `exec_container("ctr1", ["false"])` is called (exit code 1)
- **THEN** returns `ExecResult(returncode=1, stdout="", stderr="")` (no exception)

#### Scenario: exec_container raises ContainerNotFoundError for missing container
- **WHEN** `exec_container("nonexistent", ["true"])` is called and stderr contains "No such container"
- **THEN** raises `ContainerNotFoundError("nonexistent")`

### Requirement: run() routing matrix is accurate

ARCHITECTURE.md routing table (L188-197) reflects the actual four branches:

| Condition | Transport | Output | Return |
|---|---|---|---|
| `detach=True` | `streaming.stream()` no callbacks | captured | `stdout.strip()` (container ID) |
| `effective_tty=True` | `pty_transport.execute_pty()` | → `output_stream` | `""` |
| `stream_output=True` & !TTY | `streaming.stream()` with callbacks | → `output_stream` | `""` |
| neither | `streaming.stream()` no callbacks | captured | `stdout.strip()` |

Note: `detach=True` uses `streaming.stream()`, not batch `transport.execute()`. The doc now matches code.