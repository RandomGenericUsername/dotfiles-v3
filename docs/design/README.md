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

Open it directly in a browser; there are no external assets, scripts or
network dependencies. It is a design reference, not a runtime surface.
