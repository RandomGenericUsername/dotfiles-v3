## ADDED Requirements

### Requirement: prune counts both bare-hex and deleted-prefixed IDs
`parse_prune()` SHALL count deleted image/container/volume/network IDs matching either the bare-hex format (`^[a-f0-9]{12,64}$`) or the `docker ... prune --force --all` format (`deleted: sha256:<hex>`). The count MUST include both line shapes.

#### Scenario: image prune --all counts deleted sha256 lines
- **WHEN** `parse_prune()` receives `"deleted: sha256:abc123def456\ndeleted: sha256:789012abcdef\nTotal reclaimed space: 1.2GB\n"`
- **THEN** it returns `PruneResult(deleted=2, reclaimed_bytes=1288490188)`

#### Scenario: normal prune counts bare hex lines
- **WHEN** `parse_prune()` receives `"abc123def456\n789012abcdef\nTotal reclaimed space: 1.2GB\n"`
- **THEN** it returns `PruneResult(deleted=2, reclaimed_bytes=1288490188)`

### Requirement: prune does not false-match prose
`parse_prune()` MUST NOT count hex strings that appear inside prose (not line-anchored as deleted IDs).

#### Scenario: prose hex not counted
- **WHEN** `parse_prune()` receives `"Nothing deleted. Reference abc123def456 in docs.\nTotal reclaimed space: 0B\n"`
- **THEN** it returns `PruneResult(deleted=0, reclaimed_bytes=0)`

### Requirement: prune handles missing reclaimed line
`parse_prune()` SHALL return `reclaimed_bytes=0` when no `Total reclaimed space:` line is present, and SHALL not raise if the reclaimed-space value is unparseable.

#### Scenario: no reclaimed line
- **WHEN** `parse_prune()` receives `"deleted: sha256:111111111111\n"`
- **THEN** it returns `PruneResult(deleted=1, reclaimed_bytes=0)`

#### Scenario: unparseable reclaimed value yields zero
- **WHEN** `parse_prune()` receives `"deleted: sha256:111111111111\nTotal reclaimed space: blob\n"`
- **THEN** it returns `PruneResult(deleted=1, reclaimed_bytes=0)` without raising
