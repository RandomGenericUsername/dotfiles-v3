## Context

Provisioning's config-in-spine model: `config_copies` copies static
`dotfiles/config/*` dirs into `<install>/config/`, `config_links` symlinks
`~/.config/<target>` to them, `filesystem` creates the config home, and `verify`
asserts the results. Rendered (machine-specific) configs live in their own roles
— `zsh_config` renders `.zshrc.j2` with `COLOR_SCHEME_CURRENT_DIR =
<XDG_STATE_HOME>/dotfiles/current` and links `~/.config/zsh`.

kitty supports `include` (absolute or relative) and reloads config on SIGUSR1
(`kill -SIGUSR1 $KITTY_PID`); `auto_reload_config` exists but relies on
file-watching. On the host `~/.config/kitty/` is empty.

## Goals / Non-Goals

**Goals**
- kitty reads the runtime palette at `current/colors.kitty` on every start and on
  every `KittyReloader` reload.
- The provisioned config is machine-portable (absolute state path rendered at
  apply time) and survives re-provisioning without clobbering user customisation.
- Full provisioning: package, spine config, `~/.config/kitty` link, verify.

**Non-Goals**
- CSG/runtime changes (sibling changes).
- Any kitty behavior beyond colour include (fonts, keybinds, tabs stay default).

## Decisions

### D1. A dedicated rendered role (`kitty_config`), not `config_copies`
The file embeds an absolute, machine-specific state path, so it must be templated
at apply time like `zsh_config` — the static `config_copies` set cannot render.

### D2. The provisioned `kitty.conf` includes the runtime palette + a user-local file
`kitty.conf.j2`:
```
# managed by provisioning — do not edit; put customisations in local.conf
include <state_root>/dotfiles/current/colors.kitty
include local.conf
```
`local.conf` is created only if absent (`force: false`) so user edits survive
re-provisioning; `include local.conf` must not fail when the file is missing
(empty file created at first provision).

### D3. `auto_reload_config -1` — the runtime signals reloads
Reloading a symlinked `current/colors.kitty` via kitty's file watcher is not
guaranteed (the symlink target changes, not the watched path's content). The
runtime's `KittyReloader` sends `SIGUSR1` deterministically, so the config
disables auto-reload to avoid double work. kitty 0.48 types `auto_reload_config`
as a float number of seconds (negative disables); the earlier `no` value is a
parse error, not a boolean.

### D4. config-in-spine + link, consistent with the existing model
Config lives at `<install>/config/kitty/kitty.conf`; `config_links` symlinks
`~/.config/kitty -> <install>/config/kitty` (kitty resolves `include` relative to
the config file, and the runtime palette include is absolute, so the link is
transparent). `filesystem` ensures the config home; `verify` asserts the linked
dir, `kitty.conf`, and the include line.

### D5. State-path derivation mirrors `zsh_config`
`<XDG_STATE_HOME | ~/.local/state>/dotfiles/current` (F4 lock: `ansible_facts.env`,
not `ansible_env`). One XDG read per role.

### D6. Ensure kitty is installed
kitty SHALL be present via the package manifest (it is launched by keybinds and
AGS today). If absent from the manifest, add it (Arch `kitty`; Debian-family
`kitty`).
