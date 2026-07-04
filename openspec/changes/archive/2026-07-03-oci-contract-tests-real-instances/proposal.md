## Why

`ContractTestCase` abstract class exists but no test instantiates it with a real parser class. T1/T2 from v4 requirements were never concretized into tests.

## What Changes

- Add `test_contract_real_parsers.py` that creates a `ContainerListContract` test case bound to each real parser (Docker, Podman, Lima) and asserts it passes.

## Capabilities

### Modified Capabilities

- `oci-test-contracts`: contract test cases SHALL be instantiated with each real parser in a conformance-style test.

## Impact

- **Code**: none.
- **Tests**: new `tests/conformance/test_contract_real_parsers.py`.