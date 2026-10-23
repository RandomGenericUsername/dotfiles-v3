# Doc Cleanup V3

## Purpose

Aligns documentation (ARCHITECTURE.md, remediation logs) to reflect v3 actual module structure and behavior.

## Requirements

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

## Removed requirements (history)

- **`Managers` aggregate public port artifact** — removed: it was never used; the factory
  constructs managers directly and the port layer exposes only `Parsers`.
- **Shared adapter bases as architecture components** — removed: `BaseCliParser`,
  `CliBaseManager`, and `BaseCliRuntimeProvider` were deleted in v3; their responsibilities moved to
  domain helpers, helper ports, and direct ABC implementations.
