## MODIFIED Requirements

### Requirement: parse_id_from_pull returns sha256-prefixed id for both runtimes

`parse_id_from_pull` must return a `sha256:`-prefixed image id for both docker and podman pull output. The current podman parser falls back to returning the first non-Trying/Getting/Error/Warning line as-is, which may be a bare hex id without the `sha256:` prefix. This makes the return value inconsistent between runtimes and violates the implicit contract that pull returns a digest-style id.

#### Scenario: Docker pull with Digest line
- **WHEN** docker pull output contains `Digest: sha256:abc123...`
- **THEN** `parse_id_from_pull` returns `"sha256:abc123..."` (unchanged)

#### Scenario: Podman pull with bare hex id
- **WHEN** podman pull output for a cached image is a single line with a bare hex id `d529dd0c6e55...`
- **THEN** `parse_id_from_pull` returns `"sha256:d529dd0c6e55..."`, not the bare hex string

#### Scenario: Unparseable pull output raises ImageError (unchanged)
- **WHEN** pull output cannot be parsed to extract any id
- **THEN** `pull()` raises `ImageError` (the manager-level check, unchanged from prior spec)
