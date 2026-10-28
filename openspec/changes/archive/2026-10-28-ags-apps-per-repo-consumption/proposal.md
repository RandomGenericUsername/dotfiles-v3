# Proposal: Consume AGS apps as independently pinned repos

## Why

`ags-apps` currently ships all seven AGS apps as one monorepo tag, so one app
cannot move without moving every app. The app unit is being split into one repo
per app; `dotfiles` must consume those units individually, with exactly one owner
per app and no empty monorepo left behind.

## What Changes

- Add `dotfiles/provisioning/apps.yaml` as the single app list: app id,
  `installDir`, `owner: legacy|standalone`, repo/tag (standalone), instance,
  config dir, config/spine/XDG/bin links, launcher, autostart, launch policy,
  bar palette pointer and cutover id.
- Add `dotfiles/provisioning/program-tuple.yaml` with the one
  `ags-platform`/`contracts`/`dotfiles-assets` tag tuple per install.
- Extend `deploy-coverage` to validate the list, the program tuple and the
  one-owner invariant.
- Add the per-app cutover checklist: quiesce, flip `owner`, install/start,
  verify all ownership surfaces; rollback is the reverse.
- Update `docs/WORKSPACE.md`, the provisioning shape docs and the AGS app
  consumption notes.
- Remove the `ags-apps` monorepo pin and role at program completion; archive the
  repo. No permanent meta repo.
- **BREAKING** at cutover for each app: its deployed source moves from the
  monorepo to its own repo; config dir/instance stay stable except the declared
  clipboard rename.

## Capabilities

### New Capabilities

- `ags-app-consumption`: how `dotfiles` consumes independently pinned AGS apps,
  proves one owner per app, applies the program tuple, and cuts over/rolls back
  without duplicate or missing deployment.

### Modified Capabilities

(none)

## Impact

- `dotfiles-v3`: app list, program tuple, deploy coverage, docs.
- `dotfiles-provision`: consumes the list/tuple (separate ticket).
- `dotfiles-runtime`, `dotfiles-assets`: consumers of the same topology.
- No app repo source is created or moved by this change; app cutovers depend on
  the per-app prerequisites.

## Non-goals

- Implementing the generic provision role, runtime manifest driver or app repos.
- Bumping any app tag or the final program tuple.
- A permanent `ags-apps` meta repo.
