#!/usr/bin/env bash
#
# Deploy ONLY the audio panel from this worktree to the running desktop, and
# restart ONLY the AGS instance that owns it.
#
# WHY THIS EXISTS
# ---------------
# The full provisioning run (`make bootstrap` / the compositor_configs role)
# deploys whatever tree is checked out in the MAIN worktree. Working on master
# therefore re-provisions the spine from master, and the audio panel's files are
# silently replaced with master's older ones -- which is exactly what happened
# on 2026-10-07 at 14:55: `app.tsx`, `audio/AudioPopup.tsx` and `audio/state.ts`
# were rewritten, and the composition root, adapters, domain, application and
# presentation directories were removed, because they are not in master's
# manifest.
#
# So "why doesn't the panel change?" had a boring answer: the deploy had been
# clobbered. This script makes an audio-only deploy a single command, so the
# panel can be iterated on without provisioning (and therefore without touching
# the bar, Wi-Fi, Bluetooth, battery, notifications, capture or wallpaper).
#
# WHAT IT TOUCHES -- and nothing else
# -----------------------------------
#   dotfiles/config/ags/audio/**        the panel and its boundary
#   dotfiles/config/ags/types.d.ts      ambient `*.css` module declaration
#   dotfiles/config/ags/app.tsx         ONLY with --with-app (see below)
#   AGS: the single instance whose cwd is the spine's config/ags
#
# app.tsx is the composition point: it constructs the binding and passes it to
# AudioPopup. Once the panel is already wired on disk, iterating on the audio
# tree does NOT require re-sending app.tsx. Sending it is therefore opt-in, and
# it is the flag that widens the blast radius -- the merged app.tsx also brings
# up the Bluetooth and Battery popups.
#
# NOT a provisioning replacement. It writes files directly, exactly as a
# human `cp` would, so it cannot be used to verify provisioning (use
# `make bootstrap` / the role tests for that). It is a developer loop tool.
#
# Usage:
#   scripts/deploy-audio-panel.sh [--with-app] [--dry-run] [--yes]
#
# Exit 0 on success. Non-zero, with an explanation, on any precondition failure
# and without making changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC="$REPO/dotfiles/config/ags"

# The spine. `~/.config/ags` is a symlink to this; resolve through it so the
# path we compare process cwds against is the real one.
DEPLOY_ROOT="${DOTFILES_SPINE:-$HOME/.local/share/dotfiles/config/ags}"
STATE_LOG="${HOME}/.local/state/ags/main.log"

WITH_APP=0
DRY_RUN=0
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --with-app) WITH_APP=1 ;;
    --dry-run)  DRY_RUN=1 ;;
    --yes)      ASSUME_YES=1 ;;
    -h|--help)  sed -n '2,45p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '  %s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }
die()  { printf '\nFAIL: %s\n' "$*" >&2; exit 1; }

[ -d "$SRC/audio" ] || die "no audio sources at $SRC/audio -- is this the worktree?"
[ -d "$DEPLOY_ROOT/audio" ] || die "no deployed audio at $DEPLOY_ROOT/audio -- is the desktop provisioned?"

step "Sources"
say "repo:   $SRC"
say "spine:  $DEPLOY_ROOT"
say "app.tsx will be deployed: $([ "$WITH_APP" = 1 ] && echo yes || echo 'no (use --with-app)')"

# ---------------------------------------------------------------------------
# 1. Gates first, and fail closed.
#
# A deploy that ships a panel which cannot render is worse than no deploy: the
# failure takes the Bar window with it, which is a whole-desktop outage rather
# than a broken popup. The gates are cheap relative to that, so they run before
# anything is written.
# ---------------------------------------------------------------------------
step "Gates (fail closed -- nothing is written if these do not pass)"
if [ "$DRY_RUN" = 1 ]; then
  say "dry-run: skipping gate execution"
else
  ( cd "$REPO" && make audio-panel-gates >/dev/null 2>&1 ) \
    || die "audio-panel-gates failed. Run 'make audio-panel-gates' to see why. Nothing was deployed."
  say "audio-panel-gates: PASS"
fi

# ---------------------------------------------------------------------------
# 2. Backup.
# ---------------------------------------------------------------------------
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$HOME/.local/share/dotfiles/.audio-panel-deploy-$STAMP"
step "Backup -> $BACKUP"
if [ "$DRY_RUN" = 1 ]; then
  say "dry-run: not creating backup"
else
  mkdir -p "$BACKUP/audio"
  cp -a "$DEPLOY_ROOT/app.tsx" "$BACKUP/app.tsx" 2>/dev/null || true
  cp -a "$DEPLOY_ROOT/audio/." "$BACKUP/audio/" 2>/dev/null || true
  say "$(find "$BACKUP" -type f | wc -l) file(s) backed up"
fi

# ---------------------------------------------------------------------------
# 3. Copy. Directory-aware: the source tree is the file list, so a new module
#    is deployed the moment it appears without editing this script.
# ---------------------------------------------------------------------------
step "Copy audio tree"
if [ "$DRY_RUN" = 1 ]; then
  ( cd "$SRC" && find audio -type f ) | sed 's/^/  would deploy /'
else
  mkdir -p "$DEPLOY_ROOT/audio"
  ( cd "$SRC" && find audio -type f -print0 ) | while IFS= read -r -d '' f; do
    mkdir -p "$DEPLOY_ROOT/$(dirname "$f")"
    cp -a "$SRC/$f" "$DEPLOY_ROOT/$f"
  done
  cp -a "$SRC/types.d.ts" "$DEPLOY_ROOT/types.d.ts"
  say "$(cd "$SRC" && find audio -type f | wc -l) audio file(s) + types.d.ts deployed"
fi

if [ "$WITH_APP" = 1 ]; then
  step "Copy app.tsx (composition point)"
  if [ "$DRY_RUN" = 1 ]; then say "would deploy app.tsx"; else
    cp -a "$SRC/app.tsx" "$DEPLOY_ROOT/app.tsx"
    say "app.tsx deployed -- Bluetooth and Battery popups come with it"
  fi
fi

# ---------------------------------------------------------------------------
# 4. Restart ONLY the main instance.
#
# Identified by cwd, not by name or by killing everything that looks like ags:
# notifications, capture, icme, hypr-pano and wallpaper-selector each run their
# own `gjs -m /run/user/$UID/ags.js` worker, and killing one of those takes its
# instance down. That mistake has been made here once already.
# ---------------------------------------------------------------------------
step "Identify the owning AGS instance"
MAIN_WORKER=""
for pid in $(pgrep -f "gjs -m /run/user/$UID/ags.js" 2>/dev/null || true); do
  cwd="$(readlink -f "/proc/$pid/cwd" 2>/dev/null || true)"
  if [ "$cwd" = "$DEPLOY_ROOT" ]; then MAIN_WORKER="$pid"; break; fi
done

if [ -z "$MAIN_WORKER" ]; then
  say "no running instance owns $DEPLOY_ROOT -- nothing to restart"
  say "start one with:  nohup ags run --log-file $STATE_LOG >/dev/null 2>&1 &"
  exit 0
fi
say "owner: pid $MAIN_WORKER"

if [ "$DRY_RUN" = 1 ]; then
  say "dry-run: would restart pid $MAIN_WORKER"
  exit 0
fi

if [ "$ASSUME_YES" != 1 ]; then
  printf '  Restart pid %s? [y/N] ' "$MAIN_WORKER"
  read -r reply </dev/tty || reply="n"
  [ "$reply" = "y" ] || [ "$reply" = "Y" ] || die "aborted by user"
fi

step "Restart"
# `ags quit` targets the default instance (the one at ~/.config/ags -> this
# spine). The worker's parent owns the bus name, so quit is the correct verb;
# the worker is then verified gone before relaunching.
ags quit >/dev/null 2>&1 || true
for _ in 1 2 3 4 5 6 7 8 9 10; do
  [ -d "/proc/$MAIN_WORKER" ] || break
  sleep 0.5
done
[ -d "/proc/$MAIN_WORKER" ] && say "warning: pid $MAIN_WORKER still alive after quit" || say "old instance stopped"

( cd "$HOME" && nohup ags run --log-file "$STATE_LOG" >/dev/null 2>&1 & ) || die "could not relaunch ags"

# Wait for the bar surface to actually map rather than sleeping a fixed guess.
for _ in $(seq 1 40); do
  if hyprctl layers 2>/dev/null | grep -q "1920 48"; then break; fi
  sleep 0.5
done

step "Result"
if hyprctl layers 2>/dev/null | grep -q "1920 48"; then
  say "bar layer mapped -- instance is up"
else
  say "WARNING: no bar layer detected. Check $STATE_LOG"
fi
if grep -qiE "ReferenceError|TypeError|is not defined" "$STATE_LOG" 2>/dev/null; then
  say "WARNING: errors in $STATE_LOG:"
  grep -iE "ReferenceError|TypeError|is not defined" "$STATE_LOG" | tail -5 | sed 's/^/    /'
else
  say "no runtime errors in $STATE_LOG"
fi
say "backup: $BACKUP"
printf '\nOpen the panel (click the bar speaker icon) and check it.\n'
