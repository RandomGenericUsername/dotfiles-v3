---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/gtk-theming-investigation.md
  - _bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md
  - _bmad-output/specs/spec-dotfiles-runtime-phase2/cache-model.md
  - _bmad-output/specs/spec-dotfiles-runtime-phase2/consumer-wiring.md
  - _bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md
---

# dotfiles-repo-v3 - Epic Breakdown (GTK Theming Consumer — Phase 2.x remediation)

## Overview

Makes the **system GTK toolkit (GTK3 + GTK4/libadwaita) and new-shell terminal colors
runtime consumers** of the wallpaper palette, closing the investigation in
`gtk-theming-investigation.md`. Cross-domain: csg (format), runtime (artifact set +
declarative consumer pointers), provisioning (GTK config-in-spine + zshrc repoint),
AGS/icme (polish). Built on worktree `feat/gtk-theming-consumer`.

## Requirements Inventory

### Functional Requirements

FR-1: csg derives `colors.adw.css` — palette mapped to libadwaita named colors — as a first-class format alongside the existing nine. (P1)
FR-2: Runtime palette cache entries contain `colors.adw.css` + `colors.sequences` artifacts, hashed in `meta.json`, keyed by the unchanged `sha256(ph‖templates)`. (P1, P3)
FR-3: `current/colors.adw.css` and `current/colors.sequences` exist after derive/seed/reconcile, and consumer-pointer symlinks `config/gtk-3.0/colors.css → current/colors.gtk.css`, `config/gtk-4.0/colors.css → current/colors.adw.css` join the AGS pointer via a **declarative ConsumerPointer spec** (single adapter loop; null-palette removal, file-replace, never-dangling rules). (P1, P2, P3)
FR-4: Provisioning deploys GTK config-in-spine: spine `config/gtk-3.0/` + `config/gtk-4.0/` with `gtk.css` `@import "colors.css";` skeletons; user's existing `gtk-3.0` files migrated via the backup guard; `~/.config/gtk-{3,4}.0` symlinks. (P2)
FR-5: `.zshrc` cats `$XDG_STATE_HOME/dotfiles/current/colors.sequences` — never the orphaned `generated/` tree. (P3)
FR-6: `TerminalColorApplier` applies the palette from the `current/colors.sequences` artifact (byte-read) instead of re-deriving OSC bytes from colors.yaml. (P3)
FR-7: AGS/icme surfaces (bar buttons, menus/popovers) inherit the wallpaper palette through libadwaita named-color overrides; `style.css` manual light-theme resets are removed where they fight the palette. (P1)

### Non-Functional Requirements

NFR-1: Hexagonal — dependencies point inward; domain pure; `test_layering.py` green at every story. (AD-1/AD-13/AD-14)
NFR-2: §11 boundary — runtime writes under install spine ONLY the ConsumerPointer symlinks (AD-11 exception extended to a spec'd class); provisioning never writes under `state_root`. (AD-5/AD-15)
NFR-3: Same atomicity as Phase 2 (tmp+rename, O_APPEND); pointer loop idempotent and re-runnable. (AD-6/AD-12)
NFR-4: No new hash formulas, no cache-layout change, no SQLite. (AD-2/AD-3/AD-8)
NFR-5: Consumers pick up new colors on relaunch (documented limitation, same class as AGS restart); no daemon/watchers. (AD-12)

### Additional Requirements

AR-1: Consumer-pointer table is contract data in `shared-data-contract.md`; adding a consumer = spec entry + `@import`, no adapter code change.
AR-2: The adw mapping table (palette slot → named color) is pinned in csg docs; template edits auto-invalidate via the existing cache key.
AR-3: Stories keep Phase 2 behaviors byte-compatible where not in scope (default `cache list` output, history schema, swap sequence).
AR-4: `icme` is an AGS/GTK4 app — covered by FR-7's libadwaita overrides; no icme-specific code.

### FR Coverage Map

FR-1: Epic 1 — csg adw.css format
FR-2: Epic 2 — artifact set growth (domain + adapters)
FR-3: Epic 2 — declarative consumer pointers + current/ entries
FR-4: Epic 3 — GTK config-in-spine (provisioning)
FR-5: Epic 3 — zshrc repoint (provisioning)
FR-6: Epic 2 — TerminalColorApplier artifact switch
FR-7: Epic 4 — AGS/icme palette polish + docs

## Epic List

### Epic 1: csg adw.css format
csg gains the libadwaita named-color override format so GTK4 surfaces can wear the wallpaper palette. Own suite; standalone package unchanged in shape.
**FRs covered:** FR-1

### Epic 2: Runtime artifact set + declarative consumer pointers
Runtime cache gains the two artifacts and generalizes consumer-path flipping into contract-driven data, killing the hardcoded AGS repoint.
**FRs covered:** FR-2, FR-3, FR-6

### Epic 3: GTK config-in-spine (provisioning)
Provisioning deploys the GTK consumer skeleton into the spine with backup-guard migration and repoints the shell's palette source to runtime state.
**FRs covered:** FR-4, FR-5

### Epic 4: Consumer polish + docs
AGS/icme visual convergence and documentation reconciliation.
**FRs covered:** FR-7

<!-- End Epic List -->

---

## Epic 1: csg adw.css format

csg gains the libadwaita named-color override format so GTK4 surfaces can wear the wallpaper palette. Own suite; standalone package unchanged in shape.
**FRs covered:** FR-1

### Story 1.1: `ColorFormat.ADW_CSS` + `colors.adw.css.j2`

As a developer,
I want a new csg format `adw.css` mapping the palette to libadwaita named colors,
So that GTK4/libadwaita apps (AGS bar chrome, icme, dialogs) can be recolored from the wallpaper palette.

**Acceptance Criteria:**

**Given** the existing `ColorFormat` enum and template catalog (`colors.gtk.css.j2` pattern)
**When** `ADW_CSS = "adw.css"` is added with `defaults/templates/colors.adw.css.j2`
**Then** rendered output defines `window_bg_color`, `view_bg_color`, `headerbar_bg_color`, `card_bg_color`, `dialog_bg_color`, `popover_bg_color`, `sidebar_bg_color` ← background; `window_fg_color`, `view_fg_color`, `headerbar_fg_color`, `card_fg_color`, `sidebar_fg_color` ← foreground; `accent_color`/`accent_bg_color` ← color_04 with `accent_fg_color` ← background; destructive/success/warning/error sets from the pinned §5 mapping table
**And** `@define-color color_00..15` passthrough lines are included (GTK3-compatible custom names)
**And** `csg generate <img> -f adw.css` writes `colors.adw.css` locally AND in container mode
**And** the mapping table is documented in csg's docs (AR-2) and covered by unit + an integration render test asserting named-color completeness
**And** `csg dump-templates` includes the new template; catalog/dry-run list it

---

## Epic 2: Runtime artifact set + declarative consumer pointers

Runtime cache gains the two artifacts and generalizes consumer-path flipping into contract-driven data, killing the hardcoded AGS repoint.
**FRs covered:** FR-2, FR-3, FR-6

### Story 2.1: Palette artifact set growth (contract + domain + adapters)

As a developer,
I want the palette cache entry to contain `colors.adw.css` and `colors.sequences`,
So that GTK and shell consumers read runtime-owned, hash-addressed artifacts.

**Acceptance Criteria:**

**Given** `shared-data-contract.md` pins the palette artifact set
**When** the set grows to `colors.yaml, colors.conf, colors.gtk.css, colors.adw.css, colors.sequences`
**Then** domain `PaletteArtifacts` gains `colors_adw_css` + `colors_sequences` fields
**And** `CsgAdapter` requests `-f ... -f adw.css -f sequences` and hashes all five artifacts into meta.json
**And** `derive.py`, `seeder.py`, `reconcile.py`, `inspect.py` expected-name lists include the new artifacts
**And** `current/` gains `colors.adw.css` + `colors.sequences` symlinks in seed AND reconcile paths
**And** cache keys are unchanged (`sha256(ph‖templates)` — NFR-4); `test_layering.py` green
**And** existing cache entries WITHOUT the new artifacts are cache misses → regenerated (migration note documented)

### Story 2.2: `IConsumerPathSpec` — declarative consumer pointers

As a developer,
I want the consumer-pointer table as contract data driving a single adapter loop,
So that adding a consumer (rofi, dunst, wlogout) is a spec entry, never bespoke code.

**Acceptance Criteria:**

**Given** the pinned ConsumerPointer table in `shared-data-contract.md` (ags/gtk-3.0/gtk-4.0 entries + rules)
**When** `IConsumerPathSpec` (ports) exposes the table and `CacheSeeder.repoint_consumer_symlinks` consumes it generically
**Then** each pointer follows the rules: palette null → pointer removed (`missing_ok`); regular file at destination → replaced with symlink; missing target artifact → skip + warn (never dangling)
**Then** — additionally — the AGS behavior is byte-compatible with today's (P2 migration preserved)
**And** doctor and `inspect status` report the new pointers (ok/missing/diverged/dangling) without bespoke per-consumer code
**And** no new writes under the install spine beyond the spec'd pointers (AD-11 exception class, NFR-2); layering test green

### Story 2.3: TerminalColorApplier reads the artifact

As a user,
I want the terminal palette applied from the pinned `current/colors.sequences` artifact,
So that the OSC bytes have a single source of truth shared with new shells.

**Acceptance Criteria:**

**Given** `current/colors.sequences` exists as a cache artifact
**When** `TerminalColorApplier.reload()` runs
**Then** it reads the artifact bytes and writes them to `/dev/tty` once (behavior-identical payload to the re-derived bytes)
**And** the colors.yaml parser path is retired (or kept only as fallback documented as deprecated — pick one and pin it)
**And** vacuous/missing/dangling precedence (AC-4-before-AC-3) is preserved; unit + integration tests updated

---

## Epic 3: GTK config-in-spine (provisioning)

Provisioning deploys the GTK consumer skeleton into the spine with backup-guard migration and repoints the shell's palette source to runtime state.
**FRs covered:** FR-4, FR-5

### Story 3.1: GTK config dirs in the spine + config_links

As a user,
I want `~/.config/gtk-3.0` and `~/.config/gtk-4.0` as spine symlinks with palette-importing skeletons,
So that GTK apps read the wallpaper palette from the runtime's `current/` pointers.

**Acceptance Criteria:**

**Given** the user's existing `~/.config/gtk-3.0/{settings.ini,gtk.css}` (real files, user-owned)
**When** provisioning apply runs
**Then** spine `config/gtk-3.0/` holds the user's migrated `settings.ini` + `gtk.css` (backup guard: timestamped copy under `~/.config/.dotfiles-backups/`, never `rm -rf`) plus a palette import line appended/merged into `gtk.css` (`@import "colors.css";`)
**And** spine `config/gtk-4.0/` holds a new `gtk.css` with `@import "colors.css";`
**And** `config_links` creates `~/.config/gtk-{3,4}.0` → spine symlinks (idempotent, already-ours = no-op)
**And** verify gains a criterion asserting both symlinks + skeleton files; `nwg-look` write-through is documented (writes land in the spine through the link)

### Story 3.2: zshrc repoint to current/colors.sequences

As a user,
I want every new shell themed from the runtime's current palette,
So that my terminal stops reading the orphaned pre-Epic-4 `generated/` tree.

**Acceptance Criteria:**

**Given** `dotfiles/config/zsh/.zshrc.j2:30` cats `{{COLOR_SCHEME_OUTPUT_DIR}}/colors.sequences`
**When** the template is repointed to the state root (`$XDG_STATE_HOME/dotfiles/current/colors.sequences`)
**Then** rendered `.zshrc` cats the current pointer (absent until first seed → harmless backgrounded cat)
**And** the `COLOR_SCHEME_OUTPUT_DIR` template var is retired or repurposed with no dangling references
**And** provisioning verify/CLI-parity tests updated; a live-shell test sources the new `.zshrc` and reads the correct palette

---

## Epic 4: Consumer polish + docs

AGS/icme visual convergence and documentation reconciliation.
**FRs covered:** FR-7

### Story 4.1: AGS style palette inheritance + icme verification

As a user,
I want the bar buttons, menus/popovers, and icme to wear the wallpaper palette,
So that no GTK surface renders default light Adwaita.

**Acceptance Criteria:**

**Given** the adw overrides land via `~/.config/gtk-4.0/gtk.css @import colors.css → current/colors.adw.css`
**When** AGS and icme relaunch
**Then** button chrome, popovers/menus, and dialogs inherit the palette (no white Adwaita surfaces — matches the screenshot symptom)
**And** `style.css` manual light-theme resets (`.widget` background-image strips etc.) are removed where the palette now supplies the colors — deliberate per-line decision recorded
**And** a manual verification checklist (bar, popover, icme, screenshot tool) is recorded in the story file with relaunch steps

### Story 4.2: Docs + contract reconciliation

As a maintainer,
I want docs and contracts reconciled,
So that the consumer set, artifact set, and AD-11 exception are stated correctly.

**Acceptance Criteria:**

**Given** the changes above
**When** docs reconcile
**Then** `shared-data-contract.md` (artifact set + ConsumerPointer table), `consumer-wiring.md` (GTK3/GTK4/icme/sequences chains), `docs/99` consumer prose, ARCHITECTURE-SPINE AD-11 note, and `cache-model.md` layout are updated
**And** no doc still claims `.zshrc` reads `generated/palettes/`
