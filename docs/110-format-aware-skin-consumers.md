# 110 — Format-aware skin consumers (Phase 3 design)

> **Status:** **delivered** (Phase 3A, 2026-11-11) — GTK3/GTK4/rofi consumers live; btop/kitty remain palette-only.

## TL;DR — the recommendation

1. **Do not widen `appearance.targets`.** That array is parsed by every AGS app
   through `ags-platform`, which hard-rejects any target whose path is not
   `appearance/<configDir>.css`
   (`ags-platform/ports/appearance.ts:839-853, 887-940`). Widening it is a
   breaking change hidden inside an otherwise additive field.
2. **Add a second, optional target family: `appearance.artifacts`**, one entry
   per non-CSS consumer:
   `{ "consumer": "rofi", "path": "appearance/rofi.rasi", "format": "rasi" }`.
   Existing `targets` stay frozen and remain the CSS family (AGS, wlogout,
   GTK3, GTK4).
3. **Use consumer aliases for GTK**: `gtk3` and `gtk4` are ordinary CSS
   consumers (`appearance/gtk3.css`, `appearance/gtk4.css`). Provisioning maps
   `config/gtk-3.0/appearance.css -> current/appearance/gtk3.css` and the same
   for 4.0. This avoids relaxing `configDir` to allow dots.
4. **First shipping slice:** contract (`v0.10.0`) + GTK3/GTK4 CSS templates +
   rofi `.rasi` template + runtime generic format plumbing + provisioning links
   + composition cutover. **btop stays palette-only** and **kitty stays
   palette-only** in this slice; the `.conf` format is accepted in the contract
   but no kitty template ships until the colour/unit rules below are resolved.
5. **No false live lane:** GTK3/4, rofi and wlogout are `launch`; kitty is
   `live` only via the existing `SIGUSR1` reloader; btop is `live` via
   `SIGUSR2` but palette-only; Hyprland/hyprpaper/hyprlock are out of scope.

## 1. Problem

### 1.1 The target path is CSS-only, by construction

The frozen generation manifest requires every appearance target to be
`{configDir, path}` with `path` exactly `appearance/<configDir>.css`:

- `contracts/schemas/generation-manifest.schema.json:233-253` — `target` has
  `additionalProperties: false`, required `configDir` + `path`, and the path
  regex `^appearance/[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.css$`.
- `contracts/generations.md:168, 234` — the spec restates the same rule.
- `dotfiles-runtime/src/runtime/adapters/generation_store.py:742-752` enforces
  it again at manifest self-check time.
- `dotfiles-runtime/src/runtime/domain/models.py:173-187` derives the consumer
  set by stripping `.css` from artifact names.
- `dotfiles-assets/scripts/validate-skins.py:126-128` freezes the only accepted
  template suffix: `<configDir>.gtk.css.j2`.
- `dotfiles-runtime/src/runtime/adapters/skin_expander.py:104, 408-434`
  discovers only `*.gtk.css.j2` and writes `<configDir>.css`.

So today a skin can only emit a GTK-style CSS sheet. A rofi theme is `.rasi`,
a kitty config is `.conf`, a btop theme is `.theme`; none can be named by the
contract, even though the *palette* layer already emits all four formats
(`current/colors.rasi`, `current/colors.kitty`, `current/colors.btop.theme`,
`current/colors.conf`; `dotfiles-runtime/src/runtime/adapters/generation_store.py:99-108`).

### 1.2 Why "fake CSS" is wrong

Forcing non-CSS consumers to read CSS does not merely look odd; it fails in
four different, mostly silent ways:

| Consumer | What happens if we hand it CSS | Evidence |
| --- | --- | --- |
| rofi | `alpha(@role, n)` is a parse error; role names containing `_` are invalid identifiers. `rofi -dump-theme` still exits **0** and only prints a `Rofi-WARNING: Failed to parse theme` on stderr. | Probe below: `rc=0` for both bad files |
| btop | btop reads `theme[key]="value"` key/value lines only. A CSS file yields no keys and btop silently falls back to `Default_theme`. | `theme-producer/src/theme_producer/adapters/projections/btop.py:1-27`; btop has no include/parser for CSS |
| kitty | kitty reads `key value` lines. CSS is not a config language; unknown keys are warnings, not failures. | Probe: `Ignoring unknown config key` on stderr, `rc=0` |
| GTK3 vs GTK4 | Same extension, different dialects: GTK3 rejects `var()` and `color-mix()`; GTK4 accepts them. One "CSS" target cannot honestly serve both. | Probe below |

That is the core reason for a format-aware target: **the format is part of the
contract, and validation must match the format**. A `.css` target that is
really a rofi fragment is a false claim that every gate would have to special
case.

### 1.3 What already works today (palette parity)

These are already real and must not be regressed:

- GTK3 `~/.config/gtk-3.0/gtk.css` imports `colors.css` →
  `current/palette/colors.gtk.css`
  (`dotfiles-provision/ansible/roles/config_links/tasks/_link_one.yml:120-137`).
- GTK4 `~/.config/gtk-4.0/gtk.css` does the same → `colors.adw.css`
  (`state_links/vars/main.yml:36-40`).
- rofi `~/.config/rofi/colors.rasi -> current/palette/colors.rasi` and
  `config.rasi` imports `../colors.rasi` (`dotfiles-assets/configs/rofi/launcher/config.rasi:1`).
- kitty `kitty.conf` includes `current/colors.kitty`
  (`dotfiles-assets/templates/kitty/kitty.conf.j2:1-3`).
- btop `btop.conf` selects `colors.btop.theme` by filename, exposed through
  `config/btop/themes/colors.btop.theme` (`dotfiles-assets/templates/btop/btop.conf.j2`).
- wlogout imports the generated `appearance/wlogout.css` last
  (docs/108 delivery evidence).

Phase 3 is therefore **not** "make palette work"; it is "let the skin project
its paint/rhythm/type into formats that are not CSS where that is honest".

## 2. Recommended contract shape

### 2.1 Two target families, one optional addition

```json
"appearance": {
  "tokensPath": "appearance/tokens.json",
  "targets": [
    { "configDir": "ags",        "path": "appearance/ags.css" },
    { "configDir": "gtk3",       "path": "appearance/gtk3.css" },
    { "configDir": "gtk4",       "path": "appearance/gtk4.css" },
    { "configDir": "wlogout",    "path": "appearance/wlogout.css" }
  ],
  "artifacts": [
    { "consumer": "rofi",  "path": "appearance/rofi.rasi",  "format": "rasi" }
  ]
}
```

Rules for `appearance.artifacts` (proposed, contracts `v0.10.0`):

- Optional array; absent in every pre-Phase-3 generation.
- `consumer`: `^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$` (the existing safe segment;
  no dots, which is why GTK uses `gtk3`/`gtk4`).
- `format`: enum `rasi | conf | theme`. **`css` is deliberately excluded**:
  every CSS sheet belongs to `targets`, so there is exactly one way to express
  a CSS consumer.
- `path`: exactly `appearance/<consumer>.<ext>` where `<ext>` is the canonical
  extension for the format (`rasi`, `conf`, `theme`). JSON Schema cannot
  cross-compare two properties in draft-07; the runtime and verify enforce the
  pair (same pattern already used for `intent.host == host.fingerprint`).
- `consumer` unique across `targets` and `artifacts`.
- No colours, structure, variants, transitions or app lists in the target;
  these are identities and paths only, matching the manifest's existing
  "opaque hashes and identities" rule.

### 2.2 Why `artifacts` and not a widened `targets`

`ags-platform` is the decisive consumer:

```ts
// ags-platform/ports/appearance.ts:887-940
const expectedPath = `appearance/${value.configDir}.css`;
if (value.path !== expectedPath) {
  manifestFail(source, `${path}.path`, `expected ... (the sheet for ${value.configDir})`);
}
```

Every AGS app parses the generation manifest through this function. If a rofi
target were appended to `targets`, every AGS app would reject the generation
and go dark. A separate family avoids touching that code path at all. The
platform's parser also ignores unknown keys on `appearance` (it only reads
`tokensPath`, `targets`, `mode`), so an old pin tolerates the new key.

The same separation makes `verify` and `generation_store` changes additive:
they add an artifacts loop next to the existing targets loop instead of
rewriting target semantics.

### 2.3 Versioning and migration from contracts `v0.9.0`

| Concern | Decision |
| --- | --- |
| Contract release | `v0.10.0` (minor; additive schema). `v0.9.0` tag is never moved. |
| Generation manifest `version` | stays **3**. The generation identity formula does not change; the CSS target family is byte-identical. |
| Schema status | `frozen v3` remains for `targets`; `artifacts` is documented as the additive v3.1 extension. |
| Existing manifests | Valid unchanged; `artifacts` is optional. |
| Existing CSS consumers | `appearance.targets` is untouched; AGS/wlogout behavior is byte-identical. |
| Old consumers seeing a new manifest | AGS parser ignores the extra `appearance.artifacts` key (evidence: `parseGenerationManifest` reads only the known keys). Provisioning verify reads `from_json` and asserts `targets`; it ignores extras. The **strict** JSON-Schema validator from `v0.9.0` would reject `artifacts`, so all in-tree validators must be re-pinned before the first artifact-emitting runtime ships. |
| Mixed-version rule | A runtime that can emit artifacts must pin the new contract; a composition must not pin that runtime while any in-tree strict validator is still on `v0.9.0`. Release tags remain the sync boundary (`SC-7`). |

**Rejected alternatives**

- Add optional `format` to existing targets. Still breaks the AGS parser, and
  makes `path` a union that every consumer must learn.
- Bump the manifest to version 4 with a new shape. Unnecessary churn for an
  additive family; it would also invalidate every existing generation for no
  consumer benefit.
- A separate per-consumer sidecar file outside the manifest. Hidden state that
  cannot be generation-verified; rejected by the v3 "manifest is the only
  app-list input" rule.

## 3. Runtime derivation and rendering

### 3.1 Template naming

Templates stay in `dotfiles-assets/skins/templates/` (one shared set for all
skins; the manifest is per skin). Add a suffix table:

| Suffix | Family | Format | Output | Example |
| --- | --- | --- | --- | --- |
| `<consumer>.gtk.css.j2` | `targets` | css | `<consumer>.css` | `gtk3.gtk.css.j2` → `appearance/gtk3.css` |
| `<consumer>.rasi.j2` | `artifacts` | rasi | `<consumer>.rasi` | `rofi.rasi.j2` → `appearance/rofi.rasi` |
| `<consumer>.conf.j2` | `artifacts` | conf | `<consumer>.conf` | `kitty.conf.j2` (deferred) |
| `<consumer>.theme.j2` | `artifacts` | theme | `<consumer>.theme` | reserved; not shipped |

Keeping `.gtk.css.j2` for CSS avoids any churn in the existing eight templates
and keeps `targets` exactly as it is. A `.rasi.j2` file is unambiguous because
the format token is a distinct filename segment.

**Fail-closed discovery:** today `skin_expander._discover_templates` silently
ignores any file that is not `*.gtk.css.j2`
(`dotfiles-runtime/src/runtime/adapters/skin_expander.py:408-434`). A new
format template shipped before the runtime update would therefore vanish with
no error. The runtime change must make any `*.j2` in the templates dir either
match a known suffix or fail the expansion.

### 3.2 Generic plumbing + per-format renderer

Do **not** add a `RofiAdapter`/`KittyAdapter` class. Keep the generic pipeline
and make the value/projection step a small table:

```text
discover templates → (family, format, output) per file
resolve tokens (mode + host) → one token document
render values per format → template text
publish:
  css      → <consumer>.css  in appearance/<consumer>.css
  rasi/... → <consumer>.<ext> in appearance/<consumer>.<ext>
manifest:
  css      → appearance.targets   {configDir, path}
  non-css  → appearance.artifacts {consumer, path, format}
```

The pipeline already renders every template once per generation
(`appearance.py:711-756`) and copies the composed artifacts into the generation
(`generation_store.py:583-600`). The new part is a format dispatcher at those
two points, not a new pipeline.

### 3.3 Token projection rules per format

The same token has different legal spellings per format. The renderer must be
format-aware, and the template gate must reject the wrong spelling.

| Token kind | CSS | rasi | conf | theme |
| --- | --- | --- | --- | --- |
| paint (`@role`, `alpha(@role, n)`) | verbatim; `@define-color` block provides roles | verbatim role names **hyphenated** (`@on-surface`); **no `alpha()`**; no literal hex | **not representable** (kitty has no `@role` variables) → do not project colours | **not representable** → palette-only |
| length (`border-width`, `radius`, `padding`) | `<n>px` | `<n>px` | needs an explicit unit rule (kitty uses pt/cells); defer | n/a |
| `font-weight` | unitless | unitless (or drop: Pango takes a family/size string) | unitless | n/a |
| `letter-spacing` | `<n>em` | `<n>em` is unverified in rofi → **omit** | n/a | n/a |
| `type.font-family` | verbatim | must be a Pango family string; safe | kitty `font_family`; safe | n/a |
| `type.size-*` | `<n>px` | Pango **points**, not px → **omit in Phase 3A** | kitty **points**, not px → **omit until a pt rule is approved** | n/a |

Consequences:

- **rofi** can honestly take solid palette paint and geometry. It cannot take
  `alpha()` or underscore names; probes below prove both are rejected.
- **kitty** cannot take any skin colour because `.conf` has no role variables
  and the skin output may not contain literal hex (`SC-5`). It can take
  `font_family` and geometry, but not `size-*` until we define a px→pt rule.
  Therefore kitty is **palette-only in Phase 3A**, with the `.conf` format
  reserved for a later, explicit type/unit decision.
- **btop** needs literal hex (`theme[key]="#rrggbb"`), which the skin plane
  forbids as skin output. btop remains palette-only permanently unless the
  contract gains a resolved-palette projection step (a much larger change).

### 3.4 Composition per format

- **css:** unchanged. `_compose_css` prepends `colors.gtk.css` + the
  `@define-color` role block, then the skin sheet (`appearance.py:400-416`).
  This is what makes `@role`/`alpha(@role, n)` resolve.
- **rasi:** do **not** prepend CSS. Emit the skin fragment only; it references
  the palette variables that `colors.rasi` already defines
  (`* { surface: #…; on-surface: #…; }`). The static rofi config imports
  `colors.rasi` first and the generated fragment after it, so the variables
  are in scope. This keeps the fragment free of literal hex.
- **conf:** no composition surface; a generated file is included after
  `colors.kitty`. Keep it paint-free.
- **theme:** no generated file in Phase 3A; the palette projection is the
  existing `colors.btop.theme`.

## 4. Per-consumer feasibility matrix

| Consumer | Format | Today | Skin surface that is honest | Refresh | Validation | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| **GTK3** (`gtk3`) | css | palette-only (`colors.css` import) | paint, geometry, type via `@define-color` + `alpha(@role,n)` | `launch` | GTK3 `CssProvider` + Broadway smoke | **Go** |
| **GTK4** (`gtk4`) | css | palette-only (`colors.css` import) | paint, geometry, type; GTK4 dialect (`var()`/`color-mix()` available, but a named-colour-only sheet is preferred) | `launch` | GTK4 `CssProvider` + temp-XDG app smoke | **Go, separate template** |
| **rofi** | rasi | palette-only (`colors.rasi`) | solid palette roles (hyphenated), radius, border, padding, spacing; **no alpha, no underscore, no type size** | `launch` | `rofi -dump-theme` **+ stderr assertion** | **Go** |
| **kitty** | conf | palette-only (`colors.kitty`, SIGUSR1) | `font_family` only; geometry/type need a unit rule; colours impossible without literal hex | `live` via `SIGUSR1` | `kitty +runpy` `load_config(..., accumulate_bad_lines=…)` + stderr | **Defer** (format reserved) |
| **btop** | theme | palette-only (`colors.btop.theme`, SIGUSR2) | none: key/value hex only, no reference to palette roles | `live` via `SIGUSR2` | 48-key allowlist + key/value parse | **Palette-only** |
| **wlogout** | css | generated `appearance.css` | paint/rhythm (delivered) | `launch` | GTK3 `CssProvider` + Broadway | **Already delivered** |
| **Hyprland/hyprpaper/hyprlock** | conf | palette `colors.conf` / wallpaper | out of scope for skin paint/rhythm in Phase 3 | compositor events | unchanged | **Out of scope** (`W-3.6`) |

### 4.1 GTK3 vs GTK4 details

GTK3 and GTK4 share `@define-color` and `alpha()`, but differ in dialect and
selector surface. Probe evidence (2026-11-10):

```text
$ python3 /tmp/gtkprobe2.py 3.0
gtk3.0 alpha ok
gtk3.0 mix FAIL ... 'color-mix' is not a valid color name
gtk3.0 var FAIL ... Invalid name of pseudo-class
$ python3 /tmp/gtkprobe2.py 4.0
gtk4.0 alpha ok
gtk4.0 mix ok
gtk4.0 var ok
```

They still require separate templates because:

- GTK4/libadwaita applications expect named colours (`window_bg_color`,
  `accent_bg_color`, …) or `--window-bg-color` custom properties; a GTK3
  widget-selector sheet is not a drop-in.
- A global `gtk.css` is read by **every** GTK app. Broad selectors can break
  unrelated apps. The GTK templates must therefore be restricted by an assets
  gate to a small allowlist: `@define-color` declarations and generic paint
  selectors (`window`, `headerbar`, `button`, `entry`, `popover`, `.card`,
  `*:focus` ring), never structure/layout/scale/size properties.
- `configDir` cannot be `gtk-3.0` (dots are excluded by the schema), hence the
  consumer aliases `gtk3`/`gtk4` and provisioning links that map the real
  config dirs.

### 4.2 rofi details

- Role names: the palette projection already hyphenates
  (`theme-producer/.../colors.rasi.j2`), and the static config uses
  `@surface-container`, `@on-surface`, etc. So the generated fragment must use
  hyphens too.
- `alpha()` is not a rofi function; a solid role is required.
- `rofi -dump-theme` exit status is **not** a validation signal. Observed:

```text
$ rofi -dump-theme -theme bad-alpha.rasi ; echo rc=$?
Rofi-WARNING: Failed to parse theme: "bad-alpha.rasi"
rc=0
$ rofi -dump-theme -theme bad-name.rasi ; echo rc=$?
Rofi-WARNING: Failed to parse theme: "bad-name.rasi"
rc=0
```

Validation must assert **no `Failed to parse theme` on stderr** and a
non-empty dump. This corrects the literal wording in `W-3.3` ("exit 0").

### 4.3 kitty details

- `colors.kitty` is a deliberate ANSI table with literal hex. It is palette,
  not skin, and it already reloads live (`SIGUSR1`).
- A generated `.conf` cannot reference `@role`; emitting hex would violate
  `SC-5`. It could only carry `font_family` today.
- kitty validates config with `load_config`; unknown keys only warn. Probe:

```text
$ kitty +runpy "from kitty.config import load_config; b=[]; load_config('kitty.good.conf', accumulate_bad_lines=b); print(b)"
[]
$ kitty +runpy "... load_config('kitty.badval.conf', accumulate_bad_lines=b) ..."
[BadLine(number=1, line='background notacolor', exception=ValueError(...))]
```

- `kitty --debug-config` does **not** exist (observed "Unknown flag"). The
  validator must use `+runpy` plus a stderr check for
  `Ignoring unknown config key`.

### 4.4 btop details

- 48 documented keys, emitted by `theme-producer`; no rhythm/type surface.
- btop resolves `color_theme` by filename against themes found at startup; it
  silently falls back to `Default_theme` on a miss
  (`dotfiles-assets/templates/btop/btop.conf.j2`).
- A skin `.theme` would need literal hex for every key. That is palette, not
  skin. **No btop artifact.**

### 4.5 wlogout / Hyprland status

- wlogout is the delivered CSS consumer; its paint/rhythm already follow the
  skin and host defaults (docs/108 `W-2.11`–`W-2.16`). No change.
- Hyprland/hyprpaper/hyprlock keep palette/background behavior. Phase 3 does
  not map gaps, borders or window structure to skin tokens (`W-3.6`, `H-3.3`).

## 5. Provisioning: stable links and verify

### 5.1 New stable links

All links are **provisioning-owned**, name `current/`, and are never repointed
by the runtime (docs/107 §2.7).

| Destination (spine) | Raw target | Consumer |
| --- | --- | --- |
| `config/gtk-3.0/appearance.css` | `state/current/appearance/gtk3.css` | GTK3 |
| `config/gtk-4.0/appearance.css` | `state/current/appearance/gtk4.css` | GTK4 |
| `config/rofi/appearance.rasi` | `state/current/appearance/rofi.rasi` | rofi |
| `config/kitty/appearance.conf` | `state/current/appearance/kitty.conf` | kitty (deferred) |

Existing palette links stay unchanged (gtk `colors.css`, rofi `colors.rasi`,
btop `colors.btop.theme`, kitty `current/colors.kitty`).

### 5.2 Static import order

The generated sheet must win the cascade/parse order, but never own structure:

- GTK3/4 `gtk.css`: `@import "colors.css";` **then**
  `@import "appearance.css";` last, per config dir. `config_links` currently
  appends only `colors.css`; it gains the second import idempotently.
- rofi `config.rasi`: `@import "../colors.rasi"` first, then
  `@import "../appearance.rasi"`; structure/geometry keep app-owned constants
  where the skin does not provide them.
- kitty `kitty.conf`: `include current/colors.kitty` then
  `include appearance.conf`; local overrides last if the user has them. (Only
  when the deferred kitty target lands.)
- wlogout: unchanged (`appearance.css` last).

### 5.3 Ownership and immutability

- `state_links` owns the new links (same role, same `state_links_consumers`
  table, new entries with `base: appearance`).
- The runtime owns only `state/generations/<gen>/appearance/*` and `current`.
  It must never write `config/<dir>/appearance.*` or anything under an app tag.
- `verify` must assert, for every new link: `islnk`, raw target exactly
  `current/appearance/<consumer>.<ext>`, no `generations` or `/apps/` substring,
  and a resolving regular file. It must also assert no runtime artifact exists
  inside an app tag (existing check) and no state symlink points into an app
  tag.
- `state_links` currently asserts "resolves under palette or appearance"; the
  new entries fit the same check with `base: appearance`.

## 6. Refresh lanes

| Consumer | Lane | Real mechanism | Why not more |
| --- | --- | --- | --- |
| GTK3 | `launch` | GTK loads `gtk.css` when an app starts; providers are installed per process | No system-wide GTK reload signal; assuming live is false |
| GTK4 | `launch` | same, plus libadwaita startup | same |
| rofi | `launch` | theme read when rofi opens | rofi is short-lived; no daemon |
| wlogout | `launch` | CSS read at launch | docs/108 `W-2.8` |
| kitty | `live` | `KittyReloader` enumerates PIDs and sends `SIGUSR1` (`dotfiles-runtime/src/runtime/adapters/kitty_reloader.py:77-120`) | real signal; vacuous success when no kitty runs |
| btop | `live` | `BtopReloader` sends `SIGUSR2` (`btop_reloader.py:105-146`) | palette-only but real |
| Hyprland | n/a | existing compositor reloaders | out of scope |

The reloaders are invoked from the one reconcile path
(`reconcile.py:660-670`), which the v3 `ConvergenceEngine` calls for every
committed generation (`generation_converge.py:106-124`). A kitty skin change
would therefore ride the existing live lane **if** kitty gets a `.conf`
target; until then the lane claim is palette-only.

**Rule:** the lane is a property of the consumer, not of the format. A `.rasi`
target is always `launch`; a `.css` GTK target is `launch`; only a consumer
with a verified signal handler may claim `live`.

## 7. Validation strategy

### 7.1 Format gates

| Format | Gate | Command / assertion | Evidence |
| --- | --- | --- | --- |
| css | GTK3 parse | `Gtk.CssProvider.load_from_data(generated)`, `combined`, and negatives (`var()` on GTK3) | GTK3 probe above |
| css | GTK4 parse | same with GTK4 typelib; `var()`/`color-mix()` positives | GTK4 probe above |
| css | real smoke | Broadway-backed app with temp `XDG_CONFIG_HOME`/`XDG_STATE_HOME`; no CSS warnings | docs/108 `W-2.7` method |
| rasi | dump + stderr | `rofi -dump-theme` → **stderr must not contain `Failed to parse theme`**, dump non-empty; negative fixture with `alpha()` and with `_` role fails | probes above |
| rasi | name check | every role reference matches `^[a-z0-9-]+$`; no `alpha(`; no `#` literals | template gate |
| conf (deferred) | kitty parse | `kitty +runpy` `load_config(path, accumulate_bad_lines=b)` → `b == []`; stderr has no `Ignoring unknown config key` | probe above |
| theme | btop key/value | parse `theme[key]="value"`; key ∈ the 48 documented keys; value is `#rrggbb`; no other lines | `theme-producer/.../btop.py` |
| all | no literal hex / structure / transitions | existing assets gate extended per format | `validate-skins.py` |

### 7.2 What "validation" must not do

- Do not trust a process exit code where the tool warns and continues
  (rofi, kitty unknown keys).
- Do not start a GUI as the only check; use provider-level parse plus one
  Broadway/temp-XDG smoke.
- Do not validate a generated file by reading the template: run the renderer,
  then parse the bytes.

### 7.3 Negative fixtures (mandatory)

1. `rofi.rasi.j2` containing `alpha(@surface, 0.5)` → gate fails.
2. `rofi.rasi.j2` containing `on_surface` → gate fails (hyphen rule).
3. `gtk3.gtk.css.j2` containing `var()` → GTK3 parse fails (expected).
4. `gtk4.gtk.css.j2` containing a GTK3-only pseudo-class → GTK4 parse fails.
5. Any template containing literal hex, `transition`, `structure`,
   `variant` or a `layout.` placeholder → fails.
6. Unknown template suffix under `skins/templates/` → runtime expansion fails
   (not silently ignored).

## 8. Phased implementation order and acceptance criteria

Each slice is a separate repo/ticket/release; release tags are the sync
boundary (`SC-7`). No slice may pin a branch.

### Phase 3A-1 — contracts `v0.10.0`

- **F-1.1** `appearance.artifacts` is optional in
  `generation-manifest.schema.json`; each item requires `consumer`, `path`,
  `format`; `format` enum is `rasi|conf|theme` (CSS stays exclusively in
  `targets`); `consumer` is unique across both families.
- **F-1.2** The runtime/verify extension rule `path == appearance/<consumer>.<ext>`
  is documented and enforced (schema cannot express cross-property equality).
- **F-1.3** Positive/negative fixtures: CSS-only manifest (unchanged), rasi
  manifest, duplicate consumer, wrong extension, unknown format.
- **F-1.4** `v0.9.0` fixtures remain valid; no existing tag moves.

### Phase 3A-2 — assets

- **F-2.1** `gtk3.gtk.css.j2`, `gtk4.gtk.css.j2`, `rofi.rasi.j2` ship for every
  bundled skin; `required_targets` names `gtk3`, `gtk4`, `rofi` (or the
  artifact equivalent) and a missing template fails `validate-skins`.
- **F-2.2** Format-specific gates: no `alpha()`/`_` role in rasi; no
  `var()`/`color-mix()` in gtk3; no forbidden structure/hex/transition.
- **F-2.3** GTK selector allowlist enforced; no layout/size/structure
  properties in the generated sheets.
- **F-2.4** `rofi.rasi.j2` has no literal hex and only solid roles.

### Phase 3A-3 — runtime

- **F-3.1** Template discovery maps suffix → (family, format, output) and
  fails closed on an unknown suffix.
- **F-3.2** A format value renderer implements the §3.3 table; CSS output is
  byte-identical to `v1.2.0` for existing skins.
- **F-3.3** `appearance.artifacts` is published in the generation manifest;
  `AppearanceEntry`/`skin_config_dirs` remain CSS-only and a new artifact list
  is derived separately.
- **F-3.4** The generation store copies artifacts into
  `appearance/<consumer>.<ext>` and `verify()` requires every declared artifact.
- **F-3.5** No production per-consumer adapter; one dispatcher, table-driven.

### Phase 3A-4 — provisioning `v0.1.xx`

- **F-4.1** `state_links_consumers` gains gtk3/gtk4/rofi `appearance` links.
- **F-4.2** Static `gtk.css` imports `appearance.css` **last**; rofi
  `config.rasi` imports `appearance.rasi` last.
- **F-4.3** `verify` asserts raw target, current-only resolution, no
  generation/app-tag path, and regular-file resolution for every new link.
- **F-4.4** An AGS app tag remains immutable (no runtime artifact inside).

### Phase 3A-5 — composition cutover

- **F-5.1** Pins contract `v0.10.0`, runtime/assets/provision releases in the
  documented order; `make gates-ci`, `make deploy-coverage`.
- **F-5.2** Live: GTK3/GTK4 parse the combined sheets; rofi `-dump-theme`
  produces no stderr warning; a rofi launch shows the skin geometry/colour.
- **F-5.3** Reload lanes documented as `launch`; no false live claim.
- **F-5.4** One-time template-hash churn and a full appearance refresh are
  recorded (adding three shared templates changes every skin entry hash).

### Phase 3B — deferred formats

- **F-6.1** kitty `.conf`: decide a colour strategy (impossible without hex →
  palette-only) and a px→pt rule; if approved, add
  `kitty.conf.j2`, the `appearance.conf` link and `live` lane; validate with
  `kitty +runpy`.
- **F-6.2** btop `.theme`: remains palette-only unless a resolved-palette
  projection step is designed; no skin template.

**Recommended order:** F-1 → F-3 (runtime can read/validate the new shape) →
F-2 (templates) → F-4 (links) → F-5 (cutover). Assets before runtime would be
silently ignored; runtime after assets must already fail closed on unknown
suffixes.

## 9. What is possible today vs what needs changes

### 9.1 Possible today (no contract/runtime/assets/provisioning change)

- Palette parity for GTK3, GTK4, rofi, kitty, btop (verified in §1.3).
- wlogout generated CSS skin (delivered).
- Manual local overrides (e.g. a user-authored rofi or kitty fragment) — but
  not part of the generation/verify model.

### 9.2 Needs a contract change

- A format-aware target family (`appearance.artifacts`) with
  `consumer/path/format`.
- The path/format consistency rule and the `css|rasi|conf|theme` enum.
- Version bump and fixtures.

### 9.3 Needs an assets change

- `gtk3.gtk.css.j2`, `gtk4.gtk.css.j2`, `rofi.rasi.j2` (and later, if
  approved, `kitty.conf.j2`).
- Per-format template gates (no alpha/underscore in rasi; GTK dialect;
  selector allowlist) and `required_targets`.
- One-time template-hash churn.

### 9.4 Needs a runtime change

- Suffix→format discovery + fail-closed unknown suffix.
- Per-format value renderer and the artifact publication path.
- Manifest `artifacts`, generation-store copy/verify, artifact list on the
  entry model.
- Tests proving CSS output is byte-identical.

### 9.5 Needs a provisioning change

- gtk3/gtk4/rofi `appearance` stable links and last-position imports.
- `verify` raw-target/current-only/no-tag assertions.
- No runtime link ownership.

## 10. Risks, non-goals, migration and rollback

### 10.1 Risks

| Id | Risk | Handling |
| --- | --- | --- |
| R-1 | Appending non-CSS to `targets` breaks every AGS app | Separate `appearance.artifacts` family; never widen `targets` |
| R-2 | Old strict schema validators reject `artifacts` | Re-pin every in-tree validator in the contract slice before an artifact-emitting runtime ships; AGS parser ignores the key (evidence §2.2) |
| R-3 | GTK global CSS breaks unrelated apps | Selector allowlist; prefer named colours + generic paint; gate rejects structure/size/layout |
| R-4 | rofi silently accepts an invalid theme (`rc=0`) | Stderr assertion in the gate; negative fixtures |
| R-5 | kitty unknown keys are warnings only | `accumulate_bad_lines` + stderr check; defer kitty until semantics exist |
| R-6 | Unit mismatch (px vs Pango/kitty pt) | Do not project `size-*` in Phase 3A; define a rule before shipping type in rasi/conf |
| R-7 | Literal-hex leakage in non-CSS formats | rasi uses `@role`; conf/theme cannot reference roles → no colour projection; gate rejects `#` |
| R-8 | Template churn creates a full refresh | Document the one-time churn (`W-2.10` precedent) |
| R-9 | Assets ship a template the runtime ignores | Runtime fails closed on unknown suffix; release order F-3 before F-2 |
| R-10 | `consumer` vs real config dir divergence (`gtk3`/`gtk-3.0`) | Explicit provisioning map table; verify asserts the real path |

### 10.2 Non-goals

- A live GTK-wide reload lane; there is no such mechanism.
- Skin ownership of layout, icons, wallpaper, structure, variants, transitions.
- Mapping Hyprland gaps/borders/window structure into skin tokens.
- A btop rhythm/typography surface; btop has none.
- Resolving palette hex inside the runtime to invent `.conf`/`.theme` colours.
- A second appearance pipeline or per-consumer adapter classes.

### 10.3 Migration and rollback

- **Forward:** additive `artifacts`; skins that do not ship non-CSS templates
  produce no artifacts and remain valid. Existing generations and CSS targets
  are byte-identical.
- **Rollback:** re-pin the previous contract/runtime/assets/provisioning tags
  and remove the new provisioning links. New generations may still contain
  `appearance.artifacts`; old consumers ignore it, and GC removes unreferenced
  generations. No state migration is needed.
- **Stable links** are provisioning-owned and never repointed; removing them is
  a provisioning rollback, not a runtime action.

## 11. Open questions for review

1. **Name of the family.** `appearance.artifacts` is proposed; `formats` or
   `nonCssTargets` are alternatives. The decision matters less than keeping it
   out of `targets`.
2. **GTK selector allowlist.** Which exact selectors are safe across GTK3
   apps and GTK4/libadwaita? The design recommends named colours plus a small
   generic set; assets must freeze the list.
3. **rofi type.** Is dropping `font` from the skin acceptable for Phase 3A, or
   do we need a Pango-point projection rule? Recommendation: drop it now.
4. **kitty type.** Is a documented px→pt approximation acceptable, or should
   kitty remain palette-only indefinitely? Recommendation: defer.
5. **`theme` format.** Keep it in the enum for future btop use, or omit it
   until a resolved-palette projection exists? Recommendation: keep the enum
   but ship no template.
6. **Manifest version.** Staying at 3 is recommended; confirm no consumer
   requires a version bump to treat `artifacts` as legal.

## 12. Definition of done for this design

1. Review approves the two-family target shape and the `gtk3`/`gtk4` alias
   decision.
2. Review approves rofi's solid-palette/geometry-only scope and the kitty/btop
   deferrals.
3. The tracking ticket is opened and the first implementation slice is named
   (contract `v0.10.0`).
4. No schema, runtime, asset, provisioning or composition change is part of
   this document.

## Appendix A — probe log (2026-11-10)

```text
# rofi — exit 0 is not validation
$ rofi -dump-theme -theme bad-alpha.rasi ; echo rc=$?
Rofi-WARNING: Failed to parse theme: "bad-alpha.rasi"
rc=0
$ rofi -dump-theme -theme bad-name.rasi ; echo rc=$?
Rofi-WARNING: Failed to parse theme: "bad-name.rasi"
rc=0
$ rofi -dump-theme -theme good-solid.rasi ; echo rc=$?
rc=0   # no stderr warning

# GTK dialects
gtk3.0 alpha ok; gtk3.0 mix FAIL ('color-mix' is not a valid color name); gtk3.0 var FAIL
gtk4.0 alpha ok; gtk4.0 mix ok; gtk4.0 var ok

# kitty
$ kitty +runpy "from kitty.config import load_config; b=[]; load_config('kitty.good.conf', accumulate_bad_lines=b); print(b)"
[]
$ kitty +runpy "... load_config('kitty.badval.conf', accumulate_bad_lines=b) ..."
[BadLine(number=1, line='background notacolor', exception=ValueError("Invalid color name: 'notacolor'"), ...)]
$ kitty --debug-config
Unknown flag: --debug-config use --help.

# live target files (read-only)
~/.config/rofi/colors.rasi -> ~/.local/state/dotfiles/current/palette/colors.rasi
~/.config/btop/themes/colors.btop.theme -> .../current/palette/colors.btop.theme
~/.config/kitty/kitty.conf: include .../current/colors.kitty
~/.config/gtk-3.0/gtk.css: @import "colors.css";
~/.config/gtk-4.0/gtk.css: @import "colors.css";
```

## Appendix B — exact code anchors

- Contract target rule: `contracts/schemas/generation-manifest.schema.json:233-253`;
  `contracts/generations.md:168, 231-236`.
- AGS hard parse: `ags-platform/ports/appearance.ts:839-853, 887-940`.
- Runtime target derivation: `dotfiles-runtime/src/runtime/domain/models.py:173-187`.
- Runtime template suffix: `dotfiles-runtime/src/runtime/adapters/skin_expander.py:104, 408-434`.
- Runtime composition: `dotfiles-runtime/src/runtime/adapters/appearance.py:400-416, 711-756`.
- Generation publication: `dotfiles-runtime/src/runtime/adapters/generation_store.py:583-600, 742-770`.
- Provisioning links: `dotfiles-provision/ansible/roles/state_links/vars/main.yml`;
  static GTK import: `config_links/tasks/_link_one.yml:120-137`.
- Reloaders: `kitty_reloader.py:77-120`, `btop_reloader.py:105-146`,
  invocation at `reconcile.py:660-670`.
- Asset template gate: `dotfiles-assets/scripts/validate-skins.py:48-56, 126-128, 1114-1188`.
