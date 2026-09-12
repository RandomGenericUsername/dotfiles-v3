#!/usr/bin/env bash
# Negative demonstrations for the single-source-of-truth claim.
#
# Each case edits the XML (or asserts an undeclared emission) and REQUIRES the
# conformance tool to fail. The script exits 0 only if every negative case was
# correctly detected, i.e. the guard is not vacuous.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
XML="$HERE/org.dotfiles.Events1.xml"
RUN=(uv run "$HERE/conformance.py")

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail=0

expect_fail() {
  local label="$1"; shift
  echo "================================================================"
  echo "CASE: $label"
  echo "CMD : $*"
  echo "----------------------------------------------------------------"
  if "$@"; then
    echo ">>> UNEXPECTED PASS (guard vacuous)"
    fail=1
  else
    echo ">>> correctly FAILED (exit $?)"
  fi
  echo
}

echo "######## NEGATIVE CASE A: XML drops ReportProgress, contract still lists it"
python3 - "$XML" "$TMP/missing-method.xml" <<'PY'
import sys
src = open(sys.argv[1], encoding="utf-8").read()
block = """    <method name="ReportProgress">
      <arg name="job_id" type="s" direction="in"/>
      <arg name="fraction" type="d" direction="in"/>
    </method>

"""
assert block in src, "expected ReportProgress block not found"
open(sys.argv[2], "w", encoding="utf-8").write(src.replace(block, ""))
print(f"wrote {sys.argv[2]} with ReportProgress removed")
PY
expect_fail "XML<->contract drift: method removed from XML only" \
  "${RUN[@]}" --xml "$TMP/missing-method.xml"

echo "######## NEGATIVE CASE B: interface renamed to org.dotfiles.Events2"
python3 - "$XML" "$TMP/events2.xml" <<'PY'
import sys
src = open(sys.argv[1], encoding="utf-8").read()
out = src.replace("org.dotfiles.Events1", "org.dotfiles.Events2")
assert out != src
open(sys.argv[2], "w", encoding="utf-8").write(out)
print(f"wrote {sys.argv[2]} with interface renamed")
PY
expect_fail "XML<->contract drift: interface version mismatch" \
  "${RUN[@]}" --xml "$TMP/events2.xml"

echo "######## NEGATIVE CASE C: producer emits JobCrashed, undeclared in XML"
expect_fail "undeclared emitted signal rejected" \
  "${RUN[@]}" --check-emitted JobCrashed

echo "######## NEGATIVE CASE D: declared signal still passes the emit guard (control)"
if "${RUN[@]}" --check-emitted JobFinished >/dev/null 2>&1; then
  echo "control: JobFinished accepted as declared (as expected)"
else
  echo ">>> control FAILED: JobFinished should be declared"
  fail=1
fi

echo "================================================================"
if [[ "$fail" -eq 0 ]]; then
  echo "ALL NEGATIVE CASES CORRECTLY DETECTED"
else
  echo "SOME NEGATIVE CASES WERE NOT DETECTED"
fi
exit "$fail"
