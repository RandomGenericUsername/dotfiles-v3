## Why

`adapters/transport/pty.py:54` uses `assert process.stderr is not None` before `process.stderr.fileno()`. Under `python -O`, asserts are stripped; production runs leak `AttributeError: 'NoneType' object has no attribute 'fileno'` instead of a typed contract error.

## What Changes

- Replace `assert process.stderr is not None` with an explicit guard that kills the process and raises `OciError` with a diagnostic message.

## Capabilities

### Modified Capabilities

- `oci-pty-timeout`: `CliPtyTransport.execute_pty` SHALL raise `OciError` (not `AttributeError`) when `subprocess.Popen` returns `stderr=None` despite `stderr=PIPE`.
- `oci-exception-typing`: bare `assert` on production invariants in adapter code SHALL be replaced with typed guards.

## Impact

- **Code**: one block in `adapters/transport/pty.py:54`.
- **Tests**: one test patching `Popen` to return `stderr=None`, asserting `OciError` not `AttributeError`.
- **Risk**: none — strictly tighter error contract.