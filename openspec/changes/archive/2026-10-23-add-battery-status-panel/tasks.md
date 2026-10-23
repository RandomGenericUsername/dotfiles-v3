# Tasks — battery status panel

Two workstreams. **Both A (A1–A9) and B (B1–B9) are implemented.** B was built by
a second agent and then **reviewed** by a third, which is where B9 and the
corrections recorded against B1/B4 come from.

Design decisions the tasks depend on: `design.md` §2.2 (why `power-mode` is not a
bar group), §2.3 (why there are no `system-*` copies), §4.1 (why the tier→mode
grouping is declared), §5.1 (the `GetProfilesInfo` contract), §4.4 (the >24h
bound).

---

## Workstream A — foundation (implemented)

### A1. Power-mode icon templates — DONE

- [x] `dotfiles/assets/icon-templates/power-mode/powersave/default/icon.svg`
      (from `battery-empty-unplugged-default.svg`)
- [x] `dotfiles/assets/icon-templates/power-mode/balanced/default/icon.svg`
      (from `balance-law-svgrepo-com 1.svg`)
- [x] `dotfiles/assets/icon-templates/power-mode/performance/default/icon.svg`
      (from `car-engine-1 1.svg`)
- [x] Rewrite every hardcoded near-black fill to `{{COLOR_FOREGROUND}}`:
      `powersave` 0 → 4 placeholders (three `fill="black"` **plus** one
      `fill="#0F0000"` — see `design.md` §2.1), `balanced` 0 → 2,
      `performance` 0 → 3.
- [x] Geometry byte-identical: verified by masking the fill *value* in both the
      source and the template and diffing — the diff is empty. Path data,
      `transform`, `fill-rule`, `clip-rule`, `viewBox` and element order
      unchanged. Root `fill="none"` deliberately untouched.

### A2. ITR manifest group — DONE

- [x] `power-mode` group in
      `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`, modelled
      on `settings-panel`: `color_mappings: {COLOR_FOREGROUND: foreground}` plus
      three `variants` with `name` / `template` / `output`.
- [x] **No `bar_mappings`** — this is not a bar group (`design.md` §2.2).
- [x] **No `system-*` variants** (`design.md` §2.3). The reasoning is written into
      the manifest's own comment block so it travels with the file.
- [x] **`power-mode` NOT added to `BAR_GROUPS`**
      (`src/runtime/src/runtime/domain/icon_contrast.py:22-38`). Verified
      unchanged.
- [x] Three variants only — `powersave`, `balanced`, `performance` — one per
      declared MODE, which is what `glyphForTier` returns for all five tiers
      (`design.md` §2.4).

### A3. Regenerate the AGS manifest — DONE

- [x] Regenerate `dotfiles/config/ags/icons.json` with the repo's own generator
      (`(from_yaml) | to_nice_json(indent=2)`, ansible's filter plugin from the
      provisioning venv). Not hand-edited, and not a `json.dumps` approximation.
- [x] Verify the `battery` group is **byte-identical** before/after — 3823 bytes,
      identical.
- [x] Verify the only semantic change outside the new group is the pre-existing
      `settings-panel` staleness the regeneration corrected
      (`design.md` §2.5), and that it is inert at runtime
      (`icon-registry.ts` reads only `name` / `output` / `bar_mappings`).

### A4. Register the pure module for provisioning — DONE

- [x] `compositor_configs_skeleton_files`: add
      `dotfiles/config/ags/components/battery/presentation.ts`. Placement is
      **per-file**, so an unregistered source silently never deploys.
- [x] `compositor_configs_config_dirs`: ensure
      `…/ags/components/battery` (copy does not create dest parents for file
      sources).
- [x] Bump the skeleton-file assertion in
      `src/provisioning/tests/unit/test_compositor_configs_role.py` from **65 to
      66**, including the count's prose breakdown and the sorted `expected`
      list. The test stays strict — it is updated to the truth, not relaxed.

### A5. The test harness — DONE

- [x] `dotfiles/config/ags/tests/tsconfig.tests.json`. Module list is an
      **explicit** `include`, not a glob (`design.md` §3) — that is what keeps
      GTK out of the program and the suite runnable in CI.
- [x] `dotfiles/config/ags/tests/ts/resolve-hooks.mjs` — the capture tool's
      hook, adapted, with the "scratch-only, not in
      `compositor_configs_skeleton_files`" note.
- [x] `dotfiles/config/ags/tests/ts/fixtures/extensions-fixture.ts` +
      `resolve-hooks.test.ts`, so the hook is exercised rather than shipped as
      untested infrastructure (`design.md` §3.3).

### A6. The pure presentation logic — DONE

- [x] `dotfiles/config/ags/components/battery/presentation.ts` — zero
      `gi://` / `Gio` / `Gdk` / `ags` imports, zero I/O, no module-level mutable
      state.
- [x] Exactly the specified exports (`design.md` §4): the tier→mode model
      (`POWER_MODES`, `modeForTier`, `resolveMode`, `glyphForTier`,
      `railModes`, `profilesForMode`, `hasVariantChoice`,
      `variantToSelect`, `railMeta`) plus the time and percentage helpers.
      The declaration is the single place that says which tiers share a glyph.
- [x] `formatBatteryTime`: charging → `full in`, discharging → `remaining`;
      `seconds <= 0` → `Charging` / `Discharging` with no number;
      `> 24h` → the same fallback (`design.md` §4.4).
- [x] `formatDuration` returns `null` for `0`, negatives, and non-finite
      (`design.md` §4.2).
- [x] Resolution keys off the **stable tier**: `Superpowersave` → Powersave
      (leaf), `Ultraperformance` → Performance (engine). A rename does not move
      the art, because the name is not the key.
- [x] An undeclared tier falls back to the neutral `Unlisted` pseudo-mode and is
      labelled `unmapped tier`; it is never dropped or blanked.
- [x] `variantToSelect` resolves a mode click to the daemon's offered variant,
      preferring the current one; selection is by daemon index.
- [x] Extras for the panel: `MAX_RENDERED_SECONDS`, `clampPercentage`,
      `formatPercentage` (`design.md` §5).

### A7. Unit tests — DONE

- [x] `dotfiles/config/ags/tests/ts/battery-presentation.test.ts`: every
      `formatBatteryTime` branch, `formatDuration` including the `null` case, the
      literal declaration, tier→mode resolution for every live tier, the
      unknown-tier fallback and its label, the variant-selection rules, and a
      rename still resolving through its unchanged tier, plus the 24h boundary
      and the two percentage helpers.
- [x] 51 tests, **0 fail, 0 skipped**.

### A8. Wire the gate in — DONE

- [x] `ags-test` + `ags-test-deps` in the `Makefile`, in `capture-test`'s exact
      dependency shape (`npm install --no-save --no-package-lock`, gitignored
      `node_modules`, guarded so a present package skips the network, `--prefix`
      so it cannot prune the root install).
- [x] `ags-test-deps` installs `@types/node` under `dotfiles/config/ags/tests/`
      — a **sibling** of `tsconfig.tests.json`, because tsc's `typeRoots` walk
      starts at the config's directory and walks **up** (`design.md` §3.1).
- [x] `ags-test` **fails** rather than skips when `node`, `npx`, `tsc` or
      `@types/node` is unresolvable (`design.md` §3.2).
- [x] Added to `GATES` and to `gates-ci` (it needs no desktop stack, unlike
      `capture-typecheck`). `.PHONY` updated.
- [x] `.github/workflows/gates.yml`: one job, pinned `node-version: '24'`, no
      `npm install` step (the target declares its own deps), header counts
      updated from six-of-seven to seven-of-eight.

### A9. Verify nothing regressed — DONE

- [x] `make ags-test` — 51 pass / 0 fail / 0 skipped, 0 type errors.
- [x] `make capture-test` — **144 pass / 0 fail / 0 skipped**, unaffected.
- [x] `make capture-typecheck` — 0 errors.
- [x] `python3 scripts/capture-hexagonal-gate.py` — PASS, check 6 at
      **33 used / 28 styled**, untouched.
- [x] `capture pytest tests/` — 97.
- [x] `uv run --directory src/provisioning pytest tests/unit -q` —
      **0 failed / 720 passed**.
- [x] `scripts/wifi-mock-parity.py`, `scripts/speedtest-mock-parity.py` green.
- [x] `make gates-ci` all green.
- [x] No `node_modules` staged or committed (`.gitignore` extended for
      `/dotfiles/config/ags/tests/node_modules/`).

---

## Workstream B — panel UI (implemented, then reviewed)

### B1. Battery status panel widget

- [x] `components/battery/BatteryContent.tsx`. Every decision comes from
      `presentation.ts`; every effect lives in the widget (`design.md` §1).
- [x] `components/battery/state.ts` + `battery-icon.ts` — the pure state-key
      table shared by the bar icon and the panel header, so the two cannot draw
      different glyphs for the same reading.
- [ ] **Review correction.** The bar widget's tooltip had been choosing the state
      word and the word ORDER itself (`"Charging"` / `full in X` / `X remaining`
      inline) — the same fact `formatBatteryTime` decides, rendered a second
      time. Fixed by adding `formatBatteryStatusLine` to `presentation.ts`
      (derived from `formatBatteryTime`, so only the ORDER is added) and
      composing the tooltip from it. A tooltip that says "charging" where the
      panel says "Charging", or prints `0m remaining` for a missing estimate, is
      the exact drift this change's own split exists to prevent.

### B2. Popup windows

- [x] `components/battery/BatteryPopup.tsx`: catcher + panel, registered
      catcher-FIRST so the panel stacks above it. `keymode` NONE (nothing in the
      panel takes typed input) plus an Escape key controller.
- [ ] **Review correction.** Mutual exclusion with the **Wi-Fi** popup was
      missing in both directions. Both panels are OVERLAY/IGNORE windows with
      their own full-screen catcher, so two open at once means two live catchers
      and the top one swallows every click outside itself — the panel underneath
      is unreachable, not merely ugly. Fixed by closing the Wi-Fi popup from the
      battery icon's click handler, plus an effect in `BatteryPopup` that stands
      down if the Wi-Fi popup becomes visible. Done on the battery side
      specifically, so `bar/widgets/network.tsx` is untouched.

### B3. CSS

- [x] `style.css` rules for the panel: the two-level selector vocabulary
      (`.battery-mode-rail` / `.battery-mode-cell` / `.battery-mode-label`,
      `.battery-variant` / `.battery-variant-opt`, `.battery-rail-meta`)
      replaces the retired flat `.battery-profile-list` / `.battery-profile` /
      `.battery-profile-tier` rules. `.widget-icon` sizing convention reused for
      the bar glyph; `.battery-profile-icon` keeps the mode glyph at 24px.
- [x] `.power-profile-item` and `.power-profile-item.active` **deleted**, with a
      comment recording why they are gone rather than relocated. Nothing
      references them (`grep` proves it).
- [x] The `++` tiers are **variants of one mode**, not extra modes: the two
      Powersave tiers share the leaf, the two Performance tiers share the
      engine, and the tier is named once on the meta line. No badge, no
      per-tier glyph, no per-tier colour.

### B4. Registration / wiring

- [x] `app.tsx`: the two windows added in the same block and the same ORDER as
      the Wi-Fi pair; `popup-close` now closes the battery panel **and** Wi-Fi.
- [x] `bar/widgets/battery.tsx`: LEFT opens the panel, RIGHT launches
      `power-options-gtk`; the `<popover>` and its buttons are gone, and the
      power-profile D-Bus work moved to `services/power-service.ts` (it was built
      at widget-module scope with no teardown path). Battery bindings and the
      `is-present` visibility rule retained.

### B5. Provisioning registration for the new widget files

- [x] Five widget files + `services/power-service.ts` in
      `compositor_configs_skeleton_files`; the skeleton-file count in
      `src/provisioning/tests/unit/test_compositor_configs_role.py` pinned at
      **71** — in the count's prose breakdown, the sorted `expected` list, AND
      the ansible-execution variant's placed-file list. The exact-count pin
      stays exact: placement is per-file, so an unregistered file deploys
      nothing, and relaxing the assertion would convert that silence into a pass.
- [x] `…/ags/components/battery` added to `compositor_configs_config_dirs`.

### B6. Pure modules, if any

- [x] `components/battery/battery-icon.ts` added to
      `dotfiles/config/ags/tests/tsconfig.tests.json`'s explicit `include` list
      **by name**, with tests beside `battery-presentation.test.ts`. That edit is
      the statement that the module is pure.

### B7. Mock parity

- [x] `battery-popup-mockup.html` (six anchored states, drawing the two-level
      selector: multi-variant Performance/Powersave, the mono-variant Balanced
      with no control, daemon-absent, and a `++` variant selected) +
      `scripts/battery-mock-parity.py` (`design.md` §7). Wired into `make gates`
      / `gates-ci` as `battery-mock-parity` and into
      `.github/workflows/gates.yml` as its own job. `KNOWN_GAPS` is empty, and the
      harness has been seen to FAIL on perturbations.

### B8. The `icons.json` drift (found while regenerating)

- [x] Recorded in `design.md` §2.6: master's committed `icons.json` carried
      `null` for the four `wifi-signal-*` `color_mappings` its own YAML declares,
      and nothing asserted `icons.json == to_nice_json(icons.yaml)`.
- [x] **Decision: add the gate.** `scripts/icons-json-drift.py` regenerates and
      compares, using the role's OWN `to_nice_json` filter rather than a
      `json.dumps` reconstruction, and FAILS (never skips) when ansible is
      unimportable. Wired in as `icons-json-drift` in `gates`/`gates-ci` plus a
      CI job. Negative-tested by perturbing `icons.json` back to the historical
      drift.

### B9. Verify nothing regressed (reviewing agent)

- [x] `make gates-ci` — all green, including the two new gates.
- [x] `make ags-test` — 51 pass / 0 fail / 0 skipped, 0 type errors (was 37;
      the model tests replace the flat-list ones).
- [x] `make capture-test` — 144 pass / 0 fail / 0 skipped, unaffected.
- [x] `make capture-typecheck` — 0 errors (28 third-party tolerated).
- [x] `python3 scripts/capture-hexagonal-gate.py` — PASS, check 6 at
      **33 used / 28 styled**, untouched.
- [x] capture `pytest tests/` — 97.
- [x] `uv run --directory src/provisioning pytest tests/unit -q` — **0 failed /
      720 passed**.
- [x] `scripts/wifi-mock-parity.py` still green (the Wi-Fi panel is unchanged);
      `scripts/speedtest-mock-parity.py` green.
- [x] `git add -An | grep -c node_modules` → **0**.
- [ ] **NOT verified here, needs a human with the bar open**: real click paths,
      anchor position, and window stacking. One monitor, no input injection
      (`ydotool`/`wtype`/`xdotool`), `ags bundle` transpiles but does not
      typecheck, and the popup is `visible={false}` until opened. A pixel
      comparison is **unsound** for this panel (translucent over live desktop
      content) and is deliberately not quoted as evidence — see `design.md` §8.

---

## Explicitly out of scope for BOTH workstreams

- [ ] Adding `power-mode` to `BAR_GROUPS` — it would break the glyphs on dark
      glass (`design.md` §2.2).
- [ ] `system-*` duplicate variants for `power-mode` — there is no bar consumer
      for the group to be exempt from (`design.md` §2.3).
- [ ] Clamping an implausible duration to 24h and displaying the result
      (`design.md` §4.4).
- [ ] Inferring the tier→mode grouping from a `++` name suffix or from
      `base_profile` alone (`design.md` §4.1).
- [ ] Weakening, disabling or skipping any gate to reach green.