## Context

`pty.py:54` uses bare `assert` for a production invariant. Stripped under `-O`; leaks `AttributeError`.

## Goals / Non-Goals

**Goals:** Typed `OciError` with diagnostic message when `Popen(stderr=PIPE)` returns `stderr=None`.
**Non-Goals:** Changing `Popen` invocation (stderr=PIPE is correct).

## Decisions

Replace `assert process.stderr is not None` with:
```python
if process.stderr is None:
    process.kill()
    raise OciError("CliPtyTransport.execute_pty: subprocess.Popen returned stderr=None despite stderr=PIPE — internal invariant violated")
```
Kill the process before raising to avoid a zombie.

## Risks / Trade-offs

- None. The invariant never fires in practice (Popen with stderr=PIPE always returns a pipe); the guard is defensive.