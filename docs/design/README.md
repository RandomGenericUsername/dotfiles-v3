# Design previews

- [`skins.html`](./skins.html) — a self-contained static gallery of the four
  skins (`glass`, `flat`, `paper`, `terminal`) over one identical app
  structure. It uses the live terminal/dark palette roles and mirrors the
  paint/rhythm values in `dotfiles-assets/skins/manifests/*.toml`.
- [`terminal-host-radius.html`](./terminal-host-radius.html) — a self-contained
  side-by-side of `terminal` (explicit, square) and `terminal-host` (Hyprland
  rounding `9`). It shows the rectangle roles that follow the host — panel,
  card, control and cell — alongside wlogout, rofi, GTK and notification
  consumers, and isolates the pill decision: `surface.pill.radius` stays
  explicit (`2px` here; `999px` capsules in flat/paper). It also marks the
  rejected “pill follows 9px” result. See
  [`111`](../111-host-radius-granularity.md).
- [`kitty-btop-window-roles.html`](./kitty-btop-window-roles.html) — a
  self-contained side-by-side of kitty's palette-only config and the one
  honest next skin knob (`font_family`), btop's 48-key colour-only theme and
  its “not applicable” geometry/type surface, and the role map
  `panel` (outer) / `card` (inner) / `control` / `cell` / `pill` with a
  deferred `surface.window`. It makes clear that notification cards are not an
  outer surface. See [`112`](../112-kitty-btop-window-roles.md).

Open it directly in a browser; there are no external assets, scripts or
network dependencies. It is a design reference, not a runtime surface.
