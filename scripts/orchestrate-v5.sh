#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "/home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3")"
CHANGES_DIR="$ROOT/openspec/changes"

# ── Dependency graph ──────────────────────────────────────────────────
# Each entry: "phase:name:deps"
#   phase   = wave number (0-5) for ordering
#   name    = openspec change name
#   deps    = space-separated changes that must be archived first
PHASES=(
  "0:oci-runtime-audit-remediation-v4:"
  "0:oci-strict-hexagonal-layering-v2:"
  "1:oci-docker-ports-null-handling:"
  "1:oci-timeout-precision:"
  "1:oci-json-parsing-informative-error:"
  "1:oci-pty-stderr-guard:"
  "1:oci-named-constants:"
  "1:oci-image-build-context-validation:"
  "1:oci-exception-context-parity:"
  "1:oci-subcommand-enum:"
  "1:oci-conformance-fixture-presence-guard:"
  "1:oci-conformance-fixture-author-path-scrub:"
  "1:oci-smoke-skip-tightening:"
  "1:oci-binary-resolver-tests:"
  "1:oci-list-executor-branch-tests:"
  "1:oci-docker-port-parsing-extract:"
  "1:oci-domain-unit-test-suites:"
  "1:oci-contract-tests-real-instances:"
  "1:oci-contract-suite-real-parsers:"
  "1:oci-detach-stream-semantics:"
  "1:oci-build-tar-posixpath:"
  "2:oci-factory-builder-pattern:oci-strict-hexagonal-layering-v2"
  "2:oci-cancellation-adapter-relocation:oci-strict-hexagonal-layering-v2"
  "3:oci-concurrency-boundary-tests:oci-domain-unit-test-suites"
  "4:oci-transport-subprocess-runner:oci-concurrency-boundary-tests"
  "4:oci-logs-follow-thread-safety:oci-concurrency-boundary-tests oci-transport-subprocess-runner"
  "5:oci-v5-remediation-doc-sync:"
)

# ── Helpers ────────────────────────────────────────────────────────────
red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
bold()   { printf "\033[1m%s\033[0m\n" "$*"; }

# Fetch full list once for batch status queries
LIST_CACHE=""
fetch_list() {
  LIST_CACHE=$(openspec list --json 2>/dev/null)
}

get_field() {
  local name="$1" field="$2"
  python3 -c "import sys,json; data=json.load(sys.stdin); changes=data.get('changes', data if isinstance(data,list) else []); [print(c.get('$field','?')) for c in changes if c.get('name')=='$name']" <<< "$LIST_CACHE"
}

is_archived() {
  local name="$1"
  ls "$CHANGES_DIR/archive/"*"$name" 2>/dev/null && return 0 || return 1
}

archive_change() {
  local name="$1"
  yellow "  → archiving $name ..."
  openspec archive "$name" -y 2>&1 | sed 's/^/    /'
  green "  ✓ $name archived"
}

validate_change() {
  local name="$1"
  yellow "  → validating $name ..."
  openspec validate "$name" 2>&1 | sed 's/^/    /'
}

# ── Commands ───────────────────────────────────────────────────────────
cmd_status() {
  fetch_list
  bold "=== v5 Orchestration Status ==="
  printf "%-42s %-6s %-10s %s\n" "CHANGE" "PHASE" "STATUS" "DEPS MET"
  printf -- "─%.0s" {1..80}; echo
  for entry in "${PHASES[@]}"; do
    IFS=':' read -r phase name deps <<< "$entry"
    status=$(get_field "$name" "status")
    if is_archived "$name" 2>/dev/null; then status="archived"; fi
    deps_met=true
    for d in $deps; do
      if ! is_archived "$d" 2>/dev/null; then deps_met=false; break; fi
    done
    dm="no"
    $deps_met && dm="yes"
    printf "%-42s %-6s %-10s %s\n" "$name" "$phase" "$status" "$dm"
  done
}

cmd_next() {
  fetch_list
  bold "=== Next Change(s) Ready to Implement ==="
  found=false
  for entry in "${PHASES[@]}"; do
    IFS=':' read -r phase name deps <<< "$entry"
    status=$(get_field "$name" "status")
    is_archived "$name" 2>/dev/null && continue
    [[ "$status" == "complete" ]] && continue
    deps_met=true
    for d in $deps; do
      if ! is_archived "$d" 2>/dev/null; then deps_met=false; break; fi
    done
    if $deps_met; then
      found=true
      tasks=$(get_field "$name" "completedTasks")/$(get_field "$name" "totalTasks")
      echo "  $name  (wave $phase, tasks: $tasks)"
      echo "    openspec instructions apply --change \"$name\" --json"
      echo ""
    fi
  done
  $found || echo "  No changes ready — all done or deps not met."
}

cmd_archive_ready() {
  fetch_list
  bold "=== Archiving All Completed Changes ==="
  for entry in "${PHASES[@]}"; do
    IFS=':' read -r phase name deps <<< "$entry"
    status=$(get_field "$name" "status")
    is_archived "$name" 2>/dev/null && continue
    if [[ "$status" == "complete" ]]; then
      deps_met=true
      for d in $deps; do
        if ! is_archived "$d" 2>/dev/null; then deps_met=false; break; fi
      done
      if $deps_met; then
        archive_change "$name"
      else
        yellow "  ✗ $name is complete but deps not yet archived, skipping"
      fi
    fi
  done
}

cmd_plan() {
  bold "=== Master Implementation Plan ==="
  current_phase=""
  for entry in "${PHASES[@]}"; do
    IFS=':' read -r phase name deps <<< "$entry"
    if [[ "$phase" != "$current_phase" ]]; then
      current_phase="$phase"
      echo ""
      bold "── Wave $phase ──"
    fi
    echo "  $name"
  done
  echo ""
  bold "Execution order respects dependency arrows:"
  echo "  A4 (layering) → wave 1 (parallel) → A5/A3 → T5/T11 → B8/B9 → B6 → doc sync"
}

# ── Main ──────────────────────────────────────────────────────────────
case "${1:-help}" in
  status)     cmd_status ;;
  next)       cmd_next ;;
  archive)    cmd_archive_ready ;;
  plan)       cmd_plan ;;
  help|*)
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  plan         Show the full implementation plan with dependency waves"
    echo "  status       Show status of all 25 changes"
    echo "  next         Show which change(s) are ready to implement now"
    echo "  archive      Archive all complete + dependency-met changes"
    echo ""
    echo "Typical workflow:"
    echo "  1. \$0 plan        # review the plan"
    echo "  2. \$0 next        # see what's ready"
    echo "  3. implement the change (code + tests)"
    echo "  4. openspec archive <name>"
    echo "  5. \$0 next        # next change unblocked"
    echo "  6. repeat 3-5"
    ;;
esac
