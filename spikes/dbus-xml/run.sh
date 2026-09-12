#!/usr/bin/env bash
# Run the whole dbus-xml single-source-of-truth spike.
#
#   1. positive conformance: python parser == gjs parser == contracts/event-contract.json
#   2. negative demos: the guard must fail on XML<->contract drift and undeclared signals
#   3. runtime validation demos on both sides (no code generation)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
XML="$HERE/org.dotfiles.Events1.xml"

echo "################################################################"
echo "# 1. POSITIVE CONFORMANCE"
echo "################################################################"
uv run "$HERE/conformance.py" --xml "$XML"

echo
echo "################################################################"
echo "# 2. NEGATIVE DEMOS (must all be detected)"
echo "################################################################"
bash "$HERE/negative_demos.sh"

echo
echo "################################################################"
echo "# 3a. GJS RUNTIME VALIDATION (Gio.DBusInterfaceInfo)"
echo "################################################################"
gjs "$HERE/gjs_runtime_validate.js" "$XML"

echo
echo "################################################################"
echo "# 3b. PYTHON RUNTIME VALIDATION (dbus-fast SignatureTree)"
echo "################################################################"
uv run "$HERE/python_runtime_validate.py" "$XML"
