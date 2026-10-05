#!/usr/bin/env bash
# Pixel-equivalence harness for fix-capture-monitor-lifecycle.
#
# WHY A CONTROL EXPERIMENT. The capture panel is a translucent layer-shell
# surface: `btop` runs behind it and shows through, so two screenshots of the
# SAME build already differ wherever the background differs. A raw old-vs-new
# pixel delta therefore proves nothing on its own -- the honest reading is
# "old-vs-new must be indistinguishable FROM new-vs-new".
#
# So this captures each build TWICE and compares:
#     control = new build vs new build      (the noise floor)
#     subject = old build vs new build      (the claim)
# A subject at or below the control is a pass.
#
# Usage:  ./pixel-parity.sh <old-app.tsx> <new-app.tsx> <tool-dir>
set -uo pipefail

OLD_APP="${1:?old app.tsx}"
NEW_APP="${2:?new app.tsx}"
TOOL="${3:?capture tool dir}"
OUT="${PIXEL_OUT:-/tmp/opencode/pixel}"
mkdir -p "$OUT"

shoot() {  # shoot <tag> <appfile>
  local tag="$1" app_file="$2"
  local dir="$OUT/run-$tag"
  rm -rf "$dir"; mkdir -p "$dir"
  cp -r "$TOOL" "$dir/ags-capture"
  cp "$app_file" "$dir/ags-capture/app.tsx"
  # A DISTINCT instance name. This host already has a live `capture` instance,
  # and `ags run` against an instance name that is already on the bus is a
  # silent no-op -- the exact trap capture-ui.j2's own header warns about. With
  # the shared name, `ags toggle` would drive the ALREADY-RUNNING instance and
  # every screenshot would be of nothing.
  sed -i 's/instanceName: "capture"/instanceName: "capturepix"/' "$dir/ags-capture/app.tsx"
  mkdir -p "$dir/state" "$dir/config"
  XDG_STATE_HOME="$dir/state" XDG_CONFIG_HOME="$dir/config" \
    ags run -d "$dir/ags-capture" >/dev/null 2>&1 &
  local pid=$!
  sleep 7
  if ! ags toggle capture-window -i capturepix >/dev/null 2>&1; then
    echo "  WARNING: ags toggle failed for $tag"
  fi
  sleep 3
  grim "$OUT/$tag.png" 2>/dev/null || echo "grim failed for $tag"
  ags quit -i capturepix >/dev/null 2>&1 || true
  kill "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
  sleep 1
}

echo "==> capturing control (new build, twice)"
shoot new-1 "$NEW_APP"
shoot new-2 "$NEW_APP"
echo "==> capturing subject (old build)"
shoot old-1 "$OLD_APP"

# The panel is a fixed-size centred layer-shell surface. Comparing the full
# frame instead of just the panel mixes the panel's own pixels with whatever
# animates behind it, and the whole point of the control is to separate the two.
# This crop is the panel's bounds on a 1920x1080 screen; it is asserted by the
# control run being 0, which is what proves the crop is stable.
CROP="${PIXEL_CROP:-700x650+610+215}"

echo "==> comparing full frame"
for pair in "new-1 new-2 CONTROL" "old-1 new-1 SUBJECT"; do
  set -- $pair
  if [ -f "$OUT/$1.png" ] && [ -f "$OUT/$2.png" ]; then
    d=$(compare -metric AE "$OUT/$1.png" "$OUT/$2.png" null: 2>&1 || true)
    echo "  $3 ($1 vs $2): $d differing pixels"
  else
    echo "  $3: MISSING IMAGE"
  fi
done

echo "==> comparing the panel region only (crop $CROP)"
for f in old-1 new-1 new-2; do
  convert "$OUT/$f.png" -crop "$CROP" +repage "$OUT/crop-$f.png" 2>/dev/null
done
for pair in "new-1 new-2 CONTROL" "old-1 new-1 SUBJECT"; do
  set -- $pair
  d=$(compare -metric AE "$OUT/crop-$1.png" "$OUT/crop-$2.png" null: 2>&1 || true)
  echo "  $3 ($1 vs $2): $d differing pixels"
done
echo "artifacts in $OUT"