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
cd ~/Development/dotfiles-new-architectures/dotfiles-repo-v3

# Create VM + full provision (first run takes ~5-10 min)
scripts/dev/vmtest/vm fresh
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
- **Resources:** 2 CPU, 4 GiB RAM, 10 GiB disk
- **User:** `arch` (sudo NOPASSWD)
- **Password:** `arch` (for SDDM login)
- **Network:** Incus bridge (NAT), DHCP
- **DNS:** Google (8.8.8.8, 8.8.4.4)
- **Mirrors:** mirror.rackspace.com, geo.mirror.pkgbuild.com

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
- `vm-fresh.sh` — creates VM, sets up network/packages, pushes repo, runs bootstrap
- `vm-continue.sh` — resume an existing provisioned VM
- `README.md` — this file
