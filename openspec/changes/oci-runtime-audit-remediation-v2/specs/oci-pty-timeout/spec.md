## MODIFIED Requirements

### Requirement: execute_pty timeout uses OperationTimeoutError

`PtyTransport.execute_pty()` (renamed from `run_pty()`) must raise `OperationTimeoutError(OciError)` on timeout, not `subprocess.TimeoutExpired`. This keeps timeouts within the `OciError` hierarchy so `except OciError` catches them.

#### Scenario: PTY timeout raises OperationTimeoutError
- **WHEN** `execute_pty(["/bin/sleep", "5"], timeout=0.3)` exceeds the deadline
- **THEN** `OperationTimeoutError` is raised, and `except OciError` catches it

### Requirement: Stream timeout uses OperationTimeoutError

`CliStreamingTransport.stream()` must raise `OperationTimeoutError(OciError)` on deadline expiry, not `subprocess.TimeoutExpired`.

#### Scenario: Stream timeout raises OperationTimeoutError
- **WHEN** `stream(["docker", "ps"], timeout=0.01)` exceeds the deadline
- **THEN** `OperationTimeoutError` is raised, and `except OciError` catches it

## ADDED Requirements

### Requirement: CliTransport.execute timeout uses OperationTimeoutError

`CliTransport.execute()` must raise `OperationTimeoutError(OciError)` on deadline expiry, using the same poll-loop `process.wait(timeout=...)` pattern as the streaming and PTY transports. The timeout must be enforced through the full process lifecycle, including after pipes are drained.

#### Scenario: Execute timeout raises OperationTimeoutError
- **WHEN** `execute(["sleep", "30"], timeout=0.1)` exceeds the deadline
- **THEN** `OperationTimeoutError` is raised, and `except OciError` catches it

#### Scenario: Execute cancellation returns returncode=-1
- **WHEN** `execute(cmd, cancel_token=pre_cancelled_token)` is called
- **THEN** `RawExecResult(returncode=-1, ...)` is returned without raising

### Requirement: run() passes timeout through to execute_pty and stream

`CliContainerManager.run()` must pass `config.timeout` to both `pty_transport.execute_pty(timeout=config.timeout)` and `streaming.stream(timeout=config.timeout)`. This ensures the user-configured timeout is enforced regardless of TTY mode.

#### Scenario: run with TTY passes timeout to execute_pty
- **WHEN** `run(config)` is called with `tty=True` and `timeout=30.0`
- **THEN** `execute_pty()` receives `timeout=30.0`

#### Scenario: run without TTY passes timeout to stream
- **WHEN** `run(config)` is called with `tty=False` and `timeout=30.0`
- **THEN** `stream()` receives `timeout=30.0`
