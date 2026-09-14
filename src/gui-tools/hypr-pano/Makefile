.PHONY: run lint test

DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

run:
	ags run $(DIR)/app.tsx

lint:
	ags bundle $(DIR)/app.tsx /tmp/hypr-pano-bundle-check.js -r $(DIR) --gtk 4

test:
	node $(DIR)/tests/event-contract-drift.mjs
