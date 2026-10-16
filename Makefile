.PHONY: bootstrap contracts-check contract-pin-check gates gates-ci ci-gates-parity capture-types capture-typecheck capture-test capture-test-deps ags-platform-dev capture-hexagonal-gate dev-deps vm-fresh vm-up vm-down vm-console vm-shell vm-destroy vm-status vm-verify vm-help per-app-drift-symbol-suites

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
# first (it is the source of truth), then the capture domain unit tests, then
# the capture GUI typecheck, then the capture hexagonal structure gate, then the
# Ansible embedded-template lint, then the provisioning-shape coverage gate, then
# the per-app contract drift/symbol suites, then the check that keeps the CI
# workflow's job set equal to this list.
#
# `gates` is the DEVELOPER gate set and runs ALL of them, including the one that
# needs the desktop stack. Nothing is dropped for convenience: a gate that is not
# run here is a gate nobody runs.
GATES := contracts-check capture-test capture-typecheck \
         capture-hexagonal-gate ansible-embedded-template-lint \
         deploy-coverage ci-gates-parity per-app-drift-symbol-suites
gates: $(GATES)

# The CI gate set: every gate that can run on a stock `ubuntu-latest` runner.
#
# ONE gate is excluded -- `capture-typecheck` -- and it is excluded because it
# CANNOT run there, not because it is inconvenient there (openspec change
# `enable-ci-gates`, design.md §"Why capture-typecheck cannot run in CI"). It
# needs `ags` on PATH plus the Astal/GIR libraries, and `ags types` writes
# ~49 MB of machine-specific .d.ts describing THIS host's GTK/Astal version. A
# GitHub-hosted runner has no AGS, no Astal and no GTK4, so it has nothing to
# typecheck against. Its third-party error buckets are keyed to the literal path
# /usr/share/ags/js/ as well, which only exists on a provisioned desktop. It
# stays a developer gate. See the comment on the target below.
#
# This target exists so a developer can reproduce a CI run without the desktop
# stack, and so the split is stated in ONE place that cannot drift from the
# workflow: `.github/workflows/gates.yml` runs these as one job per gate.
gates-ci: $(filter-out capture-typecheck,$(GATES))

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

CAPTURE_DIR := src/gui-tools/capture-tool
# tsconfig.capture.json is HAND-WRITTEN and committed. `ags types -u` also
# writes its own tsconfig.json into $(CAPTURE_DIR) and overwrites it on every
# run, so the committed settings must live under a name that does not collide;
# the generated one is gitignored and is NOT what the typecheck reads.
CAPTURE_TSCONFIG := $(CAPTURE_DIR)/tsconfig.capture.json

# Generate the AGS/TypeScript type definitions for the capture GUI.
#
# REQUIRES THE DESKTOP STACK: `ags` on PATH plus the Astal/GIR libraries it
# describes. This target does nothing at all without them.
#
# `ags types -u` writes $(CAPTURE_DIR)/@girs/ (168 .d.ts files, ~49 MB),
# env.d.ts, tsconfig.json, and node_modules/{ags,gnim} symlinks into
# /usr/share/ags/js. All of it is gitignored and machine-specific — it
# describes the GTK/Astal version installed here and is rebuilt from scratch
# on demand rather than committed.
#
# TIMING: first run takes ~2-4 minutes and needs network (npx pulls
# ts-for-gir). Subsequent runs skip: the definitions only change when the
# system's libraries do, which is rare. Force a rebuild with `rm -rf
# $(CAPTURE_DIR)/@girs`.
capture-types:
	@if [ -d "$(CAPTURE_DIR)/@girs" ]; then \
		echo "==> capture-types: @girs/ already generated, skipping (rm -rf $(CAPTURE_DIR)/@girs to force)"; \
	else \
		echo "==> capture-types: generating GIR types (~2-4 min, needs network, requires the desktop stack)"; \
		ags types -d "$(CURDIR)/$(CAPTURE_DIR)" -u || exit 1; \
	fi

# Typecheck the capture GUI: zero errors allowed in our own files.
#
# WHY THIS GATE EXISTS: `ags bundle` TRANSPILES WITHOUT TYPE CHECKING.
# Verified — a file assigning a string to a `number` bundles with exit 0, so a
# wrong signature otherwise reaches production silently. A missing module IS
# caught; a wrong type is not (design.md §1.1).
#
# REQUIRES THE DESKTOP STACK (`ags` + Astal) and runs `capture-types` first.
# TIMING: ~30s once @girs/ exists; the first run pays the 2-4 min generation.
# It needs `tsc`, which this repo does not vendor — installed into an ignored
# ./node_modules on first run.
#
# The AGS runtime and gnim ship 28 errors of their own under
# /usr/share/ags/js. Those are third-party and tolerated BY LOCATION. Zero
# tolerance for src/gui-tools/capture-tool/. Errors in neither bucket fail the
# gate too — "tolerated because it was third-party" must never become a silent
# pass.
capture-typecheck: capture-types
	@if [ ! -x node_modules/.bin/tsc ]; then \
		echo "==> installing typescript (npm install --no-save, ignored by git)"; \
		npm install --no-save --no-package-lock typescript@5.9 >/dev/null || exit 1; \
	fi
	@# Module resolution for `ags/*` and `gnim` is PER-DIRECTORY: the tool needs
	@# its own gitignored `node_modules` symlinks, which `ags types` creates —
	@# but `capture-types` skips whenever `@girs/` exists, and the symlinks are
	@# written by that same run. So an environment that already has `@girs/`
	@# (a fresh clone seeded from another worktree, or a partially-restored
	@# tree) never gets them, and the gate dies with
	@# `Cannot find module 'ags/gtk4'` — MEASURED, and hit independently by two
	@# agents working in fresh worktrees on 2026-10-07. Same defect `3b283830`
	@# fixed in the retired bar typecheck; provisioned here too rather than
	@# relying on a skip decision made for a different reason.
	@mkdir -p "$(CAPTURE_DIR)/node_modules"
	@[ -e "$(CAPTURE_DIR)/node_modules/ags" ] || ln -sfn /usr/share/ags/js "$(CAPTURE_DIR)/node_modules/ags"
	@[ -e "$(CAPTURE_DIR)/node_modules/gnim" ] || ln -sfn /usr/share/ags/js/node_modules/gnim "$(CAPTURE_DIR)/node_modules/gnim"
	@echo "==> capture-typecheck: tsc --noEmit -p $(CAPTURE_TSCONFIG)"
	@log=$$(mktemp); \
	npx tsc --noEmit -p "$(CAPTURE_TSCONFIG)" > "$$log" 2>&1; \
	ours=$$(grep 'error TS' "$$log" | grep -F "$(CAPTURE_DIR)/" || true); \
	thirdparty=$$(grep 'error TS' "$$log" | grep -F '/usr/share/ags/js/' || true); \
	other=$$(grep 'error TS' "$$log" | grep -vF "$(CAPTURE_DIR)/" | grep -vF '/usr/share/ags/js/' || true); \
	echo "    tolerated third-party errors (/usr/share/ags/js): $$(printf '%s\n' "$$thirdparty" | grep -c . || true)"; \
	if [ -n "$$other" ]; then \
		echo "FAIL: errors in neither the capture tool nor the known ags runtime:"; \
		printf '%s\n' "$$other"; rm -f "$$log"; exit 1; \
	fi; \
	if [ -n "$$ours" ]; then \
		echo "FAIL: type errors in $(CAPTURE_DIR):"; \
		printf '%s\n' "$$ours"; rm -f "$$log"; exit 1; \
	fi; \
	echo "    OK: 0 errors in $(CAPTURE_DIR)"; \
	rm -f "$$log"

# Unit tests for the capture tool's extracted pure domain (workstream A4).
#
# WHY THIS GATE EXISTS: `mergeSettings`, `validateSettings`, `configDefaults`,
# the `loadUiState` merge, `audioToUi` and `GIF_SIZE_ARG` are the code a file
# move silently breaks. They encode the config/UI/backend vocabulary mismatches
# (`mic` vs `microphone`, `75%` vs `75`) whose failure mode is NOT an exception
# — it is a panel that quietly ignores the user's choice, or a backend argparse
# that rejects the flag after the fact. Before the A3 extraction this logic had
# ZERO direct coverage; the only thing exercising it was the Python CLI suite,
# which reads the same config through a DIFFERENT reader.
#
# WHY NODE'S BUILT-IN RUNNER AND NOT VITEST/JEST: the domain layer imports
# nothing from `ags/*` or `gi://*` — that purity is what makes it testable — so
# plain `node --test` runs it as-is. No bundler, no browser, no GTK, no network,
# no package.json, and no dependency to drift. Node strips the types natively
# (>= 22.18 unflagged for .ts; this repo's node is well past that). The suite is
# offline-capable by construction rather than by convention.
#
# DOES NOT NEED THE DESKTOP STACK — unlike capture-typecheck. TIMING: ~0.1s.
#
# The tests import the domain modules with an explicit `.ts` suffix because
# Node's ESM resolver does no extensionless lookup; the `->` suffix is why
# tsconfig.tests.json sets allowImportingTsExtensions.
#
# resolve-hooks.mjs covers the OTHER direction, added in A6: now that
# domain/cli-args.ts really imports domain/ui-state.ts (isGif + GIF_SIZE_ARG),
# the DOMAIN's own extensionless `./ui-state` import has to survive Node too.
# The hook teaches the test runner the one thing `ags bundle` already does, so
# the app sources stay idiomatic. See the file for why this is not solved by
# rewriting app imports to `./x.ts`.
CAPTURE_TS_TESTS := $(CAPTURE_DIR)/tests/ts

# The dependencies this gate needs, installed on demand, in the same shape
# `capture-typecheck` already uses for typescript (`npm install --no-save
# --no-package-lock`, into gitignored node_modules, no package.json committed).
# A gate that cannot run on a clean checkout is not a gate, so it DECLARES what
# it needs rather than inheriting whatever the machine happens to have. Both
# installs are idempotent: the guards skip the network round-trip when the
# package is already there.
#
# @types/node MUST land under $(CAPTURE_DIR)/tests/ and nowhere else. The app
# config pins `"types": []` (harden-capture-typecheck-config), so a reachable
# @types/node no longer widens the GJS program — but keeping it out of the
# typeRoots walk is the second half of that fix, not an optional extra. Moving
# it to the repo root or to capture-tool/ puts 66 of its files one
# accidentally-deleted pin away from being ambient in app code. tests/ is below
# the app config's directory, so the upward walk never descends into it. The
# path is gitignored explicitly (see .gitignore) because the capture tool's
# placement is per-file and a committed node_modules is a deployment hazard.
#
# A separate npm project (--prefix, no package.json) also means this install
# cannot PRUNE the root one: `npm install --no-save X` at the repo root removes
# previously --no-save'd packages, which is how a previous measurement in this
# repo's history turned into a false green.
capture-test-deps:
	@if [ ! -x node_modules/.bin/tsc ]; then \
		echo "==> capture-test: installing typescript (npm install --no-save, ignored by git)"; \
		npm install --no-save --no-package-lock typescript@5.9 >/dev/null || exit 1; \
	fi
	@if [ ! -d $(CAPTURE_DIR)/tests/node_modules/@types/node ]; then \
		echo "==> capture-test: installing @types/node under $(CAPTURE_DIR)/tests/ (gitignored)"; \
		npm install --no-save --no-package-lock --prefix $(CAPTURE_DIR)/tests @types/node@24 >/dev/null || exit 1; \
	fi

capture-test: capture-test-deps
	@echo "==> capture-test: node --test $(CAPTURE_TS_TESTS)"
	node --import ./$(CAPTURE_TS_TESTS)/resolve-hooks.mjs --test $(CAPTURE_TS_TESTS)/*.test.ts
	@echo "==> capture-test: tsc --noEmit -p $(CAPTURE_DIR)/tests/tsconfig.tests.json"
	npx tsc --noEmit -p "$(CAPTURE_DIR)/tests/tsconfig.tests.json" || exit 1
	@echo "    OK: 0 type errors in the domain unit tests"

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
# in the bar's repo.)
#
# NO DESKTOP STACK: plain `node` over the apps' pure modules and the committed
# contract, so the target is in gates-ci and runs on a stock runner. Node 22.18+
# is required for native .ts type-stripping; CI pins Node 24.
PER_APP_SUITES := \
	src/gui-tools/hypr-pano/tests/event-contract-drift.mjs \
	src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs \
	src/gui-tools/wallpaper-selector/tests/event-contract-drift.mjs

per-app-drift-symbol-suites: ags-platform-dev
	@command -v node >/dev/null || { echo "FAIL: per-app-drift-symbol-suites: node is not on PATH" >&2; exit 1; }
	@for suite in $(PER_APP_SUITES); do \
		echo "==> per-app-drift-symbol-suites: $$suite"; \
		node "$$suite" || exit 1; \
	done
	@echo "    OK: per-app contract drift + symbol suites green"

# Hexagonal structure + class-vocabulary gate for the capture GUI
# (scripts/capture-hexagonal-gate.py, design.md §5). "Refactor only, zero
# behaviour change" is otherwise unenforceable prose, so the layering
# invariants, the single pure request->argv translator, the absence of the
# dead pre-hexagonal scaffolding, per-file provisioning registration and the
# classic layout's CSS class vocabulary are all checked BY EXECUTION.
#
# RED UNTIL THE REFACTOR LANDS. The gate counts down to zero across the
# refactor-capture-tool-hexagonal workstreams and only goes green at A8. A red
# run in the meantime is the expected state, NOT a regression — read the
# per-check `ok` lines and the violation count rather than the exit code.
#
# Stdlib-only Python; needs no desktop stack (unlike capture-typecheck).
capture-hexagonal-gate:
	python3 scripts/capture-hexagonal-gate.py

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
