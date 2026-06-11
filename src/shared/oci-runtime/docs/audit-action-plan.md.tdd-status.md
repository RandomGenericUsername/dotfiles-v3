# TDD Status
Plan: docs/audit-action-plan.md

## Done
- [x] Cycle 1 — A3: Export domain types from `domain/__init__.py` (2026-06-11)
- [x] Cycle 2 — A6: Make `_create_tar` reproducible (2026-06-11)
- [x] Cycle 3 — A1: Refactor `run_pty()` with callback pattern (2026-06-11)
- [x] Cycle 4 — A4: Rename `exec()` → `exec_container()` (2026-06-11)
- [x] Cycle 5 — A5: Rename `all` → `show_all` (2026-06-11)
- [x] Cycle 6 — A2: Distinguish stdout vs stderr in streaming `on_output` (2026-06-11)
- [x] Cycle 7 — A7: Separate provider registration from config defaults (2026-06-11)

## Next
- All cycles complete!

## Final Summary
| Cycle | Item | Status | Tests |
|-------|------|--------|-------|
| 1 | A3 — Domain __init__.py exports | ✅ DONE | 649 (+4) |
| 2 | A6 — _create_tar reproducible | ✅ DONE | 650 (+1) |
| 3 | A1 — run_pty() callback pattern | ✅ DONE | 652 (+2) |
| 4 | A4 — exec → exec_container | ✅ DONE | 652 (rename) |
| 5 | A5 — all → show_all | ✅ DONE | 652 (rename) |
| 6 | A2 — on_output stream distinction | ✅ DONE | 652 (sig change) |
| 7 | A7 — Separate provider registration | ✅ DONE | 652 (extract)

## Decisions Made
- Used `importlib.import_module` + `__all__` check instead of `from oci_runtime.domain import *` inside a function (syntax error in Python)
- Used `patch.object(sys.stdout.buffer, "write")` instead of `patch.object(sys.stdout, "buffer", ...)` since `sys.stdout.buffer` is a readonly attribute

## Deviations
- None
