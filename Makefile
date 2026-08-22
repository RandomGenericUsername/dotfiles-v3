.PHONY: bootstrap dev-deps vm-fresh vm-up vm-down vm-console vm-shell vm-destroy vm-status

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
