---
id: REQ-114
title: "GloView survives Hyprland ABI upgrades"
kind: requirement
status: proposed
lane: design
links:
  openspec: none
  bmad: none
  design: docs/114-gloview-abi-resilience.md
worktree: .worktrees/REQ-114/
branch: ticket/REQ-114-gloview-abi-resilience
---

# GloView survives Hyprland ABI upgrades

## Requirement

GloView (`/usr/lib/gloview.so`, `gloview-git` AUR) must degrade visibly and
recoverably when a Hyprland upgrade invalidates its build ABI, instead of
silently losing the overview and gestures. Detection, state, and remediation
must work without giving a login task sudo and without auto-installing AUR
packages.

Adopt the design in [`docs/114-gloview-abi-resilience.md`](../114-gloview-abi-resilience.md):

- **Authoritative detection:** always load/verify through the running
  compositor and check `hyprctl plugin list -j` for `GloView`; never trust the
  exit status of `hyprctl plugin load` (observed exit 0 on a reported failure).
- **Early warning:** compare the stored `hyprctl version -j .abiHash` stamp and
  the `gloview-git` `BUILDDATE` vs `hyprland` `INSTALLDATE` chronology.
- **Observable surface:** a systemd user oneshot
  (`dotfiles-gloview.service`) owns activation, ordered after
  `graphical-session.target` and `dotfiles-ags-notifications.service`; remove
  the fire-and-forget `autostart.lua` line.
- **Durable state:** `~/.local/state/dotfiles/gloview/status.json` plus
  `activate.log`; remove `gloview-active` on failure.
- **One-click, user-authenticated remediation:** notification action opens a
  terminal running `gloview-rebuild` (`yay -S --rebuild gloview-git`). No
  `sudo`/`yay`/`pacman`/network call from the service or autostart.
- **Fallback:** guard `SUPER+TAB` and the GloView left/right gestures so a
  missing plugin leaves native workspace behavior, not dead dispatchers.
  Hyprland 0.57 has no built-in overview; hyprexpo/hyprspace are plugins with
  the same ABI constraint.
- **Not adopted:** automatic rebuild, root pacman hook running `yay`, default
  `IgnorePkg` pinning, or switching to hyprpm (not installed; gloview has no
  `hyprpm.toml`).

## Why now

On 2026-11-12 the host is healthy (`hyprland 0.57.2-1`,
`gloview-git 0.3.0.r34.67857e6-1`, GloView listed) because it was rebuilt after
the last upgrade. The user's context (`r28`, empty plugin list, undefined
symbol) is the exact post-upgrade failure mode. The current activator discards
the loader error, treats a compositor failure as shell success, leaves a stale
`gloview-active` marker, and has no systemd failure state. This ticket closes
that gap as a design pass only.

## Scope of this ticket

1. Design record: `docs/114-gloview-abi-resilience.md`.
2. This tracking ticket.
3. No implementation, no live config edit, no package install, no sudoers
   change, no tag.

## Criteria

- **G-1** Activation verifies `hyprctl plugin list -j` and ignores the
  `hyprctl plugin load` exit code as a success signal.
- **G-2** On failure, `status.json` records `ok:false`, the current `abiHash`,
  package/build metadata, `.so` BuildID/mtime, and the exact loader output;
  `gloview-active` is removed.
- **G-3** A changed stored `abiHash` is reported as `abi_changed`; a successful
  load still updates the stamp and clears the warning.
- **G-4** The package-chronology check warns only when gloview `BUILDDATE`
  precedes Hyprland `INSTALLDATE`.
- **G-5** Activation runs from `dotfiles-gloview.service` (user scope) and a
  failure is visible in `systemctl --user --failed` and the journal.
- **G-6** The service/script contains no `sudo`, `yay`, `pacman`, or network
  invocation; the rebuild helper is interactive and user-run.
- **G-7** The failure notification names `yay -S --rebuild gloview-git` and the
  relog step; no silent auto-rebuild exists.
- **G-8** Missing/stale plugin leaves no dead `hyprctl gloview…` binds; native
  workspace gestures still work.
- **G-9** Activation is idempotent per session and fail-open when Hyprland IPC
  is unavailable.
- **G-10** `hyprctl reload` (or an equivalent safe re-parse) still registers the
  pcall-guarded GloView binds after a successful load.

## Acceptance

- [ ] `docs/114-gloview-abi-resilience.md` records the evidence, options,
  design, exact commands, risks and fallback.
- [ ] Implementation slice in `dotfiles-v3` (activator source), `dotfiles-assets`
  (autostart/keybind/gesture guards), and `dotfiles-provision` (user unit +
  `gloview-rebuild` helper) lands with tests.
- [ ] Healthy-host probe passes G-1…G-10.
- [ ] Simulated stale/undefined-symbol fixture fails visibly with the exact
  command and no privilege escalation.
- [ ] No live config, package install, sudoers, or tag in this design pass.

## Evidence (design pass, 2026-11-12)

- `hyprctl version -j` → `abiHash=11cbc6c5…_aq_0.16_hu_0.14_hg_0.6_hc_0.1_hlg_0.6`.
- `hyprctl plugin list -j` → `GloView 0.3.0`.
- `expac`: Hyprland install `2026-11-10 19:34:36`, gloview build
  `2026-11-11 10:32:40`.
- `hyprctl plugin load /nonexistent.so` prints an error but exits `0`.
- `ldd -r` reports Hyprland-internal undefined symbols even on the healthy
  build — not an ABI test.
- `systemctl --user show-environment` exports
  `HYPRLAND_INSTANCE_SIGNATURE`; notification daemon advertises `actions`.

## Next step

Implement G-1…G-3 (activator verification/state) first, then G-5/G-6 (user
unit + rebuild helper), then G-8 (bind guards). Keep the design doc as the
source of truth. Do not add sudo or auto-update behavior.
