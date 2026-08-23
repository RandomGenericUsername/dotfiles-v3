---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md
  - _bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md
  - _bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md
---

# dotfiles-repo-v3 - Epic Breakdown (Phase 2: Runtime Desktop Reconciliation Core)

## Overview

This document provides the complete epic and story breakdown for the dotfiles-repo-v3 Phase 2 runtime desktop reconciliation core, decomposing the requirements from the SPEC (dotfiles-runtime-phase2), the Architecture spine, and the shared data contract into implementable stories.

## Requirements Inventory

### Functional Requirements

FR-1: User can set the desktop wallpaper from any image path via a single command, deriving palette + effects + icons, updating configs, reloading the desktop, and persisting state. (CAP-1)
FR-2: System reuses previously-derived palette/effects/icons for a wallpaper it has seen before (content-hash cache hit, zero csg/weg/itr invocations). (CAP-2)
FR-3: Changing wallpaper converges all desktop consumers (Hyprland, AGS bar shell, Hyprpaper, terminal) to the new state via `current/` symlink repoint, no file copying; crash-mid-swap leaves desktop consistent and repairable on next run. (CAP-3)
FR-4: System records current desktop state (current.json) and append-only history (history.jsonl), one line per reconcile, survives restarts, never overwritten. (CAP-4)
FR-5: On a freshly provisioned machine, runtime self-seeds its cache from provisioning's default output (default.png palette/effects/icons), writes current.json, creates current/ symlinks, and repoints consumer paths. (CAP-5)
FR-6: System reloads desktop components after a swap: Hyprland reload, AGS bar re-reads its palette fragment, Hyprpaper shows new wallpaper, terminal applies new palette. (CAP-6)
FR-7: User can inspect runtime state: current wallpaper/palette/effects/icons (status), state history (history), cache contents (cache list). (CAP-7)
FR-8: Cache-key correctness is verified before caching is trusted: CSG determinism (same wallpaper + templates -> same palette) must be confirmed. (derived from assumption audit / R4)
FR-9: Provisioning re-apply must not clobber runtime-repointed consumer symlinks (colors.conf/colors.css); a don't-clobber guard preserves runtime ownership across re-applies. (derived from cascading failure / R3)
FR-10: The bar shell is AGS (Aylur's GTK Shell v2), fully replacing Waybar across provisioning and runtime. (correct-course 2026-08-18)
FR-11: Per-monitor wallpaper configuration: each monitor can have a different wallpaper source and backend (hyprpaper, swaybg, swww, mpvpaper), configured via `current.json.monitors`. Auto-detection by file extension (video→mpvpaper, GIF→swww, static→hyprpaper). (AD-18)
FR-12: Wallpaper backend abstraction: `IStaticWallpaperBackend` (hyprpaper, swaybg, swww) and `IVideoWallpaperBackend` (mpvpaper) ports with `IWallpaperBackendFactory` for instantiation. Backend availability verified at use-time; missing backend = hard error. mpvpaper IPC socket at `$XDG_RUNTIME_DIR/mpvpaper-<monitor>.sock`. (AD-18)
FR-13: Provisioning installs all wallpaper backends (hyprpaper, swaybg, swww/awww, mpvpaper) via packages role. (AD-18, provisioning delta)

### NonFunctional Requirements

NFR-1: Hexagonal architecture; dependencies point inward; domain pure (stdlib allowlist, no os/subprocess/shutil/pathlib, no Path FS calls); ports are ABCs; layering mechanically enforced by test_layering.py mirroring provisioning. (Constraint 1)
NFR-2: Synchronous imperative execution model for Phase 2; no daemon, async, event bus, plugin system, or distributed execution. (Constraint 2)
NFR-3: Filesystem is the authority; cache/ contents and current/ symlinks are truth; current.json/history.jsonl/meta.json are an index + history, re-derivable except history. (Constraint 3)
NFR-4: state_root = XDG_STATE_HOME/dotfiles/, runtime-owned; runtime never writes under install spine after seeding; provisioning never writes under state_root. (Constraint 4)
NFR-5: JSON/dict-like store only (current.json + history.jsonl + per-entry meta.json, schemas pinned in shared-data-contract.md); no SQLite, ORM, or multi-backend. (Constraint 5)
NFR-6: Content hashing is SHA-256, recorded as hash_algorithm in every meta.json; cache entry dirs named by hash of ALL derivation inputs (templates/catalog/mappings included). (Constraint 6)
NFR-7: Swap = repoint current/ symlinks only (no copying); symlinks lead, current.json follows; swap sequence owned by ReconcileDesktopStateUseCase per shared-data-contract. (Constraint 7)
NFR-8: CSG/WEG/ITR output directed via env-var overrides per call (literal keys in shared-data-contract); provisioning-rendered settings.toml never edited by runtime; csg container-mode override passed into container env. (Constraint 8)
NFR-9: Cross-package boundary: runtime imports only cli_output (and declared deps); never provisioning or cli-tools packages; reads provisioning output/settings as data only. (Constraint 9)
NFR-10: Runtime core is a nested-hexagon uv package at src/runtime/src/runtime/{domain,ports,adapters,application,cli} with tests/architecture/test_layering.py. (Constraint 10)

### Additional Requirements

AR-1: Runtime core is a Typer CLI installed via provisioning cli_tools role (uv tool install); provisioning owns install/PATH/container-engine; ops are synchronous CLI commands; logging via cli_output. (AD-18)
AR-2: Layered content-addressed cache: one cache level per derivation layer (wallpapers/palettes/effects/icons), entry keyed by hash of ALL derivation inputs. (AD-2)
AR-3: history.jsonl is must-not-lose; append-only, atomic append, never overwritten; every reconcile appends before reload considered complete. (AD-4)
AR-4: Cache population uses staging-dir pattern (cache/.staging-<pid>/ then os.rename); existing final entry never overwritten; staging discarded if target exists. (AD-9)
AR-5: Domain model is a derivation graph (WallpaperEntry → PaletteEntry + EffectsEntry; PaletteEntry → IconsEntry); DesktopState = projection of current derivation outputs. (AD-10)
AR-6: First-run self-seeding when current.json absent and <install>/generated/ output exists; post-seed regeneration reads spine inputs (templates/catalog/mappings) READ-ONLY. (AD-11)
AR-7: Wallpaper hardlinked into cache/wallpapers/<hash>/wallpaper.png at population time (copy fallback cross-filesystem). (AD-16)
AR-8: Consumer wiring: Hyprland colors.conf → current/colors.conf; AGS bar CSS palette fragment → current/colors.gtk.css; Hyprpaper → current/wallpaper.png; ITR color_scheme.path → current/colors.yaml. Consumer-path flips performed by the runtime seeder (R2); provisioning keeps pre-runtime copies + don't-clobber guard. (AD-17)
AR-9: On-disk schemas (current.json, history.jsonl, per-layer meta.json), canonical cache-key input sets, literal env-override keys, and swap sequence are pinned in shared-data-contract.md and must be written exactly. (shared-data-contract)
AR-10: Phase 2 non-goals: no content-hash invalidation (P3), no diff engine/declarative reconciliation (P4), no daemon/watchers (P5), no parallel/plugins/distributed cache (P6), no package installation (provisioning domain), no cache eviction policy (P3+; list/prune stubs only in P2).

### FR Coverage Map

FR-1: Epic 1 - Wallpaper set command + derivation pipeline (CAP-1)
FR-2: Epic 1 - Content-hash cache hit reuse (CAP-2)
FR-3: Epic 2 - Symlink repoint swap + crash consistency (CAP-3)
FR-4: Epic 3 - State persistence + history (CAP-4)
FR-5: Epic 1 - First-run self-seeding (CAP-5)
FR-6: Epic 2 - Desktop reload adapters (CAP-6)
FR-7: Epic 3 - Inspection commands (CAP-7)
FR-8: Epic 1 - Cache-key correctness verification / CSG determinism (R4)
FR-9: Epic 1 - Provisioning don't-clobber guard (R3)
FR-10: Epic 1 - AGS bar-shell provisioning swap (correct-course 2026-08-18, replaces Waybar)
FR-11: Epic 1 - Per-monitor wallpaper config + auto-detect (AD-18)
FR-12: Epic 1 - Wallpaper backend ports + factory + adapters (AD-18)
FR-13: Epic 1 - Provisioning wallpaper backend packages (AD-18, provisioning delta)

## Epic List

### Epic 1: Wallpaper & State Foundation
User can set a wallpaper and the system derives + caches its palette/effects/icons for instant reuse, while recording the current desktop state (current.json + minimal IStateRepository) so later convergence and recovery are grounded — including on a freshly provisioned machine. Supports per-monitor wallpaper configuration with pluggable backends (hyprpaper, swaybg, swww, mpvpaper) via auto-detection and explicit selection.
**FRs covered:** FR-1, FR-2, FR-5, FR-8, FR-9, FR-10, FR-11, FR-12, FR-13
**CAPs covered:** CAP-1, CAP-2, CAP-5 (+ minimal CAP-4 store)

### Epic 2: Desktop Convergence
User's desktop visually converges to the new wallpaper's colors — Hyprland, AGS bar, Hyprpaper, terminal — via atomic symlink swap + reload, resilient to crashes and repairable on next run from the state recorded in Epic 1. Per-monitor convergence: each monitor's wallpaper backend (hyprpaper, swaybg, swww, mpvpaper) is invoked to apply its configured source.
**FRs covered:** FR-3, FR-6, FR-11
**CAPs covered:** CAP-3, CAP-6

**Correct-course (2026-08-18): the bar is AGS (Aylur's GTK Shell v2), fully replacing Waybar across provisioning and runtime.** This adds cross-domain stories: an AGS provisioning swap (packages/config-in-spine/compositor_configs/config_links/verify + the 13 waybar tests → AGS) and an AGS reload-channel verification (hot-reload vs restart vs dbus). The AGS swap is a prerequisite to Epic 2's reload adapter — it must land in Epic 1 (or as a pre-Epic-2 change) so the bar exists for the runtime to converge.

### Epic 3: State Inspection & History
User can inspect the current runtime state and view an append-only history of desktop state transitions, plus cache listing.
**FRs covered:** FR-4, FR-7
**CAPs covered:** CAP-4, CAP-7

<!-- End Epic List -->

## Implementation notes (from advanced elicitation R1-R5)

- **R1 (state-first):** Epic 1 owns the store schema + minimal IStateRepository (current.json write + read for recovery). Epic 3 completes history + inspection. Epic 2's crash-repair reads current.json written by Epic 1.
- **R2 (provisioning delta ownership):** the consumer-path flip (colors.conf/colors.css -> current/) is performed by the RUNTIME SEEDER as its last step, NOT by provisioning apply. Provisioning keeps the pre-runtime copy (Phase-1 behavior); no dangling-symlink first boot. Amends AD-17.
- **R3 (don't-clobber guard):** provisioning compositor_configs/config_copies roles skip overwriting colors.conf/colors.css when they are already runtime symlinks. New cross-domain story in Epic 1.
- **R4 (determinism verification):** CSG determinism verification is an explicit Epic 1 story, before the cache is trusted.
- **R5 (recovery + reload-failure ACs):** Epic 2 stories carry acceptance criteria for crash-mid-swap recovery (revert to last-good current.json, re-run is cache hit) and reload-failure handling (reload adapter reports failure; known limitation in Phase 2, no daemon).

---

## Epic 1: Wallpaper & State Foundation

### Story 1.1: Nested-hexagon scaffold with layering test

As a developer,
I want the `dotfiles-runtime` package scaffolded as a nested hexagon,
So that Phase 2 code lands in the right layers from day one and the §11 boundary is enforced mechanically.

**Acceptance Criteria:**

**Given** the `src/runtime/` uv package does not exist
**When** the scaffold story completes
**Then** `src/runtime/src/runtime/{domain,ports,adapters,application,cli}` exist with `__init__.py` files
**And** `tests/architecture/test_layering.py` mirrors provisioning's (domain stdlib allowlist, banned stdlib, no Path FS calls, ports-as-ABCs, cross-package forbidden set)
**And** a deliberately-violating import fails the layering test
**And** `uv run --directory src/runtime pytest` passes on the scaffold

### Story 1.2: Domain model — derivation graph

As a developer,
I want the derivation-graph domain entities,
So that the core has pure, zero-I/O representations of wallpapers, palettes, effects, and icons keyed by their derivation inputs.

**Acceptance Criteria:**

**Given** the domain layer exists
**When** `WallpaperEntry`, `PaletteEntry`, `EffectsEntry`, `IconsEntry` are defined as frozen dataclasses
**Then** each carries its input hashes and `artifact_hashes` per the shared-data-contract schemas
**And** the domain imports only the stdlib allowlist (no os/subprocess/shutil/pathlib)
**And** the layering test passes for domain files

### Story 1.3: Ports — domain capabilities

As a developer,
I want ABC ports for every runtime capability,
So that adapters can be swapped without touching the core.

**Acceptance Criteria:**

**Given** the ports layer exists
**When** `IWallpaperBackend`, `IColorSchemeGenerator`, `IEffectsGenerator`, `IIconRenderer`, `IDesktopConfigWriter`, `IDesktopReloader`, `IStateRepository` (minimal `load_current`/`save`) are defined
**Then** all are ABCs (or Protocols) with abstract methods
**And** any concrete class in ports/ fails the layering test

### Story 1.4: CSG determinism verification

As a developer,
I want to verify CSG is deterministic,
So that the cache key (wallpaper_hash, template_hash) is trustworthy before caching is relied on.

**Acceptance Criteria:**

**Given** a fixed wallpaper and CSG template set
**When** `csg generate` runs twice on the same inputs
**Then** both runs produce identical palette content (same artifact hashes)
**And** the determinism result is recorded in the run memlog
**And** if nondeterministic, the cache key is amended to include a pinned seed (documented decision)

### Story 1.5: Content hashing and cache-key canonicalization

As a developer,
I want SHA-256 content hashing with canonicalized derivation-input keys,
So that cache entries are addressed by the hash of all their inputs and template/catalog changes invalidate correctly.

**Acceptance Criteria:**

**Given** the shared-data-contract canonicalization rules
**When** an input set (wallpaper+templates, wallpaper+catalog, palette+templates+mappings) is hashed
**Then** identical input sets yield identical hashes and differing sets yield differing hashes
**And** cache entry dirs are named `<layer>/<hash>` and `meta.json` records `hash_algorithm: sha256`

### Story 1.6: Layered cache populator with staging-dir

As a developer,
I want write-once cache entries populated via the staging-dir pattern,
So that concurrent population is safe and cache entries are never half-written.

**Acceptance Criteria:**

**Given** a target `cache/<layer>/<hash>/` entry
**When** population runs
**Then** artifacts are generated into `cache/.staging-<pid>/` then atomically renamed to the final entry
**And** an existing final entry is never overwritten (staging discarded)
**And** the wallpaper is hardlinked (copy fallback cross-filesystem), surviving source-file deletion

### Story 1.7: csg adapter with env override

As a developer,
I want a csg adapter that directs output via env override,
So that palettes land in the cache without editing provisioning's settings.toml.

**Acceptance Criteria:**

**Given** a cached wallpaper entry
**When** `IColorSchemeGenerator.generate` is invoked with `COLORSCHEME__OUTPUT__DIRECTORY=<state>/cache/palettes/<ph>/`
**Then** `colors.yaml`, `colors.conf`, `colors.gtk.css` are written to the target dir
**And** the rendered settings.toml is untouched
**And** container mode passes the override INTO the container environment

### Story 1.8: weg adapter with env override

As a developer,
I want a weg adapter that directs effects output via env override,
So that effect images land in the cache without editing provisioning's settings.toml.

**Acceptance Criteria:**

**Given** a cached wallpaper entry
**When** `IEffectsGenerator.generate` is invoked with `WALLPAPER__OUTPUT__DIRECTORY=<state>/cache/effects/<eh>/`
**Then** effect images are written to the target dir
**And** the rendered settings.toml is untouched

### Story 1.9: itr adapter with env overrides

As a developer,
I want an itr adapter that directs icon output and palette input via env overrides,
So that icons land in the cache chained to the cached palette without editing settings.toml.

**Acceptance Criteria:**

**Given** a cached palette entry
**When** `IIconRenderer.render` is invoked with `ICON_RENDERER__OUTPUT__OUTPUT_DIR=<state>/cache/icons/<ih>/` and `ICON_RENDERER__COLOR_SCHEME__PATH=<state>/cache/palettes/<ph>/colors.yaml`
**Then** rendered SVG icons are written to the target dir
**And** the rendered settings.toml is untouched

### Story 1.10: Minimal IStateRepository with JSON adapter

As a developer,
I want the minimal state store (current.json read/write per the pinned schema),
So that Epic 2's crash recovery is grounded in recorded state.

**Acceptance Criteria:**

**Given** the shared-data-contract current.json schema
**When** `IStateRepository.save(state)` and `load_current()` run
**Then** save is atomic (tmp + `os.replace`), load round-trips the state
**And** a schema_version mismatch is surfaced as an error
**And** absent store (first run) returns an empty state without crashing

### Story 1.11: First-run self-seeding

As a user,
I want a freshly provisioned machine to adopt the default desktop state automatically,
So that I never perform manual seeding steps.

**Acceptance Criteria:**

**Given** `current.json` is absent and provisioning's `<install>/generated/` output exists
**When** the first runtime command runs
**Then** cache entries are seeded from the default palette/effects/icons, `current.json` is written, `current/` symlinks are created
**And** consumer paths are repointed to `current/` as the final step (no dangling symlinks on a fresh machine)
**And** `history.jsonl` gains a line with `trigger: seed`

### Story 1.12: Provisioning don't-clobber guard

As a user,
I want provisioning re-applies to respect runtime-owned consumer symlinks,
So that my configured wallpaper survives a `dotfiles-provision apply` re-run.

**Acceptance Criteria:**

**Given** colors.conf/colors.css are already runtime symlinks into `current/`
**When** `compositor_configs`/`config_copies` run again
**Then** the runtime symlinks are left untouched
**And** pre-runtime (plain copy) paths are still written on a fresh machine
**And** `dotfiles-provision verify` criterion 6 accepts either generated/ or current/ palette presence

### Story 1.13: ApplyWallpaperUseCase — derive, cache, persist

As a user,
I want `dotfiles-runtime wallpaper set <img>` to derive, cache, and persist the desktop state,
So that my wallpaper's palette/effects/icons are ready for instant reuse and the state is recorded.

**Acceptance Criteria:**

**Given** a provisioned machine with seeded state
**When** `dotfiles-runtime wallpaper set <img>` runs with a new wallpaper
**Then** the wallpaper is hashed, cache entries are created (miss path invokes csg/weg/itr), and `current.json` is updated
**And** re-setting the same img is a cache hit (zero tool invocations)
**And** re-setting a previously-used wallpaper is a cache hit
**And** `current.json` reflects the new wallpaper hash (full desktop convergence + reload land in Epic 2)

### Story 1.14: AGS bar-shell provisioning swap ✅ IMPLEMENTED (2026-08-18)

As a user,
I want the AGS (Aylur's GTK Shell) bar to replace Waybar across provisioning,
So that the bar is AGS and the runtime has a real bar to converge in Epic 2.

**Sequencing (2026-08-18):** this story was pulled ahead of Epic 2 runtime
convergence at the human's direction — build + verify the provisioning swap and a
minimal AGS project FIRST, so the runtime has a proven bar to converge later. Done.

**Acceptance Criteria:**

**Given** the completed Phase 1 provisioning that installs Waybar
**When** the AGS swap story completes
**Then** `packages.yaml` installs `ags` (AUR-only `aylurs-gtk-shell-git`, routed via the packages role `aur_packages` channel) instead of `waybar` ✅
**And** `dotfiles/config/ags/` holds the minimal AGS project (`app.tsx` + `style.css` applying the palette fragment `colors.css` at RUNTIME via `app.apply_css`), replacing `dotfiles/config/waybar/` (removed) ✅
**And** `compositor_configs`, `filesystem`, `config_links`, and `verify` reference AGS (`~/.config/ags` symlink into the spine, `config/ags` dir, AGS as a system binary + done-criteria) ✅
**And** the Waybar references in the 13+ provisioning tests are updated to AGS ✅
**And** `dotfiles-provision verify` passes on a fresh machine with AGS (475 unit tests green) ✅

**Evidence:** minimal AGS project auto-discovered by bare `ags run` at
`~/.config/ags/app.tsx`; `exec-once = ags run` autostart in hyprland.conf; AGS has NO
native hot-reload (verified `cli/cmd/run.go:145`) — the Epic 2 reload adapter must
restart the process. The palette fragment repoint to `current/colors.gtk.css` works
because AGS applies `colors.css` at runtime.

---

## Epic 2: Desktop Convergence

User's desktop visually converges to the new wallpaper's colors — Hyprland, AGS bar,
Hyprpaper, terminal — via atomic `current/` symlink swap + reload, resilient to crashes
and repairable on next run from the state recorded in Epic 1.
**FRs covered:** FR-3, FR-6
**CAPs covered:** CAP-3, CAP-6

### Story 2.1: Atomic `current/` symlink repoint and swap sequencing

As a user,
I want a wallpaper swap to converge the desktop by repointing the `current/` symlinks only,
So that all consumers atomically see the new state with no file copying.

**Acceptance Criteria:**

**Given** a completed derivation (wallpaper/palette/effects/icons cached, `current.json` written in Epic 1)
**When** the ReconcileDesktopStateUseCase performs a swap
**Then** it repoints only the `current/` symlinks (Hyprland `colors.conf`, AGS `colors.gtk.css`, Hyprpaper `wallpaper.png`, ITR `colors.yaml`) — the shared-data-contract swap sequence exactly, symlinks lead, `current.json` follows (AR-8, AD-7/NFR-7)
**And** no file is copied during the swap
**And** the swap is ordered as a discrete step so a later, single non-atomic point is identifiable for crash recovery (the recovery story builds on this ordering)
**And** the ReconcileDesktopStateUseCase is callable as an independently-invoked command (`dotfiles-runtime reconcile`), and the full-pipeline orchestration (derive → cache → swap → reload) is owned by a later capstone story

### Story 2.2: Crash-mid-swap recovery to last-good state

As a user,
I want the desktop to stay consistent if a swap or reload is interrupted,
So that the next run repairs the state instead of leaving a partial swap.

**Acceptance Criteria:**

**Given** a swap is interrupted mid-sequence (crash, killed process, reload failure)
**When** the next run starts
**Then** it detects the incomplete swap from the persisted `current.json` + `current/` symlink comparison and reverts the stray `current/` repoints to the last-good `current.json` (FR-3, R5)
**And** re-running the interrupted reconcile is a cache hit (no tool re-invocation)
**And** a reload-failure is reported (known Phase 2 limitation — no daemon/watcher; the command surfaces which consumer failed to reload and exits non-zero) (R5)

### Story 2.3: Hyprland reload adapter

As a user,
I want Hyprland to pick up the new colors.conf after a swap,
So that the compositor's borders/decoration match the new palette.

**Acceptance Criteria:**

**Given** a swap repointed `current/colors.conf` (through the `~/.config/hypr` spine symlink)
**When** the Hyprland reload adapter runs
**Then** it invokes `hyprctl reload` (FR-6)
**And** it verifies the reload outcome and reports success/failure (R5 reload-failure handling)

### Story 2.4: AGS restart-based reload adapter

As a user,
I want the AGS bar to re-read its palette fragment after a swap,
So that the bar converges to the new colors.

**Acceptance Criteria:**

**Given** a swap repointed `current/colors.gtk.css` (through the `~/.config/ags` spine symlink to `colors.css`, applied at runtime via `app.apply_css`)
**When** the AGS reload adapter runs
**Then** it restarts the AGS process (`ags quit` then `ags run`) — AGS has NO native hot-reload (verified), so a restart is the reload channel (FR-6)
**And** it verifies the restart succeeded and reports failure if the process fails to come back (R5)

### Story 2.5: Hyprpaper channel verification and reload adapter

As a user,
I want the wallpaper to visually change after a swap,
So that the desktop shows the new wallpaper.

**Acceptance Criteria:**

**Given** a swap repointed `current/wallpaper.png` (through the Hyprpaper config spine path)
**When** the Hyprpaper adapter runs
**Then** it uses the HYPAPER reload mechanism VERIFIED against the installed Hyprpaper version — reload-after-symlink-repoint vs `hyprctl hyprpaper wallpaper <monitor> <path>` IPC — and the chosen channel is recorded in the code + docs (FR-6)
**And** the unverified-to-verified transition (from the opening fact list) is closed with the evidence of which channel works
**And** it reports failure if the wallpaper does not update (R5)

### Story 2.6: Terminal palette applier

As a user,
I want the terminal to apply the new palette after a swap,
So that shell/terminal colors match the wallpaper.

**Acceptance Criteria:**

**Given** a swap produced `current/colors.yaml` (and the derived palette)
**When** the terminal palette applier runs
**Then** it applies the palette to the terminal consumers wired in Epic 1/seeding (starship/zsh per the consumer-wiring chain, AD-17/AR-8) (FR-6)
**And** it reports failure if the terminal cannot be re-themed (R5)

### Story 2.7: Full `wallpaper set` end-to-end capstone

As a user,
I want `dotfiles-runtime wallpaper set <img>` to converge the entire desktop in one command,
So that changing a wallpaper is a single synchronous step that derives, caches, swaps, reloads, and persists.

**Acceptance Criteria:**

**Given** the pipeline components from Epic 1 (derive/cache/persist) and Epic 2 (swap + reload adapters 2.3–2.6)
**When** `dotfiles-runtime wallpaper set <img>` runs
**Then** it derives + caches (cache hit on repeat), performs the atomic swap (2.1), reloads all consumers (2.3–2.6), and persists `current.json` + appends `history.jsonl` (FR-1)
**And** on crash, the next run repairs via 2.2
**And** on reload failure, the command reports which consumer failed and exits non-zero (R5)

---

## Epic 3: State Inspection & History

User can inspect the current runtime state, view an append-only history of desktop state transitions, and list the layered cache.
**FRs covered:** FR-4, FR-7
**CAPs covered:** CAP-4, CAP-7

### Story 3.1: history.jsonl must-not-lose persistence

As a user,
I want every desktop state transition recorded in an append-only, never-lost history,
So that I can audit what changed and when, even across restarts.

**Acceptance Criteria:**

**Given** a reconcile completes (Epic 1/2 pipeline)
**When** the state transitions
**Then** a history.jsonl line is appended ATOMICALLY, one line per reconcile, in the pinned schema (shared-data-contract), AFTER the swap and BEFORE reload is considered complete (AR-3, AD-4/NFR-5)
**And** history.jsonl is never overwritten or rewritten — only appended (must-not-lose)
**And** the store survives restart: history persists across process runs (FR-4)
**And** `current.json` (written in Epic 1) + `history.jsonl` together form the full persisted state (index + history; filesystem/current/ remains the authority, NFR-3)

### Story 3.2: inspect status command

As a user,
I want to see the current desktop state,
So that I know what wallpaper/palette/effects/icons are active.

**Acceptance Criteria:**

**Given** `dotfiles-runtime inspect status` runs
**Then** it prints the current wallpaper, palette, effects, and icons derived from `current.json` + the `current/` symlink targets (FR-7, CAP-7)
**And** it reflects the live `current/` symlink (filesystem authority) not just the index
**And** it exits non-zero with a clear message if state is absent (never seeded / missing current.json)

### Story 3.3: inspect history command

As a user,
I want to view the append-only desktop history,
So that I can review past state transitions.

**Acceptance Criteria:**

**Given** `dotfiles-runtime inspect history` runs
**Then** it prints the transition log from `history.jsonl`, newest-first, using the pinned line schema (FR-7, CAP-7)
**And** it pages/limits output for large histories
**And** it reports cleanly if history is empty

### Story 3.4: inspect cache list command

As a user,
I want to inspect the layered cache,
So that I can see what derived artifacts are cached (and by hash).

**Acceptance Criteria:**

**Given** `dotfiles-runtime inspect cache list` runs
**Then** it lists each cache layer (wallpapers/palettes/effects/icons) and its entries by hash (FR-7, AR-2, CAP-7)
**And** prune/eviction are NOT implemented in Phase 2 — list-only, eviction is a future-phase stub (AR-10, NFR-3)
