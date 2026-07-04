## 1. Add fixture integrity test

- [ ] 1.1 Create `tests/conformance/test_fixture_integrity.py` with a `REQUIRED_FIXTURES` list enumerating all committed fixture paths. Add `test_all_required_fixtures_present` asserting each exists.
- [ ] 1.2 Run `uv run pytest -q tests/conformance/test_fixture_integrity.py` — green (all fixtures committed).
- [ ] 1.3 Verify: temporarily remove one fixture, run, assert test fails; restore the fixture.