## ADDED Requirements

### Requirement: Podman parsers achieve full parity with Docker parsers

All Podman parser classes SHALL handle the same edge cases as their Docker counterparts. Specifically: null `RepoTags` (Docker returns `null`, Podman returns `[]` — both must produce an empty list), Podman-specific auth-error patterns, and robust digest extraction from multi-line pull output.

#### Scenario: Podman inspect with null RepoTags does not crash
- **WHEN** `PodmanImageParser.parse_inspect()` is fed JSON with `"RepoTags": null`
- **THEN** `info.tags` is `[]` (empty tuple after deep-freeze), not `None`, and iterating does not raise `TypeError`

#### Scenario: Podman inspect with absent RepoTags does not crash
- **WHEN** `PodmanImageParser.parse_inspect()` is fed JSON without a `RepoTags` key
- **THEN** `info.tags` is `[]`, not `None`

#### Scenario: Podman parse_digest_from_pull handles multi-line output
- **WHEN** `PodmanImageParser.parse_digest_from_pull()` is fed multi-line output where the bare hex ID is NOT the last line (e.g. "Storing signatures" appears after the hex ID in a combined stream)
- **THEN** the parser scans all lines in reverse, skips known progress prefixes, and returns `sha256:<hex>`, not `""`

#### Scenario: Podman parse_digest_from_pull with quiet mode
- **WHEN** `PodmanImageParser.parse_digest_from_pull()` is fed a single bare hex ID line (quiet mode)
- **THEN** it returns `sha256:<hex>`

#### Scenario: Podman auth failure raises ImagePullAccessDeniedError
- **WHEN** `CliImageManager.pull()` for Podman gets stderr containing `"authentication required"` or `"requested access to the resource is denied"`
- **THEN** `ImagePullAccessDeniedError` is raised (not `ImageRuntimeError` or `ImageNotFoundError`)

#### Scenario: Podman parse_digest_from_pull with no hash in output
- **WHEN** `PodmanImageParser.parse_digest_from_pull()` is fed output with no bare hex hash and no `sha256:` line
- **THEN** it returns `""` (the manager then raises `ImageError`)
