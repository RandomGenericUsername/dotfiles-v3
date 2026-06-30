## MODIFIED Requirements

### Requirement: PTY empty-command raises OciError not ContainerRuntimeError

`CliPtyTransport.execute_pty()` raises `OciError` (with `command=[]` attached) when `command` is an empty list. `ContainerRuntimeError` is a container-specific exception and must not be raised from a generic transport port.

#### Scenario: Empty command raises OciError
- **WHEN** `pty_transport.execute_pty([], output_stream=stream)` is called
- **THEN** `OciError` raised with `message="Empty command list"`, `command=[]`, `exit_code=None`, `stderr=None`

#### Scenario: OciError formatted message includes empty command
- **WHEN** the `OciError` from empty command is formatted (str())
- **THEN** the message includes the `command=[]` (even though empty, it is represented)

### Requirement: PTY timeout raises OperationTimeoutError

`CliPtyTransport.execute_pty()` with `timeout=...` raises `OperationTimeoutError(OciError)` on deadline expiry, same as `CliTransport.execute()` and `CliStreamingTransport.stream()`. The timeout-aware poll loop (`process.wait(timeout=0.5)` checking `cancel_token`) is present and functional.

#### Scenario: PTY deadline raises OperationTimeoutError
- **WHEN** `execute_pty(cmd, timeout=0.1)` and the process runs >0.1s
- **THEN** `OperationTimeoutError` raised with `command=cmd`, `timeout=0.1`

### Requirement: PTY stderr separation preserved

The architecture decision (PTY for stdout, PIPE for stderr) is maintained. `_check_result` inspects stderr for not-found patterns in PTY mode.

#### Scenario: PTY mode not-found detection works
- **WHEN** `run(config, effective_tty=True)` and the CLI emits "No such image: foo" to stderr
- **THEN** `ImageNotFoundError("foo")` is raised (via `_check_result` on the PTY result's stderr)