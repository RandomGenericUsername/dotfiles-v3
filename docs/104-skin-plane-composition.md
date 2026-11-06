# 104 — the skin plane in the composition

> **Status:** live (skin-plane cutover, 2026-11-05). This page is the
> composition-side view: where the data comes from, what the runtime publishes,
> what each app consumes, and which boundary the program froze. The normative
> vocabulary is `contracts` `skins.md` + its schemas; the renderer and apps live
> in their pinned repos.

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

## Data path (assets → spine)

`dotfiles/provisioning/assets.yaml` pins `dotfiles-assets` at **`v0.11.0`** and
lists the sixth corpus class:

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

## Runtime outputs

`dotfiles-runtime` **`v0.8.1`** derives the skin from the selected manifest and
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

## App consumption

Every AGS app applies the platform factory with its **own** config dir:

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

## Composition pins

```yaml
# program-tuple.yaml
schemaVersion: 1
ags-platform: v0.8.0
contracts: v0.6.0
dotfiles-assets: v0.11.0
```

- `cli-tools.yaml`: `dotfiles-runtime v0.8.1`
- `installer.pin`: `v0.1.35`
- `assets.yaml`: `assets.tag v0.11.0` + the `skins` class/entry
- `apps.yaml`: the seven app tags listed above

The composition gates validate the pin set, the sixth asset class, the final
app inventory and the tuple ↔ engine agreement; see
[`epics/SKIN-PLANE-skin-plane-cutover.md`](./epics/SKIN-PLANE-skin-plane-cutover.md)
for the cross-repo child rollup.

> **Engine prerequisite (open at composition close):** the exact engine pin
> `v0.1.35` still mirrors `ags_platform_version: v0.5.0` (installer and verify).
> The final tuple is `v0.8.0`, so `make deploy-coverage` fails until an engine
> release moves both mirrors to `v0.8.0` and `installer.pin` follows. Do not
> deploy this composition before that; the shared platform shortcut would point
> at a unit the engine does not install.

## Deploy (user, after this composition release)

This ticket is composition-only and never runs the deploy. On the target host,
after the local tags are published / available to the installer:

```bash
make bootstrap ARGS="--ask-become-pass"
# or, on an already-bootstrapped host:
make provision ARGS="apply"
make provision ARGS="verify"
```

The first applied run installs `<install>/skins`, starts the runtime reconcile,
and writes `current/skins/<configDir>.css` + `current/skin.json`. The bar and
other always-on apps restart; on-demand apps pick up their skin when launched.
