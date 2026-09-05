## Context

`scripts/gloview-activate` is exec'd by `dotfiles/config/hypr/autostart.lua` on `hyprland.start` and installed to `~/.local/bin` by the `cli_tools` role. The broken branch moved it correctly but bundled it with the capture extraction, so it never shipped alone. The tree currently also carries uncommitted `gloview-plugin` role work — this change must rebase onto that.

## Goals / Non-Goals

**Goals:** new home `dotfiles/provisioning/scripts/gloview-activate`, identical installed behavior.
**Non-Goals:** no logic edits, no autostart/keybind changes, no capture/VM moves.

## Decisions

- **Verbatim `git mv` + one-line `src:` edit** in `cli_tools/tasks/main.yml`. Alternative (symlink shim) rejected: provisioning helper, single consumer.
- **Rebase onto uncommitted gloview-plugin work first**, then implement, to avoid `src:`-line collision.

## Risks / Trade-offs

- **[Risk] Stale `scripts/gloview-activate` reference** → Mitigation: grep for `scripts/gloview-activate` post-move (expect only history); `ansible-lint`/dry-run `cli_tools`.
