## MODIFIED Requirements

### Requirement: Parser conformance with real CLI output shapes

Conformance fixtures SHALL NOT contain author-specific absolute paths (e.g. `/home/...`). A test SHALL scan all fixture files and fail if any contain `/home/`. Existing author-specific paths in podman fixtures SHALL be scrubbed to `<SCRUBBED>`.

#### Scenario: No fixture contains /home/ paths
- **WHEN** all files under `tests/conformance/fixtures/` are scanned for `/home/`
- **THEN** no matches are found and the test passes

#### Scenario: Fixture with /home/ fails the test
- **WHEN** a fixture file contains `/home/inumaki/.local/share/...` in any field
- **THEN** the test fails listing the offending file and line