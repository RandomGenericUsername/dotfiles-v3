# TDD Status
Plan: docs/AUDIT_REMEDIATION_PLAN.md

## Done
- [x] Phase 1: Domain Layer (7/7 cycles)
- [x] Phase 2: Port Layer (9/9 cycles)
- [x] Phase 3: Adapter Layer (33/33 cycles)
- [x] Phase 4: Tests, Docs, Format (11/11 cycles)

All 60 cycles complete.

## Final Test Results
- Core tests (domain/ports/contract/boundary/adapters): 647 passed, 1 skipped
- Architecture layering tests: 53 passed
- Audit tests: 19 passed
- Conformance tests: 31 passed
- ruff src/: clean (13 pre-existing F401 in __init__.py)

## Notes
- All 6 issues from initial review are FIXED:
  - A4: cancellation_factory and pty_transport are now required params (no fallbacks)
  - B2/B10: CliTransport.execute() uses Popen+ProcessPipeReader+DeadlineCancellationToken; cancel_token is wired; no subprocess.TimeoutExpired leak
  - B12: test_parser_conformance.py try/except/pytest.xfail wrapper removed; asserts directly
  - D3: ARCHITECTURE.md remediation log documents F15-F42
  - D6: ARCHITECTURE.md references domain/capabilities.py → ports/capabilities.py; frozen narrative added
  - D7: test_parser_conformance.py docstring rewritten (no xfail claim)
- 9 ProcessPipeReader tests still use old mocking (test_cli_streaming_transport.py) — tests use `from_process` which works via backward compat
- ruff src/: clean (1 pre-existing F401 in __init__.py)
