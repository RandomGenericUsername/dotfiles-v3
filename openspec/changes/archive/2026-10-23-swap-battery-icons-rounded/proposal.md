## Why

The status-bar battery glyphs are the only bar artwork still drawn from the
old square-shouldered icon set, and they no longer match the rounded set the
owner downloaded for the rest of the bar. The mismatch is visible: the battery
ring and nub are near-square while the network / volume / tray glyphs around them
are rounded, so the bar reads as two different drawing families side by side.

The new artwork cannot simply be dropped into the asset tree. It arrives with
**hardcoded near-black fills** — `black`, `#0F0000`, `#141414`, `#0F0F0F` — and
neither half of the pipeline will touch a literal:

- ITR substitutes only `{{PLACEHOLDER}}` tokens
  (`PLACEHOLDER_VALUE_RE = r"\{\{(\w+)\}\}"` in
  `src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/domain/services.py`);
  a literal colour is passed through verbatim into the rendered SVG.
- The WCAG contrast guard rewrites only
  `PLACEHOLDERS = ("COLOR_FOREGROUND", "COLOR_JOIN")`
  (`src/runtime/src/runtime/domain/icon_contrast.py:42`), so a literal cannot be
  retargeted on a light wallpaper either.

Shipped as downloaded, the new icons would therefore render near-black forever —
including on the light-wallpaper case the guard exists to solve — and the
charging bolt would never pick up its accent colour.

## What Changes

- **Replace the ten `status-bar/battery/battery-{0,25,50,75,100}[-charging]/default/icon.svg`
  templates in place** with the owner's rounded set, after rewriting every
  literal colour to a palette placeholder (`{{COLOR_FOREGROUND}}` for the ring,
  nub and fill; `{{COLOR_ACCENT}}` for the charging bolt).
- **Nothing else.** No new variants, no parallel `rounded` style, no new groups,
  no `bar_mappings.states` edits.

### Why in place, and not as a parallel set

The `system-battery-{0,25,50,75,100}` variants (the Bluetooth device rows,
added by `bluetooth-row-battery-signal`) point at the **same five unplugged
templates** with a variant-level `COLOR_FOREGROUND: foreground` pin. Replacing
the templates updates those rows too, automatically and consistently.

Adding a parallel `rounded` style instead would leave the Bluetooth rows
rendering the OLD artwork directly beneath a NEW bar icon — the exact seam this
change exists to remove. In-place replacement also means `icons.yaml`,
`icons.json`, `verify_icons_samples` and its pinning test all stay untouched,
which is why this diff contains ten files and nothing else.

## The mapping — derived by measurement, not by filename

The ten source files are named `battery-empty-unplugged-default.svg` and `-1` …
`-9`. The numbering is **not** the charge ramp and it **wraps**: `-8`/`-9` are the
empty icons, not the fullest.

Calibration: the cavity is x ∈ [113, 756], width **643**, and the 100% icon's
fill spans exactly that. Each file's fill width ÷ 643 gives the level.

| source file | fill x-extent | fill width | level | assigned variant |
|---|---|---|---|---|
| `default.svg` | [118, 279] | 161 | 25% | `battery-25` |
| `-1.svg` | [118, 279] | 161 | 25% | `battery-25-charging` |
| `-2.svg` | [113, 434] | 321 | 50% | `battery-50` |
| `-3.svg` | [113, 379.83] | 266.83 | 50% ¹ | `battery-50-charging` |
| `-4.svg` | [113, 595] | 482 | 75% | `battery-75` |
| `-5.svg` | [113, 595] | 482 | 75% | `battery-75-charging` |
| `-6.svg` | [113, 756] | 643 | 100% | `battery-100` |
| `-7.svg` | [113, 756] | 643 | 100% | `battery-100-charging` |
| `-8.svg` | — no fill path | — | 0% | `battery-0` |
| `-9.svg` | — no fill path | — | 0% | `battery-0-charging` |

¹ `-3` is the one measurement that does not read 321 directly. See
design.md §"`-3` is the anomaly, and why it is still 50%".

Parity is exact: **odd = charging** (notch-cut filled ring + bolt), **even =
unplugged** (stroked ring, no bolt).

## Non-goals

- Not adding a `rounded` style, new variants, or new groups.
- Not touching `icons.yaml`, `icons.json`, `bar_mappings.states`,
  `verify_icons_samples`, or `plugged/default/icon.svg` — the in-place design
  exists precisely so these need no change.
- Not editing anything under `dotfiles/config/ags/components/`, `bar/`, or
  `style.css`.
- Not changing the widget's state machine or its thresholds
  (`getBatteryStateKey` in `bar/widgets/battery.tsx`) or any icon NAME.
- Not renaming `plugged`, which keeps its existing artwork.

## Impact

- 10 template files under `dotfiles/assets/icon-templates/status-bar/battery/`.
- 16 rendered variants change appearance: the 10 bar variants plus the 5
  `system-battery-*` copies that share the unplugged templates. `plugged` is
  unaffected.
- No behavioural change: variant names, thresholds, manifest, and generated
  projection are all byte-identical to `master`.

## Verification status

Verified mechanically: YAML parses; every `template:` path resolves; variant
names match what the widget requests; zero unfilled placeholders; zero literal
colours; geometry byte-identical to the source after normalising paint values;
all 16 variants substitute cleanly through the real ITR substitution service.

**Not verified: that they actually render.** Templates reach the runtime through
an Ansible `synchronize` into `<install>/icon-templates/`, and `sudo` requires a
password in this environment, so provision could not run. See design.md
§"What could not be verified".