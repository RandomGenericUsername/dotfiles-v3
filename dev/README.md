# Dotfiles Dev VM

A graphical Arch Linux VM for verifying dotfiles changes end-to-end: provisioning,
SDDM/Pixie login, Hyprland, AGS bar, palette chain — without touching the host.

Uses **Incus** (LXC/VM manager) for clean Wayland-native VGA console access.

## Why a VM

Containers can't fully validate two things this stack needs:
- **SDDM login** — `systemctl enable sddm` + the greeter need a real systemd/PID1.
- **csg container image** — the palette chain builds csg's image via podman, which
  a nested container can't do; a KVM VM (real podman) can.

## Prerequisites (one time)

```bash
# Install Incus
sudo pacman -S incus
sudo systemctl enable --now incus

# Add your user to the incus-admin group (log out/in after this)
sudo usermod -aG incus-admin inumaki

# Install SPICE viewer (for graphical VGA console)
sudo pacman -S spice-gtk
```

## Quick Start

```bash
cd ~/Development/dotfiles-v3

# Create VM + full provision (first run takes ~5-10 min), then asserts the
# result (verify green, SDDM, Hyprland, AGS, icons, GloView, Wi-Fi), reboots
# to prove boot persistence, and asserts again:
./dev/vm fresh

# Re-run just the post-provision assertions any time:
./dev/vm verify
```

## Usage

All commands go through the `vm` script:

```bash
vm fresh       # wipe + recreate + full provision
vm up          # start the VM
vm down        # stop the VM
vm console     # open SPICE graphical console
vm shell       # get a shell inside the VM
vm destroy     # delete the VM entirely
vm status      # show VM state
vm verify      # post-provision assertions inside the VM (P1)
```

### Graphical Console

```bash
vm console
```

Opens a SPICE window showing the VM's VGA output. Log in with `arch` / `arch`.

**Keyboard grab:** Inside the SPICE window, press **Ctrl+Alt+G** to grab the
keyboard. All keys (including Super) go to the VM. Press **Ctrl+Alt+G** again
to release back to the host.

Keybindings inside the VM (when grabbed):
- **Super+Enter** — terminal (kitty)
- **Super+Q** — close window
- **Super+M** — kill active window
- **Super+V** — toggle floating

### Shell Access

```bash
vm shell
```

## Session-Bounce Checker (OPS-0113)

`scripts/check-session-bounce.py` reads `journalctl -u sddm` and fails when a
login bounces instead of starting a session. It is dev tooling (not installed by
provisioning) and uses only the Python standard library.

A login is red when the window contains any of:

- `Session started false` — SDDM's 30 s `waitForStarted` handshake timed out;
- `Auth: sddm-helper exited with 2` — the session helper failed (SDDM tears the
  session down ~60 s after the false handshake);
- `Failed to launch the display server, falling back to DisplayServer=x11-user`
  — the greeter lost its Wayland display server; or
- a session logout within 180 s of login without a shutdown/reboot marker.

### Run the checker

From the repo root (master or a worktree):

```bash
# Current boot; default is --boot 0.
python3 scripts/check-session-bounce.py

# Previous boot / an explicit window.
python3 scripts/check-session-bounce.py --boot -1
python3 scripts/check-session-bounce.py --since "today"
python3 scripts/check-session-bounce.py --since "2026-10-26 08:00:00"

# Machine-readable report (still exits 1 on red).
python3 scripts/check-session-bounce.py --boot 0 --json

# Embedded red/green fixtures; no journal access needed.
python3 scripts/check-session-bounce.py --self-test
```

Exit codes: **0** green, **1** bounce/fallback found, **2** cannot read the
journal or bad invocation. The script never calls `sudo` itself. If your user
cannot read the journal (`journalctl` says no journal files / permission
denied), read it through a user in the `systemd-journal` group or run only the
read as root, e.g. `sudo python3 scripts/check-session-bounce.py --boot 0`.

The self-test must print `SELF-TEST: PASS (10/10)` and exit 0. It covers the real
red sequence, a clean green login, fallback-only, early logout, shutdown logout,
autologin (no greeter `Login` line), and journalctl `short`-format variants.

### Red baseline (2026-10-26, before the BUG-004 fix)

```text
$ python3 scripts/check-session-bounce.py --boot 0
SDDM session-bounce check — boot 0 — 4 attempt(s)

LOGIN      VT  STARTED  HELPER  DURATION  VERDICT
08:29:29   2   false    2       1m30s     FAIL
08:31:05   2   false    2       1m30s     FAIL
08:33:25   2   false    2       1m30s     FAIL
08:35:01   2   true     ok      0s        PASS

FAILURES
  08:28:27  x11-user-fallback      DisplayServer=x11-user fallback before any login
  08:29:59  session-started-false  Session started false
  08:30:59  helper-exit-2          Auth: sddm-helper exited with 2 (+90s)
  08:31:00  x11-user-fallback      DisplayServer=x11-user fallback (+91s)
  08:31:35  session-started-false  Session started false
  08:32:35  helper-exit-2          Auth: sddm-helper exited with 2 (+90s)
  08:32:35  x11-user-fallback      DisplayServer=x11-user fallback (+90s)
  08:33:55  session-started-false  Session started false
  08:34:55  helper-exit-2          Auth: sddm-helper exited with 2 (+90s)
  08:34:55  x11-user-fallback      DisplayServer=x11-user fallback (+90s)

DisplayServer=x11-user fallback line(s): 4
  08:28:27  Failed to launch the display server, falling back to DisplayServer=x11-user
  08:31:00  Failed to launch the display server, falling back to DisplayServer=x11-user
  08:32:35  Failed to launch the display server, falling back to DisplayServer=x11-user
  08:34:55  Failed to launch the display server, falling back to DisplayServer=x11-user

RESULT: FAIL — 3 failed login attempt(s) of 4; 4 x11-user fallback line(s)
# exit 1
```

```text
$ python3 scripts/check-session-bounce.py --boot -1
SDDM session-bounce check — boot -1 — 7 attempt(s)

LOGIN      VT  STARTED  HELPER  DURATION  VERDICT
06:23:21   2   false    2       1m30s     FAIL
06:24:56   2   false    2       1m30s     FAIL
06:28:17   2   false    2       1m30s     FAIL
06:31:01   2   false    2       1m31s     FAIL
06:34:02   2   false    2       1m30s     FAIL
06:40:47   2   false    2       1m31s     FAIL
08:07:10   2   true     ok      0s        PASS

FAILURES
  06:23:02  x11-user-fallback      DisplayServer=x11-user fallback before any login
  06:23:51  session-started-false  Session started false
  06:24:51  helper-exit-2          Auth: sddm-helper exited with 2 (+90s)
  06:24:51  x11-user-fallback      DisplayServer=x11-user fallback (+90s)
  06:25:26  session-started-false  Session started false
  06:26:26  helper-exit-2          Auth: sddm-helper exited with 2 (+90s)
  06:26:26  x11-user-fallback      DisplayServer=x11-user fallback (+90s)
  06:28:47  session-started-false  Session started false
  06:29:47  helper-exit-2          Auth: sddm-helper exited with 2 (+90s)
  06:29:48  x11-user-fallback      DisplayServer=x11-user fallback (+91s)
  06:31:32  session-started-false  Session started false
  06:32:32  helper-exit-2          Auth: sddm-helper exited with 2 (+91s)
  06:32:32  x11-user-fallback      DisplayServer=x11-user fallback (+91s)
  06:34:32  session-started-false  Session started false
  06:35:32  helper-exit-2          Auth: sddm-helper exited with 2 (+90s)
  06:35:32  x11-user-fallback      DisplayServer=x11-user fallback (+90s)
  06:41:17  session-started-false  Session started false
  06:42:18  helper-exit-2          Auth: sddm-helper exited with 2 (+91s)
  06:42:18  x11-user-fallback      DisplayServer=x11-user fallback (+91s)

DisplayServer=x11-user fallback line(s): 7
  06:23:02  Failed to launch the display server, falling back to DisplayServer=x11-user
  06:24:51  Failed to launch the display server, falling back to DisplayServer=x11-user
  06:26:26  Failed to launch the display server, falling back to DisplayServer=x11-user
  06:29:48  Failed to launch the display server, falling back to DisplayServer=x11-user
  06:32:32  Failed to launch the display server, falling back to DisplayServer=x11-user
  06:35:32  Failed to launch the display server, falling back to DisplayServer=x11-user
  06:42:18  Failed to launch the display server, falling back to DisplayServer=x11-user

RESULT: FAIL — 6 failed login attempt(s) of 7; 7 x11-user fallback line(s)
# exit 1
```

The summary counts **login attempts**, so one bounced login with a false
handshake, a helper exit 2, and a fallback is one failed attempt (three failure
lines). Boot 0 therefore reports 3 failed attempts and 4 fallback lines; boot -1
reports 6 failed attempts and 7 fallback lines.

This is the failing artifact the provision fix (weston/compositor, BUG-004)
must turn green. A green run looks like five `PASS` rows and
`RESULT: PASS — 5 login attempt(s), no bounce or x11-user fallback`; exit 0.

### VM assertion

`dev/vm-assert.sh` (run by both `make vm-fresh` and `make vm-verify`) now also:

1. fails if `journalctl -b -u sddm` contains
   `falling back to DisplayServer=x11-user`;
2. runs `scripts/check-session-bounce.py --boot 0` inside the guest (as root via
   `sudo incus exec`, so journal groups do not matter) and requires exit 0;
3. requires `weston` on the guest PATH (the Wayland fallback compositor).

`sudo` is required for every Incus operation. The user runs the VM checks; an
implementation agent must not run them:

```bash
make vm-fresh     # sudo: wipe/recreate/provision, assert, reboot, assert again
make vm-verify    # sudo: re-run only the post-provision assertions
```

Until the provision fix is deployed, the new checks are expected to be red —
that is the regression this harness proves.

### Optional deterministic timeout repro

`dev/vm-session-loop.sh` proves the 30 s timeout → ~60 s teardown chain
independently of the VT state. It is optional, only for the provisioned Incus
VM, and needs `sudo` (it asks itself; run it as your user, not through `sudo`):

```bash
./dev/vm-session-loop.sh        # VM dotfiles-test must be RUNNING
```

It temporarily writes `/usr/share/wayland-sessions/repro-delay.desktop` whose
`Exec` sleeps 40 s before `uwsm start -e -D Hyprland hyprland.desktop`, points
SDDM autologin at it with `Relogin=true`, restarts SDDM, and asserts
`Session started false` followed ~60 s later by
`Auth: sddm-helper exited with 2`. The original autologin drop-in and all repro
files are restored on exit (including Ctrl-C), so the VM is not left in the
repro state.

If the VM has no KMS/Wayland display server, the script prints a documented
`[SKIP]` and relies on the VM fallback assertion plus the host acceptance below;
the timeout chain needs a working Wayland greeter to be meaningful.

### Host 5-login acceptance (user step)

This is the final proof and is a **user-run step after the provision fix is
deployed and the host rebooted**:

```bash
# Log in through SDDM five times, leaving each session up for at least 180 s
# before logging out (the intentional early-logout rule treats a shorter
# teardown as a bounce unless a shutdown/reboot was logged). Then:
python3 scripts/check-session-bounce.py --boot 0
# required: exit 0, five PASS rows, no fallback line
```

Use `--since "<start of the test>"` to scope the check to the five logins.

## What Gets Provisioned

Full `dotfiles-provision bootstrap` pipeline:
- **packages** — system packages + AUR (yay) + fonts (incl. emoji)
- **cli_tools** — csg, weg, itr via `uv tool install`
- **assets** — wallpapers, WEG effects catalog
- **default_palette** — palette generation via csg container
- **compositor_configs** — Hyprland/Hyprpaper skeleton + palette fragments
- **config_copies** — config dirs (hypr, ags, nvim, zsh, etc.)
- **settings** — rendered csg/weg/itr settings files
- **zsh_tools** — oh-my-zsh, pyenv, nvm
- **zsh_config** — rendered .zshrc
- **wlogout_config** — rendered style.css
- **config_links** — symlinks `~/.config/*` into the spine
- **icons** — rendered SVG icons
- **display_manager** — SDDM + Pixie theme + graphical.target
- **verify** — all gates pass

Canonical spine: `~/.local/share/dotfiles/`

## VM Details

- **Image:** Arch Linux (latest cloud image)
- **Resources:** 2 CPU, 4 GiB RAM, 20 GiB disk (auto-expanded on reuse)
- **User:** `arch` (sudo NOPASSWD)
- **Password:** `arch` (for SDDM login)
- **Network:** Incus bridge (NAT), DHCP
- **DNS:** Google (8.8.8.8, 8.8.4.4)
- **Mirrors:** mirror.rackspace.com, geo.mirror.pkgbuild.com

## What the VM Cannot Test

Two things need bare metal, in any VM software (not an Incus limitation):

- **Trackpad gestures** — laptop trackpads are PS/2- or I2C-attached, so they
  cannot be passed through to a guest; the VM only ever sees a generic mouse.
  The GloView plugin *build + load* is asserted in the VM (`vm verify`), but
  finger input needs real hardware.
- **Physical radios** — the guest gets virtual Ethernet (plus a simulated
  Wi-Fi AP for the bar's connected state), never your Wi-Fi/Bluetooth card.

For hardware truth, provision a throwaway user account on the host instead:
fresh `$HOME`, same kernel/trackpad/radios, SDDM login into Hyprland gives
the genuine first-login flow. Delete it afterwards.

## Troubleshooting

### Super key doesn't work in VM
Press **Ctrl+Alt+G** inside the SPICE window to grab the keyboard. The host's
Hyprland intercepts Super until keyboard is grabbed.

### Glycin SVG crash
The host's glycin SVG loader may crash with certain icon themes. If
`remote-viewer` crashes immediately, the icon theme's `image-missing.svg`
triggers a glycin/bwrap seccomp bug. Fix: replace SVGs with PNGs in the
offending theme, or remove the theme's `image-missing.svg`.

### Disk full during bootstrap
Destroy and recreate:
```bash
vm destroy
vm fresh
```

## Files

- `vm` — single entry point for all VM operations
- `check-prereqs.sh` — host prerequisite gate (incus, daemon, KVM, group, viewer)
- `vm-assert.sh` — post-provision assertions inside the guest (P1, re-run after P2 reboot), including the session-bounce checker and x11-user fallback gate
- `vm-fresh.sh` — creates VM, sets up network/packages, pushes repo, runs bootstrap
- `vm-session-loop.sh` — optional deterministic repro of the SDDM `waitForStarted` timeout → teardown chain
- `vm-continue.sh` — resume an existing provisioned VM

The SDDM journal checker itself lives at `scripts/check-session-bounce.py`.

`vm-fresh.sh` provisions the base machine first, then adds a VM-only SDDM
autologin for `arch`. That starts a real Hyprland session so the session
autostart can run `gloview-activate`; the script waits for its successful
`hyprctl plugin list` verification before reporting the VM ready. GloView is
not installed during headless Ansible bootstrap because `hyprpm` requires the
live Hyprland IPC session.
- `README.md` — this file
