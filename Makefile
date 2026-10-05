.PHONY: bootstrap contracts-check gates audio-mock-parity ags-typecheck \
	audio-core-test audio-presentation-test pipewire-adapter-test \
	audio-session-runtime-test audio-panel-render-test audio-panel-gates dev-deps vm-fresh vm-up vm-down vm-console vm-shell vm-destroy vm-status vm-verify vm-help

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
# anti-invention check. Same commands as .github/workflows/gates.yml, so
# a green run locally is a green run in CI.
#
# audio-mock-parity is deliberately NOT in this list: it gates the in-flight
# redesign-ags-audio-panel change, and the panel is mid-rewire (tasks.md 6.0 is
# unchecked). Run it via `make audio-panel-gates`; it joins `gates` when the
# change lands and the panel is wired.
gates: contracts-check wifi-mock-parity speedtest-mock-parity speedtest-no-new-architecture

wifi-mock-parity:
	python3 scripts/wifi-mock-parity.py

speedtest-mock-parity:
	python3 scripts/speedtest-mock-parity.py

speedtest-no-new-architecture:
	python3 scripts/speedtest-no-new-architecture.py

audio-mock-parity:
	python3 scripts/audio-mock-parity.py

# Typecheck the AGS layer (tasks.md 6.5). `ags bundle` transpiles without
# typechecking, which is how a mis-cased shorthand property shipped through
# every other gate and died on startup.
#
# Baseline is 32: errors that exist on master today, untouched by this change
# (battery, tray, wifi-service, ...). Verified by diffing the error file list
# against master -- this change introduces none and removes 5. Do not raise the
# baseline to make the gate green; fix the error or record why it is foreign.
ags-typecheck:
	python3 scripts/ags-typecheck.py --baseline 31

# Audio panel gates, cheapest and most local first. Order matters: the unit
# suites are fast and stateless, then mock/code parity (the mock is the source
# of truth for the surface), then the render gate (is the panel wired at all),
# then the tsc gate (task 6.5, not yet implemented), then the repo-wide gates.
# The live checks in openspec/changes/redesign-ags-audio-panel/validation/ are
# NOT here: they change live playback/routing and must be run deliberately.
AUDIO_VALIDATION := openspec/changes/redesign-ags-audio-panel/validation

audio-core-test:
	node $(AUDIO_VALIDATION)/audio-core.test.mjs

audio-presentation-test:
	node $(AUDIO_VALIDATION)/audio-presentation.test.mjs

pipewire-adapter-test:
	node $(AUDIO_VALIDATION)/pipewire-adapter.test.mjs

audio-session-runtime-test:
	node $(AUDIO_VALIDATION)/audio-session-runtime.test.mjs

audio-panel-render-test:
	node $(AUDIO_VALIDATION)/audio-panel-render.test.mjs

audio-panel-gates: audio-core-test audio-presentation-test pipewire-adapter-test \
	audio-session-runtime-test audio-panel-render-test audio-mock-parity ags-typecheck

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
