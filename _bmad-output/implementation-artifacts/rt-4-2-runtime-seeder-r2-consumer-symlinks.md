---
baseline_commit: f45eb4a80537f0bb5e2097e9ce4b9e22db04f5cb
---

# Story rt-4.2: runtime seeder implements missing R2 consumer-path symlinks

Status: review

## Story

As a user,
I want the runtime seed (and every `wallpaper set`) to point the
desktop's config paths at `current/`,
So that Hyprland/AGS always read the current palette with zero copies.

## Scope Reality (READ FIRST)

This implements the R2 step from `provisioning-delta.md` /
`cache-model.md` that was specified but NEVER BUILT: "replace the
provisioning copies of `~/.config/hypr/colors.conf` and the AGS CSS
palette fragment with symlinks → `current/...` as the seeder's LAST
step". `CacheSeeder` today only creates `current/` symlinks → `cache/`;
it never touches the spine config paths. The `compositor_configs`
dont-clobber guard (Story 1.12) protects a symlink state nothing
creates — after rt-4-1 deletes the copy tasks, NOTHING places palette
into config dirs unless this story lands.

**What the seeder must do (R2, last step of seed + every reconcile
that changes the palette):**

- `<install>/config/ags/colors.css` → `current/colors.gtk.css`
  (atomic tmp-symlink + `os.replace`, same `_repoint_symlink` helper;
  note the rename: cache artifact is `colors.gtk.css`, consumer name
  is `colors.css`)

**Deliberately NOT in scope (verified against the repo):**
- `<install>/config/hypr/colors.conf` — NOTHING sources it: no file
  under `dotfiles/config/hypr/*.lua` references `colors.conf`
  (verified 2026-09-04). Creating an R2 symlink for an unsourced file
  would be dead clutter. If a future Hyprland config sources it, that
  change owns the symlink then.
- hyprpaper.conf rewrite — unnecessary: the hyprpaper reloader (rt-2-5
  verified channel) passes the resolved `current/wallpaper-<monitor>.png`
  path via `hyprctl hyprpaper wallpaper` IPC. Fresh-boot behavior is
  unchanged and explicit: before first IPC, hyprpaper shows
  `wallpapers/default.png` from the static conf (the default wallpaper —
  correct); after IPC, per-monitor `current/` targets.
- ITR `color_scheme.path` rewrite — unnecessary: the settings template
  (rt-4-3) points at `current/colors.yaml` as a static string; ITR
  resolves it at render time.

**AD-11 exception (recorded, not hand-waved):** AD-11 ("runtime never
writes under install spine") gains a documented exception for exactly
these R2 symlinks: the seeder may replace
`<install>/config/{hypr,ags}/colors.*` *files* with symlinks to
`current/`, and must write nothing else under `<install>/`. Rationale:
the two paths are consumer *pointers*, not generated content — the
content lives in `cache/` (runtime-owned). This exception is recorded
in `ARCHITECTURE-SPINE.md` AD-11/AD-17 as part of this story's
definition of done.

**Failure semantics (decided):**
- Palette null (CSG failure path): REMOVE the R2 symlinks if present
  (`missing_ok` unlink, warning logged). Rationale: a stale symlink
  would serve the previous wallpaper's colors as if current — worse
  than absent. AGS with no `colors.css` falls back to its bundled
  default (visible degradation, never wrong-palette).
- Crash between R2 symlink creation and `current.json` save: recovery
  is idempotent re-seed/reconcile — the next run recomputes hashes
  from spine inputs and repoints (same code path, no special-case
  recovery needed; the symlinks resolve to write-once cache entries
  that either exist or get regenerated).
- AGS re-apply confirmation: the AGS reloader (rt-2-4) RESTARTS the
  AGS process, which re-executes `app.apply_css(.../ags/colors.css)`
  (`dotfiles/config/ags/app.tsx:10`) through the symlinked path.
  Symlink repoint + restart = new palette applied. No additional
  reload work in this story.

**Pre-runtime window:** on a fresh machine between provisioning and
first seed, `<install>/config/hypr/colors.conf` and
`<install>/config/ags/colors.css` do not exist (no copies anymore).
Hyprland/AGS started in that window have no palette — acceptable and
documented: bootstrap runs the seed before first login (Epic 4
ordering), and `hyprland.lua` sources no colors file today.

## Acceptance Criteria

1. **Seeder creates consumer symlink** — After seed (or any reconcile
   that repoints `current/`), `<install>/config/ags/colors.css` is a
   symlink resolving to `current/colors.gtk.css`. Atomic
   (`_repoint_symlink`), idempotent re-run.
2. **No spine writes outside the one symlink** — The seeder writes
   NOTHING else under `<install>/` (AD-11 holds except for this single
   documented R2 symlink; the exception is recorded in
   `ARCHITECTURE-SPINE.md` AD-11/AD-17 as part of this story).
3. **Missing palette degrades cleanly** — If the palette layer is null,
   the R2 symlink is REMOVED if present (`missing_ok` unlink + warning),
   never left dangling or stale. AGS falls back to its bundled default.
4. **No regressions** — `pytest` + `ruff` + `mypy --strict` + layering
   green; existing seed/reconcile/apply tests updated where they assert
   the old copy-based layout; new tests cover symlink creation,
   idempotent re-run, and null-palette removal.

## Tasks / Subtasks

- [x] Task 1: Add R2 method to `CacheSeeder` (AC 1-3)
- [x] Task 2: Wire into seed + reconcile swap sequence (AC 1)
- [x] Task 3: Update/extend tests (AC 4)

## Dev Notes

### Pinning sources

- Epic 4: `_bmad-output/planning-artifacts/epics-runtime-single-source.md`
- `provisioning-delta.md` R2 section + `cache-model.md` step 8
- `consumer-wiring.md` (the `→ (NEW symlink, was a copy)` annotations)
- Existing helper: `seeder.py:_repoint_symlink` + `repoint_current_symlinks`
- Fragment names: `compositor_configs/vars/main.yml:164-166`

### Scope boundary

Do NOT touch provisioning roles (rt-4-1), AGS registry (rt-4-3),
settings templates (rt-4-3), or verify (rt-4-4) in this story.

## Dev Agent Record

### Agent Model Used

OpenCode powered by Meta Muse Spark (muse-spark-1.3-contributor-free)

### Debug Log References

- Verified the R2 gap against code: `CacheSeeder` only ever created
  `current/` symlinks; no path ever wrote `<install>/config/*/colors.*`
  symlinks (the dont-clobber guard protected a state nothing produced).
- Verified Hyprland exclusion: no reference to `colors.conf` under
  `dotfiles/config/hypr/*.lua` — symlink dropped from scope with rationale.
- Verified hyprpaper fresh-boot: conf hardcodes `wallpapers/default.png`
  (correct default until first IPC); IPC channel (rt-2-5) needs no conf edit.
- Verified AGS re-apply: rt-2-4 reloader RESTARTS AGS, re-executing
  `app.apply_css(.../ags/colors.css)` through the symlink.
- Design deviation from story draft (recorded): R2 paths ride a separate
  `ReconcileResult.consumer_symlinks` field, NOT merged into `repointed`
  (keeps CLI counts + JSON `repointed` contract current/-only; CLI renders
  `N consumer link(s)` suffix + `consumer_symlinks` JSON key when non-empty).
- End-to-end on host: `wallpaper set wave.png` →
  `<install>/config/ags/colors.css` is a symlink resolving to
  `current/colors.gtk.css` with live palette content.
- Runtime suite: 569 passed / 2 skipped; ruff 3 / mypy 4 / format clean /
  layering 57 (all baseline).

### Completion Notes List

- ✅ Task 1 (rt-4-2): `CacheSeeder.repoint_consumer_symlinks()` added
  (create/replace/remove semantics, null-palette removal, missing-target
  skip, parent mkdir via `_repoint_symlink`).
- ✅ Task 2 (rt-4-2): wired into seed (`_seed`) + reconcile (inside lock,
  after `current/` repoint); `install_spine` stored on the reconcile
  use case; `ReconcileResult.consumer_symlinks` added (defaulted field —
  existing constructions unaffected); CLI surfaces count + JSON key.
- ✅ Task 3 (rt-4-2): AD-11 exception recorded in ARCHITECTURE-SPINE.md;
  seed/reconcile spine tests rewritten to the R2 contract; reconcile
  happy-path extended with R2 assertions; null-palette removal test added.

### File List

- `src/runtime/src/runtime/adapters/seeder.py` (modified — R2 method)
- `src/runtime/src/runtime/application/seed_cache.py` (modified — wire-in)
- `src/runtime/src/runtime/application/reconcile.py` (modified — install_spine store, wire-in, result field)
- `src/runtime/src/runtime/cli/main.py` (modified — summary + JSON)
- `src/runtime/tests/unit/test_seed_cache.py` (modified — R2 contract + 2 new tests)
- `src/runtime/tests/integration/test_seed_cache_integration.py` (modified — R2 contract)
- `src/runtime/tests/unit/test_reconcile.py` (modified — R2 assertions + null-palette test)
- `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` (modified — AD-11 exception)
