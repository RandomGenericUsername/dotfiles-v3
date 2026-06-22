## MODIFIED Requirements

### Requirement: run_pty timeout uses OperationTimeoutError

`run_pty()` must raise `OperationTimeoutError(OciError)` on timeout, not `subprocess.TimeoutExpired`. This keeps timeouts within the `OciError` hierarchy so `except OciError` catches them.

#### Scenario: PTY timeout raises OperationTimeoutError
- **WHEN** `run_pty(["/bin/sleep", "5"], timeout=0.3)` exceeds the deadline
- **THEN** `OperationTimeoutError` is raised, and `except OciError` catches it

### Requirement: Stream timeout uses OperationTimeoutError

`CliStreamingTransport.stream()` must raise `OperationTimeoutError(OciError)` on deadline expiry, not `subprocess.TimeoutExpired`.

#### Scenario: Stream timeout raises OperationTimeoutError
- **WHEN** `stream(["docker", "ps"], timeout=0.01)` exceeds the deadline
- **THEN** `OperationTimeoutError` is raised, and `except OciError` catches it
