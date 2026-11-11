# SKIN-CONSUMERS — non-AGS apps and host-aligned skin defaults

> **id:** `SKIN-CONSUMERS`
> **kind:** epic (follow-on to [`SKIN-PLANE-V3`](./SKIN-PLANE-V3-generations.md))
> **status:** **delivered** (Phase 1/2 + wlogout Phase 2b/2c + terminal-host,
> 2026-11-10) — wlogout cards and Hyprland host defaults are live. Phase 3
> format-aware consumers/reload remain explicitly deferred.
> **designs:** [`docs/108`](../108-non-ags-skin-consumers.md) ·
> [`docs/109`](../109-hyprland-host-defaults.md) ·
> [`docs/110`](../110-format-aware-skin-consumers.md)
> **predecessor:** [`SKIN-PLANE-V3`](./SKIN-PLANE-V3-generations.md) — delivered
> **baseline:** contracts `v0.10.0`, ags-platform `v1.0.1`,
> dotfiles-runtime `v1.3.1`, dotfiles-assets `v0.17.0`,
> dotfiles-provision `v0.1.60`, composition `v0.1.65`; apps `bar v0.6.1`,
> `notifications v0.5.1`, `capture v0.7.1`, `clipboard v0.6.1`,
> `wallpaper-selector/icme/btop-theme-studio v0.5.1`.

This epic extends the delivered v3 skin plane in two independent but
composable directions:

1. **more consumers of the same appearance plane** — wlogout first, then
   format-specific consumers (GTK/rofi/kitty), with btop/Hyprland remaining
   palette-only where the format has no skin surface;
2. **host-aligned design defaults** — skins may delegate selected paint/rhythm
   tokens (starting with Hyprland `decoration:rounding` and
   `general:border_size`) to the compositor, with explicit overrides.

Both keep the frozen v3 rule: the skin owns palette/ink mapping, paint and
rhythm; structure stays app-owned.

## Frozen criteria

- **SC-1** A skin never owns an app's layout, buttons, icons, wallpaper or
  grid. A generated consumer sheet contains paint/rhythm only.
- **SC-2** Appearance targets remain content-addressed generation artifacts;
  no consumer reads a generation-specific path or an app tag.
- **SC-3** The target set is derived from the selected skin's templates, not a
  hardcoded app list. A named consumer is a config-directory name.
- **SC-4** Every consumer declares a real refresh lane: `live`, `restart` or
  `launch`; no false live lane.
- **SC-5** No literal hex, transition, structure/variant token, unknown role or
  poll-as-correctness in any skin output.
- **SC-6** Host defaults are opt-in per skin and token; an undelegated token is
  always explicit. Host values never inject colours.
- **SC-7** Release tags are the synchronization boundary; no production pin
  points at a branch or moving SHA.

## Child workstreams

| Repo / workstream | Scope | Acceptance criteria | Status |
| --- | --- | --- | --- |
| `dotfiles-assets` — wlogout template | `wlogout.gtk.css.j2` paint/rhythm; README/tests; every skin ships it | `W-2.1`–`W-2.16` in [108](../108-non-ags-skin-consumers.md) | delivered `v0.15.2` |
| `dotfiles-provision` — wlogout consumer | stable `appearance.css` link; verify; static style import last; no layout/icons in generated sheet | `W-2.5`–`W-2.8` in [108](../108-non-ags-skin-consumers.md) | delivered `v0.1.50` |
| `dotfiles-runtime` — wlogout regression | prove target/template publication; no production adapter expected | `W-2.3` in [108](../108-non-ags-skin-consumers.md) | delivered `v1.0.7` + doctor `v1.0.8` |
| `dotfiles-v3` — wlogout cutover | composition/app-consumption pins only after releases | `SC-1`–`SC-7`; `W-2.*` | delivered `v0.1.55` |
| `contracts` — host policy | optional `[host]` policy; generation `host` block; `appearance.v3` | `H-1.1`–`H-1.5` in [109](../109-hyprland-host-defaults.md) | delivered `v0.9.0` |
| `dotfiles-runtime` — host defaults | Hyprland adapter, resolver, hashing, doctor, one lock | `H-2.1`–`H-2.10` in [109](../109-hyprland-host-defaults.md) | delivered `v1.1.1` |
| `dotfiles-assets` — host opt-in | glass/paper `[host]`; terminal/flat explicit; `terminal-host` opt-in variant | `H-1.5` in [109](../109-hyprland-host-defaults.md) | delivered `v0.16.0` |
| `dotfiles-v3` — host cutover | tuple/app pins only after releases | `H-1.*`–`H-2.*` | delivered `v0.1.59` |
| Phase 3 consumers | GTK3/4, rofi, kitty format-aware targets; btop/Hyprland palette-only | `W-3.1`–`W-3.7`; `H-3.1`–`H-3.5` | GTK3/GTK4/rofi delivered; kitty/btop palette-only; other compositors deferred |
| Phase 3 host refresh | socket2 `configreloaded` + debounce; other compositor sources | `H-3.4`, `H-3.5` | socket2 delivered `v1.2.0`; other compositors deferred |

## Sequencing and collision rules

1. Start after runtime `v1.0.6` and composition `v0.1.53`; freeze the baseline
   above. Do not branch from an active agent worktree.
2. **wlogout Phase 1/2 first** — additive, no contract change. Implement
   assets + provisioning + runtime-test slice in one ticket per repo. Do not
   edit composition pins until its releases are green.
3. **Hyprland Phase 1 second** — contract release, then runtime/assets
   releases, then composition cutover.
4. Both touch `dotfiles-assets`; merge wlogout assets first, then rebase the
   host-default assets branch. Never run two composition cutovers at once.
5. Use one worktree per repo and a dedicated tracking ticket. Suggested
   branches: `ticket/SKIN-WLOGOUT`, `ticket/SKIN-HOST-DEFAULTS`; baseline tags
   from the table above.
6. Validate wlogout with temp `XDG_CONFIG_HOME`/`XDG_STATE_HOME`, GTK3
   `CssProvider` and Broadway. Validate host defaults read-only against
   `hyprctl`; no live apply.
7. Do not pin branches or SHAs in production. Release assets, then the engine
   (if provisioning changes), then composition in one cutover.

## Epic acceptance (definition of done)

- **SC-A1** wlogout consumes a generated `appearance/wlogout.css` as a named
  target, with a stable link through `current/`, and renders palette + skin on
  next launch with no GTK warnings. Its layout/icons/wallpaper are unchanged
  and app-owned.
- **SC-A2** The wlogout template is present for every bundled skin; missing
  coverage fails the release gate; the one-time template-hash churn is
  documented.
- **SC-A3** The host-default contract is additive and backward-compatible:
  existing skins/generations without `[host]` remain valid; delegated tokens
  resolve mode override > host > skin fallback; `fallback="error"` fails
  closed.
- **SC-A4** A Hyprland change to a delegated value creates a new generation
  identity; a non-delegated change does not. Headless/no-instance behavior is
  deterministic.
- **SC-A5** `doctor` reports host drift only for delegated values; no polling
  is introduced.
- **SC-A6** Non-CSS consumers either have an approved format-aware contract or
  are explicitly deferred; btop/Hyprland remain palette-only.
- **SC-A7** Every release is tagged, gates are green, and no live apply is part
  of the design/criteria phase.

## Handoff for a new session

Start from the baseline tags, create a tracking ticket, and read
[`docs/108`](../108-non-ags-skin-consumers.md) and
[`docs/109`](../109-hyprland-host-defaults.md) before editing. The first
deliverable is the wlogout assets/provisioning/runtime-test slice; do not
touch runtime lock code, composition pins, contracts schema, or live state.
Copy the `/tmp/opencode` prototypes into durable test fixtures in the
implementing repo before relying on them.
