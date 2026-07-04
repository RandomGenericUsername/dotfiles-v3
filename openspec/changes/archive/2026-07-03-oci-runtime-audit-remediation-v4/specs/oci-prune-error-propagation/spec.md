## ADDED Requirements

### Requirement: parse_prune_result counts Docker's capitalized Deleted lines

`domain/prune_parsing.parse_prune_result` SHALL count deleted IDs regardless of the case of the `deleted:` prefix. The `id_pattern` regex is compiled with `re.MULTILINE | re.IGNORECASE` so that Docker's actual output (`Deleted: sha256:<hex>`, capital **D**) is counted, in addition to the lowercase `deleted: sha256:<hex>` form and the bare-hex form used by Podman. Both compiled patterns SHALL be hoisted to module scope to avoid recompilation per call.

#### Scenario: Docker capitalized Deleted lines are counted
- **WHEN** `parse_prune_result("Deleted: sha256:abc123def456abcd\nTotal reclaimed space: 1.2GB")` is called
- **THEN** it returns `PruneResult(deleted=1, reclaimed_bytes=1288490188)`

#### Scenario: Lowercase deleted lines still counted (no regression)
- **WHEN** `parse_prune_result("deleted: sha256:abc123def456\ndeleted: sha256:789012abcdef\nTotal reclaimed space: 1.2GB")` is called
- **THEN** it returns `PruneResult(deleted=2, reclaimed_bytes=1288490188)`

#### Scenario: Podman bare-hex lines still counted (no regression)
- **WHEN** `parse_prune_result("abc123def456\n789012abcdef\nTotal reclaimed space: 1.2GB")` is called
- **THEN** it returns `PruneResult(deleted=2, reclaimed_bytes=1288490188)`

#### Scenario: Prose hex not counted (no regression)
- **WHEN** `parse_prune_result("Nothing deleted. Reference abc123def456 in docs.\nTotal reclaimed space: 0B")` is called
- **THEN** it returns `PruneResult(deleted=0, reclaimed_bytes=0)`
