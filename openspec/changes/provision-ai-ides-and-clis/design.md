## Context

The provisioning contract has three layers (NFR-3): the logical manifest
(`dotfiles/provisioning/packages.yaml`), the per-distro name maps
(`group_vars/{arch,debian-family}.yml`), and the AUR channel
(`roles/packages/vars/arch.yml` `aur_packages`, installed by yay and subtracted
from the pacman list). Structural tests lock all three together.

The desktop launcher is rofi in `drun` mode: `SUPER+D` → provisioned `rofi-ui` →
`rofi -config ~/.config/rofi/launcher/config.rasi -show drun`. drun reads
`.desktop` files from `/usr/share/applications` and `$XDG_DATA_HOME/applications`;
a user entry with the same filename shadows the packaged one. The
`compositor_configs` role already places such overrides
(`compositor_configs_desktop_entries`, `force: true`) — `tidal-hifi.desktop` is
the precedent for adding Wayland flags to an Electron app.

## Goals / Non-Goals

**Goals**
- One `make bootstrap` installs all five tools on Arch and makes every one of
  them (including the two CLIs) launchable from rofi.
- The installed set matches the declared set (no manifest drift), enforced by
  the existing parity locks.
- Exactly one Codex on PATH after provisioning.

**Non-Goals**
- Debian support, IDE config/extension provisioning, interactive auth, new
  keybindings (see proposal Non-goals).

## Decisions

### D1. All five are Arch/AUR-only logical keys

The AUR is the native distribution path for these tools; none has a sane
distro-agnostic mapping here. They are added as **Arch-only** logical keys
(`group_vars/arch.yml` only, mirrored in the test's `_ARCH_EXTRA_KEYS`), exactly
like `power-options-gtk` and `hyprmod`. The shared manifest still lists them, and
`test_every_manifest_entry_is_reachable_from_a_provisioning_path` proves
reachability through the Arch map + `aur_packages` (union across distros).

Consequence, documented: a Debian-family host does not get these five. That is
the intended scope (owner decision 2026-10-09), not an oversight.

### D2. `windsurf` maps to `devin-desktop` (the rebrand)

Windsurf (Codeium) was rebranded **Devin Desktop**; there is no `windsurf` AUR
package any more. The stable package `devin-desktop` still pulls from
`windsurf-stable.codeiumdata.com` and ships `/usr/bin/devin-desktop` +
`devin-desktop.desktop`. The logical key stays `windsurf` (the user's term,
stable across the rebrand); the value is `devin-desktop`. The beta channel
(`devin-desktop-next`) is deliberately not used.

### D3. VSCode = `visual-studio-code-bin` (Microsoft build)

Chosen over the official-repo OSS `code` because the user wants the Marketplace
and Copilot. It `provides: code`/`vscode` and `conflicts: code`, so the OSS
package must not be installed alongside it — it is not in any group_vars map.

### D4. rofi-launchable IDE entries are user-scoped overrides with Wayland flags

Installing the packages already makes rofi show them (packaged entries), but
these are Electron/VS Code forks and without Ozone flags they run under XWayland
on Hyprland. Repo-idiomatic fix: author `dotfiles/applications/{antigravity-ide,
code,devin-desktop}.desktop` and register them in
`compositor_configs_desktop_entries`, which copies them to
`$XDG_DATA_HOME/applications/` (`force: true`) where they shadow the packaged
entries. Each carries the combined flag set validated for TIDAL:

`--enable-features=UseOzonePlatform,WaylandWindowDecorations --ozone-platform-hint=auto`

The override filename MUST equal the packaged filename to shadow it
(`antigravity-ide.desktop`, `code.desktop`, `devin-desktop.desktop`).

### D5. The two CLIs get `Terminal=false` kitty launchers

`copilot` and `codex` ship no `.desktop` entry. To make them rofi-searchable,
author `copilot.desktop`/`codex.desktop` with `Exec=kitty --title "…" copilot`
(resp. `codex`) and `Terminal=false`. `kitty` is the provisioned terminal
(packages.yaml `terminal`), so this is deterministic and does not depend on
rofi's `-terminal` resolution. No `%U`/MimeType — they take no file argument.

### D6. Remove the standalone Codex shadow in `cli_tools`, guarded

`~/.local/bin/codex` is the standalone installer's symlink into
`~/.codex/packages/standalone/current/bin/codex`; it precedes `/usr/bin` on PATH
and would keep the AUR package from ever being the resolved binary. The
`cli_tools` role owns the user bin dir (`cli_tools_bin_dir`), is user-scoped (no
become — matching the "never install into root's home" contract), and already
installs host-side CLIs, so the cleanup lives there:

1. `stat` `{{ cli_tools_bin_dir }}/codex`.
2. Remove it **only** when `stat.islnk` and the link target contains
   `.codex/packages/standalone` (never a user's own codex).
3. Remove `{{ HOME }}/.codex/packages` (the standalone payload) when present,
   leaving `~/.codex/config.toml` and auth untouched.

Removals are check-gated (`when: not ansible_check_mode`), mirroring the
compositor_configs/gui_tools legacy-cleanup tasks.

### D7. The five binaries join `verify_system_binaries`

`antigravity-ide`, `code`, `devin-desktop`, `copilot`, `codex` are added to the
criterion-2 PATH gate. `power-options-gtk` and `pavucontrol` set the precedent
for GUI app binaries in that list. The exact-list test
(`test_system_binaries_are_compositors`) is updated in lockstep — this is what
makes "installed but not on PATH" fail the provision instead of passing
silently.

## Gates / Harnesses (acceptance)

- **G1 — Provisioning parity (automated).** `pytest src/provisioning/tests` green:
  manifest-reader expected set, `_ARCH_EXTRA_KEYS`, `aur_packages` reachability,
  duplicate/empty/rollup invariants, verify binary list.
- **G2 — Role syntax (automated).** `ansible-playbook --syntax-check` for both
  `os_family` values (covered by `test_packages_role.py`).
- **G3 — rofi wiring (structural + manual).** The desktop-entry list contains the
  five new sources under `dotfiles/applications/` with dests under
  `$XDG_DATA_HOME/applications/`; on the host, `rofi -show drun` lists
  "Antigravity IDE", "Visual Studio Code", "Devin", "GitHub Copilot CLI", "Codex".
- **G4 — Real provisioning (manual, scripted).** `packages` + `compositor-configs`
  + `cli_tools` playbooks against `install_dir=$HOME/.local/share/dotfiles`;
  re-run idempotent; assert the five binaries resolve and the five `.desktop`
  files exist in `~/.local/share/applications/`; assert `~/.local/bin/codex` is
  gone.
- **G5 — Full gate run.** `make gates` green (or the CI-subset equivalent).

## Risks / Trade-offs

- **AUR availability drift.** `devin-desktop` (rebrand) and the VS Code binary
  names can change upstream. The logical keys are stable; only the group_vars
  values would need a re-point. Documented so the next maintainer knows where.
- **Wayland flags are version-sensitive.** Ozone flag names occasionally change
  across Electron/VS Code releases. If a launch misbehaves, the fix is isolated
  to one `dotfiles/applications/*.desktop` file (the same surface TIDAL uses).
- **Removing a user binary is destructive.** Guarded to the standalone
  installer's symlink + its `~/.codex/packages` payload only; a user's own
  `~/.local/bin/codex` is never touched. `~/.codex` config/auth is preserved.
- **Arch-only scope** means Debian hosts silently lack these five. Recorded in
  proposal Non-goals and D1.
