## 1. Rewrite logs --follow

- [ ] 1.1 In `src/oci_runtime/adapters/managers/container.py`, replace raw-thread logs follow with `_AsyncStreamReader` + `_CancelContext`. Import from `oci_runtime.adapters.transport`.
- [ ] 1.2 Add `timeout` parameter to `logs` method signature.
- [ ] 1.3 Update `test_container_logs_follow` for new timeout behavior.

## 2. Verify

- [ ] 2.1 Run `uv run pytest -q tests/unit/adapters/test_cli_container_manager.py` — green.
- [ ] 2.2 Run `uv run ruff check .` — green.