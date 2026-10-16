# ags-apps-bar-first

## Why

The platform is extracted and consumed by the bar in-place (`ags-consume-platform`;
spine **AD-1**: `contracts ← ags-platform ← ags-apps`, **AD-20**: sequenced migration).
The next step in `docs/HANDOFF-ags-platform.md` §5 is iteration 4: **`ags-apps`
starts with the bar only** as a thin platform consumer, then the remaining five
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
  target running typecheck + tests). Maps to backlog REQ-001.
- **Slice 2 — dotfiles consumes the moved bar:** provisioning installs
  `ags-apps/bar` as one pinned unit and `config/ags` resolves to it (same
  one-unit + shortcut pattern as AD-17 for the platform); the in-place
  `dotfiles/config/ags/` becomes the bridge until this slice lands. Until
  slice 2, dotfiles keeps deploying from the in-place source so every slice
  stays shippable.
- **Slices 3–7 — remaining apps migrate one at a time:** `notifications`,
  `capture-tool`, `hypr-pano`, `wallpaper-selector`, `icme` (backlog REQ-002…
  REQ-006), each depending on `ags-platform` only, never on another app (AD-1).
  Each slice is independently shippable with its own gate line.
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
- `ags-apps/tickets/` REQ-001…REQ-006 link to this change's slices.
