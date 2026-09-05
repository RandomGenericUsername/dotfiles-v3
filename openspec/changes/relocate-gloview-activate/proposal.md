## Why

`scripts/gloview-activate` is a provisioning-time helper (Hyprland `hyprpm` needs a live Wayland IPC session, so autostart runs it after compositor start) sitting in the generic `scripts/` bucket next to the user-facing `capture-tool` backend. Moving it to `dotfiles/provisioning/scripts/` puts it beside the manifests that own it and makes `scripts/` one step closer to empty.

## What Changes

- Move `scripts/gloview-activate` → `dotfiles/provisioning/scripts/gloview-activate` verbatim (no logic change).
- Update `cli_tools` Ansible role copy `src:` to the new path; `dest` (`~/.local/bin/gloview-activate`, 0755) unchanged.
- No autostart, keybind, or VM changes.

## Capabilities

### New Capabilities

- `provisioning-scripts-layout`: provisioning-owned helper scripts live under `dotfiles/provisioning/scripts/` and are installed to the user bin dir by the `cli_tools` role.

### Modified Capabilities

*(None — pure relocate.)*

## Impact

- `dotfiles/provisioning/scripts/` created; one fewer file in `scripts/`.
- `cli_tools` role tasks only. NOTE: branch currently carries uncommitted `gloview-plugin` role work (hyprpm update flow) — rebase this change on top of that before implementing so the `src:` edit doesn't collide.
