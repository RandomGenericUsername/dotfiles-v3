---
id: REQ-112
title: "kitty/btop projection and the surface.window role review"
kind: requirement
status: proposed
lane: design
links:
  openspec: none
  bmad: none
  design: docs/112-kitty-btop-window-roles.md
worktree: .worktrees/REQ-112/
branch: ticket/REQ-112-kitty-btop-window-roles
---

# kitty/btop projection and the `surface.window` role review

## Requirement

Record, with execution evidence, how far skins can project into kitty and btop,
and whether the appearance vocabulary needs a `surface.window` role.

- **kitty** includes `current/colors.kitty`; new windows read it, open windows
  reload via `KittyReloader`/`SIGUSR1`. Palette-only is current and honest;
  `font_family` is the only further knob without a unit rule.
- **btop** is palette-only: 48 colour keys, no radius/padding/type/rhythm
  theme surface. No skin projection is meaningful.
- **`surface.panel` is the outer surface**; `surface.card` is an inner card
  (including notification cards). `surface.control`/`cell`/`pill` stay
  distinct. No new `surface.window` role is needed now.
- **No behaviour change.** Docs + mockup only; no schema, runtime, assets,
  provisioning, composition, live config or tag change.

## Scope

1. Design record: `docs/112-kitty-btop-window-roles.md`.
2. Visual artifact: `docs/design/kitty-btop-window-roles.html`, linked from
   `docs/design/README.md`.
3. This tracking ticket.

## Criteria

- **K-1** kitty current path is confirmed by config + live parse, including
  the `SIGUSR1` reloader.
- **K-2** kitty candidates are classified with units; `font_size`/padding `px`
  rejection is proven by a `kitty +runpy` parse probe.
- **B-1** btop is confirmed as 48 colour keys plus the two-setting managed
  config; geometry/type are "not applicable".
- **W-1** `surface.panel` is the outer role; `surface.card` is an inner card.
- **W-2** notification cards are shown as cards on a layer-shell container.
- **W-3** `surface.window` is deferred with explicit W-1…W-6 criteria.
- **D-1** the mockup is self-contained, live-dark-palette, no external assets.

## Acceptance

- [x] `docs/112-kitty-btop-window-roles.md` records evidence, decisions,
      criteria, open questions and the next slice.
- [x] `docs/design/kitty-btop-window-roles.html` is self-contained and linked
      from `docs/design/README.md`.
- [x] No schema/token/host path/consumer mapping added.
- [x] No live config, assets value, runtime, provisioning or tag changed.
- [x] `make gates-ci` green in this worktree (observed 2026-11-11: four gates
      PASS).

## Evidence (design pass)

- kitty template: `dotfiles-assets/templates/kitty/kitty.conf.j2:1-4`.
- Live parse: `load_config("~/.config/kitty/kitty.conf")` → `[]`, background
  `#111318`, font `monospace 11.0`, padding `0`, opacity `1.0`.
- Unit probe: `window_padding_width 9px` / `font_size 12px` both produce
  `BadLine(ValueError(...))` on kitty 0.50.0.
- Reloader: `dotfiles-runtime/src/runtime/adapters/kitty_reloader.py:1-9,77-116`.
- btop keys: `theme-producer/src/theme_producer/adapters/projections/btop.py:24-102`;
  managed config `dotfiles-assets/templates/btop/btop.conf.j2:48-49`.
- Notification layer: `ags-notifications/ui/NotificationsWindow.tsx:963-967`;
  card mapping `dotfiles-assets/skins/templates/ags-notifications.gtk.css.j2:4-5,22-28`.
- Role vocabulary: `contracts/appearance.md:234-250`.

## Next implementation slice (optional)

**Repo:** `dotfiles-assets` only, if `font_family` is approved.

1. Add `skins/templates/kitty.conf.j2` that references only
   `{{SKIN_TYPE_FONT_FAMILY}}` (first family of the CSS list; document the
   rule), with a comment that no paint/size/padding/opacity is projected.
2. Register `kitty`/`conf` in `skins/schema.json` `required_artifacts` and the
   assets gate.
3. Add a `kitty +runpy` `load_config(..., accumulate_bad_lines=b)` gate
   asserting `b == []` and no paint placeholder.
4. Leave provisioning's `appearance.conf` link and the live lane to a separate
   provisioning ticket; do not claim a live lane here.

No btop slice and no `surface.window` slice.
