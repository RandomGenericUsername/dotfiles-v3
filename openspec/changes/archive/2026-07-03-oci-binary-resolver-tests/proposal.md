## Why

`tests/unit/domain/test_binary_resolver.py` covers happy path and error cases but lacks edge-case tests: empty `$PATH` component, `$PATHEXT` on Windows (marked skip), trailing separator, binary with no suffix. The `_resolve_from_path` helper is untested in isolation.

## What Changes

- Add edge-case tests for `BinaryResolver.resolve` and `_resolve_from_path`: empty string in PATH, PATH ending with separator, binary with `.exe` extension, file-not-found on first candidate but found on second.
- Add `test_resolve_from_path_empty_component` etc.

## Capabilities

### Modified Capabilities

- `oci-test-contracts`: binary resolver tests SHALL cover edge-case paths.

## Impact

- **Tests**: add ~6 test cases to `tests/unit/domain/test_binary_resolver.py`.
- **Code**: none.