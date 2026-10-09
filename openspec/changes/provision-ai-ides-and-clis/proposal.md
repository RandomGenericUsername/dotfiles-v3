## Why

The user runs five AI development tools — Antigravity IDE, Windsurf (now
branded **Devin Desktop**), Visual Studio Code, the GitHub Copilot CLI, and the
OpenAI Codex CLI — and wants them installed **by the provisioner**, not by hand,
so a fresh machine reaches the same state in one `make bootstrap`. Today none of
them is declared anywhere in the provisioning tree: a fresh machine gets them
only if someone runs `yay`/`npm` manually, exactly the manifest-vs-install drift
`repair-package-manifest-drift` was created to eliminate.

The second half of the ask is launchability: the desktop's app launcher is rofi
(`SUPER+D` → the provisioned `rofi-ui` → `rofi -show drun`), and drun reads
`.desktop` files from `$XDG_DATA_HOME/applications`. Installing the packages
gives rofi their own packaged entries, but the Electron/VS Code forks need
Wayland/Ozone launch flags on Hyprland (the same reason the repo already ships
`dotfiles/applications/tidal-hifi.desktop`). The two CLIs have no `.desktop`
entry at all, so they are invisible to rofi.

## What Changes

- **Packages manifest + AUR channel (Arch-only).** `packages.yaml` gains five
  logical entries; `group_vars/arch.yml` maps each to its AUR package;
  `roles/packages/vars/arch.yml` `aur_packages` routes them through yay:

  | logical | AUR package | binary | notes |
  |---|---|---|---|
  | `antigravity-ide` | `antigravity-ide` | `antigravity-ide` | Google's VS Code fork (distinct from the `antigravity` Hub) |
  | `windsurf` | `devin-desktop` | `devin-desktop` | Windsurf's current stable brand |
  | `vscode` | `visual-studio-code-bin` | `code` | Microsoft build (Marketplace + Copilot); `conflicts: code` |
  | `copilot-cli` | `github-copilot-cli` | `copilot` | the new `@github/copilot` |
  | `codex-cli` | `openai-codex-bin` | `codex` | OpenAI Codex CLI |

- **rofi-launchable desktop entries.** Five repo-authoritative `.desktop`
  overrides are authored under `dotfiles/applications/` and placed into
  `$XDG_DATA_HOME/applications/` by the `compositor_configs` role
  (`compositor_configs_desktop_entries`, `force: true`), shadowing the packaged
  entries:
  - `antigravity-ide.desktop`, `code.desktop`, `devin-desktop.desktop` add the
    Wayland/Ozone flags (`UseOzonePlatform,WaylandWindowDecorations`,
    `--ozone-platform-hint=auto`).
  - `copilot.desktop`, `codex.desktop` are `Terminal=false` launchers that exec
    `kitty` with the CLI, so the CLIs are searchable in rofi too.

- **Legacy standalone Codex shadow removed.** The host carries a self-updating
  standalone Codex at `~/.local/bin/codex` → `~/.codex/packages/standalone/…`
  that shadows `/usr/bin/codex` on PATH. The `cli_tools` role (which owns the
  user bin dir) removes that symlink and its package dir **only when the target
  is the standalone installer's**, leaving the AUR `/usr/bin/codex` as the single
  source of truth. `~/.codex/config.toml`/auth is untouched.

- **Verify gate.** The five binaries join `verify_system_binaries`
  (criterion-2 PATH gate), so a missing install fails the provision loudly.

- **Structural tests** updated for the new manifest entries, group_vars keys,
  AUR channel names, and verify binary list.

## Non-goals

- No Debian-family mapping. All five are Arch/AUR-only; they live in the
  Arch-only group_vars set (`_ARCH_EXTRA_KEYS`), consistent with
  `power-options-gtk`/`hyprmod`. A fresh Debian machine is not a target here.
- No new Hyprland keybindings; rofi (`SUPER+D`) is the only entry point.
- No IDE config/theme/extension provisioning (user-owned state), and no
  interactive login/auth (`copilot login`, `codex login`) — provisioning only
  makes the binaries present and launchable.
- No removal of the packages' own `/usr/share/applications` entries — the
  user-scoped override shadows them by XDG priority.
