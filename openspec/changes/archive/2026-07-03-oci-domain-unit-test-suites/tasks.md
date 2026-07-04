## 1. Add domain unit tests

- [ ] 1.1 Add `test_types.py` tests for BuildContext cross-field validation, ContainerId construction, port type equality/hash.
- [ ] 1.2 Add `test_exceptions.py` tests: all OciError subclasses constructed, keyword-only context params accepted.
- [ ] 1.3 Add `test_enums.py` tests: Subcommand value checks, RuntimeKind/ContainerState enum members.
- [ ] 1.4 Add `test_result_checking.py` tests: each branch of check_cli_result (success, not-found, access-denied, other error).
- [ ] 1.5 Run `uv run pytest -q tests/unit/domain/` — green.