# 111 — Host rounding granularity

> **Status:** **design decision proposed** (2026-11-11) — no schema, runtime,
> assets, provisioning or tag change. This document decides the semantic scope
> of Hyprland `decoration:rounding` in the skin plane and defines the guard
> slice that would lock it in.
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

Observed with `terminal-host` and live rounding `9`:

| Consumer slot | Token | Rendered radius |
| --- | --- | ---: |
| rofi `window` | `surface.panel.radius` | 9px |
| rofi `mainbox` | `surface.card.radius` | 0px |
| rofi `inputbar` | `surface.control.radius` | 2px |
| rofi `element` | `surface.cell.radius` | 0px |
| wlogout `button` | `surface.panel.radius` | 9px |

The question is whether the 0/2/0 inner values are a defect.

## Decision

**`decoration:rounding` is an outer-window/outer-surface value only. It must not
be mapped to inner cards, controls, cells or pills. The host allowlist stays
exactly `surface.panel.radius` and `surface.panel.border-width`.**

Consequences:

1. **Outer-only host semantics.** Hyprland rounds a toplevel window's bounding
   box. It has no concept of a card inside that window, a control inside a card,
   or a layer-shell child. Treating the scalar as a general "roundness" knob is
   a semantic escalation the compositor does not make.
2. **`surface.panel` is the canonical outer-surface role.** A consumer that owns
   an outer window/panel maps that outermost geometry to `surface.panel.radius`
   and `surface.panel.border-width`. This already covers rofi `window`, wlogout
   `window`, and the AGS bar panel. It does **not** mean "the bar panel only".
   The role name is historical and remains frozen; renaming it is not worth a
   contract/version migration.
3. **Inner radii are skin-owned design.** `card`, `control`, `cell` and `pill`
   radii express the skin's internal rhythm. `terminal-host` deliberately keeps
   the terminal's square inner identity (`0/2/0`) while following the host for
   the outer frame; `glass` and `paper` already provide rounded inner roles.
   A user who wants rounded inner components selects a skin whose inner roles
   are rounded, rather than making the host setting rewrite the skin.
4. **wlogout action cards are an outer-surface exception by mapping, not by
   host policy.** `wlogout.gtk.css.j2` maps `button` radius/border to the panel
   tokens because those buttons are wide action cards, not compact controls
   (docs/108 `W-2.12`). That is a consumer-template mapping decision and stays.
   It is not evidence that every inner control should inherit.
5. **No `surface.window` role now.** Adding a second outer role would duplicate
   `surface.panel`, force every skin and mode override to author it, and change
   the resolved surface vocabulary without solving the inner-radius question.
   A future `surface.window` is justified only by a real consumer whose
   outermost surface cannot honestly use `panel` (for example a notification
   toplevel rather than the current layer-shell card). That needs its own
   additive contract proposal; see Phase 2.

## Evidence

### Hyprland semantics

- Live host: `hyprctl -j getoption decoration:rounding` →
  `{"option":"decoration:rounding","int":9,"set":true}`; version `0.57.2`.
- The runtime maps exactly one token to it:
  `dotfiles-runtime/src/runtime/domain/host_defaults.py:28-31`:
  `surface.panel.radius -> decoration:rounding`,
  `surface.panel.border-width -> general:border_size`.
- The contract allowlist is closed to those two paths:
  `contracts/schemas/appearance-manifest.schema.json:76-95`.
- Assets enforces the same list:
  `dotfiles-assets/scripts/validate-skins.py:187`.
- Docs/109 already records the intent: `surface.panel.radius` is the "outer
  window/panel corner" (docs/109 §Phase 1 scope), and future notification outer
  alignment "needs a future `surface.window` role, not overloading card radius"
  (docs/109 §Decision; §H-3.2).

### Observed rendering at host radius 9

Generation `af4c31a8a15293a83de9c71c3e1d8d6c970a1793276baf51ee0ff7623f4b31b7`:

- manifest host defaults: `surface.panel.radius=9`,
  `surface.panel.border-width=1`;
- resolved tokens: panel radius `9`, card `0`, control `2`, cell `0`,
  pill `2`;
- `appearance/rofi.rasi`: `window` 9px, `mainbox` 0px, `inputbar` 2px,
  `element` 0px;
- `appearance/wlogout.css`: `button` 9px.

This is exactly the outer-only contract, not a resolution failure.

### Consumer mappings are already explicit

- `dotfiles-assets/skins/templates/rofi.rasi.j2`: `window → panel`,
  `mainbox → card`, `inputbar → control`, `element → cell`.
- `dotfiles-assets/skins/templates/wlogout.gtk.css.j2`: window paint from panel,
  button fill from card, button radius/border from panel.
- `dotfiles-assets/skins/templates/ags-notifications.gtk.css.j2`: notification
  cards use `surface.card.*`; the notification surface is a layer-shell overlay,
  not a compositor-rounded toplevel.

## Options considered

| Option | What changes | Verdict |
| --- | --- | --- |
| **A. Expand the host allowlist** with `surface.card.radius`, `surface.control.radius`, `surface.cell.radius`, `surface.pill.radius` | Contract enum + generation bounds/defaults, runtime `HOST_MAP`/`HOST_BOUNDS`, assets validator, skins opt in, every consumer renders host radius on every inner role | **Reject.** Semantic mismatch; over-rounds small controls; flattens pill `999` to `9`; nested corners become non-concentric; turns a compositor window hint into a global design scalar. |
| **B. Add a `surface.window` role** and map consumer outer surfaces to it; inner radii stay explicit | New role in skin/appearance/resolved schemas; every skin and mode override authors it; templates migrate outer mappings; runtime validation and assets gate update | **Defer.** It can improve naming for a second outer surface, but does not answer inner rounding and duplicates panel today. Needs a real consumer and a separate contract change. |
| **C. Keep outer-only; document `surface.panel` as the outer-surface role and inner radii as skin-owned** | Docs + regression guards only; no contract/runtime/assets behavior change | **Choose.** Matches the compositor, preserves skin identity, zero migration. |
| **D. Derive inner radii from the host value** (for example `max(0, host − padding)`) | New token arithmetic/derivation in the skin plane; new identity/versioning questions | **Reject.** No contract vocabulary for computed tokens; nested-context radius is design-owned; would make every skin's inner rhythm depend on unrelated compositor state. |

## Contract, version and identity impact

### Chosen option C

| Surface | Impact |
| --- | --- |
| Contracts schema | **None.** `host.inherit` stays the two-path enum; generation `host.defaults` stays two properties; no schema version bump. |
| Runtime | **None.** `HOST_MAP`, `HOST_BOUNDS`, `HOST_MAP_VERSION=1`, `hostHash`, generation manifest, doctor drift comparison unchanged. |
| Assets | **Documentation + guard tests only.** `HOST_INHERITABLE` already rejects inner paths; add an explicit negative fixture/test and a rofi host-probe render assertion. |
| Skins | **None.** glass/paper/terminal-host keep their current inner radii; terminal/flat remain explicit/off. |
| Provisioning / consumers | **None.** No link, target, template or app change. |
| Composition / tags | **None.** No pin or tag moves; no generation churn. |

### If option A were ever reconsidered

- Contract: enum and generation `defaults` properties need new entries and
  bounds; this is an additive contract release, not a patch.
- Runtime: `HOST_MAP`, `HOST_BOUNDS`, validation fixtures, doctor paths and
  tests change. Either keep `HOST_MAP_VERSION=1` (new paths reuse the same
  source mapping but existing generations are untouched) or bump to `2`
  (all host generations change identity and churn once). The contract/docs must
  state which; the current schema `version: const 1` makes a bump a breaking
  migration unless the schema accepts both.
- Assets: opt-in skins gain `[host]` entries; every template using those roles
  renders host values; `validate-skins` host probe must cover each new path.
- Consumer risk is the blocker: every inner control across GTK/rofi/wlogout
  changes at once, with no per-context control.

### If option B were ever reconsidered

- Add an additive role to the surface vocabulary (skin manifest, appearance
  manifest, resolved appearance JSON), define whether it is required or
  optional, and decide how mode overrides replace it.
- If it is host-inheritable, add `surface.window.radius` to the allowlist and
  generation defaults. Do **not** alias it to `surface.panel` implicitly.
- Migrate only consumers with a genuine outer surface; inner mappings never
  move to `window`.

## Visual risks

| Risk | Why it matters |
| --- | --- |
| Small controls over-round | A 9–12px radius on a 24–28px input/button reads as a capsule. `surface.control.radius` is 2–7 in the bundled skins for a reason. |
| Pills collapse | `surface.pill.radius` is `999` in flat/paper to mean "fully round". Replacing it with host `9` silently turns pills into rounded rectangles. |
| Nested corners are not concentric | An inner card at radius 9 inside a window radius 9 with 9px padding has an effective 18px corner; the correct nested value is usually `max(0, outer − inset)`, which the host cannot know. |
| Double rounding | rofi `mainbox` fills the window's padded content area; giving it the outer radius creates a second rounded rectangle inside the first. |
| Per-context GTK damage | A global `button { border-radius }` also hits headerbar buttons, entries, popovers and dialogs; Hyprland rounding says nothing about those contexts. |
| Layer-shell mismatch | AGS surfaces are layer-shell; the compositor does not round them the way it rounds toplevels. Inheriting inner card radii from `decoration:rounding` would invent geometry the compositor never applies. |
| wlogout divergence | wlogout action cards already look right at panel radius. Expanding the allowlist would not improve them and would risk changing their identity under skins that opt in. |
| Skin identity loss | `terminal-host` exists precisely to keep square inner components while following the outer host frame. Option A would erase that distinction. |

## Acceptance criteria

### Phase 1 — decision record and guards (next slice)

- **HG-1.1** `decoration:rounding` is documented as an outer-window/outer-surface
  value; the host allowlist remains exactly `surface.panel.radius` and
  `surface.panel.border-width`. No inner radius path is host-inheritable.
- **HG-1.2** Docs/109 links this decision and its Phase 2/3 wording agrees:
  inner radii are skin-owned; `surface.window` remains a future, separate
  proposal.
- **HG-1.3** Assets has an explicit negative fixture proving
  `[host].inherit` with `surface.card.radius` (representative of any inner role)
  fails with the allowlist message; `validate-skins` behavior is unchanged.
- **HG-1.4** Assets has a host-probe render assertion: under a probe host
  radius, rofi `window` equals the probe, while `mainbox`/`inputbar`/`element`
  equal their authored skin values. The assertion runs for terminal-host and
  glass/paper.
- **HG-1.5** wlogout's panel-radius button mapping is documented as an
  outer-action-card mapping, not an inner-control precedent.
- **HG-1.6** No contract, runtime, provisioning, composition, app or skin value
  changes in the guard slice; no tag moves; no generation identity churn.
- **HG-1.7** A read-only visual check records host rounding `0`, `9` (or the
  live value) and a large value: rofi outer follows; inner roles do not; nested
  corners remain visually clean; wlogout cards follow.
- **HG-1.8** `make gates-ci` in the composition is green; the assets repo's
  `make gates` / `validate-skins` and the runtime host-default tests are green
  in the implementing slice.

### Phase 2 — future `surface.window` (only if triggered)

- **HG-2.1** Trigger: a real consumer owns a **toplevel outer surface** whose
  geometry cannot honestly be expressed by `surface.panel` (candidate: a future
  notification window, not the current layer-shell cards).
- **HG-2.2** A separate contract proposal defines the role additively, with a
  migration for bundled skins and mode overrides; no implicit alias to panel.
- **HG-2.3** If host-inheritable, `surface.window.radius` is added to the
  allowlist with its own bounds and identity rule; inner roles remain excluded.
- **HG-2.4** The role is never used for cards, controls, cells or pills.

### Explicitly rejected

- **HG-X1** Mapping `surface.card.radius`, `surface.control.radius`,
  `surface.cell.radius` or `surface.pill.radius` to `decoration:rounding`.
- **HG-X2** Computing inner radii from the host value inside the skin plane.
- **HG-X3** Treating layer-shell content as compositor-rounded toplevels.

## Migration and compatibility

- No migration: no manifest, generation, cache, consumer link or app changes.
- Existing generations remain valid. `doctor` continues to compare only the
  delegated outer values.
- Rollback: nothing to roll back for the decision. If the guard slice is
  reverted, behavior is unchanged; it is tests/docs only.
- If a future opt-in is added, rollback is removing the path from the skin's
  `[host].inherit` and reconverging; it is per-skin and local.

## Phased plan

| Phase | Scope | Repo | IDs |
| --- | --- | --- | --- |
| 0 | This design doc + tracking ticket + epic/109 links | `dotfiles-v3` | — |
| 1 | Negative inner-radius fixture + rofi host-probe render assertion + docstring/README clarification | `dotfiles-assets` | `HG-1.3`, `HG-1.4`, `HG-1.5` |
| 1 | Read-only live visual probe at host 0/9/large | local, no apply | `HG-1.7` |
| 2 | Optional `surface.window` proposal, only if a genuine outer consumer appears | `contracts` → runtime/assets → composition | `HG-2.1`–`HG-2.4` |
| — | Inner-radius host mapping | rejected | `HG-X1`–`HG-X3` |

## Recommendation

Adopt **Option C: outer-only**. Keep the host allowlist unchanged, document
`surface.panel` as the outer-surface role, and keep inner radii as authored skin
identity. The observed rofi `mainbox=0`, `inputbar=2`, `element=0` under
`terminal-host` is correct: `terminal-host` is a hybrid that follows the host
outside and keeps the terminal inside. A user wanting rounded inner components
should select `glass` or `paper`, which already author them.

## Open questions

1. Should the future outer role be named `surface.window` or `surface.outer`?
   It should not imply "only real toplevels" if wlogout-style action cards also
   need it.
2. Does any consumer plan to promote notification cards from layer-shell cards
   to a real toplevel? If yes, start `HG-2.1`; if no, keep `surface.window`
   deferred.
3. Should glass/paper inner radii be audited for concentric corners against the
   panel radius and padding? This is a skin-design review, independent of host
   inheritance.
4. Is the docs wording "outer window/panel corner" sufficient, or should
   `surface.panel` get an explicit role glossary entry in the skins README?
