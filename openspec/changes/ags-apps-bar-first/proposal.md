# ags-apps-bar-first

## Why

The platform is extracted and consumed by the bar in-place (`ags-consume-platform`;
spine **AD-1**: `contracts ← ags-platform ← ags-apps`, **AD-20**: sequenced migration).
The next step in `docs/HANDOFF-ags-platform.md` §5 is iteration 4: **`ags-apps`
starts with the bar only** as a thin platform consumer, then the remaining six
apps migrate one at a time, and redundant code is deleted last. The repo-shape
question is already decided: `docs/GUIDE-ags-app-repos-refinement.md` §7 keeps
**one `ags-apps` monorepo** (per-app repos deferred until the exit gate), and the
`ags-apps` backlog already exists (`EPIC-001-apps-thin-consumers` + REQ-001…
REQ-006, all `proposed`).

Evidence: `ls /home/inumaki/Development/ags-apps/` → scaffold only
(`AGENTS.md`, `tickets/`, `openspec/`, harness); **no `bar/` dir**; local `main`
at `2d47625` (one commit ahead of `origin/main` `172be0f`, the unpushed
EPIC-001 backlog commit). `ls dotfiles/config/` → `ags/`, `ags-capture/` … are
still the in-place sources; `ls src/gui-tools/` → `notifications`,
`capture-tool`, `hypr-pano`, `wallpaper-selector`, `icon-color-mapping-editor`,
`btop-theme-studio`.

## What Changes

- **Slice 0 — decision record:** freeze the repo shape in this change (monorepo
  `ags-apps/bar/…`, GUIDE §7; bar-specific ports live in `bar/`, spine AD-1/AD-8/
  AD-14). No code.
- **Slice 1 — bar moves first:** copy `dotfiles/config/ags/` → `ags-apps/bar/`
  as a thin consumer of `ags-platform` (ports/adapters only; bar-specific code —
  layout default, `SurfaceSpec`/`PopupHost`, Shell + 4 shapes, capabilities,
  `bar-manifest.ts` — stays in `bar/`); add per-app CI (`ags-apps` Makefile
  target running typecheck + tests). Maps to backlog REQ-001. All `ags-apps`
  implementation happens in `ags-apps` repo worktrees — never in dotfiles;
  dotfiles only consumes.
- **Slice 2 — dotfiles consumes the moved bar:** provisioning installs
  `ags-apps/bar` as one pinned unit mirroring the `ags-platform`
  consumption shape — pinned GitHub tag + version dir
  (`<install>/ags-apps/<version>/`-style unit) + shared-ancestor
  `node_modules` shortcut (precedent:
  `openspec/changes/ags-consume-platform/tasks.md` 1.1 — `ags_platform_version`
  v0.1.0, shallow anonymous clone, `.git` removed, pin recorded — and 1.2 —
  shared-ancestor symlink, rollback = repoint). `config/ags` resolves to the
  unit; the in-place `dotfiles/config/ags/` becomes the bridge until this
  slice lands. Until slice 2, dotfiles keeps deploying from the in-place
  source so every slice stays shippable.
- **Slices 3–8 — remaining six apps migrate one at a time, simplest pilot
  first:** `hypr-pano` (REQ-004, simplest pilot per GUIDE §7), then
  `notifications` (REQ-002), `capture-tool` (REQ-003), `wallpaper-selector`
  (REQ-005), `icme` (REQ-006), and `btop-theme-studio` last (7th app-move
  slice; it exists in `src/gui-tools/` with no REQ ticket yet — that gap is
  the reason it is recorded here explicitly), each depending on
  `ags-platform` only, never on another app (AD-1). Each slice is
  independently shippable with its own gate line.
- **Gate per slice:** `make bar-typecheck`, `make ags-typecheck`, `make ags-test`,
  `make gates-ci`, `make deploy-coverage` green; bar/app runs from the new
  location (`ags bundle` exit 0).

## Non-goals

- **No per-app repo split.** GUIDE §7 exit gate (AD-6 + AD-17 + AD-21 closed,
  `ags-bar-validate` green, one pilot) is not met; seven repos are explicitly
  out of scope.
- **No deletion in this change.** Deleting the in-place duplicates stays in
  `ags-delete-redundant-code` (spine AD-20: delete only after consumption +
  migration are green). This change only *moves* and *consumes*.
- Not the platform extraction or the validator (separate changes).
- No behaviour change to any app.

## Impact

- `ags-apps/` (new `bar/`, then one dir per app) + its CI/Makefile.
- `dotfiles-v3`: `src/provisioning/ansible/roles/{compositor_configs,verify}/**`
  (bar source repoint), `dotfiles/config/ags/` (bridge, then retired).
- `ags-apps/tickets/` REQ-001…REQ-006 link to this change's slices
  (`btop-theme-studio` has no REQ ticket yet — one must be filed before its
  slice).
