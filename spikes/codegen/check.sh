#!/usr/bin/env bash
# Single executable check for the runtime<->shell contracts.
#
#   1. regenerate all artifacts from contract.json (the single source)
#   2. git diff --exit-code over generated/  -> catches source/artifact drift
#   3. Python runtime validation (jsonschema against generated schemas)
#   4. JS runtime validation (ajv compiled from the same generated schemas)
#   5. TypeScript type check (tsc --noEmit over generated types)
#
# PRECONDITION: generated/ MUST be tracked by git (committed), or step 2 is
# vacuous. That is the whole point of regenerate-and-diff.
set -euo pipefail
cd "$(dirname "$0")"

step() { printf '\n== %s ==\n' "$1"; }

step "1/6 drift check BEFORE regeneration (catches hand-edited artifacts)"
if ! git diff --exit-code -- generated/; then
  echo "DRIFT: generated/ differs from the tracked baseline (hand edit?)." >&2
  exit 1
fi
echo "no drift"

step "2/6 regenerate from contract.json"
python3 gen.py

step "3/6 drift check AFTER regeneration (catches source changed, artifacts not re-committed)"
if ! git diff --exit-code -- generated/; then
  echo "DRIFT: generated/ differs from the single source. Regenerate and commit." >&2
  exit 1
fi
echo "no drift"

step "4/6 ensure JS toolchain"
if [ ! -x node_modules/.bin/tsc ]; then
  npm install --no-audit --no-fund
fi

step "5/6 Python runtime validation (jsonschema)"
uv run --quiet --with jsonschema python validate_py.py

step "6/6 JS runtime validation (ajv) + TypeScript (tsc --noEmit)"
node validate_js.mjs
node_modules/.bin/tsc --noEmit -p tsconfig.json
echo "[tsc] PASS"

printf '\nALL CHECKS PASSED\n'
