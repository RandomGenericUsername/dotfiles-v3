#!/usr/bin/env bash
# vm-fresh.sh — Incus-based clean slate: fresh VM, full provision, ready to test.
#   --clean : wipe existing VM and start fresh
#   (no arg): reuse existing VM if present, only provision if not yet provisioned
set -euo pipefail

VM_NAME="dotfiles-test"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

  # Configure networkd for DHCPv4 (primary). Write a persistent .network file
  # so the config survives reboot — a live \`ip addr add\` is lost on the next boot.
  cat > /etc/systemd/network/enp5s0.network << 'NETCONF'
[Match]
Name=enp5s0

[Network]
DHCP=yes
IPv6AcceptRA=yes
NETCONF

  systemctl restart systemd-networkd
  sleep 5

  # If DHCP failed to grant a lease, fall back to a PERSISTENT static config
  # (same NAT subnet the incus bridge serves) so the VM has working networking
  # on every boot, not just this provisioning run.
  if ! ip -4 addr show enp5s0 | grep -q 'scope global'; then
    echo 'DHCP failed, assigning static config persistently...'
    cat > /etc/systemd/network/enp5s0.network << 'NETCONF'
[Match]
Name=enp5s0

[Network]
Address=10.27.121.100/24
Gateway=10.27.121.1
DNS=8.8.8.8
IPv6AcceptRA=yes
NETCONF
    systemctl restart systemd-networkd
    sleep 5
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

  # Virtual Wi-Fi radios (mac80211_hwsim): the VM has no physical wireless NIC
  # (virtio ethernet only), so astal-network/NetworkManager would always report
  # ethernet and the AGS bar could never show Wi-Fi state. Loading the kernel
  # module creates two software 802.11 radios (wlan0/wlan1 + p2p-dev-*), which
  # NetworkManager detects as genuine \`wifi\` devices. Persist the load across
  # reboots via modules-load.d (modprobe now + file for next boot) and install
  # iw so the radios are scannable/connectable in the guest (installed in the
  # packages step below after repo refresh).
  modprobe mac80211_hwsim
  echo 'mac80211_hwsim' > /etc/modules-load.d/dotfiles-vm-wifi.conf

  # 2. Packages
  printf 'Server = https://mirror.rackspace.com/archlinux/\$repo/os/\$arch\nServer = https://geo.mirror.pkgbuild.com/\$repo/os/\$arch\n' > /etc/pacman.d/mirrorlist
  pacman -Syu --noconfirm
  pacman -S --noconfirm git base-devel sudo podman iw hostapd dnsmasq

  # 3. Virtual AP (hostapd on wlan1) so wlan0 can associate and the bar shows a
  #    real connected SSID. WPA2 network "DotfilesHome" served on 192.168.50.x
  #    with DHCP (dnsmasq) + NAT out enp5s0 (the NAT uplink). A systemd unit
  #    brings it up on every boot, not just this provisioning run.
  cat > /etc/hostapd/hostapd-vm.conf << 'APCONF'
interface=wlan1
driver=nl80211
ssid=DotfilesHome
hw_mode=g
channel=6
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=testtest
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
APCONF

  sed -i 's|^#conf-dir=/etc/dnsmasq.d|conf-dir=/etc/dnsmasq.d|' /etc/dnsmasq.conf
  mkdir -p /etc/dnsmasq.d
  cat > /etc/dnsmasq.d/vm-ap.conf << 'APDHCP'
interface=wlan1
bind-interfaces
dhcp-range=192.168.50.100,192.168.50.200,12h
dhcp-option=option:router,192.168.50.1
dhcp-option=option:dns-server,8.8.8.8
APDHCP

  cat > /usr/local/sbin/dotfiles-vm-ap.sh << 'APSCRIPT'
#!/bin/bash
# Bring up the virtual Wi-Fi AP (hostapd on wlan1) + DHCP + NAT.
# Runs on boot via dotfiles-vm-ap.service. Idempotent.
set -u
modprobe mac80211_hwsim 2>/dev/null || true
ip link set wlan1 up 2>/dev/null || true
ip addr flush dev wlan1 2>/dev/null || true
ip addr add 192.168.50.1/24 dev wlan1 2>/dev/null || true
if ! pgrep -x hostapd >/dev/null 2>&1; then
  hostapd -B /etc/hostapd/hostapd-vm.conf || true
fi
systemctl start dnsmasq 2>/dev/null || true
iptables -t nat -C POSTROUTING -s 192.168.50.0/24 -o enp5s0 -j MASQUERADE 2>/dev/null \
  || iptables -t nat -A POSTROUTING -s 192.168.50.0/24 -o enp5s0 -j MASQUERADE
sysctl -w net.ipv4.ip_forward=1 >/dev/null 2>&1 || true
exit 0
APSCRIPT
  chmod +x /usr/local/sbin/dotfiles-vm-ap.sh

  cat > /etc/systemd/system/dotfiles-vm-ap.service << 'APSVC'
[Unit]
Description=Virtual Wi-Fi AP (mac80211_hwsim) for the dotfiles dev VM
After=systemd-networkd.service NetworkManager.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/dotfiles-vm-ap.sh

[Install]
WantedBy=multi-user.target
APSVC
  systemctl daemon-reload
  systemctl enable dotfiles-vm-ap.service
  systemctl start dotfiles-vm-ap.service || true

  # 4. User setup
  id arch >/dev/null 2>&1 || useradd -m -G wheel -s /bin/bash arch
  echo 'arch:arch' | chpasswd
  grep -q 'arch ALL=(ALL) NOPASSWD:ALL' /etc/sudoers || echo 'arch ALL=(ALL) NOPASSWD:ALL' >> /etc/sudoers

  # 5. Podman
  systemctl enable --now podman.socket
  loginctl enable-linger arch
  su - arch -c 'systemctl --user enable --now podman.socket 2>/dev/null || true'

  # 6. Verify
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

echo "== vm-fresh: connecting VM wifi (wlan0) to the virtual AP =="
sudo incus exec "$VM_NAME" -- bash -c '
  systemctl start dotfiles-vm-ap.service 2>/dev/null || true
  sleep 3
  ip link set wlan0 up 2>/dev/null || true
  nmcli device wifi connect DotfilesHome password testtest 2>/dev/null \
    || echo "  (wifi connect deferred — associate on first bar restart)"
'

# The plugin manager needs a live Hyprland IPC session. This VM-only SDDM
# drop-in creates that session non-interactively; normal machines retain the
# regular interactive login flow, where autostart runs gloview-activate.
echo "== vm-fresh: enabling VM autologin for Hyprland session =="
sudo incus exec "$VM_NAME" -- bash -c 'mkdir -p /etc/sddm.conf.d && cat > /etc/sddm.conf.d/90-dotfiles-vm-autologin.conf <<'"'"'AUTLOGIN'"'"'
[Autologin]
User=arch
Session=hyprland.desktop
AUTLOGIN
'

echo "== vm-fresh: starting SDDM =="
sudo incus exec "$VM_NAME" -- systemctl start sddm 2>/dev/null || true

echo "== vm-fresh: waiting for Hyprland session and GloView activation =="
for i in $(seq 1 120); do
  if sudo incus exec "$VM_NAME" -- test -f /home/arch/.local/state/dotfiles/gloview-active 2>/dev/null; then
    echo "Hyprland session active and GloView loaded"
    break
  fi
  sleep 2
  [ "$i" -eq 120 ] && {
    echo "ERROR: Hyprland/GloView activation did not complete"
    sudo incus exec "$VM_NAME" -- journalctl -u sddm --no-pager -n 80 || true
    sudo incus exec "$VM_NAME" -- su - arch -c 'pgrep -a Hyprland || true; hyprpm list 2>&1 || true'
    exit 1
  }
done

echo "== vm-fresh: provision complete. VM ready for testing =="
echo "  Console:  sudo incus console $VM_NAME --type=vga"
echo "  Shell:    sudo incus exec $VM_NAME -- su - arch"
echo "  Cleanup:  sudo incus delete -f $VM_NAME"