## ADDED Requirements

### Requirement: run_pty accepts a timeout
`run_pty()` SHALL accept a `timeout: float | None` parameter (default `None`). When `timeout` is `None`, behavior is unchanged (no deadline). When `timeout` is set, `run_pty()` SHALL enforce a wall-clock deadline: if the command has not completed within `timeout` seconds, the process MUST be killed and `subprocess.TimeoutExpired(command, timeout)` MUST be raised.

#### Scenario: timeout raises on hanging command
- **WHEN** `run_pty(["/bin/sleep", "5"], timeout=0.3)` is called
- **THEN** within approximately 0.3 seconds the function raises `subprocess.TimeoutExpired`

#### Scenario: timeout=None never raises on quick command
- **WHEN** `run_pty(["/bin/echo", "hi"])` is called without a timeout
- **THEN** the function returns a `CompletedProcess` with `returncode=0`

#### Scenario: quick command completes within timeout
- **WHEN** `run_pty(["/bin/echo", "hi"], timeout=5)` is called
- **THEN** the function returns a `CompletedProcess` with `returncode=0` and does not raise

### Requirement: run_pty kills the process on timeout
When `run_pty()` times out, it MUST kill the child process and reap it (`process.wait()`) before raising, so no zombie process remains.

#### Scenario: no zombie after timeout
- **WHEN** `run_pty(["/bin/sleep", "5"], timeout=0.3)` raises `TimeoutExpired`
- **THEN** the child process has been killed and reaped (no zombie)
