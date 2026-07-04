## MODIFIED Requirements

### Requirement: Parser conformance with real CLI output shapes

The conformance test suite SHALL include a `test_fixture_integrity.py` that enumerates all required fixture files and asserts each exists on disk. If any fixture is missing, the integrity test SHALL fail (not silently skip the conformance suite). The `pytest.skip` calls in `test_parser_conformance.py` SHALL remain as belt-and-braces per-test gating, but the integrity test is the primary guard.

#### Scenario: Missing fixture fails integrity test
- **WHEN** a required fixture file (e.g. `docker/container_list.ndjson`) is absent from `tests/conformance/fixtures/`
- **THEN** `test_fixture_integrity.test_all_required_fixtures_present` fails with a message listing all missing fixtures

#### Scenario: All fixtures present passes
- **WHEN** all required fixture files exist
- **THEN** the integrity test passes