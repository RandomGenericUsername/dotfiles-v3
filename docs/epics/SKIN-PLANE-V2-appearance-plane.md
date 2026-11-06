# SKIN-PLANE-V2 — appearance plane (epic)

> **id:** `SKIN-PLANE-V2`
> **kind:** epic (container; RFC ticket `SKIN-PLANE-V2` / slug
> `appearance-plane-v2-rfc` carries the design)
> **status:** planned / RFC open
> **design:** [`docs/105-appearance-plane-v2.md`](../105-appearance-plane-v2.md)
> **predecessor:** [`docs/epics/SKIN-PLANE-skin-plane-cutover.md`](./SKIN-PLANE-skin-plane-cutover.md)
> **v1 record:** [`docs/104-skin-plane-composition.md`](../104-skin-plane-composition.md)

This epic closes the two v1 defects found after the skin-plane cutover — no hot
skin reload reaches a running app, and always-on AGS instances have no
supervision — by replacing the split palette/skin plane with **one Appearance
plane**. It also removes the v1 workaround class with a role/state/type/mode
token model.

The children below are **planned**, not yet cut. Each child is owned by its
repo, carries its own gates and release tag, and is recorded here only as the
composition-side rollup. The RFC ticket `SKIN-PLANE-V2` edits `dotfiles-v3`
docs only; it bumps no pin.

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

## Planned children

Planned ids are placeholders until each repo cuts its own ticket; the scope and
dependency order are the commitment here.

| Wave | Repo | Planned child | Scope | Depends on |
| --- | --- | --- | --- | --- |
| 0 | `contracts` | `appearance-v2-contract` (`v0.7.0`) | Appearance artifact interface (`appearance.json`, `colors.yaml`, `tokens.json`, `<configDir>.css`), token model v2, `appearanceHash = f(palette,skin,mode)`, fail-closed rules, migration notes | — |
| 1 | `dotfiles-runtime` | `appearance-generation` | `cache/appearance/<hash>/` generation, single `current/appearance` pointer, manifest/digests, prune+grace, mode recording, hash | contracts |
| 1 | `dotfiles-runtime` | `appearance-doctor` | pointer/generation checks; unit/bus/orphan leg for §4.3 of the RFC | runtime generation |
| 2 | `ags-platform` | `appearance-adapter` | one Appearance port/adapter: one provider at USER 800, one monitor on `current/appearance`, one apply, typed tokens `surface/state/type/ink/layout/mode`; deprecate split Theme+Skin | contracts |
| 2 | `ags-platform` | `appearance-refresh-handler` | existing `palette-refresh` transport, handler re-applies the whole appearance; idempotent by hash; bar stays restart lane | platform adapter |
| 3 | `dotfiles-assets` | `appearance-v2-manifests` | convert `glass`, `flat`, `paper`; per-role borders, states, type scale, `layout.<app>`, mode-aware `paper`; parity fixture kept | contracts |
| 3 | `dotfiles-assets` | `appearance-v2-templates` | `<configDir>.css` templates consume v2 tokens; delete the v1 literal workaround table; no structure expansion | manifests |
| 4 | `ags-bar` | `appearance-v2` | apply `appearance` last; restart lane; move/absorb `audio-panel.css` so no post-appearance provider remains | platform + assets |
| 4 | `ags-notifications` | `appearance-v2` | handler applies whole appearance; keep open cards/daemon/bus state; unit-supervised | platform + assets |
| 4 | `ags-clipboard` | `appearance-v2` | delete hex/luminance contrast math; consume `ink.on-*`; one provider | platform + assets |
| 4 | `ags-capture-tool` | `appearance-v2` | consume per-role borders/states/type; remove literals | platform + assets |
| 4 | `ags-wallpaper-selector` | `appearance-v2` | consume v2 tokens; keep live palette path | platform + assets |
| 4 | `ags-icme` | `appearance-v2` | consume v2 tokens; preserve unsaved-state restart rule | platform + assets |
| 4 | `ags-btop-theme-studio` | `appearance-v2` | consume v2 tokens; preserve unsaved-state restart rule | platform + assets |
| 5 | `dotfiles-provision` | `ags-systemd-units` | install/enable `dotfiles-ags-bar.service` + `dotfiles-ags-notifications.service`; `ags-run-locked --exec`; `ExecStop=ags quit -i`; `Restart=on-failure`; verify no duplicates | platform (quit/launch semantics) |
| 5 | `dotfiles-provision` | `appearance-supervision-verify` | provision/verify checks for unit active, MainPID, bus owner, no orphans; no raw `ags run` unit start | units |
| 6 | `dotfiles-v3` | `appearance-plane-tuple` | consume the final tags, update docs 105 status, keep `docs/104` as v1 history | all waves |

## Composition pins (target, not this ticket)

The current v1 tuple stays untouched by the RFC. The final tuple is expected to
move `contracts → v0.7.0` plus the platform/runtime/assets/apps/provision tags
produced by the waves. `dotfiles-v3` owns only the final bump and its gates;
`make deploy-coverage` must stay green through the composition change.

## Acceptance

- [ ] Change skin while all seven apps are open: every live app repaints
      **without restart**; each live pid is unchanged.
- [ ] Change palette while all apps are open: same, including clipboard header
      contrast from tokens (no luminance math).
- [ ] Bar changes through the restart lane only: new pid, one registered
      instance, no duplicate.
- [ ] No orphan instances: units, `ags list`, bus owner and doctor agree;
      killing a `gjs` child (not the parent) lets `Restart=on-failure` restore
      the unit and the notification bus.
- [ ] Malformed generation fails closed: old pointer/provider stays.
- [ ] `make ci-gates-parity` and `make deploy-coverage` green on the final
      tuple; every child repo's own gates green.
- [ ] v1 `docs/104` remains as the historical v1 record; `docs/105` is marked
      live when the tuple lands.

## Out of scope

- Any structure token. A skin never owns layout trees, variants, ordering or
  presence.
- A v1.1 hotfix. Running apps restart until v2.
- Changes to the on-demand launchers beyond preserving them.
