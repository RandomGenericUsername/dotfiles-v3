#!/usr/bin/env bash
# vm-session-loop.sh — deterministic repro of SDDM's waitForStarted timeout.
#
# OPTIONAL, sudo required, and only meant for a VM created by `make vm-fresh`.
# It temporarily installs a Wayland session entry whose Exec sleeps 40 s before
# starting the real Hyprland session, points SDDM autologin at it (Relogin=true),
# and restarts SDDM.  SDDM's 30 s waitForStarted timeout must then log
# `Session started false`, and the session helper must be torn down ~60 s later
# with `Auth: sddm-helper exited with 2`.
#
# The previous autologin config and all repro files are restored on exit, even
# on Ctrl-C, so the VM is never left in the repro state.  Do not run this
# against the host.
#
# Exit: 0 PASS or documented SKIP (no KMS/Wayland display server), 1 assertion
# failure, 2 environment/usage error.
set -euo pipefail

VM_NAME="dotfiles-test"

REPRO_DESKTOP="/usr/share/wayland-sessions/repro-delay.desktop"
REPRO_EXEC="/usr/local/bin/dotfiles-vm-repro-delay"
AUTOLOGIN="/etc/sddm.conf.d/90-dotfiles-vm-autologin.conf"
BACKUP="/tmp/dotfiles-vm-session-loop-autologin.bak"
WAIT_SECONDS="${WAIT_SECONDS:-150}"

red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
warn()  { printf "\033[33m%s\033[0m\n" "$*"; }

gexec() { sudo incus exec "$VM_NAME" -- "$@"; }
gexec_sh() { sudo incus exec "$VM_NAME" -- bash -c "$1"; }

CLEANUP_ARMED=0
cleanup() {
  [ "$CLEANUP_ARMED" -eq 1 ] || return 0
  CLEANUP_ARMED=0
  # Idempotent: restore the autologin drop-in (or remove it if there was none),
  # remove the repro entry/script, and bring the normal session back.
  gexec_sh "
    rm -f '$REPRO_DESKTOP' '$REPRO_EXEC'
    if [ -f '$BACKUP' ]; then
      mv '$BACKUP' '$AUTOLOGIN'
    else
      rm -f '$AUTOLOGIN'
    fi
    systemctl restart sddm >/dev/null 2>&1 || true
  " >/dev/null 2>&1 || true
}

trap cleanup EXIT
trap 'exit 130' INT TERM

# Authenticate once up front: the script makes many sudo/incus calls.
if ! sudo -v; then
  red "ERROR: sudo authentication failed."
  exit 2
fi

if ! sudo incus info "$VM_NAME" >/dev/null 2>&1; then
  red "VM '$VM_NAME' does not exist. Run 'make vm-fresh' first (sudo required)."
  exit 2
fi
if ! sudo incus info "$VM_NAME" 2>/dev/null | grep -q "Status: RUNNING"; then
  red "VM '$VM_NAME' is not RUNNING. Run 'make vm-up' first."
  exit 2
fi
if ! gexec test -f /usr/share/wayland-sessions/hyprland-uwsm.desktop; then
  red "real hyprland-uwsm.desktop session missing in guest; run 'make vm-fresh'."
  exit 2
fi

echo "== vm-session-loop: installing temporary delayed session =="
CLEANUP_ARMED=1
# Back up the fresh-VM autologin drop-in once (remove any stale backup first).
gexec_sh "rm -f '$BACKUP'; [ ! -f '$AUTOLOGIN' ] || cp '$AUTOLOGIN' '$BACKUP'"

cat <<'REPRO_EXEC_SCRIPT' | gexec tee "$REPRO_EXEC" >/dev/null
#!/bin/sh
# Temporary repro entry: SDDM waits 30 s for the session to signal readiness;
# sleeping 40 s before exec guarantees waitForStarted times out.
sleep 40
exec uwsm start -e -D Hyprland hyprland.desktop
REPRO_EXEC_SCRIPT
gexec chmod 0755 "$REPRO_EXEC"

cat <<'REPRO_DESKTOP_FILE' | gexec tee "$REPRO_DESKTOP" >/dev/null
[Desktop Entry]
Name=Repro delay (40 s)
Comment=Temporary SDDM waitForStarted timeout repro
Exec=/usr/local/bin/dotfiles-vm-repro-delay
TryExec=uwsm
Type=Application
DesktopNames=Hyprland
REPRO_DESKTOP_FILE

# Point autologin at the delayed entry. Relogin=true keeps the loop going until
# cleanup restores the original config.
cat <<'REPRO_AUTOLOGIN' | gexec tee "$AUTOLOGIN" >/dev/null
[Autologin]
User=arch
Session=repro-delay.desktop
Relogin=true
REPRO_AUTOLOGIN

START_EPOCH="$(gexec date +%s | tr -d '\r')"
echo "== vm-session-loop: restarting SDDM (window since @$START_EPOCH) =="
gexec systemctl restart sddm

echo "== vm-session-loop: waiting up to ${WAIT_SECONDS}s for the timeout chain =="
LOG=""
FALSE_TS=""
HELPER_TS=""
for _ in $(seq 1 "$WAIT_SECONDS"); do
  LOG="$(gexec journalctl -u sddm --boot 0 --since "@$START_EPOCH" --no-pager --output=short-iso 2>/dev/null || true)"
  FALSE_TS="$(printf '%s\n' "$LOG" | grep -m1 'Session started false' | awk '{print $1}' || true)"
  HELPER_TS="$(printf '%s\n' "$LOG" | grep -m1 'Auth: sddm-helper exited with 2' | awk '{print $1}' || true)"
  if [ -n "$FALSE_TS" ] && [ -n "$HELPER_TS" ]; then
    break
  fi
  sleep 1
done

if [ -z "$FALSE_TS" ]; then
  printf '%s\n' "$LOG" | tail -n 40 || true
  if printf '%s\n' "$LOG" | grep -q 'falling back to DisplayServer=x11-user'; then
    warn "[SKIP] guest fell back to DisplayServer=x11-user (no KMS/Wayland display server)."
    warn "       The fallback itself is a vm-assert failure; the timeout chain needs a"
    warn "       working Wayland greeter. Final proof: host 5-login acceptance."
    exit 0
  fi
  red "[FAIL] no 'Session started false' within ${WAIT_SECONDS}s."
  exit 1
fi

if [ -z "$HELPER_TS" ]; then
  printf '%s\n' "$LOG" | tail -n 40 || true
  red "[FAIL] saw 'Session started false' but no 'Auth: sddm-helper exited with 2'."
  exit 1
fi

FALSE_EPOCH="$(date -d "$FALSE_TS" +%s)"
HELPER_EPOCH="$(date -d "$HELPER_TS" +%s)"
TEARDOWN_DELAY=$((HELPER_EPOCH - FALSE_EPOCH))

printf '  timeout:  %s\n' "$FALSE_TS"
printf '  teardown: %s  (delta %ss)\n' "$HELPER_TS" "$TEARDOWN_DELAY"

if [ "$TEARDOWN_DELAY" -lt 45 ] || [ "$TEARDOWN_DELAY" -gt 75 ]; then
  red "[FAIL] teardown was ${TEARDOWN_DELAY}s after 'Session started false'; expected ~60s."
  exit 1
fi

green "[PASS] SDDM timed out after ~30s ('Session started false') and tore the session down ${TEARDOWN_DELAY}s later (exit 2)."
green "       Cleaning up the temporary session/autologin now."
exit 0
