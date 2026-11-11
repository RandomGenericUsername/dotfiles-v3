---
id: REQ-113
title: "surface.window role and kitty conf projection"
kind: requirement
status: proposed
lane: design
links:
  openspec: none
  bmad: none
  design: docs/113-window-role-kitty-projection.md
worktree: .worktrees/REQ-113/
branch: ticket/REQ-113-window-role-kitty-projection
---

# `surface.window` role and the kitty `conf` projection

## Requirement

Combine the approved **D4-B** (add `surface.window` now) and **D2-B** (project
a paint-free kitty `conf` artifact) decisions into one contract/migration
proposal.

- **D4-B** — `surface.window` is a real, required outer/toplevel role with
  `bg`, `border`, `border-width`, `radius`, `padding`, `shadow`, `blur` and
  `opacity`. It is not an alias for `surface.panel`.
- **Consumer map** — rofi outer `window`, wlogout outer `window`, GTK3/GTK4
  `window`/`headerbar` move to `window`; AGS bar/settings and AGS layer-shell
  overlays stay `panel`; notification containers stay transparent and cards
  stay `card`; btop stays palette-only.
- **Host delegation** — `surface.window.radius` and
  `surface.window.border-width` join the explicit `[host].inherit` allowlist.
  Panel paths stay for the AGS bar. No padding/opacity delegation.
- **D2-B** — `appearance/kitty.conf` projects `font_family` from the first
  usable CSS family, `font_size` from `type.size-body` with an exact px→pt
  rule, `window_padding_width` from `surface.window.padding`, and
  `background_opacity` from `surface.window.opacity`. Colours stay in
  `colors.kitty`; the conf is paint-free.
- **Versioning** — appearance token model v3: manifest `schemaVersion: 3`,
  token `version: 3`, `appearance.json` `version: 3`; contract `v0.12.0`.
  Generation manifest stays `version: 3`.
- **No behaviour change in this slice.** Docs + mockup + ticket only; no
  schema, runtime, assets, provisioning, composition, live config or tag.

## Scope

1. Design record: `docs/113-window-role-kitty-projection.md`.
2. Visual artifact: `docs/design/window-role-kitty-projection.html`, linked
   from `docs/design/README.md`.
3. Cross-reference from docs 112 (superseded decisions) and the epic.
4. This tracking ticket.

## Criteria

- **W-1** The window role is exactly eight tokens and is required in every
  manifest and resolved token document.
- **W-2** `surface.window.opacity` is a unitless `[0,1]` number; no alpha
  derivation exists.
- **W-3** Manifest/token/artifact versions move to 3; the generation manifest
  stays 3.
- **W-4** The host allowlist is exactly seven paths; window padding/opacity
  and pill radius are rejected.
- **W-5** No silent alias: a missing window group fails closed; no
  `window ?? panel`.
- **W-6** rofi/wlogout/GTK outer slots map to `window`; AGS stays `panel`;
  notifications stay transparent container + `card`.
- **H-1** `glass`, `paper` and `terminal-host` opt into window host geometry;
  `terminal` and `flat` stay `[host]`-free.
- **K-1** `appearance/kitty.conf` is `consumer=kitty`, `format=conf`, and
  paint-free.
- **K-2** `font_family` follows the first-usable-family rule.
- **K-3** `font_size` / `window_padding_width` use the exact `0.75` px→pt
  rule, two-decimal round-half-up, documented clamps, bare numbers.
- **K-4** `background_opacity` is exactly `surface.window.opacity`.
- **K-5** Static kitty order is colours → appearance → `local.conf`; reload
  stays `SIGUSR1`/`auto_reload_config -1`.
- **K-6** A `kitty +runpy` parse gate covers the artifact and assembled config.
- **M-1** Every skin (including paper `mode.light`) gains an explicit window
  group; no template uses a panel token in a window slot.
- **D-1** The mockup is self-contained, live-dark-palette, no external assets,
  and linked from the design index.
- **P-1** The implementation order is contracts → runtime/platform → assets →
  provisioning → composition; no phase skips its dependency.

## Acceptance

- [x] `docs/113-window-role-kitty-projection.md` records semantics, exact
      schema/version changes, consumer mapping, host delegation, skin
      migration, kitty rules, risks, acceptance IDs, phases and open
      questions.
- [x] `docs/design/window-role-kitty-projection.html` is self-contained and
      linked from `docs/design/README.md`.
- [x] docs/112 marks its `surface.window` deferral and font-only kitty slice as
      superseded by this proposal.
- [x] `docs/epics/SKIN-CONSUMERS.md` lists this design/tracking ticket.
- [x] No schema/token/host path/consumer mapping implemented; no live config,
      assets value, runtime, provisioning or tag changed.
- [x] `make gates-ci` green in this worktree.

## Next implementation slices (not this ticket)

1. **contracts v0.12.0** — schema v3, window role/opacity, seven-path host
   enum, generation host keys, fixtures, docs, tag.
2. **dotfiles-runtime v1.5.0 + ags-platform v1.1.0** — v3 parse, v2 rejection,
   window host map/bounds, opacity renderer, `conf` px→pt renderer.
3. **dotfiles-assets v0.19.0** — window groups in all skins + paper light;
   rofi/wlogout/GTK remaps; `kitty.conf.j2`; `required_artifacts` kitty/conf;
   fixtures and gates.
4. **dotfiles-provision v0.1.63** — static kitty include order,
   `appearance.conf` stable link, verify assertions.
5. **dotfiles-v3 composition v0.1.68** — pin tuple, regenerate, host smoke.

## Evidence (design pass)

- Current role vocabulary and host policy: `contracts/appearance.md:229-350`.
- Current host map: `dotfiles-runtime/src/runtime/domain/host_defaults.py:25-46`.
- Current renderer: `dotfiles-runtime/src/runtime/adapters/skin_expander.py:108-123,368-414`.
- Current kitty config: `dotfiles-assets/templates/kitty/kitty.conf.j2`.
- kitty 0.50.0 point probe: bare `font_size 9.0` / `window_padding_width 8.25`
  parse with zero bad lines; `9px` / `12px` are `BadLine(ValueError(...))`.
- Consumer templates: `dotfiles-assets/skins/templates/{rofi.rasi,wlogout.gtk.css,gtk3.gtk.css,gtk4.gtk.css,ags-notifications.gtk.css}.j2`.
- Prior decisions: docs 109 (host defaults), 110 (formats), 111 (rectangle
  radii), 112 (kitty/btop/palette evidence).
