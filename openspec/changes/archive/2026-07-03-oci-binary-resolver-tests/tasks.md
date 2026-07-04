## 1. Add edge-case tests

- [ ] 1.1 In `tests/unit/domain/test_binary_resolver.py` add: `test_resolve_from_path_empty_component`, `test_resolve_from_path_trailing_separator`, `test_resolve_with_pathext`, `test_second_candidate_found`, `test_resolve_from_path_empty_path`.
- [ ] 1.2 Run `uv run pytest -q tests/unit/domain/test_binary_resolver.py` — green.