#!/usr/bin/env bash
# check-prereqs.sh — friendly gate for the Incus dev VM harness.
#
# `make vm-fresh` used to die on the first `sudo incus` with a cryptic
# "command not found" when the host prerequisites were never installed.
# This gate runs before every `dev/vm` command and fails loud ONLY on
# blockers (missing incus binary); everything else is a warning naming
# the exact remediation. Never prompts for a password itself.
set -euo pipefail

warn() { printf "\033[33mWARNING: %s\033[0m\n" "$*"; }
ok() { printf "%s\n" "$*"; }

# 1. incus binary — the single hard blocker.
if ! command -v incus >/dev/null 2>&1; then
  printf "\033[31mERROR: 'incus' is not installed on this host.\033[0m\n" >&2
  printf "Run:  make dev-deps\n" >&2
  printf "then log out and back in (incus-admin group), and retry.\n" >&2
  exit 1
fi
ok "prereq: incus binary present"

# 2. Daemon reachable (passwordless path first, sudo second).
if incus info >/dev/null 2>&1; then
  ok "prereq: incus daemon reachable (no sudo needed)"
elif sudo -n incus info >/dev/null 2>&1; then
  ok "prereq: incus daemon reachable via non-interactive sudo"
else
  warn "incus daemon not reachable without a password — commands will prompt"
  warn "for sudo, or fail if sudo is unavailable. Fixes: 'sudo systemctl"
  warn "enable --now incus', or 'make dev-deps' + log out/in for incus-admin."
fi

# 3. KVM acceleration — without it the VM boots emulated (very slow).
if [ -e /dev/kvm ]; then
  ok "prereq: /dev/kvm present (hardware acceleration)"
else
  warn "/dev/kvm missing — the VM will boot without KVM acceleration (slow)."
  warn "Enable virtualization in firmware / check kvm kernel modules."
fi

# 4. Group membership — informational only; sudo remains a fallback.
if id -nG 2>/dev/null | tr ' ' '\n' | grep -qx "incus-admin"; then
  ok "prereq: user in incus-admin"
else
  warn "user is not in incus-admin — falling back to 'sudo incus'."
  warn "For passwordless use: 'make dev-deps', then log out and back in."
fi

# 5. SPICE viewer — only needed for `vm console`, advisory here.
if command -v spicy >/dev/null 2>&1 || command -v remote-viewer >/dev/null 2>&1; then
  ok "prereq: SPICE viewer present"
else
  warn "no SPICE viewer (spicy/remote-viewer) — 'vm console' needs one."
  warn "Run: 'make dev-deps'."
fi

exit 0
