#!/usr/bin/env bash
# Provision the running dotfiles dev VM end-to-end over SSH.
#
# Assumes the VM was started with run-vm.sh (repo shared at /repo).
# SSH port must match run-vm.sh's chosen port: set SSHPORT (default 2222).
# Runs the REAL toolchain setup + full `dotfiles-provision bootstrap` + verify,
# then reports the key results (AGS bar, SDDM, palette).
set -euo pipefail

VMDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KEY="$VMDIR/.images/id_vm"
PORT="${SSHPORT:-${PORT:-2222}}"
U=arch

run() { ssh -i "$KEY" -p "$PORT" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=5 "$U@localhost" "$@"; }

echo "== wait for SSH (banner exchange may take minutes on slow first boot) =="
SSH_UP=0
for i in $(seq 1 120); do   # up to ~8 min (2x120s)
  if run true 2>&1; then
    SSH_UP=1
    echo "SSH_UP (after ${i}x2s)"
    break
  fi
  # show the actual error once so a real problem isn't masked
  [ "$i" = 120 ] && { echo "SSH never came up — last error:"; run true 2>&1 | tail -5; exit 1; }
  sleep 2
done

echo "== mount the shared repo (9p) at /repo =="
run "sudo mkdir -p /repo && sudo mount -t 9p -o trans=virtio,version=9p2000.L,ro repo /repo 2>/dev/null || echo '(already mounted or mount failed)'"
run "test -d /repo/src/provisioning && echo REPO_MOUNTED || echo REPO_NOT_MOUNTED"

echo "== install toolchain =="
run "sudo pacman -Syu --noconfirm --needed >/tmp/up.log 2>&1 && sudo pacman -S --noconfirm --needed uv git base-devel python python-pip >/tmp/tool.log 2>&1 && echo TOOLCHAIN_OK || { echo TOOLCHAIN_FAIL; tail -20 /tmp/tool.log; }"

echo "== install ansible collections =="
run "export HOME=/home/$U; cd /repo/src/provisioning; uv run ansible-galaxy collection install -r ansible/requirements.yml >/tmp/gal.log 2>&1 && echo GALAXY_OK || { echo GALAXY_FAIL; tail -15 /tmp/gal.log; }"

echo "== full provisioning (bootstrap) — this is the real fresh-machine test =="
run "export HOME=/home/$U XDG_DATA_HOME=/home/$U/.local/share XDG_CONFIG_HOME=/home/$U/.config XDG_STATE_HOME=/home/$U/.local/state XDG_CACHE_HOME=/home/$U/.cache; cd /repo/src/provisioning; uv run dotfiles-provision bootstrap > /tmp/bs.log 2>&1; echo BOOTSTRAP_RC=\$?"

echo "== verify =="
run "export HOME=/home/$U; cd /repo/src/provisioning; uv run dotfiles-provision verify > /tmp/vr.log 2>&1; echo VERIFY_RC=\$?"

echo "== key results =="
run '
echo "--- bootstrap ---"; grep -oE "bootstrap (succeeded|failed)" /tmp/bs.log | head -1 || head -1 /tmp/bs.log
echo "--- AGS bar ---"; command -v ags && ags --version | head -1
echo "--- ~/.config/ags symlink ---"; ls -la /home/'$U'/.config/ags 2>&1 | head -2
echo "--- colors.css (palette fragment) ---"; test -f /home/'$U'/.local/share/dotfiles/config/ags/colors.css && echo COLORS_CSS_PRESENT || echo COLORS_CSS_MISSING
echo "--- SDDM ---"; command -v sddm && sddm --version | head -1
echo "--- SDDM enabled? ---"; systemctl is-enabled sddm 2>&1
echo "--- pixie theme ---"; test -d /usr/share/sddm/themes/pixie && echo PIXIE_PRESENT || echo PIXIE_MISSING
echo "--- verify ---"; tail -3 /tmp/vr.log
'
echo "== done. See the VM window for the SDDM greeter (after reboot). =="
