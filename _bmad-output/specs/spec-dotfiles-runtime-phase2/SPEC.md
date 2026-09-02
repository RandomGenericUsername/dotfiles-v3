---
id: SPEC-dotfiles-runtime-phase2
companions:
  - ../planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md
  - ../planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md
  - cache-model.md
  - consumer-wiring.md
  - provisioning-delta.md
  - architecture-diagrams.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# dotfiles-runtime-phase2 — Runtime Desktop Reconciliation Core

## Why

Phase 1 (provisioning) is complete and verify-gated: the machine has Hyprland, the AGS (Aylur's GTK Shell) bar, Hyprpaper, csg/weg/itr, the install spine, and a single default palette. But the desktop's *runtime* state is not reconciled — there is no command to change the wallpaper and converge the palette, effects, icons, and desktop colors to it. The pain: changing a wallpaper today is a manual chain (run csg, run weg, rewrite configs, reload the bar, regenerate icons) with no state tracking, no reuse, and no recovery. This spec captures the opportunity to prove deterministic runtime orchestration — a synchronous `dotfiles wallpaper set <img>` pipeline that derives, caches, swaps, reloads, and persists — as the foundation every later phase (state awareness, reconciliation, reactive runtime) builds on. **Correct-course 2026-08-18: the bar shell is AGS v2, fully replacing Waybar across provisioning and runtime.**

## Capabilities

- **CAP-1**
  - **intent:** User can set the desktop wallpaper from any image path.
  - **success:** The wallpaper is applied (visible), a palette and effects are derived, configs updated, desktop reloaded, state persisted — all via one command.

- **CAP-2**
  - **intent:** The system reuses previously-derived palette/effects/icons for a wallpaper it has seen before.
  - **success:** Re-setting the same wallpaper (or a previously-used one) performs zero csg/weg/itr invocations and returns from the cache.

- **CAP-3**
  - **intent:** Changing wallpaper converges all desktop consumers (Hyprland, AGS bar shell, Hyprpaper, terminal colors) to the new state without file copying.
  - **success:** After a swap, every consumer reads the new palette/wallpaper/effects through `current/` symlinks; a crash mid-swap leaves the desktop consistent and repairable on next run.

- **CAP-4**
  - **intent:** The system records the current desktop state and an append-only history of state transitions.
  - **success:** `current.json` reflects the active state; `history.jsonl` has one line per reconcile, survives restarts, and is never overwritten.

- **CAP-5**
  - **intent:** On a freshly provisioned machine, the runtime adopts the provisioning default palette/effects/icons into its cache without manual steps.
  - **success:** First `wallpaper set` after provisioning seeds the cache from install spine output, writes `current.json`, creates `current/` symlinks, and repoints consumer paths (colors.conf/colors.css → symlinks to `current/`, hyprpaper conf + ITR color_scheme path → `current/`) as the final seeding step. Pre-seeding, provisioning's pre-runtime copies keep the fresh machine working (no dangling symlinks).

- **CAP-6**
  - **intent:** The system tells running desktop components to re-read their configs after a swap.
  - **success:** Hyprland reloads, AGS bar re-reads its CSS/palette fragment, Hyprpaper shows the new wallpaper, terminal applies the new palette.

- **CAP-7**
  - **intent:** The user can view current state and history.
  - **success:** Commands exist to show current wallpaper/palette/effects/icons and list state history and cache contents.

## Constraints

- **Hexagonal architecture:** dependencies point inward; domain is pure (stdlib allowlist, no `os`/`subprocess`/`shutil`/`pathlib`, no Path FS calls); ports are ABCs; layering mechanically enforced by `test_layering.py` mirroring provisioning.
- **Synchronous imperative execution** for Phase 2: no daemon, async, event bus, plugin system, or distributed execution.
- **Filesystem is the authority:** `cache/` contents and `current/` symlinks are truth; `current.json`/`history.jsonl`/`meta.json` are an index + history, re-derivable except history.
- **state_root = `$XDG_STATE_HOME/dotfiles/`, runtime-owned.** Runtime never writes under the install spine after seeding; provisioning never writes under state_root.
- **JSON/dict-like store only** (`current.json` + `history.jsonl` + per-entry `meta.json`, schemas pinned in `shared-data-contract.md`). No SQLite, no ORM, no multi-backend.
- **Content hashing is SHA-256**, recorded as `hash_algorithm` in every `meta.json`; cache entry dirs named by hash of ALL derivation inputs (templates/catalog/mappings included).
- **Swap = repoint `current/` symlinks only** (no copying); symlinks lead, `current.json` follows; swap sequence owned by `ReconcileDesktopStateUseCase` per `shared-data-contract.md`.
- **CSG/WEG/ITR output directed via env-var overrides per call** (literal keys in `shared-data-contract.md`); provisioning-rendered `settings.toml` never edited by runtime; csg runs in container mode, override passed into container env.
- **Cross-package boundary:** runtime imports only `cli_output` (and declared deps); never provisioning or the cli-tools packages; reads provisioning output/settings as data only.
- **Runtime core is a nested-hexagon uv package** at `src/runtime/src/runtime/{domain,ports,adapters,application,cli}` with `tests/architecture/test_layering.py`.
- **The bar shell is AGS (Aylur's GTK Shell v2), a TS/JS GTK4 project that fully replaces Waybar** across provisioning (package, `dotfiles/config/ags/` in the spine, compositor_configs, config_links, verify, tests) and runtime (consumer wiring, reload adapter). Its palette fragment is GTK `@define-color` from the CSG `gtk.css` output — the same mechanism Waybar used. (correct-course 2026-08-18). **The provisioning swap is IMPLEMENTED** (2026-08-18): AGS is AUR-only (`aylurs-gtk-shell-git`, routed via the packages role `aur_packages` channel), auto-discovered at `~/.config/ags/app.{js,ts,jsx,tsx}` via bare `ags run`, autostarted by `exec-once = ags run`, and the palette fragment is applied at RUNTIME via `app.apply_css(path)`. **AGS has NO native hot-reload** (verified `cli/cmd/run.go:145` `// TODO: watch and restart`) — the Epic 2 reload adapter must restart the process.

## Non-goals

- Content-hash invalidation and selective regeneration (Phase 3).
- Desired-state diff engine and declarative reconciliation (Phase 4).
- Filesystem watchers, daemon, reactive updates (Phase 5).
- Parallel execution, plugin interfaces, distributed cache (Phase 6).
- Package installation, binary provisioning, filesystem bootstrap, symlink provisioning — provisioning domain.
- Cache eviction policy and enforcement (Phase 3+); Phase 2 ships list/prune as stubs only.

## Success signal

On a provisioned machine, `dotfiles wallpaper set <img>` derives palette + effects + icons, writes them into the layered cache, repoints `current/` symlinks, reloads Hyprland/AGS/Hyprpaper/terminal, and persists `current.json` + a `history.jsonl` line — all synchronously. Re-running the same image is a cache hit (zero tool invocations). Re-selecting any previously-used wallpaper is also a cache hit. `dotfiles status` shows the active state; `dotfiles history` lists past transitions. A crash at any point is repairable by the next run.

## Assumptions

- CSG is deterministic (same wallpaper + same templates → same palette), per docs/99:983-984. Must be verified before the cache key is trusted; if non-deterministic, add a fixed seed to the key.
- ITR is deterministic (same palette + templates + mappings → same icons).
- Provisioning's rendered settings.toml for csg/weg/itr exists and is valid on a provisioned machine (`dotfiles-provision verify` green guarantees this).

## Open Questions

- Phase 2 done-criteria: what defines "done" for the runtime core? Must be defined before implementation is considered complete (mirrors provisioning's fourteen).
- Hyprpaper wallpaper channel: reload-after-symlink-repoint vs `hyprctl hyprpaper wallpaper` IPC? Must verify against installed version in Epic 2. (RESOLVED 2026-09-02: channel = per-monitor IPC `hyprctl hyprpaper wallpaper <monitor>,<path>[,<fit>]`, verified against hyprpaper 0.8.4 / hyprland 0.56.2 source; reload-after-symlink-repoint unavailable in the rewrite)

> CLI packaging resolved: separate `dotfiles-runtime` binary (mirrors `dotfiles-provision`). See spine AD-19.
