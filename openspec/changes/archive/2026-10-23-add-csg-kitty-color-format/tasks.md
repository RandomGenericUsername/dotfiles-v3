## 1. Enum + template

- [ ] 1.1 `domain/enums.py` — add `KITTY = "kitty"` to `ColorFormat`
- [ ] 1.2 `defaults/templates/colors.kitty.j2` — plain kitty syntax: `background`, `foreground`, `cursor`, `color0`…`color15`, `selection_background`, `selection_foreground` (all `key #rrggbb` from the `ColorScheme`)
- [ ] 1.3 Confirm rendering path needs nothing else (`local_processor` already iterates `request.config.formats` → `colors.<value>.j2` → `colors.<value>`)

## 2. Tests

- [ ] 2.1 `tests/unit/domain/test_enums.py` — assert `ColorFormat.KITTY.value == "kitty"`
- [ ] 2.2 `tests/unit/adapters/test_template_catalog_loader.py` — a `colors.kitty.j2` in a templates dir is discovered as `ColorFormat.KITTY` (and an unknown `colors.bogus.j2` still raises `TemplatesValidationError`)
- [ ] 2.3 New `tests/unit/adapters/test_kitty_format.py` — render the template against a fixture scheme and assert the exact expected fragment (all 21 lines, `#rrggbb`, no `$`, no metadata)
- [ ] 2.4 `csg generate … --format kitty` (or the renderer directly) writes `colors.kitty` with the expected bytes

## 3. Verification

- [ ] 3.1 `uv run --directory src/cli-tools/color-scheme-generator pytest` green
- [ ] 3.2 Manual: `kitty +runpy 'from kitty.config import load_config; load_config(["/tmp/colors.kitty"])'` parses with **no** "Ignoring invalid config line" output and reports the expected `background`/`color0`
