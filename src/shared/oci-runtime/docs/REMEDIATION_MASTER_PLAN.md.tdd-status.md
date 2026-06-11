# TDD Status
Plan: docs/REMEDIATION_MASTER_PLAN.md

## Done
- [x] Cycle 1 — Step 1.1: Convert RestartPolicy and NetworkMode to StrEnum (2026-06-11)
- [x] Cycle 2 — Step 1.2: Delete dead EngineProfile (2026-06-11)
- [x] Cycle 3 — Step 1.3: Parsers must raise ParsingError instead of returning None (2026-06-11)
- [x] Cycle 4 — Step 1.4: parse_list raises ParsingError on invalid JSON (2026-06-11)
- [x] Cycle 5 — Step 1.5: Move ParsingError to adapter layer (2026-06-11)
- [x] Cycle 6 — Step 1.6: Delete engines.py (2026-06-11)
- [x] Cycle 7 — Step 2.1: Add execute_pty to Transport port (2026-06-11)
- [x] Cycle 8 — Step 2.2: Implement execute_pty in CliTransport (2026-06-11)
- [x] Cycle 9 — Step 2.3: Update CliContainerManager.run() to use Transport (2026-06-11)
- [x] Cycle 10 — Step 2.4: Fix CliRuntime.version() — route through Transport (2026-06-11)
- [x] Cycle 11 — Step 3.1+3.2: Remove _PROVIDER_REGISTRY, add _default_providers, explicit injection (2026-06-11)
- [x] Cycle 12 — Step 3.3+3.4: Move manager construction into RuntimeProvider, remove _make_* (2026-06-11)
- [x] Cycle 13 — Step 4.1: Add _check_result() to create methods (2026-06-11)
- [x] Cycle 14 — Step 4.2: Add --format json consistently (2026-06-11)
- [x] Cycle 15 — Step 4.3: Fix _parse_docker_ports error handling (2026-06-11)
- [x] Cycle 16 — Step 4.4: Normalize image ID format (2026-06-11)
- [x] Cycle 17 — Step 4.5: Fix ContainerManager.logs() thread naming (2026-06-11)
- [x] Cycle 18 — Step 5.1+5.2: Extract shared JSON parsing into BaseCliParser, deduplicate parse_inspect (2026-06-11)

## All cycles complete!

## Decisions Made
- Used direct `StrEnum` comparison (`config.network != NetworkMode.BRIDGE`) instead of `str(x)` — more type-safe and idiomatic
- Added 8 new tests: `is_strenum`, `str_equality`, `str_fstring`, `strenum_is_str` for both `RestartPolicy` and `NetworkMode`
- Replaced TestEngineProfile class with `test_engine_profile_no_longer_exists` verification test
- ParsingError propagates through managers (no silent None); `exists()` catches ParsingError alongside NotFoundError for robustness

## Deviations
- None
