## RECONCILED Requirements

### Requirement: Doc sync on archive

v4 change (oci-runtime-audit-remediation-v4) SHALL be archived first, syncing its spec overrides to `openspec/specs/`. After all v5 changes are implemented, the v5 umbrella change SHALL be archived to sync v5 delta specs on top.

#### Scenario: v4 archived before v5
- **WHEN** `openspec archive change oci-runtime-audit-remediation-v4` is run
- **THEN** v4 spec overrides are merged into `openspec/specs/`

#### Scenario: v5 archived after all changes
- **WHEN** `openspec archive change oci-v5-remediation-doc-sync` is run after all 24 other changes are implemented
- **THEN** v5 delta specs are synced on top of v4-synced specs