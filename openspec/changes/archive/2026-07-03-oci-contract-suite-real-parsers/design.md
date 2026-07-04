## Context

T3/T4 never materialized. Need contract-suite-level tests.

## Goals / Non-Goals

**Goals:** Contract suite run against each real parser.
**Non-Goals:** CI conformance run.

## Decisions

Add `test_contract_suite_real_parsers.py` creating the full suite. Mark `@pytest.mark.slow`.

## Risks / Trade-offs

- None.