## Why

`ContainerListContract` and `ContainerListOutputParser` exist but T3/T4 (contract-suite real parsers) were never materialized as tests. Need a test that creates a contract suite and runs it against each real parser.

## What Changes

- Add `test_contract_suite_real_parsers.py` in `tests/conformance/` that creates the full contract suite and runs it against each real parser implementation.

## Capabilities

### Modified Capabilities

- `oci-test-contracts`: contract suites SHALL be runnable against each real parser.

## Impact

- **Code**: none.
- **Tests**: new `tests/conformance/test_contract_suite_real_parsers.py`.