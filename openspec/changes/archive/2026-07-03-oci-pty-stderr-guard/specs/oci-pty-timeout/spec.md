## ADDED Requirements

### Requirement: PTY transport handles Popen invariant violations with typed errors

`CliPtyTransport.execute_pty` SHALL NOT use `assert` for production invariants. When `subprocess.Popen(stderr=subprocess.PIPE)` returns `process.stderr is None`, the adapter SHALL kill the process and raise `OciError` with a diagnostic message naming the violated invariant. This replaces `AttributeError` leakage under `python -O`.

#### Scenario: stderr=None raises OciError not AttributeError
- **WHEN** `subprocess.Popen` returns a process whose `stderr` is `None`
- **THEN** `CliPtyTransport.execute_pty` raises `OciError` containing "stderr=None" in the message (not `AttributeError`)

#### Scenario: Normal execution still works
- **WHEN** `subprocess.Popen` returns a process whose `stderr` is a valid pipe
- **THEN** the transport executes normally