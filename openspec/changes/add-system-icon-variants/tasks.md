## 1. Manifest — 7 `system-*` variants (same templates, pinned color)

- [x] 1.1 `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`
  (`volume:` at `:397`, `microphone:` at `:421`): keep the existing 5 + 2
  variants byte-identical. Append after each group's variant list (2-space list
  indent; nested `color_mappings` at 8 spaces — mirror `camera-accent`
  `:249-253`). Add comment above each block:
  `# System-surface copies: same art as bar variants; variant-level pin exempts
  # them from the bar contrast guard.`
  - `system-muted` → `template: volume/muted/default/icon.svg` →
    `output: volume-system-muted.svg` + `color_mappings: {COLOR_FOREGROUND: foreground}`
  - `system-lowest` → `template: volume/lowest/default/icon.svg` →
    `output: volume-system-lowest.svg` + same pin
  - `system-low` → `template: volume/low/default/icon.svg` →
    `output: volume-system-low.svg` + same pin
  - `system-medium` → `template: volume/medium/default/icon.svg` →
    `output: volume-system-medium.svg` + same pin
  - `system-max` → `template: volume/max/default/icon.svg` →
    `output: volume-system-max.svg` + same pin
  - `system-mic-on` → `template: microphone/default/mic-on.svg` →
    `output: microphone-system-mic-on.svg` + same pin
  - `system-mic-off` → `template: microphone/default/mic-off.svg` →
    `output: microphone-system-mic-off.svg` + same pin
- [x] 1.2 Validate: `python -c "import yaml;
  yaml.safe_load(open('dotfiles/config/icon-template-color-scheme-mappings/icons.yaml'))"`
  passes; every `template:` path exists under `dotfiles/assets/icon-templates/`
  (`volume/{muted,lowest,low,medium,max}/default/icon.svg`,
  `microphone/default/mic-{on,off}.svg`).
- [x] 1.3 FORBIDDEN: no group-level `color_mappings` edits, no `bar_mappings`
  edits, no template file changes, no `panel-*` names, no new groups.

## 2. Manifest projection — regenerate `icons.json` (never hand-edit)

- [x] 2.1 Regenerate `dotfiles/config/ags/icons.json` via the established
  transform: `json.dumps(yaml.safe_load(open(icons.yaml)), indent=2,
  sort_keys=True) + "\n"` (same as `compositor_configs` manifest task).
- [x] 2.2 `git diff --stat` shows ONLY `icons.yaml` + `icons.json`; `icons.json`
  diff contains only the 7 added variant keys. `python -m json.tool
  dotfiles/config/ags/icons.json` passes.

## 3. Consumers — system surfaces to `system-*`, bar untouched

- [x] 3.1 `dotfiles/config/ags/components/sliders/VolumeSlider.tsx:66`:
  `registry.resolve("volume", variant())` →
  `registry.resolve("volume", "system-" + variant())`. Do NOT touch
  `levelVariant()` at `:32` (keeps returning bare names).
- [x] 3.2 `dotfiles/config/ags/audio/AudioPopup.tsx` — prefix every
  `volume`/`microphone` resolve with `"system-" +` (helper at `:97` unchanged):
  `:479` `"mic-off"`→`"system-mic-off"`, `:480` `"muted"`→`"system-muted"`,
  `:483` `"low"`→`"system-low"`, `:484`
  `levelVariant(false, clampVolume(level()))`→`"system-" + levelVariant(...)`,
  `:600` `"muted"/"low"`→`"system-muted"/"system-low"`, `:665`
  `"mic-off"/"mic-on"`→`"system-..."`, `:705` `glyphVariant()`→`"system-" +
  glyphVariant()`, `:806` `"low"`→`"system-low"`, `:861,887,892`
  `"mic-on"`→`"system-mic-on"`. Do NOT touch
  `media-transport` rows (`:362,379,397,445`).
- [x] 3.3 `dotfiles/config/ags/bar/widgets/audio.tsx` — NO CHANGE (stays bare,
  guard-eligible). Do NOT touch `audio/state.ts:656` (`levelVariant`).
- [x] 3.4 Grep proof: `systemIcon("volume", "` in `AudioPopup.tsx` shows only
  `system-` variants afterwards; same for `microphone` and `VolumeSlider.tsx`.

## 4. Gates + tests (additive only)

- [x] 4.1 `src/provisioning/ansible/roles/verify/vars/main.yml:367`
  (`verify_icons_samples`): append
  `{{ verify_state_current_dir }}/icons/volume-system-low.svg` and
  `{{ verify_state_current_dir }}/icons/microphone-system-mic-on.svg`.
  Do not remove the existing 3. Mirror in
  `src/provisioning/tests/unit/test_verify_role.py` fixtures if they assert
  the sample list.
- [x] 4.2 `src/runtime/tests/unit/test_derive_icon_contrast_overlay.py`: add ONE
  test mirroring the `camera-accent` exemption (`SPINE_ICONS:63-72`, assert
  `:281`): light palette flips bare `volume.COLOR_FOREGROUND` but `system-*`
  variant blocks + outputs are byte-identical in the overlay. No existing test
  may be modified.
- [x] 4.3 Pre-gates green: `uv run --directory src/runtime pytest -q`,
  `make contracts-check`, `itr list --mappings <icons.yaml> | grep -c system-`
  (= 7), `ags bundle` exit 0.

## 5. Docs (minimal)

- [x] 5.1 `docs/Adding an Icon — ITR and Provisioning Pipeline.md:728` (§14):
  replace `panel` wording with `system` for this scheme; append standing rule:
  "Bar resolves bare, system resolves `system-*`. Any group consumed on dark
  glass MUST expose `system-*` copies from day one."

## 6. Final gate — `make bootstrap` green (owner accept, NOT substitutable)

- [x] 6.1 Run `make bootstrap` on the host; it must complete green (assets →
  compositor_configs manifest + AGS deploy → runtime-seed render → verify).
- [x] 6.2 Light-wallpaper proof: `wallpaper set <light.png>` →
  `meta.json contrast.decisions` lists ONLY bare `volume`/`microphone`
  (never `system-*`); `volume-low.svg` carries the dark picked hex,
  `volume-system-low.svg` carries the bright `foreground` hex, no `{{` remains.
- [ ] 6.3 Dark-wallpaper proof: bare variants keep authored tokens (no churn);
  system outputs byte-identical across both wallpapers.
- [ ] 6.4 Owner gives green. Fast suites alone do NOT close this change.
