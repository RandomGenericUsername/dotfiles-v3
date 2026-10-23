## Why

The `KittyReloader` (`add-runtime-kitty-terminal-reload`) can only theme kitty if
kitty's config actually **includes** the runtime palette. Today
`~/.config/kitty/` is empty (verified on the host) — kitty runs with defaults and
never reads `current/colors.kitty`. This change provisions a kitty config that
includes the runtime palette, so a reload applies the wallpaper colors to every
kitty window.

## What Changes

- A new `kitty_config` provisioning role (mirroring `zsh_config`): renders
  `kitty.conf.j2` into the config-in-spine and links `~/.config/kitty` to it, so
  kitty reads it at its native XDG location.
- The rendered `kitty.conf` `include`s the runtime palette at an **absolute**
  machine path: `<state_root>/dotfiles/current/colors.kitty` (the same derivation
  `zsh_config` uses for `COLOR_SCHEME_CURRENT_DIR`). `auto_reload_config` is set
  to `-1` (negative seconds disables it in kitty 0.48, which types the option as
  a float) — the runtime signals reload explicitly (`KittyReloader`), avoiding a
  reliance on file-watching a symlink.
- The config reserves a user-local include (e.g. `include local.conf` guarded so
  it is optional) so user customisations live outside the provisioned file.
- Provisioning owns `kitty.conf`; `kitty` is ensured present in the package
  manifest; `verify` asserts the file and the include line exist.
- The `kitty` config joins the `config_copies`/`config_links` model (spine copy +
  `~/.config/kitty` symlink) — but as a **rendered** file, so it lives in its own
  role rather than the static `config_copies` set.

## Non-goals

- No CSG format and no runtime artifact/reloader (sibling changes).
- No kitty keybindings/theme beyond the color include (kitty stays otherwise
  default).
- No editing of a user's pre-existing hand-written `kitty.conf` (provisioning
  owns the file; customisations go in the included `local.conf`).
