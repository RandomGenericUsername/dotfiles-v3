#!/usr/bin/env bash
# END-TO-END Gap-2 proof: does `ags toggle capture-window` open the FOCUSED
# monitor's window?
#
# This host has one physical monitor, but Hyprland can create virtual outputs,
# so a genuine two-monitor layout exists for the length of this script.
#
# WHY NOT PIXELS. The first attempt compared screenshots, and it is unusable:
# the panel is a translucent layer-shell surface over live desktop content, so a
# whole-screen brightness mean is dominated by whatever is behind it (measured:
# 0.64 for the old build's eDP-1 against 0.05 for the new build's on the same
# screen, purely because the desktop content differed between runs). Even a
# mean-of-differences drowns in the browser animating behind the panel.
#
# WHY THIS WORKS. The panel is a layer-shell surface, and `ClassicWindow` sets
# `namespace="capture"` on it. `hyprctl layers` reports every layer surface with
# its OUTPUT and its namespace, so "which monitor is the panel on" is a direct
# read with no dependence on what is behind it:
#
#     $ hyprctl layers
#     Monitor eDP-1:
#             Layer level 3 (overlay):
#                     Layer 55e4...: xywh: 610 215 700 650, namespace: capture, ...
#
# Usage: ./launcher-focus.sh <tool-dir> <app.tsx> <label>
set -uo pipefail

TOOL="${1:?tool dir}"
APP="${2:?app.tsx}"
LABEL="${3:-run}"
OUT="${FOCUS_OUT:-/tmp/opencode/focus-$LABEL}"
DIR="$OUT/ags-capture"
INSTANCE="capturefocus$LABEL"

cleanup() {
  ags quit -i "$INSTANCE" >/dev/null 2>&1 || true
  for n in $(hyprctl monitors -j 2>/dev/null | python3 -c "
import json,sys
print(' '.join(m['name'] for m in json.load(sys.stdin) if m['name'].startswith('HEADLESS')))
"); do
    hyprctl output remove "$n" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

rm -rf "$OUT"; mkdir -p "$DIR/state" "$DIR/config"
cp -r "$TOOL/." "$DIR/"
cp "$APP" "$DIR/app.tsx"
sed -i "s/instanceName: \"capture\"/instanceName: \"$INSTANCE\"/" "$DIR/app.tsx"

# The second monitor is created BEFORE the app starts, on purpose. Creating it
# afterwards proves GAP 1 (an old build has no window for it at all, so it
# "matches" focus only by accident); creating it beforehand is what isolates
# GAP 2, where the app really does have one window per monitor and the only
# question is which one the launcher reaches.
echo "== creating a second monitor BEFORE the app starts =="
hyprctl output create headless >/dev/null 2>&1
sleep 3
VIRT=$(hyprctl monitors -j 2>/dev/null | python3 -c "
import json,sys
print(next((m['name'] for m in json.load(sys.stdin) if m['name'].startswith('HEADLESS')), ''))")

XDG_STATE_HOME="$DIR/state" XDG_CONFIG_HOME="$DIR/config" \
  ags run -d "$DIR" --log-file "$OUT/app.log" >/dev/null 2>&1 &
sleep 7

# Which outputs currently carry a `capture` layer surface.
panels_on() {
  hyprctl layers 2>/dev/null | awk '
    /^Monitor /   { mon = $2; sub(/:$/, "", mon) }
    /namespace: capture/ { print mon }
  ' | sort -u | tr '\n' ' ' | sed 's/ $//'
}

monitors_now() {
  hyprctl monitors -j 2>/dev/null | python3 -c "
import json,sys; print(' '.join(m['name'] for m in json.load(sys.stdin)))"
}
focused_now() {
  hyprctl monitors -j 2>/dev/null | python3 -c "
import json,sys
print(next((m['name'] for m in json.load(sys.stdin) if m.get('focused')), '?'))"
}

echo "monitors: $(monitors_now)   (virtual output = $VIRT)"
echo "panel surfaces before any toggle: [$(panels_on)]"
echo

for round in 1 2 3; do
  # Try to move focus to the other monitor, then report where focus actually is.
  if [ "$round" = "1" ]; then hyprctl dispatch focusmonitor "$VIRT" >/dev/null 2>&1
  elif [ "$round" = "2" ]; then hyprctl dispatch focusmonitor eDP-1 >/dev/null 2>&1
  else hyprctl dispatch focusmonitor "$VIRT" >/dev/null 2>&1; fi
  sleep 2
  f=$(focused_now)
  ags toggle capture-window -i "$INSTANCE" >/dev/null 2>&1
  sleep 2
  up=$(panels_on)
  ags toggle capture-window -i "$INSTANCE" >/dev/null 2>&1
  sleep 2
  down=$(panels_on)
  echo "round $round: focused=$f"
  echo "   panel after toggle ON : [${up:-<none>}]"
  echo "   panel after toggle OFF: [${down:-<none>}]"
  if [ -n "$up" ] && [ "$up" = "$f" ]; then
    echo "   => MATCHES the focused monitor"
  else
    echo "   => does NOT match the focused monitor ($f)"
  fi
done

echo
echo "app log:"
grep "capture:" "$OUT/app.log" 2>/dev/null || echo "  (none)"
echo "artifacts in $OUT"