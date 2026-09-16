.PHONY: run lint

DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

run:
	ags run $(DIR)/app.tsx

lint:
	ags bundle $(DIR)/app.tsx /tmp/notifications-bundle-check.js -r $(DIR) --gtk 4
