#!/usr/bin/env bash
# Boot the dotfiles DEV VM in a visible window, with the repo shared into it.
#
# What it does:
#   - Ensures host prereqs (qemu, cloud-localds). If missing, auto-suggest install.sh.
#   - Downloads the official Arch cloud image once (cached under dev/.images/).
#   - Creates a working disk copy + a cloud-init seed (SSH key, `arch` user, sudo).
#   - Boots a lightweight VM, GRAPHICAL window, KVM-accelerated.
#   - Shares the live repo read-only into the VM at /repo via virtio-9p,
#     so any host edit is immediately visible in the VM (no copying).
#
# After boot, to provision (in another terminal):
#   bash dev/provision-in-vm.sh   (SSHPORT must match; run-vm prints it)
# and/or SSH in:  ssh -i dev/.images/id_vm -p "$SSHPORT" arch@localhost
set -euo pipefail

VMDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$VMDIR/.." && pwd)"
WORKDIR="$VMDIR/.images"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

IMG_URL="https://lug.mtu.edu/archlinux/images/latest/Arch-Linux-x86_64-cloudimg.qcow2"
IMG="arch-cloud.qcow2"
DISK="working.qcow2"

# Login password for the VM's `arch` user (greeter/console). Dev-only secret —
# plaintext is fine here; override with VMPASSWORD for a different one.
VMPASSWORD="${VMPASSWORD:-arch}"

# Pick the SSH host port; bump until free to avoid colliding with a previous VM.
SSHPORT="${SSHPORT:-2222}"
while ss -ltn | grep -q ":$SSHPORT "; do
  echo "!! port $SSHPORT already in use, bumping"
  SSHPORT=$((SSHPORT + 1))
done

# 1. Prereqs
if ! command -v qemu-system-x86_64 >/dev/null || ! command -v cloud-localds >/dev/null; then
  echo "!! Missing QEMU or cloud-localds. Run: bash $VMDIR/install.sh"
  exit 1
fi

# 2. Download the cloud image once. A partial/interrupted download silently
#    yields a broken qcow2 that churns 100% CPU at boot with no SSH — reject
#    anything implausibly small (real image is hundreds of MB) and retry.
MIN_IMG_SIZE=$((200 * 1024 * 1024))
download() {
  echo "== Downloading fresh Arch cloud image (once) =="
  curl -fsSL -o "$IMG" "$IMG_URL"
  local size
  size=$(stat -c%s "$IMG")
  if [ "$size" -lt "$MIN_IMG_SIZE" ]; then
    echo "!! truncated download ($size bytes); removing — will retry"
    rm -f "$IMG"
    return 1
  fi
  echo "OK ($size bytes)"
}
while [ ! -f "$IMG" ] || [ "$(stat -c%s "$IMG")" -lt "$MIN_IMG_SIZE" ]; do
  download || { echo "download succeeded but failed size check (again)."; exit 1; }
done

# 3. Working disk copy (never mutate the base download)
if [ ! -f "$DISK" ]; then
  cp "$IMG" "$DISK"
  qemu-img resize "$DISK" 20G
fi

# 4. SSH key + cloud-init seed
if [ ! -f id_vm ]; then
  ssh-keygen -t ed25519 -N "" -f id_vm -q
fi
if [ ! -f seed.iso ]; then
  cat > seed.yaml <<EOF
#cloud-config
hostname: arch-vm
users:
  - name: arch
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - $(cat id_vm.pub)
chpasswd:
  expire: false
  list: |
    arch:$VMPASSWORD
ssh_pwauth: true
EOF
  cloud-localds seed.iso seed.yaml
fi

# 5. Boot a visible VM with the live repo shared read-only at /repo.
#    -display gtk  -> native window (Wayland/X). For headless use -vnc :1 instead.
#    virtio-9p     -> share $REPO_ROOT into the guest at /repo (read-only, live).
#    $SSHPORT:22   -> SSH port-forward (chosen free port).
echo "== Booting dotfiles dev VM (visible window) =="
echo "   repo shared read-only into the VM at /repo"
echo "   SSH: ssh -i $WORKDIR/id_vm -p $SSHPORT arch@localhost"
echo "   greeter/console login: arch / $VMPASSWORD"
echo "   To provision (must match port): SSHPORT=$SSHPORT bash $VMDIR/provision-in-vm.sh"

# Optional debug: capture the guest boot/serial log to .images/console.log
QEMU_ARG_EXTRA="-display gtk"   # default: visible window
if [ "${DEBUG:-0}" = "1" ]; then
  QEMU_ARG_EXTRA="-serial file:$WORKDIR/console.log -display none"
  echo "   DEBUG=1: serial boot log -> $WORKDIR/console.log (no window)"
fi

exec qemu-system-x86_64 \
  ${QEMU_ARG_EXTRA:-} \
  -machine accel=kvm -cpu host -smp 2 -m 4096 \
  -drive file="$DISK",if=virtio,format=qcow2 \
  -drive file=seed.iso,if=ide,media=cdrom,readonly=on \
  -netdev user,id=n0,hostfwd=tcp::$SSHPORT-:22 -device virtio-net-pci,netdev=n0 \
  -device virtio-vga -vga virtio -usb -device usb-tablet \
  -virtfs local,path="$REPO_ROOT",mount_tag=repo,security_model=none,readonly=on \
  -device virtio-9p-pci,fsdev=repo,mount_tag=repo
