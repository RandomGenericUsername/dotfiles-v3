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
#   1. uv preseed     — pinned release tarball, sha256-verified, if absent
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
# fails loud EARLY if no USABLE engine exists — a presence-only probe would let
# a stopped docker daemon through and die ~40 minutes in. Usability is probed
# via `engine info` (bounded by a 15s timeout); BOOTSTRAP_CONTAINER_ENGINE may
# pin an override. Install podman (preferred) or docker, then re-run. This
# script NEVER installs an engine: a distro-specific install here would violate
# NFR-3.
# ─────────────────────────────────────────────────────────────────────────

# ROOT derives from the script's own location (BASH_SOURCE), never from the
# git top-level — the script must work even if the checkout isn't a git
# worktree or that command fails. Symlinked invocations are resolved to the
# REAL path first (readlink -f, with a fallback) so a symlink into
# ~/.local/bin cannot point ROOT at the wrong tree.
SCRIPT_SOURCE="${BASH_SOURCE[0]}"
if command -v readlink >/dev/null 2>&1; then
  SCRIPT_SOURCE="$(readlink -f "$SCRIPT_SOURCE" 2>/dev/null || printf '%s' "$SCRIPT_SOURCE")"
fi
ROOT="$(cd "$(dirname "$SCRIPT_SOURCE")/.." && pwd)"

PROVISION_DIR="$ROOT/src/provisioning"
REQUIREMENTS_YML="$PROVISION_DIR/ansible/requirements.yml"

# ANSI color helpers strip escape codes when stdout is not a TTY (piped or
# redirected) so `| tee` logs stay clean and machine-parseable.
red()   { if [ -t 1 ]; then printf "\033[31m%s\033[0m\n" "$*"; else printf "%s\n" "$*"; fi; }
green() { if [ -t 1 ]; then printf "\033[32m%s\033[0m\n" "$*"; else printf "%s\n" "$*"; fi; }
bold()  { if [ -t 1 ]; then printf "\033[1m%s\033[0m\n" "$*"; else printf "%s\n" "$*"; fi; }

# Temp files from the uv preseed / collections stages are removed on exit no
# matter the failure path. Guards keep `set -u` happy and exit codes intact.
tmp_tarball=""
galaxy_log=""
cleanup() {
  if [ -n "$tmp_tarball" ]; then rm -f "$tmp_tarball"; fi
  if [ -n "$galaxy_log" ]; then rm -f "$galaxy_log"; fi
  return 0
}
trap cleanup EXIT

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

# ── Preflight: HOME must be set ─────────────────────────────────────────
# Cron/systemd/sudo -H contexts can run with no $HOME — without a guard the
# set -u abort (or a `/.local/bin` PATH pollution) follows. Abort early with
# a helpful message instead of a cryptic unbound-variable error.
if [ -z "${HOME:-}" ]; then
  red "ERROR: \$HOME is unset — cannot determine the user home (cron/systemd/"
  red "sudo -H contexts). Run $0 with HOME set, then re-run."
  exit 1
fi

# ── Preflight: non-root ─────────────────────────────────────────────────
# `sudo ./scripts/bootstrap.sh` is a natural fresh-machine reflex, but a root
# run provisions /root — and verify can pass green against the wrong home (the
# cli_tools role explicitly warns a root run makes AC 3 silently false). The
# packages role escalates via become, so a normal user run is all that is
# needed.
if [ "$(id -u)" -eq 0 ]; then
  red "ERROR: running as root (EUID 0) would provision /root — the wrong home."
  red "Run $0 as a regular user; the packages role escalates via become when needed."
  exit 1
fi

# ── Preflight: container engine (LOCKED Option A, 2026-08-13) ────────────
# Fail loud BEFORE the long aggregate run if no USABLE engine is available.
# The operator may pin one via BOOTSTRAP_CONTAINER_ENGINE (env override) —
# useful when a working engine lives off-PATH or the user wants to force one
# the roles' runtime detection would not pick (mirror of
# cli_tools_container_engine_override). Usability is probed with `engine info`
# (bounded by a 15s timeout): a presence-only `command -v` gate would let a
# stopped docker daemon through and die ~40 minutes in — exactly what this
# gate exists to prevent. We do NOT install an engine (distro-specific install
# would violate NFR-3) and do NOT silently proceed (the aggregate would fail
# deep in cli_tools/default_palette with an opaque engine error). No engine
# name is stored as a script variable — the roles re-detect at runtime and
# must not diverge from a second source of truth.
engine_usable() {
  local bin="$1"
  command -v "$bin" >/dev/null 2>&1 || return 1
  if command -v timeout >/dev/null 2>&1; then
    timeout 15 "$bin" info >/dev/null 2>&1
  else
    "$bin" info >/dev/null 2>&1
  fi
}

if [ -n "${BOOTSTRAP_CONTAINER_ENGINE:-}" ]; then
  if engine_usable "$BOOTSTRAP_CONTAINER_ENGINE"; then
    green "container engine detected: ${BOOTSTRAP_CONTAINER_ENGINE} (BOOTSTRAP_CONTAINER_ENGINE override)"
  else
    red "ERROR: BOOTSTRAP_CONTAINER_ENGINE is set to '${BOOTSTRAP_CONTAINER_ENGINE}'"
    if command -v "$BOOTSTRAP_CONTAINER_ENGINE" >/dev/null 2>&1; then
      red "but '${BOOTSTRAP_CONTAINER_ENGINE} info' failed — the engine is present but not usable (daemon down?)."
    else
      red "but no such command is on PATH."
    fi
    red "Unset it or fix the value, then re-run $0."
    exit 1
  fi
elif engine_usable podman; then
  green "container engine detected: podman"
elif engine_usable docker; then
  green "container engine detected: docker"
else
  red "ERROR: no container engine available on this host."
  red "  - neither podman nor docker is on PATH, or the engine's 'info'"
  red "    probe failed (e.g. the docker daemon is not running)"
  red "The container-mode chain requires podman OR docker at runtime:"
  red "  - cli_tools builds the csg image via 'csg install'"
  red "  - default_palette runs 'csg generate' in container mode"
  red "Neither role installs an engine. Install podman (preferred) or docker,"
  red "start its daemon, then re-run $0."
  exit 1
fi

# ── Stage 1: uv preseed (AC 1) ───────────────────────────────────────────
# Install uv ONLY if absent, from a PINNED release (NFR-9 reproducibility):
#   - UV_VERSION is pinned to a specific release
#   - the release tarball is fetched to a temp file and verified before
#     extraction — unverified remote bytes are never piped to a shell
#   - the pinned SHA-256 is verified against the committed value BEFORE any
#     byte from the tarball executes
#   - after extraction, `uv --version` must report exactly the pinned version
# The tarball lands uv/uvx in ~/.local/bin — same dir the cli_tools role's
# `uv tool install` binaries land in.
UV_VERSION="0.9.22"

if ! command -v uv >/dev/null 2>&1; then
  bold "── stage preseed: installing uv ${UV_VERSION} (pinned, sha256-verified) ──"

  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64)
      UV_TARGET="x86_64-unknown-linux-gnu"
      UV_SHA256="e170aed70ac0225feee612e855d3a57ae73c61ffb22c7e52c3fd33b87c286508"
      ;;
    Linux-aarch64)
      UV_TARGET="aarch64-unknown-linux-gnu"
      UV_SHA256="2f8716c407d5da21b8a3e8609ed358147216aaab28b96b1d6d7f48e9bcc6254e"
      ;;
    *)
      red "ERROR: unsupported platform '$(uname -s)-$(uname -m)' for the pinned uv preseed."
      red "Supported: Linux x86_64 / Linux aarch64. Install uv yourself, then re-run $0."
      exit 1
      ;;
  esac

  tmp_tarball="$(mktemp)"
  url="https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${UV_TARGET}.tar.gz"

  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --connect-timeout 10 --max-time 300 "$url" -o "$tmp_tarball" \
      || stage_failed "preseed (uv download)" "$?"
  elif command -v wget >/dev/null 2>&1; then
    wget --timeout=300 --tries=1 -qO "$tmp_tarball" "$url" \
      || stage_failed "preseed (uv download)" "$?"
  else
    red "ERROR: neither curl nor wget is available to fetch the uv release."
    red "Install curl or wget, or install uv yourself, then re-run $0."
    exit 1
  fi

  # Verify the pinned SHA-256 BEFORE anything from the tarball executes.
  echo "${UV_SHA256}  ${tmp_tarball}" | sha256sum -c - >/dev/null \
    || stage_failed "preseed (uv checksum)" "$?"

  mkdir -p "$HOME/.local/bin"
  tar -xzf "$tmp_tarball" -C "$HOME/.local/bin" --strip-components=1 \
    "uv-${UV_TARGET}/uv" "uv-${UV_TARGET}/uvx" \
    || stage_failed "preseed (uv extract)" "$?"
  chmod +x "$HOME/.local/bin/uv" "$HOME/.local/bin/uvx"

  # Behavioral assertion: the installed binary must be the pinned release.
  [ "$("$HOME/.local/bin/uv" --version)" = "uv ${UV_VERSION}" ] \
    || stage_failed "preseed (uv version assert)" 1
fi
export PATH="$HOME/.local/bin:$PATH"

# Behavioral assertion that the preseed actually landed on PATH — the standalone
# installer can honor XDG_BIN_HOME/UV_INSTALL_DIR and land elsewhere, and a
# partial/zero-byte install must not be misattributed to a later network
# failure in the collections stage.
command -v uv >/dev/null 2>&1 || stage_failed "preseed (uv verify)" 127

# uv owns Python provisioning: `uv run` downloads a managed interpreter
# satisfying requires-python >=3.12 when none exists. Informational only.
echo "uv: $(command -v uv) — uv will manage the Python interpreter as needed."

# ── Stage 2: Ansible collection resolution (AC 2) ────────────────────────
# Runs through the project env so ansible-galaxy (ships with ansible-core)
# is available. Collections install to ~/.ansible/collections by default —
# the default collections_paths resolves them.
bold "── stage collections: resolving ansible collections ──"
galaxy_log="$(mktemp)"
galaxy_rc=0
# `cmd || galaxy_rc=$?` preserves the TRUE exit code (an `if ! cmd` form would
# report 0 inside the then-block) while keeping `set -e` from aborting first.
uv run --directory "$PROVISION_DIR" ansible-galaxy collection install -r "$REQUIREMENTS_YML" \
  2>"$galaxy_log" || galaxy_rc=$?
if [ "$galaxy_rc" -ne 0 ]; then
  red "ERROR: ansible collection resolution FAILED (exit code ${galaxy_rc})."
  red "Requirements file: ${REQUIREMENTS_YML}"
  if [ -s "$galaxy_log" ]; then
    red "ansible-galaxy output (verbatim):"
    sed 's/^/  /' "$galaxy_log"
  fi
  red "Possible causes:"
  red "  - no network access — collections cannot be resolved"
  red "  - uv environment sync failed (uv.lock conflict, broken uv)"
  red "  - unwritable ~/.ansible, or pre-existing conflicting collections"
  red "The provisioner will NOT run with missing modules. Fix the cause, then re-run $0."
  exit "$galaxy_rc"
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
