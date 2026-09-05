#!/usr/bin/env bash
# vm-continue.sh — Resume existing Incus VM.
set -euo pipefail

VM_NAME="dotfiles-test"

if ! incus info "$VM_NAME" >/dev/null 2>&1; then
  echo "VM '$VM_NAME' does not exist. Run ./vm-fresh.sh first."
  exit 1
fi

echo "== vm-continue: starting VM =="
incus start "$VM_NAME" 2>/dev/null || true
sleep 3

echo "== vm-continue: opening graphical console =="
exec incus console "$VM_NAME" --type=vga
