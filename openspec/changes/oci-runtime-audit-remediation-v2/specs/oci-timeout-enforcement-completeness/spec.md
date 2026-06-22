## ADDED Requirements

### Requirement: All transports enforce timeout through the full process lifecycle

After `ProcessPipeReader.read()` returns (pipes drained), all three transports (`CliTransport`, `CliStreamingTransport`, `CliPtyTransport`) SHALL use a poll-loop `process.wait(timeout=0.5)` pattern that checks `effective_token.is_cancelled` between iterations. This ensures the configured timeout is enforced even when a process closes its pipes but stays alive. On deadline expiry, the process SHALL be killed and `OperationTimeoutError` raised. On user cancellation, the process SHALL be killed and `RawExecResult(returncode=-1, ...)` returned.

#### Scenario: Process closes pipes but stays alive — timeout fires
- **WHEN** a process closes stdout and stderr but does not exit, and a timeout is set
- **THEN** the poll loop detects the deadline cancellation, kills the process, and raises `OperationTimeoutError`

#### Scenario: Process closes pipes but stays alive — user cancels
- **WHEN** a process closes stdout and stderr but does not exit, and the user cancels via `cancel_token`
- **THEN** the poll loop detects the cancellation, kills the process, and returns `RawExecResult(returncode=-1, ...)`

#### Scenario: Process exits normally — no timeout
- **WHEN** a process exits normally before the timeout
- **THEN** the poll loop's `process.wait(timeout=0.5)` returns the exit code, and no `OperationTimeoutError` is raised

#### Scenario: CliTransport.execute raises OperationTimeoutError on timeout
- **WHEN** `CliTransport.execute(command, timeout=0.1)` is called with a command that hangs
- **THEN** `OperationTimeoutError` is raised, and `except OciError` catches it

#### Scenario: CliTransport.execute returns returncode=-1 on cancellation
- **WHEN** `CliTransport.execute(command, cancel_token=pre_cancelled_token)` is called
- **THEN** `RawExecResult(returncode=-1, ...)` is returned without raising
