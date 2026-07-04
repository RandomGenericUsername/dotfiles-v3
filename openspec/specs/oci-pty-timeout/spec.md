## Purpose

PTY transport timeout and error handling requirements.
## Requirements
### Requirement: PTY empty-command SHALL raise OciError not ContainerRuntimeError

`CliPtyTransport.execute_pty()` SHALL raise `OciError` (with `command=[]` attached) when `command` is an empty list. `ContainerRuntimeError` is a container-specific exception and SHALL NOT be raised from a generic transport port.

#### Scenario: Empty command raises OciError
- **WHEN** `pty_transport.execute_pty([], output_stream=stream)` is called
- **THEN** `OciError` raised with `message="Empty command list"`, `command=[]`, `exit_code=None`, `stderr=None`

#### Scenario: OciError formatted message includes empty command
- **WHEN** the `OciError` from empty command is formatted (str())
- **THEN** the message includes the `command=[]` (even though empty, it is represented)

### Requirement: PTY timeout SHALL raise OperationTimeoutError

`CliPtyTransport.execute_pty()` with `timeout=...` SHALL raise `OperationTimeoutError(OciError)` on deadline expiry, same as `CliTransport.execute()` and `CliStreamingTransport.stream()`. The timeout-aware poll loop (`process.wait(timeout=0.5)` checking `cancel_token`) SHALL be present and functional.

#### Scenario: PTY deadline raises OperationTimeoutError
- **WHEN** `execute_pty(cmd, timeout=0.1)` and the process runs >0.1s
- **THEN** `OperationTimeoutError` raised with `command=cmd`, `timeout=0.1`

### Requirement: PTY stderr separation SHALL be preserved

The architecture decision (PTY for stdout, PIPE for stderr) SHALL be maintained. `_check_result` SHALL inspect stderr for not-found patterns in PTY mode.

#### Scenario: PTY mode not-found detection works
- **WHEN** `run(config, effective_tty=True)` and the CLI emits "No such image: foo" to stderr
- **THEN** `ImageNotFoundError("foo")` is raised (via `_check_result` on the PTY result's stderr)

### Requirement: PTY transport handles Popen invariant violations with typed errors

`CliPtyTransport.execute_pty` SHALL NOT use `assert` for production invariants. When `subprocess.Popen(stderr=subprocess.PIPE)` returns `process.stderr is None`, the adapter SHALL kill the process and raise `OciError` with a diagnostic message naming the violated invariant. This replaces `AttributeError` leakage under `python -O`.

#### Scenario: stderr=None raises OciError not AttributeError
- **WHEN** `subprocess.Popen` returns a process whose `stderr` is `None`
- **THEN** `CliPtyTransport.execute_pty` raises `OciError` containing "stderr=None" in the message (not `AttributeError`)

#### Scenario: Normal execution still works
- **WHEN** `subprocess.Popen` returns a process whose `stderr` is a valid pipe
- **THEN** the transport executes normally

