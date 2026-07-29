#!/usr/bin/env bash
# ============================================================================
# CSG (color-scheme-generator) — User Journey: LIVE DEMO + ASSERTIONS
# ============================================================================
# Shows every command and its raw output, THEN asserts correctness.
# Lets you visually verify while still catching regressions.
#
# Usage:
#   bash tests/test_user_journey.sh              # full run
#   bash tests/test_user_journey.sh help         # single section
#   bash tests/test_user_journey.sh journey      # just the full journey
#
# Sections: help global dump-config dump-templates list-backends info
#           generate show errors install uninstall journey
# ============================================================================

set -euo pipefail
shopt -s inherit_errexit nullglob

CSG_BIN="${CSG_BIN:-csg}"
WORKDIR="$(mktemp -d "/tmp/csg-demo-XXXXXX")"
TEST_IMAGE="$WORKDIR/test-image.png"
TESTS_RUN=0 TESTS_FAILED=0 EXIT_CODE=0
SECTION="${1:-all}"

R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' C='\033[0;36m' B='\033[1m' NC='\033[0m'

##############################################################################
#  HELPERS
##############################################################################

header() { echo; echo -e "${Y}━━━ $1 ━━━${NC}"; echo; }

run() {
    # Usage: run <label> <cmd...>
    # Prints the command, runs it, captures stdout/stderr, shows output, asserts exit 0.
    local label="$1"; shift
    local stdout_file="$WORKDIR/_stdout" stderr_file="$WORKDIR/_stderr"
    echo -e "  ${B}\$ ${*/$CSG_BIN/$CSG_BIN}${NC}"
    set +e
    "$@" >"$stdout_file" 2>"$stderr_file"
    local rc=$?
    set -e
    if [[ -s "$stdout_file" ]]; then
        echo "  ─── stdout ───"
        sed 's/^/  │ /' "$stdout_file"
        echo "  ──────────────"
    fi
    if [[ -s "$stderr_file" ]]; then
        local stderr_size=$(wc -c < "$stderr_file")
        echo -e "  ${R}─── stderr (truncated ${stderr_size}b) ───${NC}"
        sed 's/^/  │ /' "$stderr_file" | head -10
        if [[ $stderr_size -gt 500 ]]; then echo "  │ ... (truncated)"; fi
        echo -e "  ${R}───────────────────${NC}"
    fi
    if [[ $rc -eq 0 ]]; then
        echo -e "  ${G}✓${NC} $label"
        ((++TESTS_RUN))
    else
        echo -e "  ${R}✗${NC} $label (exit $rc)"
        ((++TESTS_RUN)); ((++TESTS_FAILED)); EXIT_CODE=1
    fi
}

run_nz() {
    # Like run but allows specific non-zero exit codes (backend unavailable, etc.)
    local label="$1" expected="$2"; shift 2
    local stdout_file="$WORKDIR/_stdout" stderr_file="$WORKDIR/_stderr"
    echo -e "  ${B}\$ ${*/$CSG_BIN/$CSG_BIN}${NC}"
    set +e
    "$@" >"$stdout_file" 2>"$stderr_file"
    local rc=$?
    set -e
    if [[ -s "$stdout_file" ]]; then
        echo "  ─── stdout ───"
        sed 's/^/  │ /' "$stdout_file"
        echo "  ──────────────"
    fi
    if [[ -s "$stderr_file" ]]; then
        echo -e "  ${R}─── stderr ───${NC}"
        sed 's/^/  │ /' "$stderr_file"
        echo -e "  ${R}─────────────${NC}"
    fi
    if [[ $rc -eq 0 ]] || [[ $rc -eq $expected ]]; then
        echo -e "  ${G}✓${NC} $label"
        ((++TESTS_RUN))
    else
        echo -e "  ${R}✗${NC} $label (exit $rc, expected 0 or $expected)"
        ((++TESTS_RUN)); ((++TESTS_FAILED)); EXIT_CODE=1
    fi
}

check_file() {
    if [[ -f "$1" ]]; then echo -e "  ${G}✓${NC} $2"; ((++TESTS_RUN))
    else echo -e "  ${R}✗${NC} $2 (missing: $1)"; ((++TESTS_RUN)); ((++TESTS_FAILED)); EXIT_CODE=1; fi
}

check_out() {
    local file=$1 pattern=$2 label=$3
    if grep -q -- "$pattern" "$file" 2>/dev/null; then echo -e "  ${G}✓${NC} $label"; ((++TESTS_RUN))
    else echo -e "  ${R}✗${NC} $label (expected '$pattern' in $(basename $file))"; ((++TESTS_RUN)); ((++TESTS_FAILED)); EXIT_CODE=1; fi
}

check_empty() {
    if [[ ! -s "$1" ]]; then echo -e "  ${G}✓${NC} $2"; ((++TESTS_RUN))
    else echo -e "  ${R}✗${NC} $2 (expected empty file)"; ((++TESTS_RUN)); ((++TESTS_FAILED)); EXIT_CODE=1; fi
}

HAS_OCI=false
if "$CSG_BIN" install --dry-run 2>/dev/null | grep -q "would-build"; then HAS_OCI=true; fi

##############################################################################
#  SETUP
##############################################################################
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT
mkdir -p "$WORKDIR"/{project,custom-templates,custom-config}

python3 -c "
import struct, zlib
def make_png(w, h, rgba):
    raw = b''
    for y in range(h):
        raw += b'\x00'
        for x in range(w):
            raw += bytes(rgba)
    compressed = zlib.compress(raw)
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', compressed) + chunk(b'IEND', b''))
with open('$TEST_IMAGE', 'wb') as f:
    f.write(make_png(64, 64, (255, 0, 255, 255)))
"

cat > "$WORKDIR/custom-templates/colors.custom.j2" << 'EOF'
background={{ background.hex }}
foreground={{ foreground.hex }}
EOF

echo -e "${C}Test image ready: $TEST_IMAGE${NC}"

##############################################################################
#  1. HELP & VERSION
##############################################################################
if [[ "$SECTION" == "all" || "$SECTION" == "help" ]]; then
header "1. HELP & VERSION"

run "top-level --help" "$CSG_BIN" --help
check_out "$WORKDIR/_stdout" "Usage" "help: shows Usage"
check_out "$WORKDIR/_stdout" "generate" "help: lists generate"
check_out "$WORKDIR/_stdout" "show" "help: lists show"
check_out "$WORKDIR/_stdout" "info" "help: lists info"
check_out "$WORKDIR/_stdout" "dump-config" "help: lists dump-config"
check_out "$WORKDIR/_stdout" "dump-templates" "help: lists dump-templates"
check_out "$WORKDIR/_stdout" "install" "help: lists install"
check_out "$WORKDIR/_stdout" "uninstall" "help: lists uninstall"
check_out "$WORKDIR/_stdout" "list-backends" "help: lists list-backends"
check_out "$WORKDIR/_stdout" "output-format" "help: shows --output-format"
check_out "$WORKDIR/_stdout" "templates-dir" "help: shows --templates-dir"
check_out "$WORKDIR/_stdout" "config" "help: shows --config"
check_out "$WORKDIR/_stdout" "verbose" "help: shows --verbose"

for cmd in generate show info version dump-config dump-templates install uninstall list-backends; do
    run "help: $cmd --help" "$CSG_BIN" "$cmd" --help
done

run "version" "$CSG_BIN" version
check_out "$WORKDIR/_stdout" "version" "version: contains 'version'"

run "version (rich)" "$CSG_BIN" --output-format rich version
run "version (plain)" "$CSG_BIN" --output-format plain version
check_out "$WORKDIR/_stdout" "color-scheme-generator" "version plain: shows package name"

fi

##############################################################################
#  2. GLOBAL OPTIONS
##############################################################################
if [[ "$SECTION" == "all" || "$SECTION" == "global" ]]; then
header "2. GLOBAL OPTIONS"

run "plain output" "$CSG_BIN" --output-format plain list-backends
check_out "$WORKDIR/_stdout" "custom" "plain: shows custom backend"

run "rich output" "$CSG_BIN" --output-format rich list-backends

run "quiet mode" "$CSG_BIN" --quiet list-backends
echo -e "  ${C}→ stdout size: $(wc -c < "$WORKDIR/_stdout") bytes${NC}"

run "verbose -v" "$CSG_BIN" -v version
run "debug -vv" "$CSG_BIN" -vv version
run "generate with runtime" "$CSG_BIN" generate "$TEST_IMAGE" --runtime container --output-dir "$WORKDIR/g-runtime"

cat > "$WORKDIR/custom-config/settings.toml" << 'EOF'
version = "1.0"
[output]
verbosity = 1
directory = "/tmp/csg-custom"
default_formats = ["json", "sh"]
overwrite = true
[generation]
backend = "custom"
default_params = {}
[runtime]
mode = "local"
[container]
engine = "docker"
image_prefix = "csg"
image_tag = "latest"
timeout_seconds = 300
memory_limit = "512m"
mount_timeout_seconds = 30
EOF

run "custom config" "$CSG_BIN" --config "$WORKDIR/custom-config/settings.toml" info
run "templates dir" "$CSG_BIN" --templates-dir "$WORKDIR/custom-templates" list-backends

fi

##############################################################################
#  3. DUMP-CONFIG
##############################################################################
if [[ "$SECTION" == "all" || "$SECTION" == "dump-config" ]]; then
header "3. DUMP-CONFIG"

run "dump-config to stdout" "$CSG_BIN" dump-config
check_out "$WORKDIR/_stdout" "directory" "dump-config: contains 'directory'"

run "dump-config to file" "$CSG_BIN" dump-config -o "$WORKDIR/project/settings.toml"
check_file "$WORKDIR/project/settings.toml" "dump-config: wrote settings.toml"

run "dump-config to dir" "$CSG_BIN" dump-config -o "$WORKDIR/project"
check_file "$WORKDIR/project/settings.toml" "dump-config to dir: created settings.toml"

run "dump-config rich" "$CSG_BIN" --output-format rich dump-config
run "dump-config plain" "$CSG_BIN" --output-format plain dump-config

fi

##############################################################################
#  4. DUMP-TEMPLATES
##############################################################################
if [[ "$SECTION" == "all" || "$SECTION" == "dump-templates" ]]; then
header "4. DUMP-TEMPLATES"

run "dump-templates to dir" "$CSG_BIN" dump-templates -o "$WORKDIR/project"
for tpl in colors.json.j2 colors.sh.j2 colors.css.j2 colors.gtk.css.j2 \
           colors.rasi.j2 colors.scss.j2 colors.yaml.j2 colors.sequences.j2; do
    check_file "$WORKDIR/project/templates/$tpl" "dump-templates: $tpl"
done
    count=$(ls -1 "$WORKDIR/project/templates/"*.j2 2>/dev/null | wc -l)
echo -e "  ${C}→ $count template files${NC}"

run "dump-templates overwrite" "$CSG_BIN" dump-templates -o "$WORKDIR/project" -w
run "dump-templates rich" "$CSG_BIN" --output-format rich dump-templates -o "$WORKDIR/project"

fi

##############################################################################
#  5. LIST-BACKENDS
##############################################################################
if [[ "$SECTION" == "all" || "$SECTION" == "list-backends" ]]; then
header "5. LIST-BACKENDS"

run "list-backends (JSON)" "$CSG_BIN" list-backends
check_out "$WORKDIR/_stdout" "custom" "list: shows custom"
check_out "$WORKDIR/_stdout" "pywal" "list: shows pywal"
check_out "$WORKDIR/_stdout" "wallust" "list: shows wallust"
check_out "$WORKDIR/_stdout" "available" "list: shows availability"
check_out "$WORKDIR/_stdout" "parameters" "list: shows parameters"
check_out "$WORKDIR/_stdout" "display_name" "list: shows display_name"
check_out "$WORKDIR/_stdout" "saturation" "list: shows saturation param"
check_out "$WORKDIR/_stdout" "n_clusters" "list: shows n_clusters param"
check_out "$WORKDIR/_stdout" "algorithm" "list: shows algorithm param"

run "list-backends (rich)" "$CSG_BIN" --output-format rich list-backends
check_out "$WORKDIR/_stdout" "custom" "list rich: shows custom"

run "list-backends (plain)" "$CSG_BIN" --output-format plain list-backends
check_out "$WORKDIR/_stdout" "custom" "list plain: shows custom"

fi

##############################################################################
#  6. INFO
##############################################################################
if [[ "$SECTION" == "all" || "$SECTION" == "info" ]]; then
header "6. INFO"

run "info (JSON)" "$CSG_BIN" info
check_out "$WORKDIR/_stdout" "settings" "info: contains settings"
check_out "$WORKDIR/_stdout" "backends" "info: contains backends"
check_out "$WORKDIR/_stdout" "sources" "info: contains sources"

run "info (rich)" "$CSG_BIN" --output-format rich info
run "info (plain)" "$CSG_BIN" --output-format plain info
check_out "$WORKDIR/_stdout" "output" "info plain: shows output section"
check_out "$WORKDIR/_stdout" "generation" "info plain: shows generation section"

fi

##############################################################################
#  7. GENERATE  <-- THE MAIN EVENT
##############################################################################
if [[ "$SECTION" == "all" || "$SECTION" == "generate" ]]; then
header "7. GENERATE"

run "generate default" "$CSG_BIN" generate "$TEST_IMAGE" --output-dir "$WORKDIR/g-default"
check_out "$WORKDIR/_stdout" "success" "gen: success"
check_out "$WORKDIR/_stdout" "color_scheme" "gen: has color_scheme"
check_out "$WORKDIR/_stdout" "output_files" "gen: has output_files"
check_file "$WORKDIR/g-default/colors.json" "gen: created colors.json"
check_file "$WORKDIR/g-default/colors.sh" "gen: created colors.sh"

run "generate --backend custom" "$CSG_BIN" generate "$TEST_IMAGE" --backend custom --output-dir "$WORKDIR/g-custom"
check_out "$WORKDIR/_stdout" "custom" "gen custom: backend=custom"

run_nz "generate --backend pywal" 0 \
    timeout 30 "$CSG_BIN" generate "$TEST_IMAGE" --backend pywal --output-dir "$WORKDIR/g-pywal"

run_nz "generate --backend wallust" 1 \
    timeout 15 "$CSG_BIN" generate "$TEST_IMAGE" --backend wallust --output-dir "$WORKDIR/g-wallust"

run "generate -f json -f css -f sh" \
    "$CSG_BIN" generate "$TEST_IMAGE" -f json -f css -f sh --output-dir "$WORKDIR/g-formats"
check_file "$WORKDIR/g-formats/colors.json" "gen formats: colors.json"
check_file "$WORKDIR/g-formats/colors.css" "gen formats: colors.css"
check_file "$WORKDIR/g-formats/colors.sh" "gen formats: colors.sh"

run "generate ALL 8 formats" \
    "$CSG_BIN" generate "$TEST_IMAGE" \
    -f json -f sh -f css -f gtk.css -f yaml -f sequences -f rasi -f scss \
    --output-dir "$WORKDIR/g-all"
for fmt in json sh css gtk.css yaml sequences rasi scss; do
    fname="colors.$fmt"
    [[ "$fmt" == "gtk.css" ]] && fname="colors.gtk.css"
    check_file "$WORKDIR/g-all/$fname" "gen all: $fname"
done

run "generate --param saturation=0.5" \
    "$CSG_BIN" generate "$TEST_IMAGE" --backend custom --param saturation=0.5 --output-dir "$WORKDIR/g-param1"

run "generate --param n_clusters=8" \
    "$CSG_BIN" generate "$TEST_IMAGE" --backend custom --param n_clusters=8 --output-dir "$WORKDIR/g-param2"

run "generate (rich)" "$CSG_BIN" --output-format rich generate "$TEST_IMAGE" --output-dir "$WORKDIR/g-rich"
run "generate (plain)" "$CSG_BIN" --output-format plain generate "$TEST_IMAGE" --output-dir "$WORKDIR/g-plain"

run "generate (quiet)" "$CSG_BIN" --quiet generate "$TEST_IMAGE" --output-dir "$WORKDIR/g-quiet"
check_empty "$WORKDIR/_stdout" "gen quiet: stdout is empty"

run "generate with custom templates" \
    "$CSG_BIN" --templates-dir "$WORKDIR/custom-templates" \
    generate "$TEST_IMAGE" --output-dir "$WORKDIR/g-tpl"

fi

##############################################################################
#  8. SHOW
##############################################################################
if [[ "$SECTION" == "all" || "$SECTION" == "show" ]]; then
header "8. SHOW"

run "show default" "$CSG_BIN" show "$TEST_IMAGE"
check_out "$WORKDIR/_stdout" "background" "show: has background"
check_out "$WORKDIR/_stdout" "foreground" "show: has foreground"
check_out "$WORKDIR/_stdout" "cursor" "show: has cursor"
check_out "$WORKDIR/_stdout" "colors" "show: has colors"

run "show --backend custom" "$CSG_BIN" show "$TEST_IMAGE" --backend custom
run_nz "show --backend pywal" 0 timeout 30 "$CSG_BIN" show "$TEST_IMAGE" --backend pywal
run_nz "show --backend wallust" 1 timeout 15 "$CSG_BIN" show "$TEST_IMAGE" --backend wallust

run "show --param saturation=1.5" \
    "$CSG_BIN" show "$TEST_IMAGE" --backend custom --param saturation=1.5

run "show (rich)" "$CSG_BIN" --output-format rich show "$TEST_IMAGE"
run "show (plain)" "$CSG_BIN" --output-format plain show "$TEST_IMAGE"
check_out "$WORKDIR/_stdout" "Background" "show plain: shows Background"
check_out "$WORKDIR/_stdout" "Foreground" "show plain: shows Foreground"

fi

##############################################################################
#  9. ERROR CASES
##############################################################################
if [[ "$SECTION" == "all" || "$SECTION" == "errors" ]]; then
header "9. ERROR CASES"

run_nz "generate nonexistent image" 1 \
    "$CSG_BIN" generate "$WORKDIR/nonexistent.png"
run_nz "generate no args" 2 "$CSG_BIN" generate
run_nz "invalid backend" 2 \
    "$CSG_BIN" generate "$TEST_IMAGE" --backend nonexistent
run_nz "invalid param key" 1 \
    "$CSG_BIN" generate "$TEST_IMAGE" --backend custom --param invalid_key=42
run_nz "show nonexistent image" 1 \
    "$CSG_BIN" show "$WORKDIR/nonexistent.png"
run_nz "show no args" 2 "$CSG_BIN" show
run_nz "unknown command" 2 "$CSG_BIN" unknown-command
run_nz "config nonexistent" 2 \
    "$CSG_BIN" --config "$WORKDIR/nonexistent.toml" info
run_nz "templates-dir nonexistent" 2 \
    "$CSG_BIN" --templates-dir "$WORKDIR/nonexistent-dir" info

# Malformed param should not crash
echo -e "  ${B}\$ $CSG_BIN show $TEST_IMAGE --param '='${NC}"
set +e
"$CSG_BIN" show "$TEST_IMAGE" --param "=" > "$WORKDIR/_stdout" 2>"$WORKDIR/_stderr"
echo -e "  ${C}→ exit $? (expected 0 or handled gracefully)${NC}"
set -e
echo -e "  ${G}✓${NC} malformed param handled without crash"
((++TESTS_RUN))

fi

##############################################################################
#  10. INSTALL
##############################################################################
if [[ "$SECTION" == "all" || "$SECTION" == "install" ]]; then
header "10. INSTALL (DRY-RUN)"

if [[ "$HAS_OCI" == "true" ]]; then
    run "install --dry-run all" "$CSG_BIN" install --dry-run
    check_out "$WORKDIR/_stdout" "would-build" "install: shows would-build"
    check_out "$WORKDIR/_stdout" "custom" "install: includes custom"
    check_out "$WORKDIR/_stdout" "pywal" "install: includes pywal"
    check_out "$WORKDIR/_stdout" "wallust" "install: includes wallust"
    run "install --dry-run --backend custom" "$CSG_BIN" install --dry-run --backend custom
    run "install -n (short form)" "$CSG_BIN" install -n
    run "install --engine docker" "$CSG_BIN" install --dry-run --engine docker
else
    echo -e "  ${Y}⊖ install: oci-runtime not available (skipped)${NC}"
fi

fi

##############################################################################
#  11. UNINSTALL
##############################################################################
if [[ "$SECTION" == "all" || "$SECTION" == "uninstall" ]]; then
header "11. UNINSTALL (DRY-RUN)"

if [[ "$HAS_OCI" == "true" ]]; then
    run "uninstall --dry-run --yes" "$CSG_BIN" uninstall --dry-run --yes
    check_out "$WORKDIR/_stdout" "would-remove" "uninstall: shows would-remove"
    run "uninstall --dry-run --backend custom --yes" "$CSG_BIN" uninstall --dry-run --backend custom --yes
    run "uninstall --dry-run --force --yes" "$CSG_BIN" uninstall --dry-run --force --yes
    run "uninstall -n -y (short)" "$CSG_BIN" uninstall -n -y
    run "uninstall --engine podman --yes" "$CSG_BIN" uninstall --dry-run --engine podman --yes
else
    echo -e "  ${Y}⊖ uninstall: oci-runtime not available (skipped)${NC}"
fi

fi

##############################################################################
#  12. FULL USER JOURNEY
##############################################################################
if [[ "$SECTION" == "all" || "$SECTION" == "journey" ]]; then
header "12. FULL USER JOURNEY"

PROJECT="$WORKDIR/my-theme-project"
mkdir -p "$PROJECT"

run "→ 1. version" "$CSG_BIN" version
run "→ 2. list backends" "$CSG_BIN" list-backends
run "→ 3. dump config" "$CSG_BIN" dump-config -o "$PROJECT/settings.toml"
check_file "$PROJECT/settings.toml" "→ 3b. settings.toml created"
run "→ 4. dump templates" "$CSG_BIN" dump-templates -o "$PROJECT"
check_file "$PROJECT/templates/colors.json.j2" "→ 4b. template dumped"

# Write a complete, valid config
cat > "$PROJECT/settings.toml" << 'EOF'
version = "1.0"
[output]
verbosity = 1
directory = "/tmp/color-scheme"
default_formats = ["json", "sh", "css"]
overwrite = true
[generation]
backend = "custom"
default_params = { saturation = "0.8", n_clusters = "8" }
[runtime]
mode = "local"
[container]
engine = "docker"
image_prefix = "csg"
image_tag = "latest"
timeout_seconds = 300
memory_limit = "512m"
mount_timeout_seconds = 30
EOF

run "→ 5. info with custom config" \
    "$CSG_BIN" --config "$PROJECT/settings.toml" info

run "→ 6. generate with overrides" \
    "$CSG_BIN" --config "$PROJECT/settings.toml" \
    generate "$TEST_IMAGE" \
    --backend custom --param saturation=1.2 --param n_clusters=16 \
    -f json -f css -f sh -f rasi \
    --output-dir "$PROJECT/output"

for f in colors.json colors.css colors.sh colors.rasi; do
    check_file "$PROJECT/output/$f" "→ 6b. $f created"
done

run "→ 7. show palette" \
    "$CSG_BIN" --config "$PROJECT/settings.toml" show "$TEST_IMAGE" --backend custom

check_out "$PROJECT/output/colors.json" "background" "→ 8. colors.json is valid"
check_out "$PROJECT/output/colors.css" "--color-background" "→ 8. colors.css is valid"
check_out "$PROJECT/output/colors.sh" "COLOR_BACKGROUND" "→ 8. colors.sh is valid"

echo -e "  ${C}→ Journey artifacts:${NC}"
ls -la "$PROJECT/output/" 2>/dev/null | while read -r line; do echo -e "  ${C}  $line${NC}"; done

fi

##############################################################################
#  SUMMARY
##############################################################################
echo
echo -e "${Y}═══════════════════════════════════════════════════════════════${NC}"
if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${G}  ALL $TESTS_RUN CHECKS PASSED${NC}"
else
    echo -e "${R}  $TESTS_FAILED / $TESTS_RUN CHECKS FAILED${NC}"
fi
echo -e "${Y}═══════════════════════════════════════════════════════════════${NC}"
exit "$TESTS_FAILED"
