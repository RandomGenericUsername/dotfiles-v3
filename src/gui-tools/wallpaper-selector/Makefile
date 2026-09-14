.PHONY: run lint test

DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

run:
	ags run $(DIR)/app.tsx

lint:
	ags bundle $(DIR)/app.tsx /tmp/wallpaper-selector-bundle-check.js -r $(DIR) --gtk 4

test:
	node $(DIR)/tests/model.mjs
	node $(DIR)/tests/event-contract-drift.mjs
