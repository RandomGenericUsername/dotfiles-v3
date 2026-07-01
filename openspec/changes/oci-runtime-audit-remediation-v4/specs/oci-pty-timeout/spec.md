## ADDED Requirements

### Requirement: PtyTransport port requires output_stream

The `PtyTransport.execute_pty()` port method declares `output_stream: OutputStream` as a required keyword-only argument (no `| None`, no `= None` default). This matches the adapter (`CliPtyTransport.execute_pty`) and the R1 remediation. A caller programming to the port SHALL NOT be able to omit `output_stream`; the port contract must not be stricter than its adapter (no Liskov precondition violation).

#### Scenario: Port signature has no None default for output_stream
- **WHEN** the `PtyTransport.execute_pty` abstract signature is inspected
- **THEN** `output_stream` is annotated `OutputStream` (not `OutputStream | None`) and has no default value

#### Scenario: Adapter and port agree on required output_stream
- **WHEN** the `CliPtyTransport.execute_pty` signature is compared to the `PtyTransport.execute_pty` signature
- **THEN** both declare `output_stream: OutputStream` as required keyword-only

### Requirement: Transports check process.poll() before raising OperationTimeoutError post-read

After the pipe reader returns (EOF or cancellation) and before raising `OperationTimeoutError` on a fired deadline token, `CliTransport.execute()`, `CliStreamingTransport.stream()`, and `CliPtyTransport.execute_pty()` SHALL check `process.poll() is not None`. If the child has already exited (pipes delivered EOF), the transport SHALL return the collected `RawExecResult(process.returncode, stdout, stderr)` instead of raising. Only when the process is still running AND the deadline token is cancelled SHALL `OperationTimeoutError` be raised. This closes the race introduced by v2's timeout-aware poll loop where a completed operation was misreported as timed out.

#### Scenario: Completed operation not misreported as timeout
- **WHEN** a child process exits cleanly (closing its pipes, delivering EOF to the reader) and the `DeadlineCancellationToken` fires within the ~0.1s selector gap just before the post-read check
- **THEN** the transport returns `RawExecResult(0, stdout, stderr)` and does NOT raise `OperationTimeoutError`

#### Scenario: Still-running process with expired deadline still raises
- **WHEN** the child is still running (`process.poll() is None`) and the deadline token is cancelled
- **THEN** `OperationTimeoutError` is raised with `command` and `timeout` attached

### Requirement: CliContainerManager does not forward None output_stream to a PTY transport

`CliContainerManager` SHALL construct with a non-`None` `output_stream` for TTY runs, OR guard before calling `execute_pty` and raise a clean `OciError("output_stream required for TTY run")` when `output_stream is None`. The manager MUST NOT forward `None` to `CliPtyTransport.execute_pty`, which would raise `AttributeError: 'NoneType' object has no attribute 'write'` from inside the selector thread.

#### Scenario: TTY run without output_stream raises OciError up front
- **WHEN** `CliContainerManager` constructed without `output_stream` calls `run(config)` with `config.auto_tty=True` (or `effective_tty` truthy)
- **THEN** `OciError` is raised with a message mentioning `output_stream`, before any subprocess is started

#### Scenario: TTY run with output_stream succeeds
- **WHEN** `CliContainerManager` constructed with an `OutputStream` calls `run(config)` with TTY enabled
- **THEN** `execute_pty` is invoked and the run completes without an `AttributeError`

### Requirement: CliTransport.execute kills the child in finally on unexpected exceptions

`CliTransport.execute()` SHALL ensure the child process is killed and reaped if any exception (selector error, `ProcessPipeReader.from_process` failure, etc.) occurs between `subprocess.Popen` and the wait loop. The `finally` block SHALL do `if process is not None and not reaped: process.kill(); process.wait()` (matching `CliStreamingTransport`). This prevents orphaned/zombie children when an exception precedes `wait()`.

#### Scenario: from_process failure does not leak the child
- **WHEN** `CliTransport.execute()` starts a `Popen` and `ProcessPipeReader.from_process(process)` raises `TypeError`
- **THEN** the `finally` block kills the process and the child is reaped (no zombie)
