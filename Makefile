.PHONY: bootstrap dev-deps vm-fresh vm-up vm-down vm-console vm-shell vm-destroy vm-status vm-help

# Bootstrap the host machine (full provisioning)
bootstrap:
	./bootstrap.sh

# Dev dependencies for the VM harness
dev-deps:
	sudo pacman -S --noconfirm incus spice-gtk
	sudo systemctl enable --now incus
	sudo usermod -aG incus-admin $(USER)
	@echo "Log out/in for incus-admin group to take effect."

# VM commands
vm-fresh:   scripts/dev/vmtest/vm
	./scripts/dev/vmtest/vm fresh

vm-up:      scripts/dev/vmtest/vm
	./scripts/dev/vmtest/vm up

vm-down:    scripts/dev/vmtest/vm
	./scripts/dev/vmtest/vm down

vm-console: scripts/dev/vmtest/vm
	./scripts/dev/vmtest/vm console

vm-shell:   scripts/dev/vmtest/vm
	./scripts/dev/vmtest/vm shell

vm-destroy: scripts/dev/vmtest/vm
	./scripts/dev/vmtest/vm destroy

vm-status:  scripts/dev/vmtest/vm
	./scripts/dev/vmtest/vm status

vm-help:
	@echo "VM Usage:"
	@echo "  make vm-fresh    — wipe + recreate + full provision"
	@echo "  make vm-up       — start the VM"
	@echo "  make vm-down     — stop the VM"
	@echo "  make vm-console  — open SPICE graphical console"
	@echo "  make vm-shell    — get a shell inside the VM"
	@echo "  make vm-destroy  — delete the VM entirely"
	@echo "  make vm-status   — show VM state"
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
