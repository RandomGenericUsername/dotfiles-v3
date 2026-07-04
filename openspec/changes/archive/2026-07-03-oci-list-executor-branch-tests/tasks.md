## 1. Add branch coverage tests

- [ ] 1.1 In `tests/unit/adapters/test_unix_list_executor.py` add: `test_list_containers_all_filter`, `test_list_containers_latest_filter`, `test_list_containers_since_filter`, `test_list_containers_before_filter`, `test_builder_map_unknown_fallthrough`, `test_list_containers_empty_response`, `test_executor_teardown_error`.
- [ ] 1.2 Run `uv run pytest -q tests/unit/adapters/test_unix_list_executor.py` — green.