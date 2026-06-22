## ADDED Requirements

### Requirement: Prune methods must propagate errors

All four manager `prune()` methods (`container`, `image`, `volume`, `network`) must call `_check_result` on the transport result before parsing. A failed prune (non-zero exit code, daemon down, permission error) must raise an `OciError` subclass. It must not return `PruneResult(0, 0)` — that is indistinguishable from a successful empty prune and silently swallows the failure.

#### Scenario: Container prune with daemon error
- **WHEN** `container prune --force` returns exit code 1 with stderr `"Error: daemon is down"`
- **THEN** `ContainerManager.prune()` raises `OciError` (or a subclass), not `PruneResult(0, 0)`

#### Scenario: Image prune with daemon error
- **WHEN** `image prune --force` returns exit code 1 with stderr `"Error: daemon is down"`
- **THEN** `ImageManager.prune()` raises `OciError`, not `PruneResult(0, 0)`

#### Scenario: Volume prune with daemon error
- **WHEN** `volume prune --force` returns exit code 1 with stderr `"Error: daemon is down"`
- **THEN** `VolumeManager.prune()` raises `OciError`, not `PruneResult(0, 0)`

#### Scenario: Network prune with daemon error
- **WHEN** `network prune --force` returns exit code 1 with stderr `"Error: daemon is down"`
- **THEN** `NetworkManager.prune()` raises `OciError`, not `PruneResult(0, 0)`

#### Scenario: Successful prune returns PruneResult
- **WHEN** `container prune --force` returns exit code 0 with parsed output
- **THEN** `ContainerManager.prune()` returns `PruneResult(deleted=N, reclaimed_bytes=M)` as before
