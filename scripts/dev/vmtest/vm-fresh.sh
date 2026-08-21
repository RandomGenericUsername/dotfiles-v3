#!/usr/bin/env bash
# vm-fresh.sh — Incus-based clean slate: fresh VM, full provision, ready to test.
#   --clean : wipe existing VM and start fresh
#   (no arg): reuse existing VM if present, only provision if not yet provisioned
set -euo pipefail

VM_NAME="dotfiles-test"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

if [ "${1:-}" = "--clean" ]; then
  echo "== vm-fresh: cleaning existing VM =="
  sudo incus delete -f "$VM_NAME" 2>/dev/null || true
fi

# Ensure host firewall allows Incus VM traffic (FORWARD + NAT)
echo "== vm-fresh: checking host firewall for Incus =="
if ! sudo iptables -C FORWARD -i incusbr0 -j ACCEPT 2>/dev/null; then
  echo "  Adding FORWARD rule for incusbr0"
  sudo iptables -I FORWARD -i incusbr0 -j ACCEPT
  sudo iptables -I FORWARD -o incusbr0 -j ACCEPT
fi
if ! sudo iptables -t nat -C POSTROUTING -s 10.27.121.0/24 ! -o incusbr0 -j MASQUERADE 2>/dev/null; then
  echo "  Adding MASQUERADE for incusbr0"
  sudo iptables -t nat -A POSTROUTING -s 10.27.121.0/24 ! -o incusbr0 -j MASQUERADE
fi
sudo mkdir -p /etc/iptables
sudo iptables-save | sudo tee /etc/iptables/iptables.rules > /dev/null

# Only launch if VM doesn't exist
if ! sudo incus info "$VM_NAME" >/dev/null 2>&1; then
  echo "== vm-fresh: launching fresh Incus VM =="
  sudo incus launch images:archlinux/current "$VM_NAME" --vm \
    -d root,size=10GiB \
    -c limits.cpu=2 -c limits.memory=4GiB \
    -c security.secureboot=false
else
  echo "== vm-fresh: reusing existing VM =="
  sudo incus start "$VM_NAME" 2>/dev/null || true
fi

echo "== vm-fresh: waiting for VM agent to be ready =="
for i in $(seq 1 90); do
  if sudo incus info "$VM_NAME" 2>/dev/null | grep -q "Status: RUNNING"; then
    if sudo incus exec "$VM_NAME" -- true 2>/dev/null; then
      echo "Agent ready"
      break
    fi
  fi
  sleep 2
  [ $i -eq 90 ] && { echo "Agent never became ready"; exit 1; }
done

echo "== vm-fresh: base setup inside VM =="
sudo incus exec "$VM_NAME" -- bash -c "
  set -e

  # 1. NETWORK — disable systemd-resolved (it overwrites resolv.conf)
  systemctl stop systemd-resolved 2>/dev/null || true
  systemctl disable systemd-resolved 2>/dev/null || true
  rm -f /etc/resolv.conf

  # Configure networkd for DHCPv4
  cat > /etc/systemd/network/enp5s0.network << 'NETCONF'
[Match]
Name=enp5s0

[Network]
DHCP=yes
IPv6AcceptRA=yes
NETCONF

  systemctl restart systemd-networkd
  sleep 5

  # If DHCP failed, assign manually
  if ! ip -4 addr show enp5s0 | grep -q 'scope global'; then
    echo 'DHCP failed, assigning manually...'
    ip addr add 10.27.121.100/24 dev enp5s0
    ip route add default via 10.27.121.1
  fi

  # Write static resolv.conf (real file, not symlink)
  cat > /etc/resolv.conf << 'DNSCONF'
nameserver 8.8.8.8
nameserver 8.8.4.4
DNSCONF

  # Verify DNS with timeout
  echo 'Network + DNS configured. Verifying...'
  for i in \$(seq 1 30); do
    if timeout 3 getent hosts archlinux.org >/dev/null 2>&1; then
      echo 'DNS OK'
      break
    fi
    sleep 1
  done
  timeout 3 getent hosts archlinux.org >/dev/null 2>&1 || { echo 'ERROR: DNS still broken'; exit 1; }

  # Fast mirrors (mirrors.kernel.org is slow from some locations)
  printf 'Server = https://mirror.rackspace.com/archlinux/$repo/os/$arch\nServer = https://geo.mirror.pkgbuild.com/$repo/os/$arch\n' > /etc/pacman.d/mirrorlist

  # 2. Packages
  pacman -Syu --noconfirm
  pacman -S --noconfirm git base-devel sudo podman

  # 3. User setup
  useradd -m -G wheel -s /bin/bash arch
  echo 'arch:arch' | chpasswd
  echo 'arch ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

  # 4. Podman
  systemctl enable --now podman.socket
  loginctl enable-linger arch
  su - arch -c 'systemctl --user enable --now podman.socket 2>/dev/null || true'

  # 5. Verify
  if su - arch -c 'podman info >/dev/null 2>&1'; then
    echo 'Podman OK for arch user'
  else
    echo 'WARNING: podman info failed for arch — bootstrap may fail'
  fi
"

echo "== vm-fresh: pushing repo =="
# Use tar to preserve symlinks (incus file push -r resolves them)
sudo incus exec "$VM_NAME" -- mkdir -p /home/arch/dotfiles-repo-v3
tar -C "$REPO_ROOT" --exclude='.images' -cf - . | sudo incus exec "$VM_NAME" -- tar -C /home/arch/dotfiles-repo-v3 -xf -
sudo incus exec "$VM_NAME" -- chown -R arch:arch /home/arch/dotfiles-repo-v3

echo "== vm-fresh: running bootstrap (full provision) =="
sudo incus exec "$VM_NAME" -- su - arch -c "
  cd ~/dotfiles-repo-v3 && ./bootstrap.sh
"

echo "== vm-fresh: provision complete. VM ready for testing. =="
echo "  Console:  sudo incus console $VM_NAME --type=vga"
echo "  Shell:    sudo incus exec $VM_NAME -- su - arch"
echo "  Cleanup:  sudo incus delete -f $VM_NAME"
