#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────
# bootstrap.sh — CAP-4 fresh-machine entry point (Story 3.1)
#
# Provisions a fresh machine in ONE command:
#
#   git clone <repo>
#   ./scripts/bootstrap.sh
#
# Stage order (CAP-4 flow, plan §3):
#   1. uv preseed     — standalone installer if absent; ~/.local/bin on PATH
#   2. collections    — ansible-galaxy collection install -r (loud abort)
#   3. bootstrap      — uv run dotfiles-provision bootstrap (aggregate, Story 2.12)
#   4. verify         — uv run dotfiles-provision verify (hard gate, all ten criteria)
#
#   → exit 0 only if every stage succeeded
#
# The chicken-and-egg this solves (plan §3 "Bootstrap"): uv pre-seeds Python
# AND uv itself (uv downloads a managed interpreter satisfying
# requires-python >=3.12 when none exists), which makes the provisioner
# (ansible-core runtime) runnable; collections are resolved at bootstrap start
# so a missing module aborts loudly instead of failing deep in the run.
#
# NFR-3 INVARIANT: NO distro branching in this script. Distro differences
# live ONLY in ansible/group_vars. Do not add any distro logic here.
#
# CONTAINER ENGINE (LOCKED decision 2026-08-13, Option A): the container-mode
# chain (cli_tools builds the csg image; default_palette runs csg generate)
# needs podman OR docker at runtime. Neither role installs one, so this script
# fails loud EARLY if no engine is on PATH — before the long aggregate run.
# Install podman (preferred) or docker, then re-run. This script NEVER installs
# an engine: a distro-specific install here would violate NFR-3.
# ─────────────────────────────────────────────────────────────────────────

# ROOT derives from the script's own location (BASH_SOURCE), never from the
# git top-level — the script must work even if the checkout isn't a git
# worktree or that command fails.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PROVISION_DIR="$ROOT/src/provisioning"
REQUIREMENTS_YML="$PROVISION_DIR/ansible/requirements.yml"

red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
bold()  { printf "\033[1m%s\033[0m\n" "$*"; }

stage_failed() {
  local stage="$1" code="$2"
  red "ERROR: bootstrap stage '${stage}' failed (exit code ${code})."
  red "The machine was NOT fully provisioned. Fix the issue and re-run $0."
  exit "$code"
}

run_stage() {
  local stage="$1"
  shift
  bold "── stage ${stage} ──"
  "$@" || stage_failed "$stage" "$?"
}

# ── Preflight: container engine (LOCKED Option A, 2026-08-13) ────────────
# Fail loud BEFORE the long aggregate run if neither engine is on PATH. We do
# NOT install one (distro-specific install would violate NFR-3) and do NOT
# silently proceed (the aggregate would fail deep in cli_tools/default_palette
# with an opaque engine error).
if command -v podman >/dev/null 2>&1; then
  CONTAINER_ENGINE="podman"
elif command -v docker >/dev/null 2>&1; then
  CONTAINER_ENGINE="docker"
else
  red "ERROR: no container engine found on PATH."
  red "The container-mode chain requires podman OR docker at runtime:"
  red "  - cli_tools builds the csg image via 'csg install'"
  red "  - default_palette runs 'csg generate' in container mode"
  red "Neither role installs an engine. Install podman (preferred) or docker,"
  red "then re-run $0."
  exit 1
fi
green "container engine detected: ${CONTAINER_ENGINE}"

# ── Stage 1: uv preseed (AC 1) ───────────────────────────────────────────
# Install uv via the official standalone installer only if absent. The
# installer places uv/uvx in ~/.local/bin — same dir the cli_tools role's
# `uv tool install` binaries land in.
if ! command -v uv >/dev/null 2>&1; then
  bold "── stage preseed: installing uv via the standalone installer ──"
  if command -v curl >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh \
      || stage_failed "preseed (uv installer)" "$?"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO- https://astral.sh/uv/install.sh | sh \
      || stage_failed "preseed (uv installer)" "$?"
  else
    red "ERROR: neither curl nor wget is available to fetch the uv installer."
    red "Install curl or wget, or install uv yourself, then re-run $0."
    exit 1
  fi
fi
export PATH="$HOME/.local/bin:$PATH"

# uv owns Python provisioning: `uv run` downloads a managed interpreter
# satisfying requires-python >=3.12 when none exists. Informational only.
echo "uv: $(command -v uv) — uv will manage the Python interpreter as needed."

# ── Stage 2: Ansible collection resolution (AC 2) ────────────────────────
# Runs through the project env so ansible-galaxy (ships with ansible-core)
# is available. Collections install to ~/.ansible/collections by default —
# the default collections_paths resolves them.
bold "── stage collections: resolving ansible collections ──"
if ! uv run --directory "$PROVISION_DIR" ansible-galaxy collection install -r "$REQUIREMENTS_YML"; then
  red "ERROR: ansible collection resolution FAILED (exit code ${?})."
  red "Requirements file: ${REQUIREMENTS_YML}"
  red "Likely cause: no network access — collections cannot be resolved, and the"
  red "provisioner will NOT run with missing modules. Fix the network and re-run $0."
  exit 1
fi

# ── Stage 3: aggregate bootstrap (AC 3) ──────────────────────────────────
# The aggregate bootstrap.yaml (Story 2.12) runs the whole chain:
# packages → cli_tools → filesystem → assets → default_palette →
# compositor_configs → config_copies → settings → verify. BootstrapUseCase
# passes the install_dir + os_family seam extra-vars.
run_stage "bootstrap" uv run --directory "$PROVISION_DIR" dotfiles-provision bootstrap

# ── Stage 4: verify hard gate (AC 4) ─────────────────────────────────────
# The aggregate's internal verify import is plan-gated (check mode); this
# explicit trailing verify is a REAL check (VerifyCapabilityUseCase runs with
# check=False) asserting all ten done-criteria — the CAP-4 success signal.
run_stage "verify" uv run --directory "$PROVISION_DIR" dotfiles-provision verify

green "Bootstrap complete: uv preseed → collections → bootstrap → verify all green."
