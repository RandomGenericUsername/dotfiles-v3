## 1. Create transport package

- [ ] 1.1 Create `src/oci_runtime/adapters/transport/__init__.py` with re-exports.
- [ ] 1.2 Create `src/oci_runtime/adapters/transport/runner.py` with `_SubprocessRunner`.
- [ ] 1.3 Create `src/oci_runtime/adapters/transport/cancel.py` with `_CancelContext` using `threading.Event`.
- [ ] 1.4 Create `src/oci_runtime/adapters/transport/stream.py` with `_AsyncStreamReader` supporting timeout.

## 2. Migrate Lima adapter

- [ ] 2.1 In `src/oci_runtime/adapters/managers/transport_lima.py`, replace inline class definitions with imports from `oci_runtime.adapters.transport`.
- [ ] 2.2 Run lima-specific tests: `uv run pytest -q tests/unit/adapters/test_lima_manager.py` — green.

## 3. Migrate Docker adapter if using same primitives

- [ ] 3.1 If Docker manager uses `_SubprocessRunner`-like patterns, migrate to import.
- [ ] 3.2 Run full test suite: `uv run pytest -q` — green.

## 4. Verify

- [ ] 4.1 `uv run ruff check .` — green.