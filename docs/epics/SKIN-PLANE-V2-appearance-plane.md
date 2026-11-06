# SKIN-PLANE-V2 — appearance plane (epic)

> **id:** `SKIN-PLANE-V2`
> **kind:** epic (container; RFC ticket `SKIN-PLANE-V2` / slug
> `appearance-plane-v2-rfc` carries the design)
> **status:** **done** — appearance-plane v2 live in composition `0.6.38`
> (2026-11-06)
> **design:** [`docs/105-appearance-plane-v2.md`](../105-appearance-plane-v2.md)
> **predecessor:** [`docs/epics/SKIN-PLANE-skin-plane-cutover.md`](./SKIN-PLANE-skin-plane-cutover.md)
> **v1 record:** [`docs/104-skin-plane-composition.md`](../104-skin-plane-composition.md)

This epic closes the two v1 defects found after the skin-plane cutover — no hot
skin reload reaches a running app, and always-on AGS instances have no
supervision — by replacing the split palette/skin plane with **one Appearance
plane**. It also removes the v1 workaround class with a role/state/type/mode
token model.

Every child below is **cut, released and green** in its own repo; this epic is
the composition-side rollup only. The wave-6 tuple bump (composition `0.6.38`)
is the cutover that consumes these tags. The RFC ticket `SKIN-PLANE-V2` edited
`dotfiles-v3` docs only; the cutover ticket performed the pin bump.

## Frozen decisions

1. **One Appearance plane.** One composed palette+skin artifact, one provider,
   one monitored pointer (`current/appearance`), one refresh handler. Palette
   and skin are no longer separate watches/providers/apply calls.
2. **Token model v2.** `surface.{panel,card,cell,control,pill}`,
   `state.{hover,selected,focus,disabled}`, a type scale, `ink`,
   `layout.<app>`, `mode.dark/light`. No `structure` group; structure stays
   app-owned.
3. **Always-on apps are systemd `--user` units.** Bar and notifications are
   supervised, with `ExecStop=ags quit -i <instance>` and
   `Restart=on-failure`. On-demand apps keep their launchers.
4. **No v1.1 hotfix.** Live apps need a restart until v2 ships. The fix is the
   v2 cutover, not a patch to the v1 provider/monitor pair.
5. **Never kill the `ags run` parent.** Stop by D-Bus instance name
   (`ags quit -i`) or `systemctl --user stop`; the `gjs` child owns the bus.

## Child rollup (done)

| Repo | Child / requirement | Release | Scope | Status |
| --- | --- | --- | --- | --- |
| `contracts` | REQ-015 appearance plane v2 | `v0.7.0` | Appearance artifact interface, token model v2, `appearanceHash = f(palette,skin,mode)`, fail-closed rules, migration notes | done |
| `dotfiles-assets` | req-015 v2 manifests | `v0.12.0` | `glass`/`flat`/`paper` converted to v2, per-role borders/states/type/`ink`/`layout.<app>`/mode | done |
| `dotfiles-assets` | req-016 v2 templates | `v0.12.1` | `<configDir>.gtk.css.j2` consumes flattened v2 tokens; v1 literal workaround table deleted | done |
| `dotfiles-assets` | req-017 final layout audit | `v0.12.2` | Layout namespace/default audit; final v2 corpus consumed by the tuple | done |
| `ags-platform` | REQ-017 appearance adapter | `v0.9.0` | One Appearance port/adapter: one provider at USER 800, one monitor on `current/appearance`, one apply, whole-appearance refresh handler | done |
| `dotfiles-runtime` | REQ-014 appearance generation | `v0.9.0` | `cache/appearance/<hash>/`, `appearance.json`, single `current/appearance` pointer, prune+grace, mode recording, hash | done |
| `dotfiles-runtime` | REQ-016 v2 manifests | `v0.9.1` | Real v2 TOML manifests and flattened placeholders | done |
| `dotfiles-runtime` | REQ-017 doctor supervision | `v0.9.2` | Unit/MainPID/bus-owner/orphan checks, stale appearance hash, safe repair only | done |
| `ags-bar` | REQ-004 appearance migration | `v0.5.0` | Appearance applied last; restart lane; no post-appearance provider | done |
| `ags-notifications` | REQ-004 appearance migration | `v0.4.0` | Whole-appearance refresh; open cards/daemon/bus preserved; unit-supervised | done |
| `ags-capture-tool` | REQ-016 appearance migration | `v0.6.0` | Per-role borders/states/type; literals removed | done |
| `ags-clipboard` | REQ-004 appearance migration | `v0.4.0` | Token `ink.on-*`; hex/luminance contrast math deleted; one provider | done |
| `ags-wallpaper-selector` | REQ-003 v2 tokens + REQ-004 layout default | `v0.4.0` / `v0.4.1` | v2 tokens; live palette path; layout default size | done |
| `ags-icme` | REQ-005 v2 tokens + REQ-006 layout default | `v0.4.0` / `v0.4.1` | v2 tokens; unsaved-state restart rule preserved; layout default size | done |
| `ags-btop-theme-studio` | REQ-004 appearance migration | `v0.4.0` | v2 tokens; unsaved-state restart rule preserved | done |
| `dotfiles-provision` | REQ-023 always-on supervision | `v0.1.37` | Install/enable the two `systemd --user` units; `ags-run-locked --exec`; `ExecStop=ags quit -i`; `Restart=on-failure` | done |
| `dotfiles-v3` | appearance-plane v2 cutover (this epic) | `0.6.38` | Consume the final tuple/app/assets/runtime pins; docs 105 live, docs 104 historical; gates green | done |

## Composition pins (live)

The composition consumes the released tuple:

```yaml
# program-tuple.yaml
ags-platform: v0.9.0
contracts: v0.7.0
dotfiles-assets: v0.12.2
# cli-tools.yaml
dotfiles-runtime: v0.9.2
# installer.pin
v0.1.37
# apps.yaml
bar: v0.5.0
notifications: v0.4.0
capture: v0.6.0
clipboard: v0.4.0
wallpaper-selector: v0.4.1
icme: v0.4.1
btop-theme-studio: v0.4.0
# assets.yaml
assets.tag: v0.12.2
```

`make deploy-coverage` and the app/tuple gates pass on this set; the final
device map is in [`docs/105`](../105-appearance-plane-v2.md).

## Acceptance

- [x] Change skin while all seven apps are open: every live app repaints
      **without restart**; each live pid is unchanged.
- [x] Change palette while all apps are open: same, including clipboard header
      contrast from tokens (no luminance math).
- [x] Bar changes through the restart lane only: new pid, one registered
      instance, no duplicate.
- [x] No orphan instances: units, `ags list`, bus owner and doctor agree;
      killing a `gjs` child (not the parent) lets `Restart=on-failure` restore
      the unit and the notification bus.
- [x] Malformed generation fails closed: old pointer/provider stays.
- [x] `make ci-gates-parity` and `make deploy-coverage` green on the final
      tuple; every child repo's own gates green.
- [x] v1 `docs/104` remains as the historical v1 record; `docs/105` is marked
      live when the tuple lands.

## Out of scope

- Any structure token. A skin never owns layout trees, variants, ordering or
  presence.
- A v1.1 hotfix. Running apps restart until v2.
- Changes to the on-demand launchers beyond preserving them.
