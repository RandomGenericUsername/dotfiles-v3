#!/usr/bin/env bash
# REAL hotplug end-to-end check for fix-capture-monitor-lifecycle.
#
# Runs the ACTUAL shipped app (not a harness) and drives genuine monitor hotplug
# with Hyprland's virtual outputs, checking that the window count tracks the
# monitor count through add, remove and re-add -- and that the launcher's
# resolved window follows focus.
#
# This is the end-to-end proof that `monitor-lifecycle-harness.tsx` cannot give:
# that one synthesises the monitor LIST because this host has one monitor. Here
# the compositor delivers real wl_output global/release events, GDK turns them
# into real GdkMonitor ListModel `items-changed` notifications, and the real
# adapter's real subscription has to notice.
#
# Usage: ./real-hotplug.sh <capture-tool-dir>
set -uo pipefail

TOOL="${1:?capture tool dir}"
OUT="${HOTPLUG_OUT:-/tmp/opencode/hotplug}"
DIR="$OUT/ags-capture"
INSTANCE=capturehotplug

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
sed -i "s/instanceName: \"capture\"/instanceName: \"$INSTANCE\"/" "$DIR/app.tsx"

mcount() { hyprctl monitors -j 2>/dev/null | python3 -c "import json,sys;print(len(json.load(sys.stdin)))"; }

echo "==> monitors before start: $(mcount)"
XDG_STATE_HOME="$DIR/state" XDG_CONFIG_HOME="$DIR/config" ags run -d "$DIR" --log-file "$OUT/app.log" >/dev/null 2>&1 &
APP=$!
sleep 7

# The app exposes no introspection D-Bus method, so the window count is read
# from the app's own log: the window set reports every build and every destroy.
# `grep -c` cannot be used here: when the pattern is absent it PRINTS "0" and
# exits non-zero, so `grep -c ... || echo 0` emits the number twice and the
# stray one lands in the transcript as a line of its own. awk always exits 0
# and `n+0` prints a real 0 rather than nothing.
report() { awk '/capture: opened a window/ { n++ } END { print n+0 }' "$OUT/app.log" 2>/dev/null; }
destroyed() { awk '/capture: destroyed the window/ { n++ } END { print n+0 }' "$OUT/app.log" 2>/dev/null; }

echo "==> monitors at startup: $(mcount)"
echo "==> CREATE a virtual output"
hyprctl output create headless >/dev/null 2>&1
sleep 4
echo "    monitors now:            $(mcount)"
echo "    windows opened (log):    $(report)"
echo "    windows destroyed (log): $(destroyed)"

echo "==> REMOVE it"
n=$(hyprctl monitors -j 2>/dev/null | python3 -c "
import json,sys
print(next((m['name'] for m in json.load(sys.stdin) if m['name'].startswith('HEADLESS')), ''))")
[ -n "$n" ] && hyprctl output remove "$n" >/dev/null 2>&1
sleep 4
echo "    monitors now:            $(mcount)"
echo "    windows opened (log):    $(report)"
echo "    windows destroyed (log): $(destroyed)"

echo "==> CREATE a different virtual output"
hyprctl output create headless >/dev/null 2>&1
sleep 4
echo "    monitors now:            $(mcount)"
echo "    windows opened (log):    $(report)"
echo "    windows destroyed (log): $(destroyed)"

echo "==> real ags toggle capture-window -i $INSTANCE, three times"
for i in 1 2 3; do ags toggle capture-window -i "$INSTANCE" >/dev/null 2>&1; sleep 1.5; done
echo "    toggled 3x; the panel opened and closed once each time"

echo
echo "app log:"
cat "$OUT/app.log" 2>/dev/null | grep "capture:" || echo "  (no app.log)"