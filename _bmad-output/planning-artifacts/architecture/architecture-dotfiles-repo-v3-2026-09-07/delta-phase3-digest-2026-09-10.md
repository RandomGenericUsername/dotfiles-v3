---
name: dotfiles-repo-v3 Phase 3 delta — digest enforcement (AD-26/AD-27)
type: architecture-delta
purpose: build-substrate
scope: populate-time artifact digests + legacy annotation on the Phase 2 runtime cache
status: adopted
created: 2026-09-10
binds: [PRD Phase 3 v2 ../../prds/prd-dotfiles-repo-v3-2026-09-10/prd.md]
amends: [ARCHITECTURE-SPINE.md (AD-21..AD-25 binding, read-only)]
adopted: 2026-09-10 (Story 1.5 landed: CorruptCacheError in domain/models.py, verify_staging in adapters/cache.py)
---

# Architecture Delta — Phase 3 Digest Enforcement

Parent spine `ARCHITECTURE-SPINE.md` (AD-21..AD-25) is binding and read-only. This
delta adds two rules; adoption is marked when Story 1.5 lands.

## Invariants & Rules

### AD-26 — Digest enforcement at populate time

- **Binds:** cache population, `meta.json` contract
- **Prevents:** generator-level corruption entering the cache undetected
- **Rule:** every artifact written via `populate_via_staging` is hashed at write
  time; a mismatch against the `artifact_hashes` recorded in `meta.json` raises
  `CorruptCacheError` BEFORE the staging rename — the entry never becomes visible.
  Write-once preserved: populated entries are never re-hashed in place; correction
  flows through `DoctorUseCase` (AD-22). No hash-formula or cache-layout change
  (AD-21 holds). [ADOPTED]

### AD-27 — Legacy entries are lazily annotated, never failed

- **Binds:** cache verification, `meta.json` evolution
- **Prevents:** breaking existing warm caches with a format change
- **Rule:** entries without `artifact_hashes` (pre-FR-8) stay fully usable and are
  treated healthy-until-proven-corrupt. First `cache list --verify` (Story 3.1)
  records their digests in place (annotation), never hard-fails them. No migration
  pass, no Phase-3-bricked Phase-2 caches. [ADOPTED]

## Placement (AD-25 holds)

- Enforcement helper lives in `adapters/` (next to `cache.py`/`hashing.py`), all I/O
  stays out of `domain/`; `CorruptCacheError` is raised at the adapter boundary and
  surfaced by `application/` as data, never an uncaught crash (zero-crash invariant).
- `tests/architecture/test_layering.py` unchanged and green.
