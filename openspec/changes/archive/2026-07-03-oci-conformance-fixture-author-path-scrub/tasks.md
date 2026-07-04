## 1. Scrub fixtures

- [ ] 1.1 Run `sed -i 's|/home/inumaki[^"]*|<SCRUBBED>|g' tests/conformance/fixtures/podman/*.json` — verify with `rg '/home/' tests/conformance/fixtures/` returning zero.

## 2. Add guard test

- [ ] 2.1 In `tests/conformance/test_fixture_integrity.py` add `test_no_author_specific_paths_in_fixtures` scanning all fixture files for `/home/`.
- [ ] 2.2 Run `uv run pytest -q tests/conformance/test_fixture_integrity.py` — green.