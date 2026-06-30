## ADDED Requirements

### Requirement: Documentation drift removed and ARCHITECTURE.md aligned to v3 truth

The `docs/ARCHITECTURE.md` file is updated to reflect v3 actual behavior. Specific edits:

1. **Routing matrix** (L188-197): `detach=True` row changes from "batch execute() (via transport)" to "streaming.stream() (no callbacks)". All four rows match the actual code path.

2. **Provider contract** (L141): The `create_managers` method documented on `RuntimeProvider` is removed. The provider only defines `kind`, `capabilities`, `create_parsers`. Manager construction happens in `RuntimeFactory`.

3. **Base classes section** (L160-175): The section documenting `BaseCliParser`, `CliBaseManager`, and `BaseCliRuntimeProvider` is removed. Replaced with a note that shared adapter bases were deleted in v3 and their logic moved to domain helpers (`domain/`) and helper ports (`ports/`).

4. **Managers aggregate**: The `Managers` dataclass in `ports/aggregates.py` is deleted (was unused). `ports/__init__.py` no longer re-exports it. `Parsers` aggregate is retained (actively used).

5. **Remediation log** (L396-401): A new entry added for v3 audit remediation summarizing the 8 critical bugs, strict-hexagonal refactor, and doc alignment.

6. **Streaming transport docstring** (ports/streaming.py L11-12): Removes stale "Unlike Transport.execute() which is batch (subprocess.run)" — `CliTransport.execute()` uses `Popen`, not `subprocess.run`.

7. **Timeout types**: Notes that all manager timeouts are now `float | None` (E5 in proposal).

8. **Helper ports section**: New section added describing `ResultChecker`, `ListExecutor[T]`, and `PipeReader` helper ports—what they replace and how they are wired.

#### Scenario: Routing matrix matches implementation
- **WHEN** a reader checks the routing matrix in ARCHITECTURE.md
- **THEN** all four conditions map to the actual `CliContainerManager.run()` branches

#### Scenario: create_managers documentation removed
- **WHEN** a reader searches for `create_managers` in ARCHITECTURE.md
- **THEN** it is not present; provider only has `kind`, `capabilities`, `create_parsers`

#### Scenario: Base classes section replaced
- **WHEN** a reader searches for `BaseCliParser` in ARCHITECTURE.md
- **THEN** the reference is in the "Deleted shared adapter bases" note, not in a dedicated architecture section

#### Scenario: Managers aggregate removed
- **WHEN** `from oci_runtime.ports.aggregates import Managers` is attempted
- **THEN** `ImportError` (only `Parsers` is exported)

#### Scenario: Remediation log has v3 entry
- **WHEN** a reader checks the remediation table
- **THEN** a 2026-06-27 row for `oci-runtime-audit-remediation-v3` exists with bullet summary

#### Scenario: Helper ports section documents ResultChecker and ListExecutor
- **WHEN** a reader looks for ResultChecker in ARCHITECTURE.md
- **THEN** it is documented as a helper port in ports/ that replaces CliBaseManager._check_result, with wiring described

## REMOVED Requirements

### Requirement: Managers aggregate is a public port artifact

**Reason**: It was never used — the factory constructs managers directly. The port layer now only exposes `Parsers` (actively used by the factory).

**Migration**: Any external code importing `Managers` from `oci_runtime.ports.aggregates` must be updated to construct managers individually or removed. No known external consumers exist (module is internal).

### Requirement: Shared adapter bases documented as architecture components

**Reason**: `BaseCliParser`, `CliBaseManager`, and `BaseCliRuntimeProvider` are deleted in v3. Their responsibilities are distributed to domain helpers (`domain/`), helper ports (`ports/`), and direct ABC implementations.
