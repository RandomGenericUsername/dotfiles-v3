## Why

`tests/unit/adapters/test_unix_list_executor.py` has 45% branch coverage — `_run_containers_list` with different filter states, `_BUILDER_MAP` fallthrough to `None`, empty-array vs null-list response handling, the `exit_stack`/`self._collect` error path.

## What Changes

- Add tests: `--all` / `--latest` / `--since` / `--before` filter branches, `_BUILDER_MAP` unknown builder fallthrough, empty `id_list` response, executor teardown error propagation.

## Capabilities

### Modified Capabilities

- `oci-test-contracts`: unix list executor tests SHALL exercise all filter branches and error paths.

## Impact

- **Code**: none.
- **Tests**: add ~8 test cases.