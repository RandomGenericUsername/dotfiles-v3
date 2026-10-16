.PHONY: run lint test verify test-live

DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

run:
	ags run $(DIR)/app.tsx

# The AGS app bundles its TypeScript at startup; `ags bundle` is the
# compile-only gate (it transpiles but does not type-check).
lint:
	ags bundle $(DIR)/app.tsx /tmp/btop-theme-studio-bundle-check.js -r $(DIR) --gtk 4

# Pure-logic + generated-artifact tests (no desktop stack, no network).
test:
	node $(DIR)/tests/theme-keys.mjs
	node $(DIR)/tests/btop-conf.mjs
	node $(DIR)/tests/key-map.mjs
	node $(DIR)/tests/key-widgets-verify.mjs
	node $(DIR)/tests/theme-model.mjs
	node $(DIR)/tests/schematic.mjs
	node $(DIR)/tests/preview.mjs
	node $(DIR)/tests/targets.mjs

# Re-derive the key→widget map from the vendored btop source and check drift.
verify:
	python3 $(DIR)/tools/key_widgets.py $(DIR)/tools/btop_draw.v1.4.7.cpp \
		$(DIR)/tools/btop_theme.cpp $(DIR)/lib/key_widgets.json --verify

# Live preview engine tests (real btop on a pty; needs pyte).
test-live:
	uv run --with pyte --with pytest pytest $(DIR)/live/tests -q
