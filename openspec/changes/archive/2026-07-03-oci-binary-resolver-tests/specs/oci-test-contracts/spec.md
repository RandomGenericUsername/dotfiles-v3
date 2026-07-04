## MODIFIED Requirements

### Requirement: Binary resolver edge-case coverage

Binary resolver unit tests SHALL cover: empty string in PATH (`/usr/bin::/usr/local/bin`), PATH ending with separator, binary with `.exe` extension (marked `@pytest.mark.skipif(not sys.platform.startswith("win"))`), file-not-found on first candidate but found on second, and direct `_resolve_from_path` isolation test.

#### Scenario: Empty PATH component resolves correctly
- **WHEN** `BinaryResolver.resolve("ls")` resolves with `PATH="/usr/bin::/usr/local/bin"`
- **THEN** `ls` is found at `/usr/bin/ls` (empty component is skipped)

#### Scenario: Trailing PATH separator handled
- **WHEN** `PATH="/usr/bin/"` with trailing separator
- **THEN** resolution succeeds