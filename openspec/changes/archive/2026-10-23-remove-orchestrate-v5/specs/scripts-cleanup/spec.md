## REMOVED Requirements

### Requirement: Legacy orchestrate-v5.sh helper
**Reason**: Completed July-2026 migration coordinator; nothing in the toolchain invokes it (`Makefile`, `bootstrap.sh`, Ansible roles, and tests contain zero references — only historical planning docs mention it).
**Migration**: No replacement needed. Run change waves via the current `openspec` CLI (`openspec new change`, `openspec validate`, `/opsx-apply`).

#### Scenario: File is gone and nothing breaks
- **WHEN** inspecting the repo tree and running the unit suite
- **THEN** `scripts/orchestrate-v5.sh` does not exist and all tests pass
