# 111 — Host rounding granularity

> **Status:** **design accepted — skin-delegated rectangle model** (2026-11-11).
> This revision supersedes the outer-only decision recorded in commit
> `6f517508`. No schema, runtime, assets, provisioning, composition or tag
> change is made by this document; implementation slices are named below.
> **Epic:** [`SKIN-CONSUMERS`](./epics/SKIN-CONSUMERS.md)
> **Related:** [`108`](./108-non-ags-skin-consumers.md) ·
> [`109`](./109-hyprland-host-defaults.md) ·
> [`110`](./110-format-aware-skin-consumers.md)
> **Tracking ticket:** [`REQ-111`](./tickets/REQ-111-host-radius-granularity.md)
> **Live baseline observed:** Hyprland `0.57.2`; terminal-host generation
> `af4c31a8…` with delegated host radius `9`; current `terminal` generation
> `95f418e3…` with explicit radius `0`.

## Question

Should Hyprland `decoration:rounding` reach **inner consumer components** —
`surface.card.radius`, `surface.control.radius`, `surface.cell.radius`,
`surface.pill.radius` — or only the outer surface role it feeds today,
`surface.panel.radius`?

Observed with the existing panel-only policy and live rounding `9`:

| Consumer slot | Token | Rendered radius |
| --- | --- | ---: |
| rofi `window` | `surface.panel.radius` | 9px |
| rofi `mainbox` | `surface.card.radius` | 0px |
| rofi `inputbar` | `surface.control.radius` | 2px |
| rofi `element` | `surface.cell.radius` | 0px |
| wlogout `button` | `surface.panel.radius` | 9px |

The 0/2/0 inner values are the result of the previous outer-only rule, not a
resolution failure. This revision changes that rule deliberately.

## Decision

**Adopt a skin-delegated rectangle model.** Hyprland `decoration:rounding` is a
*rectangle corner* scalar. A skin may delegate its **rectangular surface roles**
to that scalar; it never delegates `surface.pill.radius`, and it never has to
delegate at all.

### Host-delegable set (closed)

| Skin token | Host source | Meaning |
| --- | --- | --- |
| `surface.panel.radius` | `decoration:rounding` | outer window/panel rectangle |
| `surface.card.radius` | `decoration:rounding` | card/inset rectangle |
| `surface.control.radius` | `decoration:rounding` | input/button rectangle |
| `surface.cell.radius` | `decoration:rounding` | row/list cell rectangle |
| `surface.panel.border-width` | `general:border_size` | outer frame width |

**Not delegable:** `surface.pill.radius` (always the skin's explicit capsule
value), `surface.card.border-width`, `surface.control.border-width`,
`surface.cell.border-width`, padding, spacing/gaps, type and all colour/paint
tokens. The set is closed: adding another path is a new contract decision.

### Opt-in rules

1. **The skin decides.** A skin's root `[host].inherit` may list any subset of
   the five delegable paths. No path follows the host unless that skin listed
   it.
2. **The agreed bundled policy** is: `glass`, `paper` and `terminal-host` opt
   in to the full rectangle set (all four radii plus panel border-width);
   `terminal` and `flat` remain explicit with no `[host]` policy. The assets
   slice implements this; this document does not.
3. **One source, several roles.** The four radius paths all read the same
   Hyprland option. That is a many-to-one mapping, not token arithmetic: when a
   role is delegated, its authored value is replaced verbatim by the host value
   (subject to bounds). The skin's authored value remains the fallback when the
   host is missing or invalid.
4. **Mode overrides still win.** Existing precedence is unchanged: mode
   override > host > skin fallback. A mode that authors the whole `surface`
   group (as `paper` light does) keeps that group explicit; delegation does not
   pierce a group-level override.
5. **Subset is an escape hatch.** Because opt-in is per path, a skin may later
   narrow its delegation (for example panel + card only) without a contract
   change. The baseline for opted-in skins is the full rectangle set.

### Why this changes the previous decision

The previous outer-only rule treated the compositor scalar as a semantic claim
about what Hyprland rounds. This model separates the two concerns:

- **What Hyprland rounds** is still only the toplevel bounding box. AGS
  layer-shell surfaces and inner widgets are not rounded by the compositor.
- **What a skin may use as its rectangle design value** is a separate,
  consented choice. When an opted-in skin reads the host value for an inner
  rectangle, it is adopting the host's rectangle geometry as authored design,
  not asserting that the compositor applies it there.

That distinction preserves the reason for the old rule (no forced re-rounding,
no pill collapse) while allowing a user who sets host rounding to get a
coherently rounded consumer set.

### Consumer mapping (unchanged, now meaningful for delegated skins)

| Consumer | Component | Token | Notes |
| --- | --- | --- | --- |
| rofi | `window` | `surface.panel.radius` | outer surface |
| rofi | `mainbox` | `surface.card.radius` | inset content card |
| rofi | `inputbar` | `surface.control.radius` | input rectangle |
| rofi | `element` | `surface.cell.radius` | list row rectangle |
| wlogout | `window` | `surface.panel.*` | outer surface paint |
| wlogout | `button` (action card) | `surface.panel.radius` + `surface.panel.border-width` | wide outer action card, **not** an inner control; fill stays `surface.card.bg` |
| GTK3/GTK4 global | `window` | `surface.panel.radius` | outer |
| GTK3/GTK4 global | `headerbar`, `popover`, `.card` | `surface.card.radius` | cards |
| GTK3/GTK4 global | `button`, `entry` | `surface.control.radius` | controls |
| AGS apps | panel / card / field / row | panel / card / control / cell | template mapping unchanged |
| AGS notifications | notification card | `surface.card.radius` | layer-shell card; delegated only if the skin opted in |
| Any consumer | badges, toggles, pills | `surface.pill.radius` | **explicit**, never delegated |

If a template uses a rectangle role the selected skin did not delegate, it
renders the skin's authored value. Consumers need no template change for this
model.

## Superseded work and required guard inversion

The outer-only decision already shipped guards in `dotfiles-assets` (REQ-025).
The implementation slice must deliberately invert them:

- `skins/tests/fixtures/invalid/host-inner-radius.toml` is no longer invalid;
  `surface.card.radius` becomes a legal `[host].inherit` path. Delete or move it
  to the positive fixtures.
- `test_rofi_host_probe_moves_only_the_outer_window_radius` becomes a delegated
  rectangle probe: `window`/`mainbox`/`inputbar`/`element` all follow the probe
  for opted-in skins.
- `validate-skins.py` `HOST_INHERITABLE` and `HOST_PROBE` expand to the five
  paths; the assertion that changed leaves must equal `HOST_INHERITABLE`
  remains.
- A new negative fixture is required for the remaining ban:
  `[host].inherit = ["surface.pill.radius"]` must fail with the allowlist
  message.
- The README/docstring text saying "inner radii are never host-inheritable"
  must be replaced with the pill-only ban and the opt-in rectangle set.

Do not leave both rules documented; stale outer-only wording is a failure of
this revision.

## Contract, version and identity impact

| Surface | Impact |
| --- | --- |
| Contracts schema | **Additive minor.** `appearance-manifest.schema.json` `hostPolicy.inherit.items.enum` gains `surface.card.radius`, `surface.control.radius`, `surface.cell.radius`. `generation-manifest.schema.json` `host.defaults.properties` gains the same three radius paths with `0..64`. `surface.pill.radius` stays absent. `appearance.v3` is unchanged; no breaking schema version bump. |
| Mapping version | **Keep `HOST_MAP_VERSION = 1`.** No existing path-to-option pair changes; the version identifies the source mapping, not the allowlist cardinality. Existing panel-only generations keep the same `hostHash` and identity. Revisit only if a path's source option changes. |
| Runtime | `HOST_MAP` gains three entries (same `decoration:rounding` source); `HOST_BOUNDS` gains three `0..64` entries; validation, generation defaults, doctor drift and tests accept the new paths. Pill remains rejected as an unknown host token. |
| Assets | `HOST_INHERITABLE`/`HOST_PROBE` expand; vendored contract schemas mirror the enum; glass/paper/terminal-host opt in; terminal/flat stay explicit; render/negative tests updated as above. |
| Provisioning | No consumer link, target, template or layout change. Only the assets tag and any schema/token mirror move. |
| Engine | No new skeleton file and no provisioning behavior change. If the engine mirrors contracts/assets schema constants, update the mirror and bump the engine pin after the upstream tags. |
| Composition | Tuple/pin cutover only after releases; no runtime or consumer behavior authored here. |
| Tags | One additive minor per owning repo (contracts, runtime, assets), then engine and composition pins. No branch or SHA pins. |

### If `HOST_MAP_VERSION` were instead bumped

A bump to `2` would churn every host-using generation once, change `hostHash`
even for panel-only skins, and require the generation schema's `host.version`
`const 1` to accept both versions. That is not chosen: it adds identity churn
without changing any resolved value.

## Implementation sequence

Order matters because the schema gate rejects paths before the runtime or assets
can use them.

| Step | Repo | Change | Depends on |
| --- | --- | --- | --- |
| 1 | `contracts` | Expand the enum and `host.defaults`; add schema/negative tests; release minor. | this doc |
| 2 | `dotfiles-runtime` | `HOST_MAP`, `HOST_BOUNDS`, validation/doctor/tests; release minor. | contracts tag |
| 3 | `dotfiles-assets` | Expand allowlist/probe, opt in glass/paper/terminal-host, invert guards, add pill negative, update README; release minor. | contracts tag |
| 4 | `dotfiles-provision` (engine) | Mirror any schema/token constants; verify token-path list already covers card/control/cell; bump pin if mirrored; release. | assets/contracts tags |
| 5 | `dotfiles-v3` | Update `program-tuple.yaml`/pins; run gates; tag composition. | all upstream tags |
| 6 | local validation | Read-only probe at 0 / 9 / large plus GTK/wlogout checks; no apply. | composition cutover |

Steps 2 and 3 can run in parallel after step 1. Do not cut composition between
them.

## Validation matrix

Probe the rendered outputs, not just the resolved tokens. `probe` means a
supplied host value; `authored` means the skin's explicit fallback.

| # | Consumer / state | Input | Expected |
| --- | --- | --- | --- |
| V-1 | rofi `glass`/`paper`/`terminal-host` dark, host 0 | radius 0 | `window`/`mainbox`/`inputbar`/`element` all `0px`; panel border follows `general:border_size` |
| V-2 | same, host 9 | radius 9 | all four slots `9px` |
| V-3 | same, host 24 | radius 24 | all four slots `24px`; record nested-corner appearance |
| V-4 | rofi `terminal`/`flat`, host 9 | radius 9 | authored values unchanged (`terminal` 0/0/2/0; `flat` 0/0/0/0); no `[host]` block |
| V-5 | rofi paper light, host 9 | radius 9 | mode override wins; authored paper light radii stay explicit |
| V-6 | wlogout `glass`/`terminal-host`, host 0/9/24 | radius probe | `button` radius equals probe; border width equals `general:border_size`; fill stays `surface.card.bg` |
| V-7 | GTK3 and GTK4 global sheets, host 9 | radius 9 | `button`/`entry` = 9; `popover`/`.card` = 9; `window` = 9; provider parses with no warnings |
| V-8 | AGS notifications / apps, host 9 | radius 9 | notification card = 9; every `pill` uses the authored value (`paper` 999, `flat` 999, `glass` 20, `terminal` 2) |
| V-9 | headless / no Hyprland | no host | authored fallback values; no host block; deterministic identity |
| V-10 | bound check | 64 accepts; 65 rejects | runtime bound error, generation fails closed per `fallback` |
| V-11 | negative policy | `["surface.pill.radius"]`; `["surface.card.border-width"]` | schema/validator rejects with the allowlist message |

The live check is read-only (`hyprctl`, temp `XDG_CONFIG_HOME`/`XDG_STATE_HOME`,
`rofi -dump-theme`, GTK `CssProvider`, Broadway wlogout). No `apply`, no live
generation commit.

## Acceptance criteria

### Phase 1 — decision record

- **HG-2.1** This document records the skin-delegated rectangle model: exactly
  four host-delegable radius paths plus panel border-width; `surface.pill.radius`
  and inner border widths are excluded; opt-in is per skin and per path.
- **HG-2.2** `docs/109`, `docs/108` (`W-2.12`), the `SKIN-CONSUMERS` epic and
  `REQ-111` link this revision and no longer state an unqualified outer-only
  rule. Prior outer-only evidence is marked superseded rather than deleted.

### Phase 2 — contract and runtime

- **HG-2.3** Contracts add the three radius paths to the allowlist and
  generation `host.defaults` with `0..64` bounds; pill remains absent; existing
  manifests and generations validate unchanged; release is additive and
  `appearance.v3` is unchanged.
- **HG-2.4** Runtime maps the three paths to `decoration:rounding`, adds bounds
  and fixtures, keeps `HOST_MAP_VERSION=1`, includes only participating paths in
  `hostHash`, and makes doctor compare all delegated paths. Pill and inner
  border widths are rejected as host tokens.

### Phase 3 — assets

- **HG-2.5** `validate-skins` `HOST_INHERITABLE` is exactly the five paths;
  `HOST_PROBE` supplies deterministic values for all five; a
  `surface.pill.radius` fixture fails with the allowlist message and the old
  `host-inner-radius` negative fixture is removed or converted.
- **HG-2.6** `glass`, `paper` and `terminal-host` delegate all four rectangle
  radii plus panel border-width; `terminal` and `flat` have no `[host]` policy;
  every authored value remains a valid headless fallback.
- **HG-2.7** Render tests cover the matrix: rofi all four slots at 0/9/large;
  wlogout action card follows panel; GTK3/GTK4 controls/cards follow; pills keep
  authored values; terminal/flat never move.

### Phase 4 — provisioning, engine, composition

- **HG-2.8** Any engine/verify schema or token mirror accepts the five paths;
  no consumer link, template, layout or target changes; the engine pin moves
  only after upstream tags.
- **HG-2.9** Composition updates tuple/pins only after contracts, runtime and
  assets release; `make gates-ci` and `make deploy-coverage` are green; no tag
  points at a branch or SHA.

### Phase 5 — validation and close

- **HG-2.10** The read-only validation matrix V-1…V-11 is recorded with observed
  outputs at host rounding 0 / 9 / large, including wlogout and GTK.
- **HG-2.11** Compatibility is proven: existing panel-only generations remain
  valid and keep identity; opt-in skins regenerate once; `doctor` reports only
  delegated drift; rollback is per skin by removing inherited paths and
  reconverging.
- **HG-2.12** The design slice (this document and links) changes no schema,
  runtime, assets, provisioning, composition, app or tag; docs gates are green.

### Explicitly rejected

- **HG-X1** Delegating `surface.pill.radius` or otherwise replacing capsule
  identity (`999`/full-round) with the host scalar.
- **HG-X2** Computing, scaling or concentricity-correcting inner radii from the
  host value inside the skin plane.
- **HG-X3** Forcing delegation on skins that did not opt in, or removing the
  per-path opt-out.
- **HG-X4** Delegating `card`/`control`/`cell` border widths, padding, gaps,
  type or colour to the host.
- **HG-X5** Adding a `surface.window`/`surface.outer` role in this slice.
- **HG-X6** Claiming the compositor rounds layer-shell surfaces or inner
  widgets. Delegation is skin consent, not compositor behavior.
- **HG-X7** The blanket outer-only rule recorded in `6f517508` as a permanent
  constraint. Panel-only remains a legal subset, not a universal mandate.

## Risks and mitigations

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Small controls over-round | A 9–24px radius on a 24–28px input reads as a capsule. | Opt-in per skin; `terminal`/`flat` stay explicit; per-path subset if a skin's controls look wrong; record V-1…V-3. |
| Radius hierarchy collapses | `glass` currently authors 12/9/7/7; delegating all four at host 9 renders 9/9/9/9 and loses rhythm. | Accept as the opted-in look, or narrow delegation (for example panel+card) without a contract change; visual review at 9 and 24 before closing the assets slice. |
| Nested corners are not concentric | An inner card at radius 9 inside a panel radius 9 with padding 9 has a non-concentric corner; the mathematically concentric value is usually `max(0, outer − inset)`. | No derivation in this model (HG-X2). Record nested-corner appearance in V-2/V-3; skins may keep inner roles explicit or author fallbacks that read well. |
| Double rounding in rofi | `mainbox` fills the padded window content; equal outer/inner radii create two visible rounded rectangles. | Visual review at 9/large; allow panel-only delegation for skins that dislike it. |
| Pill regression | One stale template or fixture could route capsules through the host value. | Pill stays outside the enum; HG-2.5 negative fixture; V-8 asserts authored pills. |
| GTK blast radius | A global `button`/`entry`/`popover` radius affects every GTK app, including headerbar and dialogs. | Opt-in only; GTK provider parse test plus V-7; no host value reaches non-delegated properties. |
| Layer-shell mismatch | AGS surfaces are not compositor-rounded; using host geometry there could be misread as parity. | Documented as consented design (HG-X6); no claim of compositor parity. |
| wlogout identity | wlogout action cards already follow panel; expanding card/control could change them indirectly. | Button mapping stays panel (`W-2.12`); wlogout delegates nothing on its own, so it follows only when its skin opts in. |
| Hidden identity churn | Changing host mapping version or fallback could invalidate existing generations. | Keep `HOST_MAP_VERSION=1`; old panel-only generations unchanged; only opted-in skins get a new generation. |
| Stale docs contradict guards | Both outer-only and delegated rules cannot be true. | HG-2.2 and the explicit guard-inversion section; remove stale wording in the assets slice. |

## Migration and compatibility

- **Additive:** manifests without the new paths, and generations without the new
  defaults, remain valid. No migration is required to upgrade contracts,
  runtime or assets.
- **Identity:** existing panel-only host generations keep their `hostHash`
  because `HOST_MAP_VERSION` and participating values do not change. An
  opted-in skin changes its policy and resolved surface tokens, so it produces
  a new generation once.
- **Fallback:** missing/invalid host values fall back to the skin's authored
  values under `fallback = "skin"`; `fallback = "error"` still fails closed.
- **Doctor:** compares the live host to every delegated path in the committed
  host block. More delegated paths means more drift checks, not polling.
- **Rollback:** remove the expanded paths from a skin's `[host].inherit` and
  reconverge. This is local and per skin; no contract rollback is needed.
  Reverting the contract/runtime/assets releases would restore outer-only and
  invalidate opted-in manifests, so it must be a coordinated pin rollback.

## Non-goals

- No pill/capsule delegation, no inner border-width delegation, no padding,
  gap, size, type or colour delegation.
- No computed/scaled/concentricity-corrected radii; no skin-plane arithmetic.
- No new surface role (`surface.window` remains deferred).
- No change to consumer layout, templates, links or app-owned structure.
- No forced re-rounding of layer-shell content by the compositor.
- No change to `terminal` or `flat` behavior.
- No code, tag, pin, generation or live apply in this docs slice.
- No notification toplevel promotion or non-Hyprland host source in this
  slice.

## Phased plan

| Phase | Scope | Repo | IDs |
| --- | --- | --- | --- |
| 0 | Revised decision record + 109/108/epic/ticket links | `dotfiles-v3` | `HG-2.1`, `HG-2.2` |
| 1 | Allowlist + generation defaults + schema tests; additive minor tag | `contracts` | `HG-2.3` |
| 2 | `HOST_MAP`/`HOST_BOUNDS` + doctor/tests; minor tag | `dotfiles-runtime` | `HG-2.4` |
| 3 | Probe/allowlist, skin opt-ins, inverted guards, pill negative, render tests; minor tag | `dotfiles-assets` | `HG-2.5`–`HG-2.7` |
| 4 | Schema/token mirror + pin; no consumer changes | `dotfiles-provision` | `HG-2.8` |
| 5 | Tuple/pin cutover + gates | `dotfiles-v3` | `HG-2.9` |
| 6 | Read-only 0/9/large matrix incl. wlogout/GTK; close | local + all repos | `HG-2.10`–`HG-2.12` |
| — | Pill/derived/forced delegation | rejected | `HG-X1`–`HG-X7` |

## Recommendation

Adopt the **skin-delegated rectangle model**. Keep the host influence closed to
four rectangle radii plus the panel border width, keep capsules explicit, and
let the skin opt in per path. Implement it in the order above, starting with the
contracts allowlist, and invert the now-obsolete outer-only assets guards in the
same assets slice. Do not bump the host mapping version and do not add a new
surface role.

## Open questions

1. After the visual review, do `glass`/`paper` delegate all four radii, or only
   panel + card, to preserve some radius hierarchy? The contract supports either
   without further change.
2. Should the opted-in skins re-author their fallback inner radii to be
   concentric with the authored panel radius so headless/fallback rendering is
   also clean? This is skin design, not host delegation.
3. Should the validation matrix include a real GTK app window (not only a
   `CssProvider` parse) to judge headerbar/dialog rounding at large host values?
4. Is "rectangle roles" the right glossary term for the skins README, or should
   the doc name the four paths explicitly everywhere to avoid a new abstraction?
