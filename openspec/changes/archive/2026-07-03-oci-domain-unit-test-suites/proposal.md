## Why

No domain-layer unit test suite exists (only adapter tests). Domain types (`BuildContext`, `ContainerId`, port data classes) and enums are exercised only transitively through adapter tests. Separate domain suites make TDD for layering changes possible and catch regressions faster.

## What Changes

- Create `tests/unit/domain/` with test files for each domain module: `test_types.py`, `test_exceptions.py`, `test_enums.py`, `test_result_checking.py`, `test_binary_resolver.py`.
- Some already exist; fill gaps.

## Capabilities

### Modified Capabilities

- `oci-test-contracts`: each domain module SHALL have a corresponding unit test file.

## Impact

- **Code**: none.
- **Tests**: fill ~3 new test files, add missing cases to existing ones.