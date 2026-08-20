# Dotfiles Dev VM

A lightweight, graphical Arch VM for verifying dotfiles changes (provisioning,
AGS bar, SDDM/Pixie login, palette chain) without touching a real machine.

The repo is **shared live, read-only, into the VM at `/repo`** via virtio-9p —
any host edit is immediately visible in the VM (no copying). This makes an
edit → provision → visually-verify loop fast and repeatable for future work.

## Why a VM

Containers can't fully validate two things this stack needs:
- **SDDM login** — `systemctl enable sddm` + the greeter need a real systemd/PID1.
- **csg container image** — the palette chain builds csg's image via podman, which
  a nested container can't do; a KVM VM (real podman) can.

A KVM VM (lightweight, ~1–2s boot, 4GiB RAM) covers both.

## Prereqs (one time)

```bash
bash scripts/dev/vmtest/install.sh
```
Installs `qemu-desktop` + `cloud-image-utils` (needs sudo on this Arch host).

## Usage

```bash
# 1. Boot the VM in a visible window (downloads the Arch cloud image on first run)
bash scripts/dev/vmtest/run-vm.sh

# 2. In another terminal, provision it end-to-end (toolchain + bootstrap + verify + key checks)
bash scripts/dev/vmtest/provision-in-vm.sh

# 3. Reboot the VM — it comes back to the SDDM Pixie greeter in the window
ssh -i scripts/dev/vmtest/.images/id_vm -p 2222 arch@localhost 'sudo systemctl reboot'
```

### Testing the login loop (SDDM / Pixie / Hyprland / AGS)
After step 3 the VM boots straight to the **SDDM Pixie greeter**. Log in with
`arch` / `arch` (override with `VMPASSWORD=...`). That drops you into
Hyprland with the AGS bar. **Logout** returns you to the greeter — repeat as
many login/logout cycles as you like. That's the essential graphical test:
real SDDM + Pixie theming + session start, on a real systemd/PID1.

The `/repo` mount is persisted in the VM's fstab (9p, read-only, `nofail`),
so any host edit is live in the guest even after reboots — edit → provision →
reboot → login is a tight loop.

VM facts:
- user `arch`, sudo `NOPASSWD` via SSH key
- greeter/console login: `arch` / `arch` (env `VMPASSWORD` to change)
- provisioning switches the boot target to `graphical.target` (SDDM)

### Manual access
```bash
ssh -i scripts/dev/vmtest/.images/id_vm -p 2222 arch@localhost   # SSH key, no password
```
If `run-vm.sh` picked a different port (2222 busy), pass the same `SSHPORT`.
`provision-in-vm.sh` honors `SSHPORT` too, so the port always matches.

## What gets provisioned / verified
- Full `dotfiles-provision bootstrap` (packages incl. AGS via AUR, csg/weg/itr,
  palette, bar config, SDDM)
- `dotfiles-provision verify`
- Checks AGS bar (`~/.config/ags` symlink, `colors.css`), SDDM (binary, enabled
  service, Pixie theme)

## How the repo is shared
`run-vm.sh` boots with:
```
-virtfs local,path=$REPO_ROOT,mount_tag=repo,security_model=none,readonly=on \
-device virtio-9p-pci,fsdev=repo,mount_tag=repo
```
`provision-in-vm.sh` mounts it (`mount -t 9p -o trans=virtio,version=9p2000.L,ro repo /repo`).

## Display backend
`-display gtk` opens a native window (Wayland/X). For headless, edit `run-vm.sh`:
replace `-display gtk` with `-vnc :1` and connect a VNC viewer to `localhost:5901`.

## Files
- `install.sh` — host prereqs (qemu, cloud-localds)
- `run-vm.sh` — fetch image, seed, boot visible VM with repo shared
- `provision-in-vm.sh` — SSH in, provision + verify, report key results
- `.images/` — downloaded image, working disk, SSH key, seed (git-ignored)
