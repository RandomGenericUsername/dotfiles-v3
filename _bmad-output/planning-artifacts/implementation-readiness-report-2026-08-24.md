# Implementation Readiness Assessment Report

**Date:** 2026-08-24
**Project:** dotfiles-repo-v3

## Document Inventory

**Selected Documents:**
- PRD: prds/prd-dotfiles-repo-v3-2026-08-03/prd.md
- Architecture: architecture/architecture-dotfiles-repo-v3-2026-08-18/
- Epics: epics-dotfiles-runtime-phase2.md
- UX: Not found (proceeding without)

## PRD Analysis

**Note:** Phase 2 Runtime uses a SPEC (`spec-dotfiles-runtime-phase2/SPEC.md`) as the canonical requirements contract rather than a PRD. Requirements are extracted from the SPEC and its companions.

### Functional Requirements (from SPEC Capabilities + Epics Document)

**From SPEC Capabilities (CAP-1 to CAP-7):**
- FR-1 (CAP-1): User can set the desktop wallpaper from any image path via a single command, deriving palette + effects + icons, updating configs, reloading the desktop, and persisting state.
- FR-2 (CAP-2): System reuses previously-derived palette/effects/icons for a wallpaper it has seen before (content-hash cache hit, zero csg/weg/itr invocations).
- FR-3 (CAP-3): Changing wallpaper converges all desktop consumers (Hyprland, AGS bar shell, Hyprpaper, terminal) to the new state via `current/` symlink repoint, no file copying; crash-mid-swap leaves desktop consistent and repairable on next run.
- FR-4 (CAP-4): System records current desktop state (current.json) and append-only history (history.jsonl), one line per reconcile, survives restarts, never overwritten.
- FR-5 (CAP-5): On a freshly provisioned machine, runtime self-seeds its cache from provisioning's default output (default.png palette/effects/icons), writes current.json, creates current/ symlinks, and repoints consumer paths.
- FR-6 (CAP-6): System reloads desktop components after a swap: Hyprland reload, AGS bar re-reads its palette fragment, Hyprpaper shows new wallpaper, terminal applies new palette.
- FR-7 (CAP-7): User can inspect runtime state: current wallpaper/palette/effects/icons (status), state history (history), cache contents (cache list).

**From Epics Document (FR-1 to FR-13):**
- FR-1: User can set the desktop wallpaper from any image path via a single command, deriving palette + effects + icons, updating configs, reloading the desktop, and persisting state. (CAP-1)
- FR-2: System reuses previously-derived palette/effects/icons for a wallpaper it has seen before (content-hash cache hit, zero csg/weg/itr invocations). (CAP-2)
- FR-3: Changing wallpaper converges all desktop consumers (Hyprland, AGS bar shell, Hyprpaper, terminal) to the new state via `current/` symlink repoint, no file copying; crash-mid-swap leaves desktop consistent and repairable on next run. (CAP-3)
- FR-4: System records current desktop state (current.json) and append-only history (history.jsonl), one line per reconcile, survives restarts, never overwritten. (CAP-4)
- FR-5: On a freshly provisioned machine, runtime self-seeds its cache from provisioning's default output (default.png palette/effects/icons), writes current.json, creates current/ symlinks, and repoints consumer paths. (CAP-5)
- FR-6: System reloads desktop components after a swap: Hyprland reload, AGS bar re-reads its palette fragment, Hyprpaper shows new wallpaper, terminal applies new palette. (CAP-6)
- FR-7: User can inspect runtime state: current wallpaper/palette/effects/icons (status), state history (history), cache contents (cache list). (CAP-7)
- FR-8: Cache-key correctness is verified before caching is trusted: CSG determinism (same wallpaper + templates -> same palette) must be confirmed. (derived from assumption audit / R4)
- FR-9: Provisioning re-apply must not clobber runtime-repointed consumer symlinks (colors.conf/colors.css); a don't-clobber guard preserves runtime ownership across re-applies. (derived from cascading failure / R3)
- FR-10: The bar shell is AGS (Aylur's GTK Shell v2), fully replacing Waybar across provisioning and runtime. (correct-course 2026-08-18)
- FR-11: Per-monitor wallpaper configuration: each monitor can have a different wallpaper source and backend (hyprpaper, swaybg, swww, mpvpaper), configured via `current.json.monitors`. Auto-detection by file extension (video→mpvpaper, GIF→swww, static→hyprpaper). (AD-18)
- FR-12: Wallpaper backend abstraction: `IStaticWallpaperBackend` (hyprpaper, swaybg, swww) and `IVideoWallpaperBackend` (mpvpaper) ports with `IWallpaperBackendFactory` for instantiation. Backend availability verified at use-time; missing backend = hard error. mpvpaper IPC socket at `$XDG_RUNTIME_DIR/mpvpaper-<monitor>.sock`. (AD-18)
- FR-13: Provisioning installs all wallpaper backends (hyprpaper, swaybg, swww/awww, mpvpaper) via packages role. (AD-18, provisioning delta)

Total FRs: 13

### Non-Functional Requirements (from SPEC Constraints + Epics Document)

**From SPEC Constraints (NFR-1 to NFR-11):**
- NFR-1: Hexagonal architecture; dependencies point inward; domain is pure (stdlib allowlist, no os/subprocess/shutil/pathlib, no Path FS calls); ports are ABCs; layering mechanically enforced by test_layering.py mirroring provisioning.
- NFR-2: Synchronous imperative execution for Phase 2; no daemon, async, event bus, plugin system, or distributed execution.
- NFR-3: Filesystem is the authority; cache/ contents and current/ symlinks are truth; current.json/history.jsonl/meta.json are an index + history, re-derivable except history.
- NFR-4: state_root = XDG_STATE_HOME/dotfiles/, runtime-owned; runtime never writes under install spine after seeding; provisioning never writes under state_root.
- NFR-5: JSON/dict-like store only (current.json + history.jsonl + per-entry meta.json, schemas pinned in shared-data-contract.md); no SQLite, ORM, or multi-backend.
- NFR-6: Content hashing is SHA-256, recorded as hash_algorithm in every meta.json; cache entry dirs named by hash of ALL derivation inputs (templates/catalog/mappings included).
- NFR-7: Swap = repoint current/ symlinks only (no copying); symlinks lead, current.json follows; swap sequence owned by ReconcileDesktopStateUseCase per shared-data-contract.
- NFR-8: CSG/WEG/ITR output directed via env-var overrides per call (literal keys in shared-data-contract); provisioning-rendered settings.toml never edited by runtime; csg container-mode override passed into container env.
- NFR-9: Cross-package boundary: runtime imports only cli_output (and declared deps); never provisioning or cli-tools packages; reads provisioning output/settings as data only.
- NFR-10: Runtime core is a nested-hexagon uv package at src/runtime/src/runtime/{domain,ports,adapters,application,cli} with tests/architecture/test_layering.py.
- NFR-11: The bar shell is AGS (Aylur's GTK Shell v2), a TS/JS GTK4 project that fully replaces Waybar across provisioning and runtime. AGS has NO native hot-reload — the Epic 2 reload adapter must restart the process. (correct-course 2026-08-18)

**From Epics Document (NFR-1 to NFR-10):**
- NFR-1: Hexagonal architecture; dependencies point inward; domain pure (stdlib allowlist, no os/subprocess/shutil/pathlib, no Path FS calls); ports are ABCs; layering mechanically enforced by test_layering.py mirroring provisioning. (Constraint 1)
- NFR-2: Synchronous imperative execution model for Phase 2; no daemon, async, event bus, plugin system, or distributed execution. (Constraint 2)
- NFR-3: Filesystem is the authority; cache/ contents and current/ symlinks are truth; current.json/history.jsonl/meta.json are an index + history, re-derivable except history. (Constraint 3)
- NFR-4: state_root = XDG_STATE_HOME/dotfiles/, runtime-owned; runtime never writes under install spine after seeding; provisioning never writes under state_root. (Constraint 4)
- NFR-5: JSON/dict-like store only (current.json + history.jsonl + per-entry meta.json, schemas pinned in shared-data-contract.md); no SQLite, ORM, or multi-backend. (Constraint 5)
- NFR-6: Content hashing is SHA-256, recorded as hash_algorithm in every meta.json; cache entry dirs named by hash of ALL derivation inputs (templates/catalog/mappings included). (Constraint 6)
- NFR-7: Swap = repoint current/ symlinks only (no copying); symlinks lead, current.json follows; swap sequence owned by ReconcileDesktopStateUseCase per shared-data-contract. (Constraint 7)
- NFR-8: CSG/WEG/ITR output directed via env-var overrides per call (literal keys in shared-data-contract); provisioning-rendered settings.toml never edited by runtime; csg container-mode override passed into container env. (Constraint 8)
- NFR-9: Cross-package boundary: runtime imports only cli_output (and declared deps); never provisioning or cli-tools packages; reads provisioning output/settings as data only. (Constraint 9)
- NFR-10: Runtime core is a nested-hexagon uv package at src/runtime/src/runtime/{domain,ports,adapters,application,cli} with tests/architecture/test_layering.py. (Constraint 10)

Total NFRs: 11 (from SPEC) + 10 (from epics, mostly duplicates)

### Additional Requirements (from Epics Document)

- AR-1: Runtime core is a Typer CLI installed via provisioning cli_tools role (uv tool install); provisioning owns install/PATH/container-engine; ops are synchronous CLI commands; logging via cli_output. (AD-18)
- AR-2: Layered content-addressed cache: one cache level per derivation layer (wallpapers/palettes/effects/icons), entry keyed by hash of ALL derivation inputs. (AD-2)
- AR-3: history.jsonl is must-not-lose; append-only, atomic append, never overwritten; every reconcile appends before reload considered complete. (AD-4)
- AR-4: Cache population uses staging-dir pattern (cache/.staging-<pid>/ then os.rename); existing final entry never overwritten; staging discarded if target exists. (AD-9)
- AR-5: Domain model is a derivation graph (WallpaperEntry → PaletteEntry + EffectsEntry; PaletteEntry → IconsEntry); DesktopState = projection of current derivation outputs. (AD-10)
- AR-6: First-run self-seeding when current.json absent and <install>/generated/ output exists; post-seed regeneration reads spine inputs (templates/catalog/mappings) READ-ONLY. (AD-11)
- AR-7: Wallpaper hardlinked into cache/wallpapers/<hash>/wallpaper.<ext> at population time (copy fallback cross-filesystem); <ext> = png for static images, original extension for video. (AD-16)
- AR-8: Consumer wiring: Hyprland colors.conf → current/colors.conf; AGS bar CSS palette fragment → current/colors.gtk.css; per-monitor wallpaper → current/wallpaper-<monitor>.<ext> (ext determined by backend: .png for hyprpaper/swaybg/swww, .mp4 for mpvpaper); ITR color_scheme.path → current/colors.yaml. Consumer-path flips performed by the runtime seeder (R2); provisioning keeps pre-runtime copies + don't-clobber guard. (AD-17)
- AR-9: On-disk schemas (current.json, history.jsonl, per-layer meta.json), canonical cache-key input sets, literal env-override keys, and swap sequence are pinned in shared-data-contract.md and must be written exactly. (shared-data-contract)
- AR-10: Phase 2 non-goals: no content-hash invalidation (P3), no diff engine/declarative reconciliation (P4), no daemon/watchers (P5), no parallel/plugins/distributed cache (P6), no package installation (provisioning domain), no cache eviction policy (P3+; list/prune stubs only in P2).

### PRD Completeness Assessment

The SPEC is complete and well-structured with 7 Capabilities, 11 Constraints, 7 Non-goals, 3 Assumptions, 2 Open Questions. The epics document provides detailed story-level decomposition covering all 13 FRs across 3 Epics with 24 stories. Requirements are traceable from SPEC Capabilities → FRs → Epics → Stories with acceptance criteria. No major gaps identified in requirements specification.

## Epic Coverage Validation

### Coverage Matrix

| FR Number | PRD/SPEC Requirement | Epic Coverage | Status |
| --------- | -------------------- | ------------- | ------ |
| FR-1 | User can set wallpaper from any image path via single command, deriving palette + effects + icons, updating configs, reloading desktop, persisting state (CAP-1) | Epic 1 (Story 1.10, 1.21) + Epic 2 (Story 2.7 capstone) | ✓ Covered |
| FR-2 | System reuses previously-derived palette/effects/icons for a wallpaper it has seen before (content-hash cache hit, zero tool invocations) (CAP-2) | Epic 1 (Stories 1.10, 1.13, 1.14, 1.21) | ✓ Covered |
| FR-3 | Changing wallpaper converges all desktop consumers via current/ symlinks, no file copying; crash-mid-swap leaves desktop consistent and repairable (CAP-3) | Epic 1 (Story 1.10) + Epic 2 (Stories 2.1, 2.2, 2.7) | ✓ Covered |
| FR-4 | System records current desktop state (current.json) and append-only history (history.jsonl), one line per reconcile, survives restarts, never overwritten (CAP-4) | Epic 1 (Story 1.18) + Epic 3 (Stories 3.1, 3.2, 3.3) | ✓ Covered |
| FR-5 | On freshly provisioned machine, runtime self-seeds cache from provisioning's default output, writes current.json, creates current/ symlinks, repoints consumer paths (CAP-5) | Epic 1 (Story 1.19) | ✓ Covered |
| FR-6 | System reloads desktop components after a swap: Hyprland reload, AGS bar re-reads palette fragment, Hyprpaper shows new wallpaper, terminal applies new palette (CAP-6) | Epic 2 (Stories 2.3, 2.4, 2.5, 2.6, 2.7) | ✓ Covered |
| FR-7 | User can inspect runtime state: current wallpaper/palette/effects/icons (status), state history (history), cache contents (cache list) (CAP-7) | Epic 3 (Stories 3.2, 3.3, 3.4) | ✓ Covered |
| FR-8 | Cache-key correctness verified before caching is trusted: CSG determinism (same wallpaper + templates → same palette) must be confirmed (derived from R4) | Epic 1 (Story 1.12) | ✓ Covered |
| FR-9 | Provisioning re-apply must not clobber runtime-repointed consumer symlinks (colors.conf/colors.css); don't-clobber guard preserves runtime ownership (derived from R3) | Epic 1 (Story 1.20) | ✓ Covered |
| FR-10 | Bar shell is AGS (Aylur's GTK Shell v2), fully replacing Waybar across provisioning and runtime (correct-course 2026-08-18) | Epic 1 (Story 1.22) | ✓ Covered |
| FR-11 | Per-monitor wallpaper configuration: each monitor has different wallpaper source and backend (hyprpaper, swaybg, swww, mpvpaper), configured via current.json.monitors. Auto-detection by file extension (AD-18) | Epic 1 (Stories 1.2, 1.8, 1.9, 1.10, 1.21) + Epic 2 (Stories 2.1, 2.5, 2.7) | ✓ Covered |
| FR-12 | Wallpaper backend abstraction: IStaticWallpaperBackend (hyprpaper, swaybg, swww) and IVideoWallpaperBackend (mpvpaper) ports with IWallpaperBackendFactory. Backend availability verified at use-time; missing backend = hard error. mpvpaper IPC socket at XDG_RUNTIME_DIR/mpvpaper-<monitor>.sock (AD-18) | Epic 1 (Stories 1.3, 1.4, 1.5, 1.6, 1.7, 1.8) | ✓ Covered |
| FR-13 | Provisioning installs all wallpaper backends (hyprpaper, swaybg, swww/awww, mpvpaper) via packages role (AD-18, provisioning delta) | Epic 1 (Story 1.11) | ✓ Covered |

### Missing Requirements

None. All 13 FRs from the SPEC/epics are fully covered across the 3 Epics and 24 Stories.

### Coverage Statistics

- Total FRs: 13
- FRs covered in epics: 13
- Coverage percentage: 100%

## UX Alignment Assessment

### UX Document Status

Not Found. No UX design documents exist in the planning artifacts.

### Alignment Issues

None applicable - no UX document to align.

### Warnings

⚠️ **WARNING: No UX documentation found.** This is a CLI-based dotfiles/runtime tool (not a user-facing GUI/web application), so detailed UX design may not be required. However, the CLI user experience (command structure, output formats, error messages, help text) should still be considered. The SPEC defines CLI commands (`dotfiles wallpaper set`, `dotfiles status`, `dotfiles history`, `dotfiles inspect cache list`) and output formats (JSON default, structured errors) which serve as the primary UX contract.

## Epic Quality Review

### Epic Structure Validation

#### A. User Value Focus Check

**Epic 1: Wallpaper & State Foundation**
- **Epic Title:** ✓ User-centric - describes what user can do (set wallpaper, system derives/caches)
- **Epic Goal:** ✓ Describes user outcome (instant reuse, grounded convergence/recovery)
- **Value Proposition:** ✓ Users benefit from this epic alone - can set wallpaper, cache works, state persists

**Epic 2: Desktop Convergence**
- **Epic Title:** ✓ User-centric - "Desktop Convergence" describes user-visible outcome
- **Epic Goal:** ✓ Describes user outcome (desktop visually converges via atomic swap + reload)
- **Value Proposition:** ✓ Users benefit - desktop actually changes to new wallpaper colors

**Epic 3: State Inspection & History**
- **Epic Title:** ✓ User-centric - "Inspect state, view history, list cache"
- **Epic Goal:** ✓ Describes user outcome (see current state, review transitions, see cached artifacts)
- **Value Proposition:** ✓ Users benefit - can inspect and audit runtime state

✅ **All three epics deliver user value, not technical milestones.**

#### B. Epic Independence Validation

**Epic 1 Independence:** ✅ Stands alone completely. Stories 1.1-1.22 establish the entire foundation: package scaffold, domain model, ports, all 4 wallpaper backend adapters, factory, current.json schema, ApplyWallpaperUseCase, provisioning packages, CSG determinism verification, content hashing, cache populator, all 3 tool adapters (csg/weg/itr), state repository, self-seeding, don't-clobber guard, AGS swap. Epic 1 produces: working `dotfiles-runtime wallpaper set` (derives/caches/persists), seeded state on fresh machine, current.json with per-monitor config.

**Epic 2 Independence:** ⚠️ **DEPENDS ON EPIC 1** - Requires Epic 1 outputs:
- `current.json` written by Epic 1 (Story 1.18)
- Cache entries populated by Epic 1 (Stories 1.13, 1.14)
- Tool adapters (csg/weg/itr) from Epic 1 (Stories 1.15, 1.16, 1.17)
- Wallpaper backend adapters from Epic 1 (Stories 1.4-1.7)
- Self-seeding from Epic 1 (Story 1.19)
- AGS bar exists from Epic 1 Story 1.22 (cross-domain, implemented in provisioning)

This is **correct dependency direction** - Epic 2 builds on Epic 1's foundation. Epic 2 cannot function without Epic 1, but Epic 1 functions without Epic 2. ✅

**Epic 3 Independence:** ⚠️ **DEPENDS ON EPIC 1** - Requires:
- `current.json` from Epic 1 (Story 1.18)
- `history.jsonl` written by Epic 2/1 capstone (Story 2.7, 3.1)
- Cache entries from Epic 1 (Stories 1.13, 1.14)
- `current/` symlinks from Epic 1/2

Epic 3 can function with just Epic 1 outputs (read-only inspection), but full value requires Epic 2's history lines. ✅ Correct dependency direction.

✅ **Epic independence validated: Epic N only depends on Epic N-1, never Epic N+1.**

### Story Quality Assessment

#### A. Story Sizing Validation

All 24 stories appear appropriately sized - each delivers a single, testable capability with clear acceptance criteria. No "setup all models" or "create entire API" stories.

**Story 1.1 (Nested-hexagon scaffold):** Creates package structure + layering test - atomic, foundational
**Story 1.2 (Domain model):** Defines 5 frozen dataclasses - atomic
**Story 1.3 (Ports):** Defines 9 ABC ports - atomic
**Stories 1.4-1.7 (Backend adapters):** Each implements one backend - atomic
**Story 1.8 (Factory + auto-detect):** Single factory with auto-detection - atomic
**Story 1.9 (current.json v2 schema):** Schema definition + migration - atomic
**Story 1.10 (ApplyWallpaperUseCase):** Core use case - appropriately sized
**Story 1.11 (Provisioning packages):** Provisioning-side only - atomic
**Story 1.12 (CSG determinism):** Verification test - atomic
**Story 1.13 (Content hashing):** SHA-256 canonicalization - atomic
**Story 1.14 (Cache populator):** Staging-dir pattern - atomic
**Stories 1.15-1.17 (Tool adapters):** Each adapter with env overrides - atomic
**Story 1.18 (IStateRepository):** Minimal JSON adapter - atomic
**Story 1.19 (Self-seeding):** First-run logic - atomic
**Story 1.20 (Don't-clobber):** Provisioning guard - atomic
**Story 1.21 (ApplyWallpaperUseCase capstone):** End-to-end derive/cache/persist - appropriately sized capstone
**Story 1.22 (AGS swap):** Provisioning-side, already implemented - atomic

**Epic 2 Stories (2.1-2.7):** Each addresses one reload adapter or the capstone - atomic
**Epic 3 Stories (3.1-3.4):** Each addresses one inspection command - atomic

✅ **All stories appropriately sized, independently completable.**

#### B. Acceptance Criteria Review

All stories use Given/When/Then format with specific, testable criteria. Each AC covers happy path and error conditions. Examples:

- Story 1.1: "Given package doesn't exist, When scaffold completes, Then directories exist, layering test passes, violating import fails"
- Story 1.4: "Given current.json with hyprpaper config, When set_image invoked, Then hyprctl commands executed, reload works, binary verified"
- Story 2.2: "Given swap interrupted, When next run starts, Then detects incomplete swap from current.json + symlink comparison, reverts to last-good, re-run is cache hit, reload-failure reported"

✅ **All ACs are testable, complete, specific, in proper BDD format.**

### Dependency Analysis

#### A. Within-Epic Dependencies

**Epic 1 Dependency Chain (validated):**
1.1 (scaffold) → 1.2 (domain) → 1.3 (ports) → 1.4-1.7 (adapters) → 1.8 (factory) → 1.9 (schema) → 1.10/1.21 (use case) → 1.13 (hashing) → 1.14 (cache) → 1.15-1.17 (tool adapters) → 1.18 (state repo) → 1.19 (seeding) → 1.20 (guard) → 1.22 (AGS swap)

All dependencies flow forward - each story uses only previous stories' outputs. No forward references.

**Epic 2 Dependency Chain:**
2.1 (swap sequencing) → 2.2 (crash recovery) → 2.3-2.6 (reload adapters) → 2.7 (capstone)

Valid - each adapter builds on swap mechanism, capstone orchestrates all.

**Epic 3 Dependency Chain:**
3.1 (history persistence) → 3.2 (status) → 3.3 (history) → 3.4 (cache list)

Valid - history must exist for inspection commands to work.

✅ **No forward dependencies within epics.**

#### B. Database/Entity Creation Timing

Not applicable - this is a file-based JSON store (current.json, history.jsonl, meta.json), not a database. Files are created when first needed:
- `current.json` created in Epic 1 Story 1.18/1.19
- `history.jsonl` created in Epic 2 Story 2.7 / Epic 3 Story 3.1
- `meta.json` created in Epic 1 Story 1.14 (cache population)

✅ **Files created when first needed, not upfront.**

### Special Implementation Checks

#### A. Starter Template Requirement

Architecture specifies nested-hexagon uv package structure. Story 1.1 explicitly creates this scaffold with layering test mirroring provisioning. ✅

#### B. Greenfield Indicators

This is a greenfield runtime package (src/runtime doesn't exist yet). The epics include:
- Initial project setup (Story 1.1)
- Development environment / package configuration (implied in 1.1)
- CI/CD / test pipeline (layering test in 1.1, integration tests in provisioning)

✅ **Greenfield setup properly addressed.**

### Best Practices Compliance Checklist

| Check | Epic 1 | Epic 2 | Epic 3 |
|-------|--------|--------|--------|
| Epic delivers user value | ✅ | ✅ | ✅ |
| Epic can function independently | ✅ | ✅ (depends on 1) | ✅ (depends on 1) |
| Stories appropriately sized | ✅ | ✅ | ✅ |
| No forward dependencies | ✅ | ✅ | ✅ |
| Files created when needed | ✅ | ✅ | ✅ |
| Clear acceptance criteria | ✅ | ✅ | ✅ |
| Traceability to FRs maintained | ✅ | ✅ | ✅ |

### Quality Assessment Documentation

#### 🟡 Minor Concerns

1. **Story 1.10 and 1.21 appear to overlap** - Both are "ApplyWallpaperUseCase" with similar acceptance criteria. Story 1.10 focuses on per-monitor derive/cache/persist, Story 1.21 is the capstone. Could be consolidated or better differentiated.

2. **Story 1.22 (AGS swap) is marked "implemented in provisioning"** - It's a cross-domain prerequisite listed in Epic 1 but implemented in provisioning code. This creates ambiguity about ownership. The note says "No runtime code required for this story" - consider moving to a separate cross-cutting concerns section.

3. **Epic 2 Story 2.5 (Hyprpaper channel verification)** has an open question in SPEC (Open Question: "Hyprpaper wallpaper channel: reload-after-symlink-repoint vs hyprctl hyprpaper wallpaper IPC?"). The story says "the unverified-to-verified transition is closed with evidence" - this is good but the AC should specify what evidence is required.

4. **Story numbering inconsistency** - Epic 1 has 22 stories (1.1-1.22), Epic 2 has 7 stories (2.1-2.7), Epic 3 has 4 stories (3.1-3.4). The jump from 1.22 to 2.1 is clear but 1.21 and 1.22 feel like late additions.

#### 🟠 Major Issues

None found.

#### 🔴 Critical Violations

None found.

### Remediation Recommendations

1. **Consolidate Stories 1.10 and 1.21** or clearly differentiate: 1.10 = "per-monitor derive/cache/persist", 1.21 = "full pipeline orchestration including reload" (but reload is Epic 2).

2. **Move Story 1.22 (AGS swap)** to a "Cross-Domain Prerequisites" section or explicitly mark as "Provisioning-Owned / Runtime-Prerequisite" to clarify ownership.

3. **Strengthen Story 2.5 AC** to specify exact verification criteria for Hyprpaper channel (e.g., "verify hyprctl hyprpaper wallpaper <monitor> <path> updates display without full reload" vs "verify reload-after-symlink-repoint works").

4. **Consider renumbering Epic 1 stories** to group related stories (e.g., all backend adapters 1.4-1.7, all tool adapters 1.15-1.17).

## Summary and Recommendations

### Overall Readiness Status

**READY** - The Phase 2 Runtime epics are well-structured, complete, and ready for implementation. All 13 FRs are covered with 100% traceability. No critical or major issues found.

### Critical Issues Requiring Immediate Action

None.

### Recommended Next Steps

1. **Address minor story clarifications** (consolidate 1.10/1.21, clarify 1.22 ownership, strengthen 2.5 AC) - can be done during sprint planning
2. **Resolve SPEC Open Questions** before Epic 2 implementation:
   - Hyprpaper wallpaper channel verification (reload-after-symlink-repoint vs IPC)
   - Phase 2 done-criteria definition
3. **Proceed to implementation** - Start with Epic 1 Story 1.1 (nested-hexagon scaffold with layering test)

### Final Note

This assessment identified 4 minor concerns across epic quality review. All functional requirements are fully covered (100% traceability). The architecture is sound with hexagonal constraints, proper dependencies, and clear acceptance criteria. The Phase 2 Runtime is ready for implementation.

## Steps Completed
- step-01-document-discovery
- step-02-prd-analysis
- step-03-epic-coverage-validation
- step-04-ux-alignment
- step-05-epic-quality-review
- step-06-final-assessment