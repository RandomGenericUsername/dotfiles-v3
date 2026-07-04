## Context

Author-specific paths in committed fixtures. Mechanical scrub + guard test.

## Goals / Non-Goals

**Goals:** Scrub `/home/` paths; prevent future commits from reintroducing them.
**Non-Goals:** Re-capturing fixtures from scratch (sed-scrub existing).

## Decisions

Sed-replace `/home/inumaki/.local/...` → `<SCRUBBED>` in all `tests/conformance/fixtures/podman/*.json`. Add `test_no_author_specific_paths_in_fixtures` that greps all fixture files for `/home/` and fails if found.

## Risks / Trade-offs

- None. No tests assert on these fields today.