## 1. Replace bare assert with typed guard

- [ ] 1.1 In `src/oci_runtime/adapters/transport/pty.py:54`, replace `assert process.stderr is not None` with an `if process.stderr is None:` block that kills the process and raises `OciError("CliPtyTransport.execute_pty: subprocess.Popen returned stderr=None despite stderr=PIPE — internal invariant violated")`.
- [ ] 1.2 Add `test_pty_raises_typed_error_when_stderr_is_none` to `tests/unit/adapters/test_cli_pty.py`: patch `subprocess.Popen` to return process with `stderr=None`, assert `OciError` raised (not `AttributeError`), assert message contains "stderr=None".
- [ ] 1.3 Run `uv run pytest -q tests/unit/adapters/test_cli_pty.py` — green.
- [ ] 1.4 Run `uv run ruff check src/oci_runtime/adapters/transport/pty.py` — green.