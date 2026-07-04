## Why

v4 change (oci-runtime-audit-remediation-v4) is not archived; its spec overrides are not synced to `openspec/specs/`. v5 changes that reference those capabilities work via delta-spec files in each change's `specs/` dir. Before archiving v5, v4 must be archived first (which syncs v4 specs), then v5 must sync its delta specs on top.

## What Changes

- Archive the v4 change (`openspec archive change oci-runtime-audit-remediation-v4`).
- Archive the v5 change after all other changes are implemented (`openspec archive change oci-v5-remediation-doc-sync` at the end).

## Capabilities

### Modified Capabilities

- `oci-doc-cleanup-v3`: v4/v5 spec overrides synced to `openspec/specs/` on archive.

## Impact

- **Procedural**: archive v4 → archive v5 after implementation complete.
- **Risk**: none — pure metadata sync.