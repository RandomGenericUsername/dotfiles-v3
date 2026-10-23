# Tasks: add-capture-settings

GUI and backend MAY proceed in parallel (config schema + precedence frozen in `design.md`); converge on the deploy + live smoke.

- [ ] 1. GUI: settings view (three groups, path/toggle/pill controls reusing main-view patterns), footer entry point, `Escape`/back navigation hierarchy, config read/write + validation + dir creation, stylesheet additions from the mockup recipe; NO new icon variants (text-labeled entry point)
- [ ] 2. Backend: config loading with fallbacks, pattern-based default paths, `--cursor` plumb-through (verify grim + recorder flags on-machine, record outcomes), notification gating, backend-name readout; unit tests mirroring the existing CLI suite (fallbacks, precedence, pattern, cursor, gating)
- [ ] 3. Wire initial-selection precedence (last-used > settings > hardcoded) and save-applies-forward semantics (no stomping live selections)
- [ ] 4. Verify: `ags bundle` clean; new + existing test suites green; provisioned deploy (gui-tools + cli_tools placement); live smoke — change the screenshot folder, capture, confirm location; toggle notifications off, capture, confirm silence; corrupt-config run degrades to defaults
