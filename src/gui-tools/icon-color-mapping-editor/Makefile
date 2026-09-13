.PHONY: run lint test

DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

run:
	ags run $(DIR)/app.tsx

lint:
	ags bundle $(DIR)/app.tsx /tmp/icme-bundle-check.js -r $(DIR) --gtk 4

test:
	node $(DIR)/tests/contract.mjs
	node $(DIR)/tests/svg.mjs
	node $(DIR)/tests/model.mjs
	node $(DIR)/tests/diff.mjs
	node $(DIR)/tests/templates.mjs
	node $(DIR)/tests/event-contract-drift.mjs
	node $(DIR)/tests/icme-saved-smoke.mjs
