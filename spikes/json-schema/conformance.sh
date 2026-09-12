#!/usr/bin/env bash
# Executable conformance: the SAME schema + SAME fixtures through BOTH
# maintained validators (python-jsonschema and ajv), then a byte-level
# comparison of their verdict maps.
#
#   ./conformance.sh            core: history + current neutral schema (strict)
#   ./conformance.sh --full     core + pydantic-generated schema + runtime parity
#
# Exits non-zero on any expected-verdict mismatch, any validator failure, or
# any disagreement between the two validators. --full also fails on any
# divergence between the neutral schema and the generated/runtime artifacts.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
mkdir -p out generated

FULL=0
[[ "${1:-}" == "--full" ]] && FULL=1

PY_CMD=(uv run --python 3.14 --with jsonschema python)
PY_PYDANTIC_CMD=(uv run --python 3.14 --with jsonschema --with pydantic python)

fail=0

agree_check() {
  python3 - "$1" <<'PYEOF'
import json
import sys

tag = sys.argv[1]
a = json.load(open(f"out/python.{tag}.json"))["verdicts"]
b = json.load(open(f"out/js.{tag}.json"))["verdicts"]
if a != b:
    print(f"[{tag}] DISAGREEMENT python-jsonschema vs ajv:")
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            print(f"    {k}: python={a.get(k)} ajv={b.get(k)}")
    sys.exit(1)
print(f"[{tag}] agreement: identical verdicts for {len(a)} cases")
PYEOF
}

run_pair() {
  local tag="$1" schema="$2" cases="$3"
  echo "--- stage: $tag (schema=$schema cases=$cases) ---"
  if ! "${PY_CMD[@]}" python_validate.py --schema "$schema" --cases "$cases" --out "out/python.$tag.json"; then
    fail=1
  fi
  if ! node js_validate.mjs --schema "$schema" --cases "$cases" --out "out/js.$tag.json"; then
    fail=1
  fi
  if ! agree_check "$tag"; then
    fail=1
  fi
  echo
}

run_pair history history.schema.json fixtures/history.cases.json
run_pair current current.schema.json fixtures/current.cases.json

if [[ "$FULL" == "1" ]]; then
  echo "--- stage: pydantic-generated history schema (Python model_json_schema → both validators) ---"
  if ! "${PY_PYDANTIC_CMD[@]}" pydantic_generate.py; then
    fail=1
  fi
  if ! "${PY_CMD[@]}" python_validate.py --schema generated/history.pydantic.schema.json \
      --cases fixtures/history.cases.json --out out/python.pydantic.json; then
    fail=1
  fi
  if ! node js_validate.mjs --schema generated/history.pydantic.schema.json \
      --cases fixtures/history.cases.json --out out/js.pydantic.json; then
    fail=1
  fi
  if ! agree_check pydantic; then
    fail=1
  fi
  echo

  echo "--- stage: runtime parity — history (InspectHistoryUseCase._parse_record) ---"
  if ! "${PY_CMD[@]}" python_runtime_parity.py --kind history --cases fixtures/history.cases.json \
      --out out/runtime_parity.history.json; then
    fail=1
  fi
  echo

  echo "--- stage: runtime parity — current (JsonStateRepository._dict_to_state) ---"
  if ! "${PY_CMD[@]}" python_runtime_parity.py --kind current --cases fixtures/current.cases.json \
      --out out/runtime_parity.current.json; then
    fail=1
  fi
  echo
fi

if [[ "$fail" -ne 0 ]]; then
  echo "CONFORMANCE: FAIL"
  exit 1
fi
echo "CONFORMANCE: PASS"
