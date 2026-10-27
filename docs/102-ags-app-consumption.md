# 102 — AGS app consumption (one list, one tuple, one owner)

> **Status:** composition-side adoption (2026-10-26). The app list and program
> tuple exist and the composition gate validates them. All seven apps are still
> `owner: legacy`; no app has cut over. The provision mirror, per-app cutovers
> and the final `ags-apps` removal are later tickets.

This is the composition owner's guide to the per-app AGS program defined by
`ags-apps` EPIC-002 / REQ-008 and AD-31/AD-32. It replaces the "one monorepo
tag installs every app" assumption at the composition boundary without removing
the old role before the last cutover.

## Sources of truth

| Concern | File | Owner |
| --- | --- | --- |
| Which app exists, who owns it, and every deployment surface | `dotfiles/provisioning/apps.yaml` | `dotfiles-v3` |
| The one `ags-platform` / `contracts` / `dotfiles-assets` tag triple | `dotfiles/provisioning/program-tuple.yaml` | `dotfiles-v3` |
| App-list and tuple schema | `contracts` v0.3.0 `schemas/ags-apps-install-list.schema.json`, `schemas/program-tuple.schema.json` | `contracts` |
| Install/cutover/verify behavior | `dotfiles-provision` REQ-008 | `dotfiles-provision` |
| Manifest discovery, ledger, refresh lanes | `dotfiles-runtime` REQ-002 | `dotfiles-runtime` |
| Launcher/autostart/keybind surfaces | `dotfiles-provision` `cli_tools`/`gui_tools`, `dotfiles-assets` | those repos |

There is **no second per-app list**. A role filters the one list by `owner`; a
cutover edits that entry's owner and nothing else in the composition data. The
`deploy-coverage` gate validates the list, the tuple and the legacy surfaces
against the pinned engine on every run.

## Current app list

All seven entries are legacy. The old `ags_apps` monorepo role remains the only
owner; the per-app standalone role does not act on any of them yet.

| app | owner | installDir | instance | configDir / links | launcher | autostart | launch | binLink | cutover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `bar` | legacy | `bar` | `ags` | `ags` | — | `ags` | always | — | REQ-015 |
| `hypr-pano` | legacy | `hypr-pano` | `hypr-pano` | `ags-hypr-pano` | `hypr-pano-ui` | `hypr-pano` | on-demand | — | REQ-009 |
| `notifications` | legacy | `notifications` | `notifications` | `ags-notifications` | — | `notifications` | always | — | REQ-012 |
| `capture` | legacy | `capture` | `capture` | `ags-capture` | `capture-ui` | `capture` | on-demand | `capture-tool` | REQ-011 |
| `wallpaper-selector` | legacy | `wallpaper-selector` | `wallpaper-selector` | `ags-wallpaper-selector` | `wallpaper-selector-ui` | — | on-demand | — | REQ-013 |
| `icme` | legacy | `icme` | `icon-color-mapping-editor` | `ags-icme` | `icon-color-mapping-editor` | — | on-demand | — | REQ-014 |
| `btop-theme-studio` | legacy | `btop-theme-studio` | `btop-theme-studio` | `ags-btop-studio` | `btop-theme-studio` | — | on-demand | — | REQ-010 |

The clipboard entry keeps its **current** names (`hypr-pano` / `ags-hypr-pano`);
the REQ-009 pilot changes them to `clipboard` / `ags-clipboard` as part of its
cutover, not before. `capture` is the app id while `capture-tool` remains both
the legacy unit subdir and the app-owned bin command.

### Field semantics

| Field | Meaning |
| --- | --- |
| `app` | Manifest app id; one lowercase path segment. |
| `installDir` | Standalone install directory: `<install>/apps/<installDir>/<tag>/`. Legacy entries keep living at `<install>/ags-apps/<tag>/<subdir>/` until cutover. |
| `owner` | `legacy` = old monorepo role; `standalone` = per-app role. Exactly one role acts on an entry. |
| `repo`, `tag` | Required for `standalone`; forbidden for `legacy`. Tags are immutable annotated tags. |
| `instance` | AGS bus name: `manifest.instance == app.tsx instanceName == ags list`. |
| `configDir` | Deployed config dir and manifest `configDir`; must equal the config-link basename. |
| `configLink` | Deployed config-link basename (AD-26 identity field). |
| `spineLink` | Link basename under `<install>/config`. |
| `xdgLink` | Link basename under `$XDG_CONFIG_HOME` (`~/.config/<xdgLink>`). |
| `binLink` | Optional app-owned command in the user bin dir (capture's Python backend only). |
| `launcher` | Optional provisioned launcher command that starts/toggles the app. |
| `autostart` | Autostart identity; today it is the app's own instance name. |
| `launch` | `always` = session-critical, provisioning restarts it; `on-demand` = the launcher starts it. |
| `barPalettePointer` | `true` only for the bar entry that owns the stable palette pointer. |
| `cutoverId` | The per-app cutover ticket/epoch. |

The config/spine/XDG link names are deliberately explicit even though they are
equal in today's layout. The provision role derives every link from these
fields, so moving a link name is one list edit, not a role edit.

## Program tuple

`program-tuple.yaml` names exactly three tags for the install generation:

```yaml
schemaVersion: 1
ags-platform: v0.3.0
contracts: v0.3.0
dotfiles-assets: v0.6.1
```

- One tuple per install. Every standalone app and the remaining legacy unit
  must resolve it; app repos build/test against it.
- A tuple bump is a program-wide revalidation event. It is **never** part of a
  single-app cutover.
- The composition gate requires `dotfiles-assets` to equal `assets.tag`.
- While any entry is standalone, the gate refuses a legacy unit that still
  resolves a different `ags-platform` tag. That is why the current all-legacy
  list can pass before the adoption release while a premature cutover cannot.

## One-owner rule

For every app, exactly one entry and one role own every surface:

1. `apps.yaml` is the only app list. Duplicate `app`, `instance`, `configDir`,
   `configLink`, `spineLink`, `xdgLink` or `installDir` is a gate failure.
2. `owner` is `legacy` or `standalone`; a legacy entry cannot carry `repo`/`tag`
   and a standalone entry must carry both.
3. The role for the other owner creates nothing for that entry. There is no
   deny-list and no second metadata file.
4. Exactly one entry owns `barPalettePointer`, and it must be the bar.
5. A `launcher` or `binLink` name cannot be claimed by two apps.
6. `autostart` must name the app's own instance.

`make deploy-coverage` checks all of the above, cross-checks legacy config
links/instances/launchers/bin links against the pinned engine roles, and runs
the committed legacy/mixed/all-standalone fixtures plus the negative fixtures
on every invocation.

## Per-app cutover checklist

Prerequisites (all must be true before starting an epoch):

- [ ] The app repo/tag exists and builds/tests against the current program
      tuple; its `app.manifest.json` passes schema and template conformance.
- [ ] `dotfiles-runtime` manifest/discovery support and the per-app provision
      role/verify mirror are pinned (see `dotfiles-provision` REQ-008).
- [ ] The app repo's source is absent from `ags-apps` (or is removed in the same
      epoch), so there is no second source.
- [ ] The expected launcher/autostart/keybind surface is understood and updated
      in the same epoch (REQ-009 also renames `hypr-pano` end to end).

Cutover (one app per epoch):

1. **Quiesce:** quit the old AGS instance, wait for the process to exit, confirm
   no `ags list` entry and no D-Bus name remains. Never hot-swap a link under a
   running process.
2. **Flip:** change that entry's `owner` from `legacy` to `standalone` in one
   composition commit. The old role stops acting; the new role starts acting.
   Do not flip two apps in one commit.
3. **Install/start:** install the app's tag at
   `<install>/apps/<installDir>/<tag>/`, repoint the declared spine/config/XDG
   links, update the launcher/autostart/assets surface, and start the new
   instance through the shared launch lock.
4. **Verify:** prove manifest identity (`instance == app.tsx == ags list`,
   `configDir == deployed link basename`) and exactly one owner on every listed
   surface: install dir, config link, spine link, XDG link, optional bin link,
   launcher, autostart entry, running process and D-Bus name. Run
   `make deploy-coverage` and the provision verify role.
5. **Test:** exercise the app end to end (and its `palette-refresh` handler if
   `mode: live`). Record the cutover evidence on the app ticket.
6. **Rollback (if verification fails):** quiesce the new instance, flip the
   entry back to `legacy`, reinstall/start the old unit, and re-run the same
   audit. Rollback must leave zero duplicate and zero missing surfaces.

Do not bump the app tag, engine pin or program tuple as part of an unrelated
cutover. The old role may only shrink; when the last app moves, remove the
`ags-apps` pin/role and archive the repo (final closeout ticket).

## Related tickets

- `ags-apps/tickets/REQ-008-standalone-app-contract/ticket.md` — contract,
  schemas, template and cutover fixture.
- `ags-apps/tickets/REQ-009-migrate-clipboard-standalone/ticket.md` … REQ-015 —
  the seven per-app cutovers.
- `dotfiles-provision/tickets/REQ-008-ags-app-install-topology/ticket.md` —
  generic role, owner filters, quiesce/start, verify mirror, launch lock.
- `dotfiles-runtime/tickets/REQ-002-ags-app-refresh/ticket.md` — manifest
  discovery, ledger, lanes and restart safety.
