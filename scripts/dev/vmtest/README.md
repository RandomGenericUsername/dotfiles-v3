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
bash scripts/dev/vmtest/vm-fresh.sh
```

## Usage

### Graphical Console (SDDM + Hyprland)

```bash
sudo -E incus console dotfiles-test --type=vga
```

Opens a SPICE window showing the VM's VGA output. Log in with `arch` / `arch`.

**Note:** Must use `sudo -E` (not plain `sudo`) to preserve display env vars.

### Shell Access

```bash
sudo incus exec dotfiles-test -- su - arch
```

### VM Lifecycle

```bash
# Start
sudo incus start dotfiles-test

# Stop
sudo incus stop dotfiles-test

# Re-provision from scratch (wipes everything)
bash scripts/dev/vmtest/vm-fresh.sh --clean

# Destroy completely
sudo incus delete -f dotfiles-test
```

## What Gets Provisioned

Full `dotfiles-provision bootstrap` pipeline:
- **packages** — system packages + AUR (yay) + fonts
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
- **display_manager** — SDDM + Pixie theme
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

### "cannot open display: :0"
Use `sudo -E` instead of `sudo` to preserve Wayland/X11 env vars.

### Glycin SVG crash
The host's glycin SVG loader may crash with certain icon themes. If
`remote-viewer` crashes immediately, the icon theme's `image-missing.svg`
triggers a glycin/bwrap seccomp bug. Fix: replace SVGs with PNGs in the
offending theme, or remove the theme's `image-missing.svg`.

### Slow pacman mirrors
The script sets fast mirrors automatically. If downloads are slow, check
`/etc/pacman.d/mirrorlist` inside the VM.

### Disk full during bootstrap
The VM needs ~2 GiB free for package installs. The default 10 GiB disk
provides adequate space. If you hit this, destroy and recreate:
```bash
sudo incus delete -f dotfiles-test
bash scripts/dev/vmtest/vm-fresh.sh
```

## Files

- `vm-fresh.sh` — main entry: creates VM, sets up network/packages, pushes repo,
  runs full bootstrap. Use `--clean` to wipe and start fresh.
- `vm-continue.sh` — resume an existing provisioned VM (start + shell).
- `README.md` — this file.
