## 1. Add cli_seconds helper and replace call sites

- [ ] 1.1 Create `src/oci_runtime/adapters/managers/_timeouts.py` with `cli_seconds(timeout: float | None, default: int) -> str` using `math.ceil` and `max(1, ...)`.
- [ ] 1.2 Update `src/oci_runtime/adapters/managers/container.py:213` — replace `str(int(timeout)) if timeout is not None else "10"` with `cli_seconds(timeout, default=10)`.
- [ ] 1.3 Update `src/oci_runtime/adapters/managers/container.py:226` — same replacement for `restart`.
- [ ] 1.4 Add `tests/unit/adapters/test_helpers.py::TestCliSeconds` covering: `1.9→"2"`, `1.0→"1"`, `1.01→"2"`, `None→"10"`, `0.5→"1"`.
- [ ] 1.5 Run `uv run pytest -q tests/unit/adapters/test_helpers.py tests/unit/adapters/test_cli_container_manager.py` — green.
- [ ] 1.6 Run `uv run ruff check src/oci_runtime/adapters/managers/_timeouts.py` — green.