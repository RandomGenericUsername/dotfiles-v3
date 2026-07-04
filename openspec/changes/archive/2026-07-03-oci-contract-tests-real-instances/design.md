## Context

ContractTestCase exists abstractly. T1/T2 never materialized.

## Goals / Non-Goals

**Goals:** Concrete contract test for each real parser.
**Non-Goals:** CI conformance run (needs real CLI).

## Decisions

Add `test_contract_real_parsers.py` creating `ContainerListContract(...)` for each parser. Mark `@pytest.mark.slow`.

## Risks / Trade-offs

- None.