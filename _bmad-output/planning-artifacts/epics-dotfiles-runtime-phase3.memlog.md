---
scope: Phase 3 State Awareness epics + stories (CE workflow)
updated: 2026-09-07T12:00
---

- (event) CE Step 1 prerequisites validated: PRD 2026-09-07 (FR-1..FR-7, NFR-1..NFR-4, OQ-1..OQ-3), ARCHITECTURE-SPINE 2026-09-07 (AD-21..AD-25 inheriting AD-1..AD-20), phase3-state-awareness-diagrams.md, Phase 2 epics + SPEC/cache-model/consumer-wiring, runtime layout src/runtime/src/runtime/{domain,ports,adapters,application,cli}
- (decision) Output path _bmad-output/planning-artifacts/epics-dotfiles-runtime-phase3.md (mirrors Phase 2 naming; skill-default epics.md not used to avoid clobbering)
- (decision) Scope locked to user mandate: Epic 1 invalidation+regen (FR-1/FR-2), Epic 2 doctor+repair+torn-tail (FR-3/FR-4/FR-7), Epic 3 verify+prune (FR-5/FR-6); non-goals P4/P5/P6/SQLite/hash-layout changes excluded
- (decision) Story sizing layering-clean per AD-25: ports → adapters → application → cli; 4+3+3 = 10 stories; no UX-DRs (headless CLI, no UX contract)
- (assumption) Skill menu halts pre-authorized by user prompt (fresh-context autonomous run; return only path/titles/questions)
- (event) CE Steps 1-4 completed; file validated: all FRs mapped, no forward story dependencies, layering test constraint carried in 1.1/3.2
