#!/usr/bin/env bash
# vm-assert.sh — post-provision assertions inside the dev VM (P1).
#
# Runs after `vm-fresh` provisions (and again after the P2 reboot) and checks
# the VM actually converged: verify green, SDDM up, Hyprland session live,
# AGS instances on the bus, icons rendered, GloView loaded, Wi-Fi associated.
# Anything but Wi-Fi is FAIL (provision correctness); Wi-Fi association is
# WARN (virtual-radio flakiness is environmental, and vm-fresh already
# best-effort connects it). Prints one [PASS]/[FAIL]/[WARN] line per check
# and exits non-zero when any FAIL check fails.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VM_NAME="dotfiles-test"

PASS=0
FAIL=0
WARN=0

pass() { PASS=$((PASS + 1)); printf "[PASS] %s\n" "$*"; }
fail() { FAIL=$((FAIL + 1)); printf "\033[31m[FAIL] %s\033[0m\n" "$*"; }
warn() { WARN=$((WARN + 1)); printf "\033[33m[WARN] %s\033[0m\n" "$*"; }

# Run a command as root inside the guest.
gexec() { sudo incus exec "$VM_NAME" -- "$@"; }
# Run a command as the arch user inside the guest (single-quoted inner
# script, same pattern as vm-fresh.sh).
gexec_arch() { sudo incus exec "$VM_NAME" -- su - arch -c "$1"; }

if ! sudo incus info "$VM_NAME" 2>/dev/null | grep -q "Status: RUNNING"; then
  printf "\033[31m[FAIL] VM '%s' is not RUNNING.\033[0m\n" "$VM_NAME" >&2
  exit 1
fi

# 1. The provisioner's own hard gate, re-run read-only inside the guest.
if gexec_arch 'cd ~/dotfiles-repo-v3 && PATH="$HOME/.local/bin:$PATH" uv run --directory src/provisioning dotfiles-provision verify >/tmp/vm-verify.log 2>&1'; then
  pass "dotfiles-provision verify green inside guest"
else
  fail "dotfiles-provision verify red inside guest (see /tmp/vm-verify.log via 'vm shell')"
fi

# 2. SDDM active (first-boot login path exists).
if gexec systemctl is-active --quiet sddm; then
  pass "sddm active"
else
  fail "sddm not active"
fi

# 3. Hyprland session live.
if gexec pgrep -a Hyprland >/dev/null 2>&1; then
  pass "Hyprland session running"
else
  fail "no Hyprland process in guest"
fi

# 4. Always-on AGS instances on the bus (bar + notifications overlay).
AGS_LIST="$(gexec_arch 'XDG_RUNTIME_DIR=/run/user/$(id -u) ags list 2>/dev/null' || true)"
if printf '%s' "$AGS_LIST" | grep -qx "ags"; then
  pass "AGS bar instance running"
else
  fail "AGS bar instance missing from 'ags list'"
fi
if printf '%s' "$AGS_LIST" | grep -qx "notifications"; then
  pass "AGS notifications instance running"
else
  fail "AGS notifications instance missing from 'ags list'"
fi

# 5. Rendered icons present for the live wallpaper.
if gexec_arch 'test -n "$(ls /home/arch/.local/state/dotfiles/current/icons/ 2>/dev/null)"'; then
  pass "current/icons populated"
else
  fail "current/icons empty or missing in guest"
fi

# 6. GloView plugin loaded (needs the Hyprland IPC signature of the live
# session; missing signature dir means no IPC to check against).
SIG_DIR="$(gexec_arch 'ls -d /run/user/$(id -u)/hypr/* 2>/dev/null | head -1' || true)"
if [ -n "$SIG_DIR" ] && gexec_arch "HYPRLAND_INSTANCE_SIGNATURE=\$(basename '$SIG_DIR') hyprctl plugin list 2>/dev/null | grep -qi gloview"; then
  pass "GloView plugin loaded"
else
  fail "GloView not in 'hyprctl plugin list'"
fi

# 7. Wi-Fi associated to the virtual AP (best-effort by design: WARN only).
if gexec nmcli -t -f DEVICE,TYPE,STATE dev 2>/dev/null | grep -q "^wlan0:wifi:connected"; then
  pass "wlan0 connected to virtual AP"
else
  warn "wlan0 not connected (environmental; associate via the bar or nmcli)"
fi

printf -- "---- vm-assert: %d passed, %d failed, %d warnings ----\n" "$PASS" "$FAIL" "$WARN"
[ "$FAIL" -eq 0 ]
