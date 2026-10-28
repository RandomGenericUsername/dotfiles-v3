# 102 — AGS app consumption (one list, one tuple, one owner)

> **Status:** final all-standalone composition (2026-10-28). Engine `v0.1.24`
> installs the seven released app repos from the single list; the old
> `ags-apps` monorepo role/playbook is gone. `dotfiles-assets` is `v0.6.2` and
> `dotfiles-runtime` is `v0.3.0` (manifest-driven refresh). The seven app tags
> and engine `v0.1.24` are published; the retired `ags-apps` repository is
> archived. The composition is applied on the host and
> `dotfiles-provision verify` exits 0; the program is closed out.

This is the composition owner's guide to the per-app AGS program defined by
`ags-apps` EPIC-002 / REQ-008 and AD-31/AD-32.

## Sources of truth

| Concern | File | Owner |
| --- | --- | --- |
| Which app exists, who owns it, and every deployment surface | `dotfiles/provisioning/apps.yaml` | `dotfiles-v3` |
| The one `ags-platform` / `contracts` / `dotfiles-assets` tag triple | `dotfiles/provisioning/program-tuple.yaml` | `dotfiles-v3` |
| App-list and tuple schema | `contracts` v0.3.0 `schemas/ags-apps-install-list.schema.json`, `schemas/program-tuple.schema.json` | `contracts` |
| Install/cutover/verify behavior | `dotfiles-provision` REQ-008 (engine `v0.1.24`) | `dotfiles-provision` |
| Manifest discovery, ledger, refresh lanes | `dotfiles-runtime` REQ-002 (`v0.3.0`) | `dotfiles-runtime` |
| Launcher/autostart/keybind surfaces | `dotfiles-provision` `ags_apps_units`, `dotfiles-assets` | those repos |

There is **no second per-app list**. `ags_apps_units` owns every app surface;
`verify` reads the same `apps.yaml` / `program-tuple.yaml`.

## Current app list

All seven entries are `owner: standalone`; `ags_apps_units` is the only owner.

| app | repo | tag | installDir | instance | configDir / links | launcher | autostart | launch | binLink | cutover |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `bar` | `ags-bar` | v0.1.3 | `bar` | `ags` | `ags` | — | `ags` | always | — | REQ-015 |
| `notifications` | `ags-notifications` | v0.1.0 | `notifications` | `notifications` | `ags-notifications` | — | `notifications` | always | — | REQ-012 |
| `capture` | `ags-capture-tool` | v0.1.0 | `capture` | `capture` | `ags-capture` | `capture-ui` | `capture` | on-demand | `capture-tool` | REQ-011 |
| `clipboard` | `ags-clipboard` | v0.1.0 | `clipboard` | `clipboard` | `ags-clipboard` | `clipboard-ui` | `clipboard` | on-demand | — | REQ-009 |
| `wallpaper-selector` | `ags-wallpaper-selector` | v0.1.0 | `wallpaper-selector` | `wallpaper-selector` | `ags-wallpaper-selector` | `wallpaper-selector-ui` | — | on-demand | — | REQ-013 |
| `icme` | `ags-icme` | v0.1.0 | `icme` | `icon-color-mapping-editor` | `ags-icme` | `icon-color-mapping-editor` | — | on-demand | — | REQ-014 |
| `btop-theme-studio` | `ags-btop-theme-studio` | v0.1.0 | `btop-theme-studio` | `btop-theme-studio` | `ags-btop-studio` | `btop-theme-studio` | — | on-demand | — | REQ-010 |

The bar's `v0.1.3` tag carries `colors.css` as a symlink to the runtime-owned
`$XDG_STATE_HOME/dotfiles/current/colors.gtk.css` (verified by the engine's
`barPalettePointer` contract); `icons.json` is the platform artifact. `capture`
is the app id while `capture-tool` is its bin command; `installDir` is
`capture`, not the repo stem.

### Field semantics

| Field | Meaning |
| --- | --- |
| `app` | Manifest app id; one lowercase path segment. |
| `installDir` | Per-app install directory: `<install>/apps/<installDir>/<tag>/`. |
| `owner` | `standalone` is the only owner in the final topology. |
| `repo`, `tag` | Immutable app repo + annotated tag. |
| `instance` | AGS bus name: `manifest.instance == app.tsx instanceName == ags list`. |
| `configDir` | Deployed config dir and manifest `configDir`; must equal the config-link basename. |
| `configLink` | Deployed config-link basename (AD-26 identity field). |
| `spineLink` | Link basename under `<install>/config`. |
| `xdgLink` | Link basename under `$XDG_CONFIG_HOME` (`~/.config/<xdgLink>`). |
| `binLink` | Optional app-owned command in the user bin dir (capture's `capture-tool`). |
| `launcher` | Optional provisioned launcher command that starts/toggles the app. |
| `autostart` | Autostart identity in the assets-owned `autostart.lua`; must appear exactly once. |
| `launch` | `always` = installer-started; `on-demand` = launcher starts it. |
| `barPalettePointer` | `true` only for the bar entry that owns the stable palette pointer. |
| `cutoverId` | The per-app cutover ticket/epoch. |

## Program tuple

`program-tuple.yaml` names exactly three tags for the install generation:

```yaml
schemaVersion: 1
ags-platform: v0.3.0
contracts: v0.3.0
dotfiles-assets: v0.6.2
```

- One tuple per install. Every standalone app resolves its `ags-platform` from
  the ONE `<install>/apps/node_modules/ags-platform` shortcut.
- A tuple bump is a program-wide revalidation event, never part of a single-app
  cutover.
- The composition gate requires `dotfiles-assets` to equal `assets.tag`, and
  requires `ags_platform`, assets and the verify mirrors to resolve the tuple.
- The pinned engine's `ags_apps_units` role and `verify` mirror read the same
  `apps.yaml`/`program-tuple.yaml`; its seven-app fixture covers quiesce →
  install/start → verify → rollback.

## One-owner rule

For every app, exactly one entry and one role own every surface:

1. `apps.yaml` is the only app list. Duplicate `app`, `instance`, `configDir`,
   `configLink`, `spineLink`, `xdgLink` or `installDir` is a gate failure.
2. Every entry is `owner: standalone`; a legacy entry has no installer and is
   rejected by the engine.
3. `config_links`, `cli_tools`, `gui_tools` and `compositor_configs` own no AGS
   app surface; `ags_apps_units` owns the install, links, launcher and start.
4. Exactly one entry owns `barPalettePointer`, and it must be the bar.
5. A `launcher` or `binLink` name cannot be claimed by two apps.
6. The assets-owned autostart corpus starts each declared identity exactly once
   through `ags-run-locked`; on-demand apps without `autostart` are absent.

`make deploy-coverage` checks all of the above, compares the composition list to
the engine's seven-app fixture, checks the final launcher/autostart/bin
surfaces, and runs the legacy/mixed/all-standalone and negative fixtures.

## Closeout / follow-up

The composition-side closeout is done when the app list, tuple, engine pin,
assets pin and docs are committed and the gates are green. The remaining
external steps are **not** performed here:

1. Publish the seven local app tags, the engine `v0.1.24`, assets `v0.6.2`
   and runtime `v0.3.0` to their remotes. **Done.**
2. Apply the composition on the host (`bootstrap`/`provision`) and run `verify`.
   **Done** — `dotfiles-provision verify` → exit 0 (`returncode: 0`).
3. Verify `ags list`, the XDG/spine/app links, launcher toggles, autostart
   identity, bar `colors.css`, and the absence of `<install>/ags-apps/`.
   **Done** — one live/restart owner per app; no host `ags-apps` or `hypr-pano`
   surface remains.
4. Archive the retired `ags-apps` repository after publish. **Done.**

## Related tickets

- `ags-apps/tickets/REQ-008-standalone-app-contract/ticket.md` — contract,
  schemas, template and cutover fixture.
- `ags-apps/tickets/REQ-009-migrate-clipboard-standalone/ticket.md` … REQ-015 —
  the seven per-app cutovers.
- `dotfiles-provision/tickets/REQ-008-ags-app-install-topology/ticket.md` —
  generic role, owner filters, quiesce/start, verify mirror, launch lock.
- `dotfiles-runtime/tickets/REQ-002-ags-app-refresh/ticket.md` — manifest
  discovery, ledger, lanes and restart safety.
