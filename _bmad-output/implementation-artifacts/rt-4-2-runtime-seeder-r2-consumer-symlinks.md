---
baseline_commit: f45eb4a80537f0bb5e2097e9ce4b9e22db04f5cb
---

# Story rt-4.2: runtime seeder implements missing R2 consumer-path symlinks

Status: ready-for-dev

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

- `<install>/config/hypr/colors.conf` → `current/colors.conf`
  (atomic tmp-symlink + `os.replace`, same `_repoint_symlink` helper)
- `<install>/config/ags/colors.css` → `current/colors.gtk.css`
  (note the rename: cache artifact is `colors.gtk.css`, consumer name
  is `colors.css`)

**What DISSOLVES (no work):**
- hyprpaper.conf rewrite — unnecessary: the hyprpaper reloader (rt-2-5
  verified channel) passes the resolved `current/wallpaper-<monitor>.png`
  path via `hyprctl hyprpaper wallpaper` IPC. No conf edit needed.
- ITR `color_scheme.path` rewrite — unnecessary: the settings template
  (rt-4-3) points at `current/colors.yaml` as a static string; ITR
  resolves it at render time.

**Pre-runtime window:** on a fresh machine between provisioning and
first seed, `<install>/config/hypr/colors.conf` and
`<install>/config/ags/colors.css` do not exist (no copies anymore).
Hyprland/AGS started in that window have no palette — acceptable and
documented: bootstrap runs the seed before first login (Epic 4
ordering), and `hyprland.lua` sources no colors file today.

## Acceptance Criteria

1. **Seeder creates consumer symlinks** — After seed (or any reconcile
   that repoints `current/`), `<install>/config/hypr/colors.conf` is a
   symlink resolving to `current/colors.conf`, and
   `<install>/config/ags/colors.css` is a symlink resolving to
   `current/colors.gtk.css`. Atomic (`_repoint_symlink`), idempotent
   re-run.
2. **No spine writes outside the two symlinks** — The seeder writes
   NOTHING else under `<install>/` (AD-11 holds except for these two
   documented R2 symlinks, which are the specified exception).
3. **Missing palette degrades cleanly** — If the palette layer is null
   (effects/icons-style graceful path), consumer symlinks are skipped
   with a warning, never dangling.
4. **No regressions** — `pytest` + `ruff` + `mypy --strict` + layering
   green; existing seed/reconcile/apply tests updated where they assert
   the old copy-based layout.

## Tasks / Subtasks

- [ ] Task 1: Add R2 method to `CacheSeeder` (AC 1-3)
- [ ] Task 2: Wire into seed + reconcile swap sequence (AC 1)
- [ ] Task 3: Update/extend tests (AC 4)

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

_To be filled by dev-story._

### Debug Log References

_To be filled by dev-story._

### Completion Notes List

_To be filled by dev-story._

### File List

_To be filled by dev-story._
