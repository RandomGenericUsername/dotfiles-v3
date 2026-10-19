.PHONY: bootstrap contracts-check contract-pin-check gates gates-ci ci-gates-parity ags-platform-dev dev-deps vm-fresh vm-up vm-down vm-console vm-shell vm-destroy vm-status vm-verify vm-help per-app-drift-symbol-suites

# Bootstrap the host machine (full provisioning).
# Pass become/check flags through, e.g. `make bootstrap ARGS="--ask-become-pass"`.
bootstrap:
	./bootstrap.sh $(ARGS)

# Contract conformance (AD-44): embedded schemas equal their canonical
# definitions, the D-Bus wire XML agrees with the event contract JSON, and
# every baked code constant (hub adapter tables + bar consumer binding)
# matches the machine definitions — the per-language drift gate.
# Runs by execution, never by reading prose.
contracts-check:
	uv run --directory src/runtime pytest tests/unit/test_contract_schema_conformance.py tests/unit/test_event_contract_conformance.py tests/unit/test_event_contract_drift.py tests/unit/test_history_trigger_enum.py tests/unit/test_contract_pin_check.py -q

# Cross-repo pin gate (REQ-004, spine AD-6). The generated bindings are
# VENDORED into this repo (committed copies) so the runtime needs no cross-repo
# build step; `scripts/contract-pin-check.py` diffs each vendored copy against
# the `contracts` repo's `generated/` and FAILS on a hand-edit. It is NOT in
# `GATES`/`gates-ci` on purpose: the contracts repo is a SIBLING checkout, not a
# submodule, so a CI runner for this repo has no `generated/` to diff against —
# the gate would only ever skip there. It runs on a developer machine (or a CI
# job that checks out `contracts`) via:
#
#   CONTRACTS_REPO=/path/to/contracts make contract-pin-check
#
# The `CONTRACTS_REPO` env var defaults to /home/inumaki/Development/contracts;
# when the directory is absent the gate skips with a clear message (exit 0). The
# negative test that proves it fails on a hand-edited copy is hermetic and DOES
# run in CI, via `contracts-check` (tests/unit/test_contract_pin_check.py).
contract-pin-check:
	python3 scripts/contract-pin-check.py

# Every executable gate, in the order a reviewer should read them: contract
# first (it is the source of truth), then the Ansible embedded-template lint,
# then the provisioning-shape coverage gate, then the per-app contract
# drift/symbol suites, then the check that keeps the CI workflow's job set equal
# to this list.
#
# The capture-tool GUI gates (capture-test / capture-typecheck /
# capture-hexagonal-gate) were RETIRED with the in-repo GUI (ags-apps-bar-first
# slice 5): the GUI moved into the `ags-apps` unit and its own gates live there.
# What remains in this repo for capture-tool is the Python backend (installed by
# cli_tools) and the provisioning SHAPE, which `deploy-coverage` asserts.
#
# `gates` is the DEVELOPER gate set and runs ALL of them. Nothing is dropped for
# convenience: a gate that is not run here is a gate nobody runs.
GATES := contracts-check ansible-embedded-template-lint \
         deploy-coverage ci-gates-parity per-app-drift-symbol-suites
gates: $(GATES)

# The CI gate set: every gate that can run on a stock `ubuntu-latest` runner.
#
# NO EXCLUSIONS TODAY. Every gate in `GATES` is stock-runner capable, so
# `gates-ci` IS `GATES` — there is no `filter-out`. The historical exclusion was
# `capture-typecheck`, retired with the in-repo capture GUI (ags-apps-bar-first
# slice 5): it needed `ags` on PATH plus the Astal/GIR libraries (and wrote ~49 MB
# of machine-specific .d.ts describing THIS host's GTK/Astal version), which a
# stock runner cannot provide — exactly why the GUI's gates moved to `ags-apps`
# WITH the GUI. `ci-gates-parity` reads this rule and treats an absent
# `filter-out` as "no exclusions" (see `scripts/ci-gates-parity.py`).
#
# This target exists so a developer can reproduce a CI run without the desktop
# stack, and so the split is stated in ONE place that cannot drift from the
# workflow: `.github/workflows/gates.yml` runs these as one job per gate.
gates-ci: $(GATES)

# CI<->gate-list parity: the workflow's job set must equal `gates-ci`.
#
# WHY THIS EXISTS. `.github/workflows/gates.yml` used to OPEN by claiming it was
# "the place a future change cannot quietly drop one" of the gates. No code
# backed that, and the claim was measurably false: `bluetooth-mock-parity` sat in
# `GATES` -- and so in `gates-ci`, the same header's authoritative set -- with no
# workflow job, so it had run on every developer's machine and never once on a
# push. This check compares the two lists, so the next drop fails loudly instead
# of silently. It belongs IN `GATES`: a check that proves the gate list is
# complete has to run in the list it is proving.
#
# WHY IT RUNS THROUGH uv AND NOT PLAIN python3. It parses the workflow as YAML
# (PyYAML ships with the provisioning project) rather than line-mangling it, the
# same `uv run --directory src/provisioning` mechanism
# `ansible-embedded-template-lint` uses. It needs no desktop stack, so it
# also runs in gates-ci. `../../scripts/` is required because --directory moves
# the interpreter's CWD.
#
# It FAILS rather than skipping when uv or PyYAML is unavailable: a parity check
# that quietly passes when its toolchain is missing is indistinguishable from one
# that passes.
#
# DECLARED DIFFERENCES live in the script (`RENAMES`, `CI_ONLY_EXEMPT`,
# `CI_EXCLUDED_GATES`), not here: the Makefile stays the one place the gate set is
# written, and the script reads `GATES` + the `gates-ci` filter out of it.
ci-gates-parity:
	uv run --directory src/provisioning python ../../scripts/ci-gates-parity.py

# The capture-tool GUI gates (capture-types / capture-typecheck / capture-test /
# capture-test-deps / capture-hexagonal-gate) were RETIRED with the in-repo GUI
# (ags-apps-bar-first slice 5): the AGS GUI moved into the `ags-apps` unit and
# its own gates (typecheck, domain tests, hexagonal structure) live there now.
# What remains here is the Python backend (src/gui-tools/capture-tool/bin/capture-tool,
# installed by the cli_tools role) and the provisioning SHAPE, asserted by
# `deploy-coverage`. Do NOT re-add a per-file capture gate here: it would read a
# tree this repo no longer owns.

# ---------------------------------------------------------------------------
# per-app-drift-symbol-suites -- the per-app contract drift suites, run from the
# ROOT gate (spine AD-19).
#
# WHY THIS EXISTS. Each app's drift suite ran only through that app's own
# `Makefile test` target, which nothing at the repo root invoked -- so the suites
# rotted silently and nobody saw it: the ICME drift suite was red because the
# speed-test contract gained `ssid`/`server_name` and the assertion was never
# updated. That defect is fixed and the suite now runs HERE, so the next drift
# fails a gate rather than waiting for a reader to run an app-local target.
#
# SCOPE: the drift suites (`event-contract-drift.mjs`) execute the machine
# contract (`contracts/event-contract.json` + `.xml`) against each app's baked
# constants. This target runs exactly those suites, not the apps' other unit
# tests, which each app's `make test` still owns. (The bar's own
# `ags-symbol-check.mjs` scan was retired with the in-repo bar bridge and lives
# in the bar's repo; hypr-pano's drift suite moved to the ags-apps unit with the
# app itself — ags-apps-bar-first slice 3 — and is run there.)
#
# NO DESKTOP STACK: plain `node` over the apps' pure modules and the committed
# contract, so the target is in gates-ci and runs on a stock runner. Node 22.18+
# is required for native .ts type-stripping; CI pins Node 24.
PER_APP_SUITES := \
	src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs \
	src/gui-tools/wallpaper-selector/tests/event-contract-drift.mjs

per-app-drift-symbol-suites: ags-platform-dev
	@command -v node >/dev/null || { echo "FAIL: per-app-drift-symbol-suites: node is not on PATH" >&2; exit 1; }
	@for suite in $(PER_APP_SUITES); do \
		echo "==> per-app-drift-symbol-suites: $$suite"; \
		node "$$suite" || exit 1; \
	done
	@echo "    OK: per-app contract drift + symbol suites green"

# ---------------------------------------------------------------------------
# ags-platform-dev -- the dev-time `node_modules/ags-platform` shortcut.
#
# WHY THIS EXISTS. The bar consumes the platform by the BARE SPECIFIER
# `ags-platform` (spine AD-17). AGS's embedded esbuild resolves it at bundle/run
# time through a `node_modules` shortcut; the deployed install creates one at
# <install>/config/node_modules/ags-platform (provisioning role `ags_platform`).
# The DEV tree needs the same shortcut so `per-app-drift-symbol-suites`' ICME
# event-contract drift suite resolves the specifier from a plain `node` script.
#
# IT MUST POINT OUTSIDE node_modules. Node refuses to type-strip `.ts` under a
# real `node_modules` directory (ERR_UNSUPPORTED_NODE_MODULES_TYPE_STRIPPING),
# which is why the platform's OWN tests import relatively (see the ags-platform
# repo). Node realpaths a SYMLINK, though, so a link whose target sits outside
# node_modules type-strips fine.
#
# THE SOURCE. Default: the pinned published unit, fetched shallow+anonymous into
# the gitignored $(AGS_PLATFORM_FETCH_DIR) on demand -- the same
# "declare the dependency, fetch it on demand" shape as the typescript and
# @types/node installs. Override AGS_PLATFORM_DEV=/path/to/ags-platform to test
# against a local checkout while iterating on the platform itself.
AGS_PLATFORM_VERSION := v0.1.0
AGS_PLATFORM_REPO := https://github.com/RandomGenericUsername/ags-platform.git
AGS_PLATFORM_DEV ?=
AGS_PLATFORM_FETCH_DIR := $(CURDIR)/.dev/ags-platform/$(AGS_PLATFORM_VERSION)
AGS_PLATFORM_SRC := $(if $(AGS_PLATFORM_DEV),$(AGS_PLATFORM_DEV),$(AGS_PLATFORM_FETCH_DIR))

ags-platform-dev:
	@if [ -n "$(AGS_PLATFORM_DEV)" ] && [ ! -f "$(AGS_PLATFORM_DEV)/index.ts" ]; then \
		echo "FAIL: ags-platform-dev: AGS_PLATFORM_DEV=$(AGS_PLATFORM_DEV) has no index.ts" >&2; \
		exit 1; \
	fi
	@if [ -z "$(AGS_PLATFORM_DEV)" ] && [ ! -f "$(AGS_PLATFORM_FETCH_DIR)/index.ts" ]; then \
		echo "==> ags-platform-dev: fetching ags-platform $(AGS_PLATFORM_VERSION) (shallow, anonymous HTTPS)"; \
		rm -rf "$(AGS_PLATFORM_FETCH_DIR)"; \
		mkdir -p "$$(dirname '$(AGS_PLATFORM_FETCH_DIR)')"; \
		git clone --depth 1 --branch $(AGS_PLATFORM_VERSION) $(AGS_PLATFORM_REPO) "$(AGS_PLATFORM_FETCH_DIR)" || exit 1; \
		rm -rf "$(AGS_PLATFORM_FETCH_DIR)/.git"; \
	fi
	@# A repo-root shortcut: the ICME event-contract drift suite (run by
	@# `per-app-drift-symbol-suites`) is a plain `node` script under
	@# src/gui-tools/, and Node's node_modules walk from there reaches the repo
	@# root but not the bar dev tree. Same symlink shape, one walk up.
	@mkdir -p node_modules
	@ln -sfn "$(AGS_PLATFORM_SRC)" node_modules/ags-platform
	@echo "==> ags-platform-dev: node_modules/ags-platform -> $(AGS_PLATFORM_SRC)"

# The Ansible tree must not nest a `{{ }}` template inside a Jinja string
# literal of an EXPRESSION-context value (`assert.that`, `when`,
# `changed_when`, `failed_when`, `until`). That is the construct ansible-core
# 2.23 disables by default; today ansible resolves the inner template anyway
# and warns, so `verify` passes with a warning that will become a hard failure.
#
# WHY A STATIC LINT AND NOT THE DRY-RUN TEST. `ansible-playbook --check` SKIPS
# both offending tasks (`when: not ansible_check_mode`), so the warning is
# unreachable from tests/integration/test_ansible_dryrun.py — a guard built
# there would be green forever while the defect survives. The reason is also
# recorded as a comment at that suite.
#
# WHY IT RUNS THROUGH uv AND NOT PLAIN python3. It needs PyYAML to PARSE the
# YAML (both real offenders are folded `>-` block scalars spanning two lines, so
# a line grep cannot see them) and PyYAML ships with the provisioning project —
# the same `uv run --directory src/provisioning` mechanism `ci-gates-parity`
# uses. It needs no desktop stack, so it also runs in gates-ci. `../../scripts/`
# is required because --directory moves the interpreter's CWD.
#
# It FAILS rather than skipping when uv or PyYAML is unavailable: a lint that
# quietly passes when its toolchain is missing is indistinguishable from one
# that passes.
ansible-embedded-template-lint:
	uv run --directory src/provisioning python ../../scripts/ansible-embedded-template-lint.py

# The AGS bar deploys WHOLE as the pinned external `ags-apps` unit (the
# `ags_apps` role symlinks the unit's bar/ subdir as the live
# <install>/config/ags), and the platform is the external `ags-platform` bare
# specifier (spine AD-17). This gate asserts that provisioning SHAPE: no stale
# per-file `dotfiles/config/ags/` entry may remain in
# `compositor_configs_skeleton_files` (a stale one templates INTO the unit tree
# through the live-bar link and silently diverges the live bar from the pinned
# tag), the retired in-place `platform/` dir must not exist, and both the
# `ags_platform` and `ags_apps` roles must install their pinned unit + shortcut
# (shared-ancestor for the platform, live-bar link + per-unit for the bar).
#
# THE IN-REPO TREE IS NOT REQUIRED. `dotfiles/config/ags/` is the dev/typecheck/
# test bridge and is being retired, so the gate does not require it. When it IS
# present (a developer checkout, or the gate's hermetic tests) the gate also
# reports the relative-import closure of `app.tsx` as a NOTE and still rejects a
# relative import into the retired in-place platform dir.
#
# WHY IT RUNS THROUGH uv AND NOT PLAIN python3. It parses the manifest as YAML
# (PyYAML ships with the provisioning project) rather than line-mangling it,
# the same `uv run --directory src/provisioning` mechanism
# `ansible-embedded-template-lint` uses. It needs no desktop stack, so it
# also runs in gates-ci. `../../scripts/` is required because --directory moves
# the interpreter's CWD. It FAILS rather than skipping when uv or PyYAML is
# unavailable: a coverage gate that quietly passes when its toolchain is
# missing is indistinguishable from one that passes.
deploy-coverage:
	uv run --directory src/provisioning python ../../scripts/deploy-coverage.py

# Dev dependencies for the VM harness (also auto-runs on first `make vm-*`
# when incus is missing and the terminal is interactive).
dev-deps:
	sudo pacman -S --noconfirm incus spice-gtk
	sudo systemctl enable --now incus
	sudo usermod -aG incus-admin $(USER)
	@echo "Log out/in for plain 'incus' use; 'make vm-*' activates the group itself (no re-login needed)."

# VM commands
vm-fresh:   dev/vm
	./dev/vm fresh
vm-up:      dev/vm
	./dev/vm up

vm-down:    dev/vm
	./dev/vm down

vm-console: dev/vm
	./dev/vm console

vm-shell:   dev/vm
	./dev/vm shell

vm-destroy: dev/vm
	./dev/vm destroy

vm-status:  dev/vm
	./dev/vm status

vm-verify:  dev/vm
	./dev/vm verify

vm-help:
	@echo "VM Usage:"
	@echo "  make vm-fresh    — wipe + recreate + full provision"
	@echo "  make vm-up       — start the VM"
	@echo "  make vm-down     — stop the VM"
	@echo "  make vm-console  — open SPICE graphical console"
	@echo "  make vm-shell    — get a shell inside the VM"
	@echo "  make vm-destroy  — delete the VM entirely"
	@echo "  make vm-status   — show VM state"
	@echo "  make vm-verify   — post-provision assertions inside the VM"
	@echo ""
	@echo "Inside the SPICE console:"
	@echo "  Ctrl+Alt+G       — grab/ungrab keyboard (Super key goes to VM)"
	@echo "  Ctrl+Alt+F       — toggle fullscreen"
	@echo ""
	@echo "VM keybindings (when keyboard is grabbed):"
	@echo "  Super+Enter      — terminal (kitty)"
	@echo "  Super+Q          — close window"
	@echo "  Super+M          — kill active window"
	@echo "  Super+V          — toggle floating"
	@echo ""
	@echo "Login: arch / arch"

# Dev dependencies for the VM harness (also auto-runs on first `make vm-*`
# when incus is missing and the terminal is interactive).
dev-deps:
	sudo pacman -S --noconfirm incus spice-gtk
	sudo systemctl enable --now incus
	sudo usermod -aG incus-admin $(USER)
	@echo "Log out/in for plain 'incus' use; 'make vm-*' activates the group itself (no re-login needed)."

# VM commands
vm-fresh:   dev/vm
	./dev/vm fresh
vm-up:      dev/vm
	./dev/vm up

vm-down:    dev/vm
	./dev/vm down

vm-console: dev/vm
	./dev/vm console

vm-shell:   dev/vm
	./dev/vm shell

vm-destroy: dev/vm
	./dev/vm destroy

vm-status:  dev/vm
	./dev/vm status

vm-verify:  dev/vm
	./dev/vm verify

vm-help:
	@echo "VM Usage:"
	@echo "  make vm-fresh    — wipe + recreate + full provision"
	@echo "  make vm-up       — start the VM"
	@echo "  make vm-down     — stop the VM"
	@echo "  make vm-console  — open SPICE graphical console"
	@echo "  make vm-shell    — get a shell inside the VM"
	@echo "  make vm-destroy  — delete the VM entirely"
	@echo "  make vm-status   — show VM state"
	@echo "  make vm-verify   — post-provision assertions inside the VM"
	@echo ""
	@echo "Inside the SPICE console:"
	@echo "  Ctrl+Alt+G       — grab/ungrab keyboard (Super key goes to VM)"
	@echo "  Ctrl+Alt+F       — toggle fullscreen"
	@echo ""
	@echo "VM keybindings (when keyboard is grabbed):"
	@echo "  Super+Enter      — terminal (kitty)"
	@echo "  Super+Q          — close window"
	@echo "  Super+M          — kill active window"
	@echo "  Super+V          — toggle floating"
	@echo ""
	@echo "Login: arch / arch"
