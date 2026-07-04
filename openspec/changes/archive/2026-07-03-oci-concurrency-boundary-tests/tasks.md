## 1. Add concurrency tests

- [ ] 1.1 Create `tests/unit/adapters/test_transport_concurrency.py` with `test_subprocess_runner_concurrent_calls`, `test_cancel_context_broadcast`, `test_async_stream_reader_timeout_yields_partial`, `test_async_stream_reader_stream_closed`.
- [ ] 1.2 Run `uv run pytest -q tests/unit/adapters/test_transport_concurrency.py` — green.