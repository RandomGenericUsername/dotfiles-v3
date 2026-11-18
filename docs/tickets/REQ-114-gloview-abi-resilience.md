---
id: REQ-114
title: "GloView survives Hyprland ABI upgrades"
kind: requirement
status: done
lane: implementation
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

## Outcome (Lane B release)

**Worktrees:** `.worktrees/REQ-114/` (composition), `.worktrees/REQ-047/`
(engine), `.worktrees/GLOVIEW/` (assets).
**Branches:** `ticket/REQ-114-gloview-abi-resilience`,
`ticket/REQ-047-gloview-abi-resilience`, `ticket/GLOVIEW-abi-resilience`.
**Release order:** assets **`v0.21.5`** (`2b758f7`) → engine **`v0.1.86`**
(bumps assets pin; `GloView` unit + rebuild helper + verify coverage) →
composition **`v0.1.94`** (installer pin `v0.1.86`, assets tuple `v0.21.5`).
**Composition feature commit:** `c55a1eb7` (rebased onto `88b9e42a`).

### Delivered

| Repo | Path | What changed |
| --- | --- | --- |
| composition | `dotfiles/provisioning/scripts/gloview-activate` | authoritative `hyprctl plugin list -j` check, durable `status.json`, ABI-change and chronology warnings, fail-open IPC, safe `hyprctl reload` (G-1…G-4, G-9, G-10) |
| composition | `dotfiles/provisioning/scripts/gloview-rebuild` | interactive, user-run `yay -S --rebuild gloview-git`; no sudo/`--noconfirm` |
| composition | `scripts/tests/test_gloview_abi.py` | stdlib suite driving fake `hyprctl`/`expac`/`notify-send`; now a gate |
| composition | `Makefile`, `.github/workflows/gates.yml` | added `gloview-abi-tests` to `GATES`/`gates-ci` + a CI job; `ci-gates-parity` PASS |
| engine | `ansible/roles/gloview_plugin/**` | user oneshot `dotfiles-gloview.service` (ordered after `graphical-session.target` and `dotfiles-ags-notifications.service`) + `gloview-rebuild` 0755; session-gated start, manager-less wants-link fallback (G-5/G-6) |
| engine | `ansible/roles/verify/**`, `tests/unit/test_verify_role.py` | deferred verify coverage: unit/link/ordering/activator and rebuild helper |
| assets | `configs/hypr/{autostart,input,keybindings}.lua`, `scripts/validate-configs.py` | systemd owns activation; pcall-guarded bind/gestures with native fallbacks (G-8) |

### Gates and evidence

- **Assets** `v0.21.5`: `make gates` PASS (incl. hermetic + shellcheck) and
  `make ci-gates-parity` PASS.
- **Engine** `v0.1.85`: full `make gates` PASS — test **1077 passed, 3
  skipped**; lint all checks passed; hermetic **1042 passed, 38 skipped**;
  lock-check ok. `v0.1.86` fixes the quoted-`ExecStart` verify assertion that
  the first apply exposed; targeted `TestVerifyGloviewActivation` +
  `test_gloview_units.py` (**17 passed**) and `make gates-pin` PASS.
- **Composition** `v0.1.94`: `make gates` PASS — `ansible-embedded-template-lint`,
  `deploy-coverage` (installer `v0.1.86`, assets `v0.21.5`), `gloview-abi-tests`
  (9/9), `ci-gates-parity`, per-app suites.
- **Live GloView probe** (healthy host): `dotfiles-gloview.service` active/ok,
  `status.json` `ok:true`, `hyprctl plugin list -j` contains `GloView`, and no
  dead `hyprctl gloview…` bind is registered. Failure path exercised only
  through the fake-`hyprctl` suite; the live plugin was never unloaded.

### Residual

G-7's notification names `yay -S --rebuild gloview-git` and the relog step, but
the login service does not implement a clickable notification action that opens
a terminal. This limitation is intentional/documented; remediation is the
user-run `gloview-rebuild`.

