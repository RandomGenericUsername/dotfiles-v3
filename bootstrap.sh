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
#   3.5 gloview-sync  — one-time interactive `hyprpm update` + aggregate re-run
#                       when the GloView repo is absent (fresh machine or
#                       Hyprland upgrade); skipped when present, under --check,
#                       or without a terminal (the login activator retries then)
#   4. verify         — uv run dotfiles-provision verify (hard gate, all ten criteria)
#   + session signal  — after verify, when Hyprland IPC is reachable, report
#                       whether GloView is actually loaded (green vs DEGRADED)
#
# Usage: ./bootstrap.sh [--ask-become-pass] [--become-password=...] [--check]
# Become flags are forwarded verbatim to `dotfiles-provision bootstrap`
# (which injects ANSIBLE_SUDO_PASS for the aggregate's become play, so hosts
# without passwordless escalation can still provision interactively). With no
# become flag the script probes `sudo -n true`: passwordless hosts run
# unattended, interactive terminals are prompted automatically, and
# non-terminal runs abort loud instead of failing deep in the aggregate.
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
# chain (cli_tools builds the csg image; runtime-seed runs
# `dotfiles-runtime wallpaper set`, which generates the scheme via csg)
# needs podman OR docker at runtime. Neither role installs one, so this script
# fails loud EARLY if no USABLE engine exists — a presence-only probe would let
# a stopped docker daemon through and die ~40 minutes in. Usability is probed
# via `engine info` (bounded by a 15s timeout). Install podman (preferred) or
# docker, then re-run. This script NEVER installs an engine: a distro-specific
# install here would violate NFR-3. Engine forcing is the roles' own concern
# (cli_tools_container_engine_override; the generate-side engine lives in
# csg-settings.toml [container]),
# NOT a bootstrap.sh override — a second source of truth would let the gate and
# the roles diverge (confirmation CR 2026-08-15).
# ─────────────────────────────────────────────────────────────────────────

# ROOT derives from the script's own location (BASH_SOURCE), never from the
# git top-level — the script must work even if the checkout isn't a git
# worktree or that command fails. Symlinked invocations are resolved to the
# REAL path first (readlink -f, with a fallback) so a symlink into
# ~/.local/bin cannot point ROOT at the wrong tree. A bare invocation (script
# found via PATH, no `./` or absolute path) is resolved through the PATH
# lookup first — otherwise BASH_SOURCE[0] has no slash and dirname collapses
# to the cwd's parent instead of the repo (confirmation CR 2026-08-15).
SCRIPT_SOURCE="${BASH_SOURCE[0]}"
case "$SCRIPT_SOURCE" in
  */*) ;;
  *) SCRIPT_SOURCE="$(command -v "$SCRIPT_SOURCE" 2>/dev/null || printf '%s' "$SCRIPT_SOURCE")" ;;
esac
if command -v readlink >/dev/null 2>&1; then
  SCRIPT_SOURCE="$(readlink -f "$SCRIPT_SOURCE" 2>/dev/null || printf '%s' "$SCRIPT_SOURCE")"
fi
ROOT="$(cd "$(dirname "$SCRIPT_SOURCE")" && pwd)"

PROVISION_DIR="$ROOT/src/provisioning"
REQUIREMENTS_YML="$PROVISION_DIR/ansible/requirements.yml"

# ANSI color helpers strip escape codes when stdout is not a TTY (piped or
# redirected) so `| tee` logs stay clean and machine-parseable.
red()   { if [ -t 1 ]; then printf "\033[31m%s\033[0m\n" "$*"; else printf "%s\n" "$*"; fi; }
green() { if [ -t 1 ]; then printf "\033[32m%s\033[0m\n" "$*"; else printf "%s\n" "$*"; fi; }
bold()  { if [ -t 1 ]; then printf "\033[1m%s\033[0m\n" "$*"; else printf "%s\n" "$*"; fi; }

# Temp files from the uv preseed / collections stages are removed on exit no
# matter the failure path. Guards keep `set -u` happy and exit codes intact.
# _sudo_keepalive_pid owns the timestamp keepalive (Stage 3): killed here so
# no refresh loop outlives the run (its own `kill -0 $$` self-check is the
# backstop when the parent is gone).
tmp_tarball=""
galaxy_log=""
_sudo_keepalive_pid=""
cleanup() {
  if [ -n "$_sudo_keepalive_pid" ]; then kill "$_sudo_keepalive_pid" 2>/dev/null || true; fi
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

# ── Arg forwarding: become/check flags for the aggregate run ─────────────
# The aggregate contains a become:true play, so a host without passwordless
# escalation needs a password path. These flags are forwarded verbatim to
# `dotfiles-provision bootstrap` (which prompts for --ask-become-pass with
# hidden input and injects the secret without echo). Unknown flags abort loud
# instead of silently dropping a security-sensitive option.
BOOTSTRAP_ARGS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --ask-become-pass|--check)
      BOOTSTRAP_ARGS+=("$1")
      shift
      ;;
    --become-password=*)
      BOOTSTRAP_ARGS+=("$1")
      shift
      ;;
    --become-password)
      if [ "$#" -lt 2 ]; then
        red "ERROR: --become-password requires a value."
        exit 2
      fi
      BOOTSTRAP_ARGS+=("$1" "$2")
      shift 2
      ;;
    -h|--help)
      bold "Usage: $0 [--ask-become-pass] [--become-password=...] [--check]"
      exit 0
      ;;
    *)
      red "ERROR: unknown argument '$1'."
      red "Usage: $0 [--ask-become-pass] [--become-password=...] [--check]"
      exit 2
      ;;
  esac
done

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
# run provisions the root home — and verify can pass green against the wrong
# home (the cli_tools role explicitly warns a root run makes AC 3 silently
# false). The packages role escalates via become, so a normal user run is all
# that is needed.
if [ "$(id -u)" -eq 0 ]; then
  red "ERROR: running as root (EUID 0) would provision the root user's home — the wrong home."
  red "Run $0 as a regular user; the packages role escalates via become when needed."
  exit 1
fi

# ── Preflight: container engine (LOCKED Option A, 2026-08-13) ────────────
# Fail loud BEFORE the long aggregate run if no USABLE engine is available.
# Usability is probed with `engine info` (bounded by a 15s timeout): a
# presence-only `command -v` gate would let a stopped docker daemon through and
# die ~40 minutes in — exactly what this gate exists to prevent. We do NOT
# install an engine (distro-specific install would violate NFR-3) and do NOT
# silently proceed (the aggregate would fail deep in cli_tools/runtime-seed
# with an opaque engine error). No engine name is stored as a script variable —
# the roles re-detect at runtime via their OWN detection/override vars and must
# not diverge from a second source of truth (confirmation CR 2026-08-15).
engine_usable() {
  local bin="$1"
  command -v "$bin" >/dev/null 2>&1 || return 1
  if ! command -v timeout >/dev/null 2>&1; then
    red "WARNING: 'timeout' is not on PATH — cannot bound the engine usability"
    red "probe, so '${bin}' is treated as unusable (a hung engine must not block"
    red "the bootstrap). Install coreutils/timeout, then re-run $0."
    return 1
  fi
  timeout 15 "$bin" info >/dev/null 2>&1
}

if engine_usable podman; then
  green "container engine detected: podman"
elif engine_usable docker; then
  green "container engine detected: docker"
else
  red "ERROR: no container engine available on this host."
  red "  - neither podman nor docker is on PATH, or the engine's 'info'"
  red "    probe failed (e.g. the docker daemon is not running)"
  red "The container-mode chain requires podman OR docker at runtime:"
  red "  - cli_tools builds the csg image via 'csg install'"
  red "  - runtime-seed runs 'dotfiles-runtime wallpaper set' (csg generate) in container mode"
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

# The pinned-version guarantee (NFR-9) must also hold for a PRE-EXISTING uv —
# a stale distro-packaged uv or a stale ~/.local/bin/uv that cannot `uv run
# --directory` would otherwise skip the preseed and fail later misattributed to
# network. Warn loudly on mismatch; the freshly-installed branch already
# hard-asserts the pinned version (confirmation CR 2026-08-15).
uv_path="$(command -v uv)"
uv_version="$("$uv_path" --version 2>/dev/null || echo "unknown")"
if [ "$uv_version" != "uv ${UV_VERSION}" ]; then
  red "WARNING: uv at '${uv_path}' reports '${uv_version}' — bootstrap expects"
  red "exactly 'uv ${UV_VERSION}' (NFR-9 reproducibility). A stale uv may break"
  red "the collections/bootstrap stages; upgrade uv if they fail."
fi

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
    if command -v sed >/dev/null 2>&1; then
      sed 's/^/  /' "$galaxy_log"
    else
      # No sed on an ultra-minimal host: indent with a plain while loop so the
      # TRUE galaxy exit code still propagates (set -e must not swallow it).
      while IFS= read -r line; do printf '  %s\n' "$line"; done < "$galaxy_log"
    fi
  fi
  red "Possible causes:"
  red "  - no network access — collections cannot be resolved"
  red "  - uv environment sync failed (uv.lock conflict, broken uv)"
  red "  - unwritable ~/.ansible, or pre-existing conflicting collections"
  red "The provisioner will NOT run with missing modules. Fix the cause, then re-run $0."
  exit "$galaxy_rc"
fi

# Post-collections verification (confirmation CR 2026-08-15): the preseed stage
# got a `command -v uv` verify; the collections stage gets the same treatment.
# ansible-galaxy can exit 0 having installed NOTHING (empty/typo'd
# requirements.yml, collections landing in a non-default path) — proceeding
# would violate the "never run bootstrap with missing modules" contract and
# fail deep in the aggregate instead of at the gate.
collections_dir="$HOME/.ansible/collections/ansible_collections"
if [ ! -d "$collections_dir" ] || [ -z "$(ls -A "$collections_dir" 2>/dev/null || true)" ]; then
  red "ERROR: ansible-galaxy exited 0 but no collections were installed under"
  red "${collections_dir} — the requirements file or install path is wrong."
  red "The provisioner will NOT run with missing modules. Fix the cause, then re-run $0."
  exit 1
fi

# ── Stage 3: aggregate bootstrap (AC 3) ──────────────────────────────────
# Single password entry: `make bootstrap` takes no flags by default, so a host
# without passwordless escalation would die deep in the aggregate become
# play — and a fresh machine would then prompt THREE times (BECOME for the
# first aggregate, sudo for hyprpm's own escalation in gloview-sync, BECOME
# again for the retry). Instead this block prompts ONCE here (hidden input)
# and reuses the secret for the whole run.
#
# Design (verified live 2026-09-29 — read before touching):
# - The escalation probe runs DETACHED (setsid, stdin /dev/null): that is the
#   same no-terminal context ansible's piped become runs in, so it predicts
#   correctly. A plain terminal `sudo -n true` probe is deliberately NOT
#   trusted — on this machine a warm terminal ticket is invisible to piped
#   sudo, and trusting it failed the run deep in the aggregate with "a
#   password is required" seconds after the probe passed.
# - The secret is exported as ANSIBLE_SUDO_PASS for both aggregates (ansible's
#   sudo become plugin reads become_pass from ANSIBLE_BECOME_PASS /
#   ANSIBLE_SUDO_PASS env — ticket-independent, so piped become always works)
#   and used to warm the terminal ticket the foreground `hyprpm update` in
#   gloview-sync relies on (three attempts, then abort loud — a wrong password
#   must never fail deep in the aggregate).
# - The timestamp keepalive covers hyprpm's late terminal-attached sudo calls
#   during the long header build (ansible itself needs no ticket — it has the
#   password). Killed on exit (cleanup trap).
# An explicit become flag always wins (the block is skipped, so a passed
# --become-password is never overridden). A non-terminal run without
# passwordless escalation aborts loud here instead of hanging on a prompt no
# one can answer.
_has_become_flag=false
for _flag in "${BOOTSTRAP_ARGS[@]}"; do
  case "$_flag" in
    --ask-become-pass|--become-password|--become-password=*) _has_become_flag=true ;;
  esac
done
if ! $_has_become_flag; then
  if setsid sudo -n true </dev/null >/dev/null 2>&1; then
    : # genuinely passwordless in every context; run unattended
  elif [ -t 0 ]; then
    bold "Privilege escalation needs a password — asking once up front (reused for the whole run)."
    _become_pw=""
    for _attempt in 1 2 3; do
      IFS= read -rsp "BECOME password: " _become_pw || true
      printf '\n'
      if printf '%s\n' "$_become_pw" | sudo -Sv >/dev/null 2>&1; then
        break
      fi
      red "Sorry, try again."
      _become_pw=""
      if [ "$_attempt" = 3 ]; then
        red "ERROR: sudo authentication failed 3 times — cannot provision."
        exit 2
      fi
    done
    unset _attempt
    export ANSIBLE_SUDO_PASS="$_become_pw"
    ( while true; do sudo -n true >/dev/null 2>&1; sleep 60; kill -0 "$$" 2>/dev/null || exit 0; done ) &
    _sudo_keepalive_pid=$!
  else
    red "ERROR: privilege escalation requires a password, but stdin is not a terminal."
    red "Re-run in a terminal (you will be prompted), pass --ask-become-pass, or configure passwordless escalation for the invoking user."
    exit 2
  fi
fi
unset _has_become_flag _flag
# The aggregate bootstrap.yaml (Story 2.12) runs the whole chain:
# packages → cli_tools → filesystem → assets → compositor_configs →
# gui_tools → config_copies → settings → zsh_tools → zsh_config →
# wlogout_config → config_links → runtime-seed → display_manager →
# gloview-plugin → verify. BootstrapUseCase
# passes the install_dir + os_family seam extra-vars. Flags collected in
# BOOTSTRAP_ARGS above are forwarded verbatim so the aggregate can escalate
# on hosts without passwordless setup.
run_stage "bootstrap" uv run --directory "$PROVISION_DIR" dotfiles-provision bootstrap "${BOOTSTRAP_ARGS[@]}"

# ── Stage 3.5: hyprpm header sync (fresh-machine GloView gap) ──────────────
# The gloview_plugin role SKIPS its mutating tasks when the hyprpm headers are
# not synced (fresh machine or Hyprland upgrade): the header sync is a source
# clone + header build hyprpm performs internally via its OWN `sudo`
# escalation, and the aggregate runs ansible with pipes (no pty), so that child
# sudo prompt can never be answered from inside the run. This script DOES have
# the user's terminal, so it closes the gap here instead of leaving the
# trackpad gestures (and SUPER+TAB) silently dead behind a green provision:
#   - probe: `hyprpm list` names the gloview repo → store/headers present,
#     nothing to do (PATH-resolved probe — no system paths are hardcoded here,
#     per the no-absolute-paths lock below).
#   - miss + real (non-check) run + terminal stdin → run `hyprpm update` in the
#     FOREGROUND (the multi-minute source clone stays visible; escalation was
#     authenticated once up front in Stage 3, so its sudo prompt usually never
#     appears), then re-run the aggregate (idempotent by contract) so the
#     role's add/enable/reload/assert execute for real instead of skipping.
#   - miss + --check → skip silently-in-word (a loud WARNING): dry-run must
#     never mutate.
#   - miss + non-terminal stdin → warn loud and continue: CI/VM contexts cannot
#     answer a sudo prompt. The role already warned, verify stays green by
#     design, and the login activator (gloview-activate) retries the sync at
#     the next Hyprland login.
# An interactive update FAILURE aborts loud (stage_failed): on a terminal the
# user is present and the cause (network, disk, version skew) is actionable —
# a green exit must keep meaning "gestures work", not "gestures maybe work".
gloview_check_mode=false
for _gflag in "${BOOTSTRAP_ARGS[@]}"; do
  case "$_gflag" in
    --check) gloview_check_mode=true ;;
  esac
done
unset _gflag
gloview_installed=false
if command -v hyprpm >/dev/null 2>&1 \
  && hyprpm list 2>/dev/null | grep -E -q 'Repository gloview|Plugin gloview'; then
  gloview_installed=true
fi
if $gloview_installed; then
  green "GloView already present (hyprpm) — skipping interactive header sync."
elif $gloview_check_mode; then
  red "WARNING: GloView is not installed and this is a --check run — dry-run performs no header sync; the gloview_plugin role stays skipped by design."
elif [ -t 0 ]; then
  bold "── stage gloview-sync: one-time hyprpm header sync (needs sudo, several minutes) ──"
  bold 'Hyprland plugin headers are not synced (fresh machine or Hyprland upgrade).'
  bold 'Running `hyprpm update` in the foreground now,'
  bold 'then provisioning re-runs automatically so GloView is added, enabled and asserted.'
  hyprpm update || stage_failed "gloview-sync (hyprpm update)" "$?"
  run_stage "bootstrap (gloview retry)" uv run --directory "$PROVISION_DIR" dotfiles-provision bootstrap "${BOOTSTRAP_ARGS[@]}"
else
  red "WARNING: GloView is not installed and stdin is not a terminal — no interactive header sync is possible."
  red 'The gloview_plugin role stays skipped; run `hyprpm update` once in a terminal, then re-run $0.'
  red "(At the next Hyprland login, gloview-activate retries the sync automatically.)"
fi
unset gloview_check_mode gloview_installed

# ── Stage 4: verify hard gate (AC 4) ─────────────────────────────────────
# The aggregate's internal verify import is plan-gated (check mode); this
# explicit trailing verify is a REAL check (VerifyCapabilityUseCase runs with
# check=False) asserting all fourteen done-criteria — the CAP-4 success signal.
run_stage "verify" uv run --directory "$PROVISION_DIR" dotfiles-provision verify

# ── Post-verify GloView session signal: green vs green-but-degraded ────────
# Verify passes vacuously without Hyprland IPC (TTY provision) and never
# asserts GloView, so a bare "Bootstrap complete" can hide dead gestures. When
# this script runs INSIDE a Hyprland session (IPC reachable) the plugin must
# be loaded — otherwise say DEGRADED loudly. The exit code stays 0 (verify's
# contract holds; the message, not the code, carries the warning) with the
# exact recovery command. Without IPC this stays silent: a TTY provision has
# no compositor yet and the plugin loads at first login via gloview-activate.
# PATH-resolved probes only — no system paths hardcoded (lock below).
gloview_degraded=false
if command -v hyprctl >/dev/null 2>&1; then
  if hyprctl_plugins="$(hyprctl plugin list 2>/dev/null)"; then
    if printf '%s\n' "$hyprctl_plugins" | grep -qi gloview; then
      green "session check: GloView plugin is loaded — trackpad gestures active."
    else
      gloview_degraded=true
      red "WARNING: stages are green but GloView is NOT loaded in this Hyprland session —"
      red "trackpad gestures and SUPER+TAB are dead until it loads (DEGRADED, not failed)."
      red 'Run `hyprpm update` once in a terminal, then re-run $0 (or relog — gloview-activate retries at login).'
    fi
  fi
fi
unset hyprctl_plugins

if $gloview_degraded; then
  green "Bootstrap complete (stages green): uv preseed → collections → bootstrap → verify."
else
  green "Bootstrap complete: uv preseed → collections → bootstrap → verify all green."
fi
unset gloview_degraded
