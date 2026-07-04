## Why

`tests/conformance/test_parser_conformance.py:66,228` calls `pytest.skip` when fixture paths are missing. If `fixtures/` is wiped, the entire conformance suite silently passes by skipping — false-green.

## What Changes

- Add `tests/conformance/test_fixture_integrity.py` that asserts all required fixtures exist. Fail-loud if any are missing.

## Capabilities

### Modified Capabilities

- `oci-parser-real-cli-conformance`: required fixtures MUST be present; missing fixtures SHALL fail the integrity test (not silently skip the conformance suite).

## Impact

- **Code**: new `tests/conformance/test_fixture_integrity.py` (~30 LOC).
- **Risk**: none — adds a test that can only fail or pass.