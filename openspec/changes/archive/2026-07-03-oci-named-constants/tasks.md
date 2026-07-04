## 1. Replace inlined magic numbers with named constants

- [ ] 1.1 In `src/oci_runtime/adapters/transport/cli.py`, add `_STDIN_JOIN_TIMEOUT = 5.0` at module scope; replace `stdin_thread.join(timeout=5)` at `:129` with `stdin_thread.join(timeout=_STDIN_JOIN_TIMEOUT)`.
- [ ] 1.2 In `src/oci_runtime/adapters/transport/streaming.py`, add `_STDIN_JOIN_TIMEOUT = 5.0`; replace `timeout=5` at `:84,94` with `timeout=_STDIN_JOIN_TIMEOUT`.
- [ ] 1.3 In `src/oci_runtime/adapters/managers/container.py`, add `_DEFAULT_STOP_TIMEOUT_SECONDS = 10` (note: if `oci-timeout-precision` lands first, this constant is the `default=` arg to `cli_seconds`; otherwise it replaces the bare `"10"` strings at `:213,226`).
- [ ] 1.4 In `src/oci_runtime/ports/pipe_reader.py`, add `_READ_CHUNK = 4096`; replace `4096` at `:56` with `_READ_CHUNK`.
- [ ] 1.5 Run `uv run pytest -q` — green.
- [ ] 1.6 Run `uv run ruff check .` — green.