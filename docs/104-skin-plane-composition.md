# 104 — the skin plane in the composition (v1 history)

> **Status:** **historical — v1, superseded.** The skin-plane v1 cutover
> (2026-11-05) is retained here as the record of the plane that v2 replaced.
> **The live plane is v2:**
> [`docs/105-appearance-plane-v2.md`](./105-appearance-plane-v2.md). Composition
> release `0.6.38` consumes the v2 tuple and every app reads
> `current/appearance`, not the v1 skin pointers. The v1 boundary below still
> holds (a skin is appearance, never structure); the artifact, watch and
> provider mechanics do not.
>
> The normative vocabulary for the live plane is `contracts` `v0.7.0`; the
> renderer and apps live in their pinned repos at the releases recorded in 105.

## Boundary (what a skin is)

A skin is **appearance only**:

- **palette/ink mapping + paint + rhythm/density**;
- a skin may **not** describe structure — layout trees, variants, ordering or
  presence are app-owned;
- **layout tokens are TSX-owned** (`panel-width`, `bt-list-spacing`,
  `bar-row-height`, `chip-min`): widgets read them through `skinValue()` /
  `createAppSkinValue`, and templates never expand them into CSS;
- **provider composition is fixed**: one `Gtk.CssProvider` per app composes the
  runtime palette role block + the expanded skin CSS, is added at **USER
  priority (800)**, and is **installed last** so it wins over app/theme
  providers. There is no second skin provider;
- **no new refresh protocol**: live apps answer the existing
  `palette-refresh` request; the **bar stays restart-only** and has **no
  palette-refresh handler**. A skin change for the bar is a restart.

## Data path (assets → spine, v1 history)

The v1 composition pinned `dotfiles-assets` at **`v0.11.0`** and listed the
sixth corpus class:

```yaml
assets:
  tag: v0.11.0
  classes:
    icons:     { dest: icons,     schema: icons/schema.json }
    templates: { dest: templates, schema: "**/*.vars.schema.json" }
    configs:   { dest: configs,   schema: null }
    content:   { dest: content,   schema: null }
    desktop:   { dest: desktop,   schema: desktop/desktop.yaml }
    skins:     { dest: skins,     schema: skins/schema.json }
entries:
  - name: skins
    kind: skins
    source: "{{ install_dir | trim }}/assets/v0.11.0/skins/"
```

The engine's `assets` role clones the pinned corpus once into
`<install>/assets/v0.11.0/` and mirrors the `skins/` class to **`<install>/skins`**
— the runtime's **first** skin root (`derive._skin_roots`: `<install>/skins`,
then `config/skins`, then the pinned checkout). The deployed plane is data only
(`manifests/`, `templates/`, `contracts/` + `PIN`, `schema.json`); provisioning
never renders or reconciles it.

The seven templates are named by **real `configDir`**:
`ags.gtk.css.j2` (bar) plus `ags-notifications`, `ags-capture`, `ags-clipboard`,
`ags-wallpaper-selector`, `ags-icme` and `ags-btop-studio`.

## Runtime outputs (v1 history)

The v1 `dotfiles-runtime` **`v0.8.1`** derives the skin from the selected manifest and
publishes, under its state root `current/`:

- `current/skins/<configDir>.css` — one expanded stylesheet per app config dir;
- `current/skin.json` — **one shared** grouped token map for all apps.

Per-app stable pointers are runtime-owned:

```text
{install}/config/<configDir>/skin.css  -> current/skins/<configDir>.css
{install}/config/<configDir>/skin.json -> current/skin.json
```

The runtime seeder/reconcile owns those pointers; provisioning only guarantees
the config dir and its XDG/spine links. The bar's `configDir` is `ags`, so its
pointer is `config/ags/skin.css` / `config/ags/skin.json`.

## App consumption (v1 history)

Every v1 AGS app applied the platform factory with its **own** config dir:

```ts
import { createAppSkin } from "ags-platform/adapters/skin"

const skin = createAppSkin({ configDir: "ags-notifications" })
skin.apply() // after the palette provider, last, at USER priority (800)
```

The bar uses the platform's default singleton, which is exactly
`createAppSkin({ configDir: "ags" })`. Apps with TSX-owned metrics use
`createAppSkinValue(skin, "layout.panel-width", 312)`; the bar keeps
`skinValue(...)`.

Pinned consumers: `ags-platform v0.8.0`; `ags-bar v0.4.0`,
`ags-notifications v0.3.0`, `ags-capture-tool v0.5.0`, `ags-clipboard v0.3.0`,
`ags-wallpaper-selector v0.3.0`, `ags-icme v0.3.0` and
`ags-btop-theme-studio v0.3.0`.

## Selection

The selected skin is **runtime state**, not a composition pin. It lives in
runtime `desired.json`:

```json
{ "skin": "glass" }
```

`skin` is optional and defaults to **`glass`**. There is no per-app skin choice
in v1. The frozen built-ins are `glass` (default), `flat` and `paper`; the
runtime falls back to `glass` when no valid skin is selected.

## Composition pins (v1, historical)

These are the v1 skin-plane pins; they are **not** the live composition. The
live tuple and app tags are in
[`docs/105-appearance-plane-v2.md`](./105-appearance-plane-v2.md).

```yaml
# v1 program-tuple.yaml
schemaVersion: 1
ags-platform: v0.8.0
contracts: v0.6.0
dotfiles-assets: v0.11.0
```

- v1 `cli-tools.yaml`: `dotfiles-runtime v0.8.1`
- v1 `installer.pin`: `v0.1.35`
- v1 `assets.yaml`: `assets.tag v0.11.0` + the `skins` class/entry
- v1 `apps.yaml`: bar `v0.4.0`; notifications/capture/clipboard/
  wallpaper-selector/icme/btop-theme-studio at their skin-plane releases.

The v1 cross-repo child rollup is
[`epics/SKIN-PLANE-skin-plane-cutover.md`](./epics/SKIN-PLANE-skin-plane-cutover.md).
The v2 rollup and final device map are
[`docs/105-appearance-plane-v2.md`](./105-appearance-plane-v2.md) and
[`epics/SKIN-PLANE-V2-appearance-plane.md`](./epics/SKIN-PLANE-V2-appearance-plane.md).

## Deploy (v1 history)

This page is historical. The v2 cutover deploy command and its expected
`current/appearance` output are in
[`docs/105-appearance-plane-v2.md`](./105-appearance-plane-v2.md#deploy-operator-after-this-composition-release).
The v1 data path (`<install>/skins`, `current/skins/<configDir>.css`,
`current/skin.json`) is no longer the consumption path.
