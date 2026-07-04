## MODIFIED Requirements

### Requirement: List executor branch coverage

Unix list executor tests SHALL cover: `--all` filter branch, `--latest` filter branch, `--since` / `--before` filter branches, `_BUILDER_MAP` unknown builder fallthrough (returns `None`), empty `id_list` response (empty array vs null), and executor teardown error propagation.

#### Scenario: Unknown builder maps to None
- **WHEN** `_BUILDER_MAP` receives an unrecognized builder name
- **THEN** the returned filter is `None` (no additional flags)

#### Scenario: Empty id_list returns empty result
- **WHEN** the response from `_run_containers_list` contains an empty list of container ids
- **THEN** `list_containers` returns an empty list