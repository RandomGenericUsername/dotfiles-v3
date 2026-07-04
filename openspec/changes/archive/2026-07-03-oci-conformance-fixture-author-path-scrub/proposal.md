## Why

Committed podman conformance fixtures contain the author's absolute home paths (`/home/inumaki/.local/...`) in `mountpoint`/`StaticDir` fields. Any future assertion on those fields will silently encode a developer-machine-specific value.

## What Changes

- Scrub `/home/...` paths in all fixtures to `<SCRUBBED>`.
- Add `test_no_author_specific_paths_in_fixtures` that fails if any fixture file contains `/home/`.

## Capabilities

### Modified Capabilities

- `oci-parser-real-cli-conformance`: conformance fixtures SHALL NOT contain author-specific absolute paths; a test SHALL enforce this.

## Impact

- **Fixtures**: sed-scrub podman fixtures under `tests/conformance/fixtures/podman/`.
- **Tests**: new test in `tests/conformance/test_fixture_integrity.py` (or sibling).
- **Risk**: none — no tests currently assert on `mountpoint`/`StaticDir`; scrubbing is safe.