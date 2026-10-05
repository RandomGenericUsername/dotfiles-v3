.PHONY: bootstrap contracts-check gates gates-ci capture-types capture-typecheck capture-test capture-test-deps capture-hexagonal-gate dev-deps vm-fresh vm-up vm-down vm-console vm-shell vm-destroy vm-status vm-verify vm-help

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
	uv run --directory src/runtime pytest tests/unit/test_contract_schema_conformance.py tests/unit/test_event_contract_conformance.py tests/unit/test_event_contract_drift.py tests/unit/test_history_trigger_enum.py -q

# Every executable gate, in the order a reviewer should read them: contract
# first (it is the source of truth), then mock/code parity, then the
# anti-invention check, then the capture domain unit tests, then the capture GUI
# typecheck, then the capture hexagonal structure gate.
#
# `gates` is the DEVELOPER gate set and runs ALL SEVEN, including the one that
# needs the desktop stack. Nothing is dropped for convenience: a gate that is not
# run here is a gate nobody runs.
GATES := contracts-check wifi-mock-parity speedtest-mock-parity \
         speedtest-no-new-architecture capture-test capture-typecheck \
         capture-hexagonal-gate
gates: $(GATES)

# The CI gate set: every gate that can run on a stock `ubuntu-latest` runner.
#
# ONE gate is excluded — `capture-typecheck` — and it is excluded because it
# CANNOT run there, not because it is inconvenient there (openspec change
# `enable-ci-gates`, design.md §"Why capture-typecheck cannot run in CI"). It
# needs `ags` on PATH plus the Astal/GIR libraries it describes, and `ags types`
# writes ~49 MB of machine-specific .d.ts describing THIS host's GTK/Astal
# version. A GitHub-hosted runner has no AGS, no Astal and no GTK4, so the target
# has nothing to typecheck against. Its third-party error bucket is keyed to the
# literal path /usr/share/ags/js/ as well, which only exists on a provisioned
# desktop. It stays a developer gate. See the comment on the target below.
#
# This target exists so a developer can reproduce a CI run without the desktop
# stack, and so the split is stated in ONE place that cannot drift from the
# workflow: `.github/workflows/gates.yml` runs these six as one job per gate.
gates-ci: $(filter-out capture-typecheck,$(GATES))

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
# /usr/share/ags/js. Those are third-party and tolerated BY LOCATION, exactly
# as scripts/wifi-mock-parity.py uses its ALLOWLIST. Zero tolerance for
# src/gui-tools/capture-tool/. Errors in neither bucket fail the gate too —
# "tolerated because it was third-party" must never become a silent pass.
capture-typecheck: capture-types
	@if [ ! -x node_modules/.bin/tsc ]; then \
		echo "==> installing typescript (npm install --no-save, ignored by git)"; \
		npm install --no-save --no-package-lock typescript@5.9 >/dev/null || exit 1; \
	fi
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

wifi-mock-parity:
	python3 scripts/wifi-mock-parity.py

speedtest-mock-parity:
	python3 scripts/speedtest-mock-parity.py

speedtest-no-new-architecture:
	python3 scripts/speedtest-no-new-architecture.py

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
