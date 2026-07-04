## Context

Domain unit test gaps. Must exist before TDD for A1/A3 can work.

## Goals / Non-Goals

**Goals:** One test file per domain module. Fill gaps in test_types.py, test_exceptions.py, test_enums.py, test_result_checking.py.
**Non-Goals:** 100% coverage (pragmatic).

## Decisions

Use `tests/unit/domain/` naming convention matching `src/oci_runtime/domain/`. Each test file covers one domain module.

## Risks / Trade-offs

- None.