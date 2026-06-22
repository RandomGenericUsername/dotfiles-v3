## MODIFIED Requirements

### Requirement: parse_digest_from_pull returns sha256-prefixed id for both runtimes

`parse_digest_from_pull` (renamed from `parse_id_from_pull`) must return a `sha256:`-prefixed image id for both docker and podman pull output. The Podman parser must scan all lines in reverse, skipping known progress/noise prefixes (`Resolved`, `Trying`, `Getting`, `Copying`, `Writing`, `Storing`), and return the first bare hex hash or `sha256:`-containing line. It must NOT return `""` prematurely on non-matching lines — only after exhausting all lines.

#### Scenario: Docker pull with Digest line
- **WHEN** docker pull output contains `Digest: sha256:abc123...`
- **THEN** `parse_digest_from_pull` returns `"sha256:abc123..."` (unchanged)

#### Scenario: Podman pull with bare hex id
- **WHEN** podman pull output for a cached image is a single line with a bare hex id `d529dd0c6e55...`
- **THEN** `parse_digest_from_pull` returns `"sha256:d529dd0c6e55..."`, not the bare hex string

#### Scenario: Podman pull with multi-line output and noise after hash
- **WHEN** podman pull output has progress lines after the bare hex ID (e.g. "Storing signatures" appears after the ID in a combined stream)
- **THEN** `parse_digest_from_pull` scans all lines, skips noise prefixes, and returns `sha256:<hex>`, not `""`

#### Scenario: Unparseable pull output raises ImageError
- **WHEN** pull output cannot be parsed to extract any id
- **THEN** `pull()` raises `ImageError` (the manager-level check, unchanged from prior spec)

## ADDED Requirements

### Requirement: Podman pull auth failures raise ImagePullAccessDeniedError

`PodmanImageParser` SHALL define `_auth_error_patterns` with Podman-specific auth error strings: `"authentication required"` and `"requested access to the resource is denied"`. These are the actual strings emitted by Podman's `containers/image` library (HTTP 401 → `ErrorCodeUnauthorized`, HTTP 403 → `ErrorCodeDenied`), NOT Docker's `"pull access denied"` phrasing.

#### Scenario: Podman pull with authentication required
- **WHEN** `CliImageManager.pull()` for Podman gets stderr containing `"authentication required"`
- **THEN** `ImagePullAccessDeniedError` is raised (not `ImageRuntimeError`)

#### Scenario: Podman pull with access denied
- **WHEN** `CliImageManager.pull()` for Podman gets stderr containing `"requested access to the resource is denied"`
- **THEN** `ImagePullAccessDeniedError` is raised (not `ImageRuntimeError`)
