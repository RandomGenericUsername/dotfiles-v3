# Tasks

Evidence convention: every tick names the command run and the observed result.
Nothing is ticked from reading a diff.

## 0. Repo-shape decision record (no code)

- [ ] 0.1 Record the shape: one `ags-apps` monorepo, `bar/` first, per-app
  folders after (`bar/`, `hypr-pano/`, `notifications/`, `capture-tool/`,
  `wallpaper-selector/`, `icme/`, `btop-theme-studio/`), apps → platform only
  (AD-1), bar-specific
  ports in `bar/` (AD-8/AD-14). Cite GUIDE §7 + spine AD-1/17/20 + Deferred.
  Verify: `ls openspec/changes/ags-apps-bar-first/` → `proposal.md tasks.md`.

## 1. Bar moves first (REQ-001)

- [ ] 1.1 Copy `dotfiles/config/ags/` → `ags-apps/bar/` (history-preserving
  move authored in `ags-apps`, not here); wire imports to `ags-platform`
  ports/adapters; keep only bar-specific code in `bar/` (layout default,
  `SurfaceSpec`/`PopupHost`, Shell + shapes, capabilities, `bar-manifest.ts`).
  Verify: `grep -rn "from ['\"]ags-platform" ags-apps/bar | head` → non-empty;
  `grep -rn "ags-apps/" ags-apps/bar` cross-app imports → none (AD-1).
- [ ] 1.2 Per-app CI in `ags-apps` (typecheck + tests for `bar/`).
  Verify: `make -C /home/inumaki/Development/ags-apps bar-check` (or the
  repo's gate target) → exit 0.
- [ ] 1.3 dotfiles still green with the in-place bar (bridge, pre-consumption).
  Verify: `make bar-typecheck && make ags-typecheck && make ags-test && make gates-ci && make deploy-coverage` → all exit 0.

## 2. dotfiles consumes the moved bar

- [ ] 2.1 Provisioning installs `ags-apps/bar` as one pinned unit
  (`<install>/ags-apps/<version>/`-style unit: pinned GitHub tag, version
  dir, pin recorded) and `config/ags` resolves to it via the shared-ancestor
  `node_modules` shortcut (mirror of the `ags-platform` consumption shape —
  precedent `openspec/changes/ags-consume-platform/tasks.md` 1.1 + 1.2,
  AD-17; rollback = repoint the shortcut).
  Verify: fresh provision stats the unit dir; `ags bundle <unit>/bar/app.tsx …` → exit 0.
- [ ] 2.2 Retire the in-place bridge (`dotfiles/config/ags/` no longer the
  deploy source; provisioning lists repointed; `verify` asserts the unit).
  Verify: `make deploy-coverage` → PASS; `verify` passes on a fresh host.

## 3–8. Remaining apps, one slice each (REQ-002…REQ-006 + btop, no REQ yet)

Each slice: move `<app>` → `ags-apps/<app>/` as a thin platform consumer
(no app→app imports) — implementation in `ags-apps` repo worktrees, never in
dotfiles; dotfiles only consumes — wire CI, repoint provisioning, keep gates
green. Ship in this order (bar stays slice 1 as reference; `hypr-pano` leads
as simplest pilot per GUIDE §7):

- [ ] 3.1 `hypr-pano` (REQ-004, simplest pilot). Verify: app imports
  `ags-platform` only; `make gates-ci` → exit 0; clipboard manager runs.
- [ ] 4.1 `notifications` (REQ-002). Verify: app imports `ags-platform` only;
  `make gates-ci` → exit 0; notifications window runs.
- [ ] 5.1 `capture-tool` (REQ-003). Verify: same gate line; capture UI runs.
- [ ] 6.1 `wallpaper-selector` (REQ-005). Verify: same gate line; selector runs.
- [ ] 7.1 `icme` (REQ-006). Verify: same gate line; editor runs.
- [ ] 8.1 `btop-theme-studio` (7th app-move slice; no REQ ticket — exists in
  `src/gui-tools/` but absent from `ags-apps/tickets/`; file one before this
  slice). Verify: same gate line; studio runs.

## 9. Handoff (no deletion)

- [ ] 9.1 Confirm `ags-apps` holds bar + six apps, all gates green, and hand
  off to `ags-delete-redundant-code` (deletion is a separate change, AD-20).
  Verify: `ls ags-apps/` → seven app dirs; `make gates-ci` → exit 0.
  Explicitly NOT in this change: deleting any in-place duplicate.
