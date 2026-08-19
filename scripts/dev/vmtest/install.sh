#!/usr/bin/env bash
# Install the host prerequisites for the dotfiles dev Vm (run once).
# Requires sudo (installs qemu + cloud-init image tooling).
set -euo pipefail

# Read the emulated distro arch (host-independent of the guest)
if grep -qE 'ID=(arch|endeavouros)' /etc/os-release 2>/dev/null; then
  echo "== Installing QEMU + cloud-init tooling (Arch) =="
  # qemu-desktop: full x86_64 emulator (our guest); cloud-image-utils: cloud-localds
  if ! command -v qemu-system-x86_64 >/dev/null; then
    sudo pacman -S --needed --noconfirm qemu-desktop cloud-image-utils
  elif ! command -v cloud-localds >/dev/null; then
    sudo pacman -S --needed --noconfirm cloud-image-utils
  fi
else
  echo "unsupported host distro for auto-install ($(grep -E '^ID=' /etc/os-release | head -1))"
  echo "install manually: qemu-system-x86_64 + cloud-localds (cloud-image-utils)"
  exit 1
fi

echo "== Verify =="
qemu-system-x86_64 --version | head -1
command -v cloud-localds && echo "cloud-localds OK"
echo "done. next: bash scripts/dev/vmtest/run-vm.sh"
