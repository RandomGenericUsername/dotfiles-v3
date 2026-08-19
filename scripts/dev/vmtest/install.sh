#!/usr/bin/env bash
# Install the host prerequisites for the dotfiles dev Vm (run once).
# Requires sudo (installs qemu + cloud-init image tooling).
set -euo pipefail

# Read the host distro; accept Arch and Arch-based derivatives (EndeavourOS,
# CachyOS, Manjaro...) via ID or ID_LIKE=arch, since they all use pacman.
if grep -qiE '^(ID|ID_LIKE)=(.*)?arch' /etc/os-release 2>/dev/null; then
  echo "== Installing QEMU + cloud-init tooling (Arch-based host) =="
  if ! command -v qemu-system-x86_64 >/dev/null || ! command -v cloud-localds >/dev/null; then
    sudo pacman -S --needed --noconfirm qemu-desktop cloud-image-utils
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
