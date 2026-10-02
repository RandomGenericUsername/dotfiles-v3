.PHONY: bootstrap contracts-check gates capture-types capture-typecheck dev-deps vm-fresh vm-up vm-down vm-console vm-shell vm-destroy vm-status vm-verify vm-help

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
# anti-invention check, then the capture GUI typecheck.
#
# THIS TARGET IS DEVELOPER-RUN, and that is deliberate, not an oversight.
# `.github/workflows/gates.yml` triggers on `push: branches: [main]`, but this
# repository's default branch is `master` and `main` does not exist on the
# remote, so the push trigger cannot fire. There is no working CI for any of
# these gates; repairing the trigger is a separate change the owner deferred
# (design.md §7.1). `capture-typecheck` additionally needs the desktop stack,
# which CI would not have anyway.
gates: contracts-check wifi-mock-parity speedtest-mock-parity speedtest-no-new-architecture capture-typecheck

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
