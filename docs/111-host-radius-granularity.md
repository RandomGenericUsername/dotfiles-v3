# 111 — Host rounding granularity and the pill exception

> **Status:** **delivered** (2026-11-11) — panel/card/control/cell follow the
> host; `surface.pill.radius` stays explicit.
> **Supersedes:** the original “outer-only” wording in this document for the
> rectangle roles. The rectangle revision (contracts `v0.11.0`) delegated
> `surface.card.radius`, `surface.control.radius` and `surface.cell.radius`;
> this revision records the remaining pill decision and the visual criteria.

## Question

Should Hyprland `decoration:rounding` reach inner consumer components, and
specifically should `surface.pill.radius` ever be host-delegated?

The question was settled in two parts:

1. **Rectangle roles may follow the host.** `surface.panel.radius`,
   `surface.card.radius`, `surface.control.radius` and
   `surface.cell.radius` are an explicit `[host].inherit` allowlist. The
   compositor’s corner value is a rectangle-geometry value, and a skin may
   deliberately opt into it.
2. **The pill never follows the host.** `surface.pill.radius` remains an
   authored skin value. It is a shape identity (capsule/fully-rounded chip),
   not another rectangle corner.

Observed with `terminal-host` and live Hyprland rounding `9`:

| Consumer slot | Token | Rendered radius |
| --- | --- | ---: |
| rofi `window` | `surface.panel.radius` | 9px |
| rofi `mainbox` | `surface.card.radius` | 9px |
| rofi `inputbar` | `surface.control.radius` | 9px |
| rofi `element` | `surface.cell.radius` | 9px |
| wlogout `button` | `surface.panel.radius` | 9px |
| AGS notification card | `surface.card.radius` | 9px |
| AGS notification pill | `surface.pill.radius` | **2px** |
| GTK card / control | `surface.card.radius` / `surface.control.radius` | 9px / 9px |

The 9px values are the delegated rectangle result. The unchanged 2px pill is
the deliberate exception, not a missed host mapping.

## Decision

**`decoration:rounding` may reach the rectangle roles through the explicit
`[host].inherit` allowlist. It must never reach `surface.pill.radius`. The
contract allowlist stays exactly the five current paths:**

```text
surface.panel.radius
surface.panel.border-width
surface.card.radius
surface.control.radius
surface.cell.radius
```

`surface.pill.radius` remains explicit in every skin. No `host.pill` mode, no
derived/capped pill radius and no separate pill-host policy is introduced now.

Consequences:

1. **Host value = rectangle corner geometry.** Hyprland rounds a toplevel
   window’s bounding box. The delegated rectangle roles are the skin’s opt-in
   way to echo that geometry inward. The compositor still has no concept of a
   card, control, cell or pill inside the window; delegation is a skin policy,
   not a compositor semantic.
2. **Pill value = shape declaration.** A pill radius answers “is this a capsule
   or a squared chip?”, not “how round is this rectangle?”. `999` is a sentinel
   for “fully rounded”, clamped to half the shortest side. `20`, `999` and `2`
   are different shape identities, not different points on one radius scale.
3. **A fixed host scalar cannot express a capsule.** Substituting `9` for
   `999` (flat/paper) collapses a capsule into a rounded rectangle. Substituting
   `9` for `20` (glass) changes the capsule proportion rather than following
   the compositor. Substituting `9` for `2` (terminal-host) erases the squared
   chip identity that makes that skin terminal-like.
4. **Nested pill geometry is height-dependent.** The correct capsule radius is
   derived from the rendered pill height, not from the outer window. A pill in
   a notification row, a toolbar chip and a large badge can have different
   heights inside the same card. The host cannot know those heights, so one
   scalar cannot keep every pill a capsule.
5. **Pill and control must stay distinguishable.** terminal-host authors
   `control=2` and `pill=2`; after the rectangle revision the control follows
   the host at `9`, while the pill remains `2`. That contrast is intentional:
   the control is a rectangle, the pill is a chip. Delegating the pill would
   make the two roles converge and remove a useful visual distinction.
6. **No extra host policy is justified.** A `host.pill` mode, a separate pill
   token, or a capped derivation would add contract vocabulary and versioning
   to model a compositor setting that has no pill concept. If a future product
   requirement needs host-adjacent pill behavior, it needs its own proposal,
   not an exception inside this allowlist.

What changes versus what stays:

| Role | terminal-host at host rounding 9 | Why |
| --- | --- | --- |
| `panel`, `card`, `control`, `cell` radius | **9px** — delegated | Rectangle geometry; explicit skin opt-in |
| `panel` border width | **1px** — delegated | Outer frame width; live `general:border_size` |
| `pill` radius | **2px** — explicit | Shape identity; not a rectangle corner |
| paint, type, rhythm, padding | unchanged | Never host-inheritable |

## Why pills are different

| Token | Meaning | Value domain | Can the host know it? |
| --- | --- | --- | --- |
| `surface.card.radius` | Rounded rectangle corner | Fixed pixel length | Approximately: it sees the outer rectangle; the skin opts in |
| `surface.control.radius` | Compact rectangle corner | Fixed pixel length | Approximately: same as card, with a smaller authored fallback |
| `surface.cell.radius` | List-row rectangle corner | Fixed pixel length | Approximately: same as card, with a smaller authored fallback |
| `surface.pill.radius` | Capsule / fully-rounded chip identity | Sentinel (`999`) or authored chip value (`2`, `20`) | **No**: it depends on the rendered pill height and the skin’s shape language |

Examples:

- `flat` / `paper`: pill `999` → a true capsule at any height.
- `glass`: pill `20` → a capsule whose softness is part of the glass identity.
- `terminal` / `terminal-host`: pill `2` → a compact squared chip, not a
  capsule. This is intentional; “pill” is the role name, not a promise that
  every skin renders a capsule.
- A notification action row can mix a 24px action chip and a 16px metadata
  chip. A fixed 9px host radius makes the first nearly a capsule and the second
  a rounded rectangle; neither is the authored shape.

## Evidence

### Hyprland semantics

- Live host: `hyprctl -j getoption decoration:rounding` →
  `{"option":"decoration:rounding","int":9,"set":true}`; version `0.57.2`.
- The runtime maps the delegated rectangle paths to the one rounding value:
  `dotfiles-runtime/src/runtime/domain/host_defaults.py:25-46`:
  `surface.panel.radius`, `surface.card.radius`, `surface.control.radius` and
  `surface.cell.radius` → `decoration:rounding`;
  `surface.panel.border-width` → `general:border_size`.
- `surface.pill.radius` is deliberately absent from `HOST_MAP`. The module
  comment states that a pill is a capsule whose identity must stay explicit.

### Contract and asset guards

- Contracts `v0.11.0` enum is closed to the five rectangle paths:
  `contracts/schemas/appearance-manifest.schema.json:76-95`. The description
  states that `surface.pill.radius` is deliberately absent because the pill’s
  capsule identity stays explicit.
- Assets enforces the same list:
  `dotfiles-assets/scripts/validate-skins.py:197-203` (`HOST_INHERITABLE`),
  and the host probe at `:1137-1191` asserts that a supplied host value moves
  only inherited rectangle paths.
- The negative fixture
  `dotfiles-assets/skins/tests/fixtures/invalid/host-pill-radius.toml` makes
  `surface.pill.radius` the representative invalid path; the test suite expects
  the allowlist failure (`skins/tests/test_skins.py:1447-1448`, `:2060-2063`).
  That is the executable guard; this docs-only slice does not need a second one.

### Observed rendering at host radius 9

Generation `af4c31a8a15293a83de9c71c3e1d8d6c970a1793276baf51ee0ff7623f4b31b7`
(the original matrix) plus the rectangle revision:

- manifest host defaults: `surface.panel.radius=9`,
  `surface.panel.border-width=1`;
- resolved tokens: panel `9`, card `9`, control `9`, cell `9`, pill `2`;
- `appearance/rofi.rasi`: `window` 9px, `mainbox` 9px, `inputbar` 9px,
  `element` 9px;
- `appearance/wlogout.css`: `button` 9px;
- GTK3/GTK4: card/control 9px; pill stays its authored value;
- `terminal` remains explicit: panel/card/control/cell/pill = `0/0/2/0/2`,
  `host: None`.

### Consumer mappings are explicit

- `dotfiles-assets/skins/templates/rofi.rasi.j2`: `window → panel`,
  `mainbox → card`, `inputbar → control`, `element → cell`.
- `dotfiles-assets/skins/templates/wlogout.gtk.css.j2`: window paint from panel,
  button fill from card, button radius/border from panel. wlogout action cards
  are an outer-action-card mapping, not an inner-control precedent (docs/108
  `W-2.12`).
- `dotfiles-assets/skins/templates/ags-notifications.gtk.css.j2`: notification
  cards use `surface.card.*`; pill/chip elements use `surface.pill.*`.
- `dotfiles-assets/skins/manifests/terminal-host.toml`: `[host].inherit`
  contains the five rectangle paths and **not** `surface.pill.radius`; its pill
  group is explicit `radius = 2`.

### Docs linkage

- Docs/109 records the rectangle revision and states that
  `surface.pill.radius` stays explicit; its Phase 2/3 wording links this
  decision and keeps `surface.window` as a separate future proposal.
- Docs/design/README links the visual mockup
  [`terminal-host-radius.html`](./design/terminal-host-radius.html).

## Options considered

| Option | What changes | Verdict |
| --- | --- | --- |
| **A. Keep the pill explicit** (current) | No contract/runtime change; skins keep authored pill values; existing negative fixture remains the guard | **Choose.** Shape semantics are preserved, zero migration, no version churn. |
| **B. Add `surface.pill.radius` to `[host].inherit`** | Contract enum + generation defaults/bounds, runtime `HOST_MAP`/`HOST_BOUNDS`, assets validator, opt-in skins, every pill consumer renders the host scalar | **Reject.** Flattens `999`/`20` capsules to `9`; turns a fixed scalar into a capsule; erases terminal-host’s `2px` chip; cannot keep mixed-height pills consistent. |
| **C. Separate pill policy/token** (for example `surface.pill.shape` or a host-only `pill.inherit`) | New contract vocabulary, schema/versioning, skin/mode authoring, runtime and assets changes | **Reject/defer.** It still has no compositor source. A separate policy would be a design-system feature, not host delegation, and needs its own proposal if a real need appears. |
| **D. Derived or capped pill radius** (`min(host, height/2)`, `max(2, host - inset)`, etc.) | Computed tokens or paint-time arithmetic in the skin plane; new identity/versioning rules; per-consumer height awareness | **Reject.** No contract vocabulary for computed tokens; the correct value is height- and context-dependent; a cap does not restore capsule semantics. |
| **E. `host.pill` mode** (`inherit`/`explicit`/`capsule`) | New host policy surface, schema enum, docs, runtime and asset support | **Reject.** Hyprland has no pill concept; a mode would only rename an explicit skin decision and multiply test states. |
| **F. Add a `surface.window` role instead** | New outer role, schemas, migration for every skin/mode, template remapping | **Defer, unrelated.** It may improve naming for a second outer surface, but it does not make pills host-geometry; see Phase 2. |
| **G. Original outer-only wording** (no inner rectangle delegation) | Revert the rectangle revision | **Superseded.** The delivered rectangle policy is explicit skin opt-in and passed the live matrix; this document records that history rather than reopening it. |

## Acceptance criteria

### Pill decision and guards

- **PG-1.1** The host allowlist is exactly `surface.panel.radius`,
  `surface.panel.border-width`, `surface.card.radius`,
  `surface.control.radius` and `surface.cell.radius`.
  `surface.pill.radius` is absent from the contract enum, runtime `HOST_MAP` /
  `HOST_BOUNDS`, generation defaults and assets `HOST_INHERITABLE`.
- **PG-1.2** `terminal-host` keeps an explicit pill `radius = 2` while its
  `[host].inherit` lists only the five rectangle paths. `terminal` stays
  `[host]`-free. `flat`/`paper` keep whatever pill shape they author (`999`
  capsules where declared). No skin gains a pill host path.
- **PG-1.3** The assets negative fixture `host-pill-radius.toml` fails with the
  allowlist message, and the host-probe test proves a supplied host value moves
  only the five inherited paths; non-inherited pill values remain authored.
- **PG-1.4** Docs/109, docs/111 and docs/design/README state the same split:
  rectangle roles may follow the host; the pill stays explicit. The mockup
  shows the actual live values and marks the rejected “pill follows 9px”
  result as not chosen.
- **PG-1.5** No contract, runtime, provisioning, composition, app or skin value
  changes in this docs slice; no tag moves; no generation identity churn.
- **PG-1.6** `make gates-ci` in the composition is green after the docs change;
  the design HTML parses without errors and needs no network access.

### Future pill policy (only if triggered)

- **PG-2.1** Trigger: a real consumer needs pill geometry to vary with the host
  in a way the skin cannot author — for example a compositor-provided “shape
  family” rather than a corner radius. Wanting rounded pills is **not** a
  trigger; author them in the skin.
- **PG-2.2** Any future pill policy is a separate contract proposal with its
  own vocabulary, bounds, identity rules and migration. It must not be added to
  the current `[host].inherit` allowlist.
- **PG-2.3** If the proposal ever maps a host value, it must preserve the
  capsule/chip distinction and cannot make one scalar stand for both a fixed
  rectangle corner and a height-relative capsule.

### Explicitly rejected

- **PG-X1** Mapping `surface.pill.radius` to `decoration:rounding`.
- **PG-X2** Computing or capping pill radii from the host value inside the skin
  plane.
- **PG-X3** Adding a `host.pill` mode or a second pill token to the current
  contract as a shortcut.
- **PG-X4** Treating layer-shell content as compositor-rounded toplevels.

## Contract, version and identity impact

### Chosen option A

| Surface | Impact |
| --- | --- |
| Contracts schema | **None.** The current five-path enum already excludes the pill; no schema version bump. |
| Runtime | **None.** `HOST_MAP`, `HOST_BOUNDS`, `HOST_MAP_VERSION=1`, `hostHash`, generation manifest and `doctor` drift comparison are unchanged. |
| Assets | **Documentation + existing guard.** `HOST_INHERITABLE` already rejects pill paths; the negative fixture and host probe already cover it. No new test is required for this docs slice. |
| Skins | **None.** glass/paper/terminal-host keep their current pill radii; terminal/flat remain explicit/off. |
| Provisioning / consumers | **None.** No link, target, template or app change. |
| Composition / tags | **None.** No pin or tag moves; no generation churn. |

### If option B were ever reconsidered

- Contract: enum and generation `defaults` properties need new entries and
  bounds; this is an additive contract release, not a patch.
- Runtime: `HOST_MAP`, `HOST_BOUNDS`, validation fixtures, doctor paths and
  tests change. Either keep `HOST_MAP_VERSION=1` (new paths reuse the same
  source mapping but existing generations are untouched) or bump to `2`
  (all host generations change identity and churn once). The contract/docs must
  state which; the current schema `version: const 1` makes a bump a breaking
  migration unless the schema accepts both.
- Assets: opt-in skins gain `[host]` entries; `validate-skins` host probe must
  cover the new path, and the negative fixture flips to a positive case.
- Consumer risk is the blocker: every pill across GTK/rofi/wlogout changes at
  once, with no per-context control.

### If option F were ever reconsidered

- Add an additive role to the surface vocabulary (skin manifest, appearance
  manifest, resolved appearance JSON), define whether it is required or
  optional, and decide how mode overrides replace it.
- If it is host-inheritable, add `surface.window.radius` to the allowlist and
  generation defaults. Do **not** alias it to `surface.panel` implicitly.
- Migrate only consumers with a genuine outer surface; pills never move to
  `window`.

## Visual risks

| Risk | Why it matters |
| --- | --- |
| Capsule collapse | `surface.pill.radius` is `999` in flat/paper to mean “fully round”. Replacing it with host `9` silently turns capsules into rounded rectangles; `glass` pill `20` loses its authored proportion too. |
| Shape ambiguity | terminal-host authors pill `2` as a squared chip. Host `9` would make it look like every other delegated rectangle and erase the pill/control distinction. |
| Height inconsistency | A fixed host radius on pills of different heights produces some near-capsules and some rounded rectangles; only the rendered height can define a true capsule. |
| Nested corners are not concentric | An inner card at radius 9 inside a window radius 9 with 9px padding has an effective 18px corner; the correct nested value is usually `max(0, outer − inset)`, which the host cannot know. This is a rectangle risk the skin accepts by opting in; pills should not inherit it. |
| Double rounding | rofi `mainbox` fills the window’s padded content area; giving it the outer radius creates a second rounded rectangle inside the first. The rectangle policy accepts this as skin-owned rhythm; pills are smaller and worse. |
| Per-context GTK damage | A global pill/button radius also hits headerbar buttons, entries, popovers and dialogs; Hyprland rounding says nothing about those contexts. |
| Layer-shell mismatch | AGS surfaces are layer-shell; the compositor does not round them the way it rounds toplevels. Inheriting pill radii from `decoration:rounding` would invent geometry the compositor never applies. |
| Skin identity loss | terminal-host exists precisely to keep a terminal-like inner identity while following the outer host frame. Delegating pills would erase a remaining explicit distinction. |

## Migration and compatibility

- No migration: no manifest, generation, cache, consumer link or app changes.
- Existing generations remain valid. `doctor` continues to compare only the
  five delegated paths.
- Rollback: nothing to roll back for this decision. If this docs slice is
  reverted, behavior is unchanged; it is documentation and a static mockup.
- If a future pill policy is added, rollback is removing the new policy from
  the skin and reconverging; it must be per-skin and versioned.

## Phased plan

| Phase | Scope | Repo | IDs |
| --- | --- | --- | --- |
| 0 | Rectangle radius delegation (delivered) | contracts/runtime/assets/composition | contracts `v0.11.0`, assets `v0.18.0`, runtime `v1.4.0` |
| 1 | Pill decision record + docs/109 link + self-contained visual mockup | `dotfiles-v3` | `PG-1.1`–`PG-1.6` |
| 2 | Optional separate pill policy, only if a genuine trigger appears | contracts → runtime/assets → composition | `PG-2.1`–`PG-2.3` |
| — | Pill host mapping / derived pill radius / `host.pill` shortcut | rejected | `PG-X1`–`PG-X4` |

## Recommendation

Adopt **Option A: keep the pill explicit**. The rectangle roles already follow
the host through an explicit skin opt-in, which is the honest part of the
compositor’s geometry. The pill is a shape identity — `999`/`20` capsules or
terminal-host’s `2px` chip — and a fixed host scalar cannot express it. Keep the
host allowlist unchanged at five paths, keep the existing negative fixture as
the guard, and use the mockup as the review artifact. A user who wants a
different pill shape selects or authors a skin; a user who wants rounded inner
rectangles already has `terminal-host`, `glass` or `paper`.

## Open questions

1. Is a separate pill-shape policy ever needed, or is the current skin-authored
   token sufficient? Treat this as `PG-2.1`; do not expand the host allowlist
   pre-emptively.
2. Should the skins README explicitly document `999` as a capsule sentinel so
   authors do not read it as a literal corner radius? This is a documentation
   improvement, not a contract change.
3. Should the future outer role be named `surface.window` or `surface.outer`?
   It should not imply “only real toplevels” if wlogout-style action cards also
   need it; this remains the separate Phase 2 question from the original doc.
   **Settled by [`113`](./113-window-role-kitty-projection.md): `surface.window`
   is the real toplevel role; wlogout action cards stay `card` with window
   frame geometry.**
4. Does any consumer plan to promote notification cards from layer-shell cards
   to a real toplevel? If yes, start the `surface.window` proposal; if no, keep
   it deferred. Pills are unaffected either way.

## Delivery evidence

- Contracts `v0.11.0`: five-path rectangle allowlist; `surface.pill.radius`
  absent and documented as explicit.
- Assets `v0.18.0`: `HOST_INHERITABLE` rectangle-only; negative fixture
  `host-pill-radius.toml`; host probe leaves non-inherited tokens untouched.
- Runtime `v1.4.0`, engine `v0.1.61`, composition `v0.1.66`.
- Live `terminal-host` with Hyprland rounding 9: panel/card/control/cell = 9;
  rofi window/mainbox/inputbar/element = 9px; wlogout card = 9px; GTK3/GTK4
  card/control = 9px; pill = 2px explicit; doctor clean.
- `terminal` remained explicit (0/0/2/0/2, host None).
- Docs/mockup:
  [`docs/design/terminal-host-radius.html`](./design/terminal-host-radius.html)
  (self-contained, live terminal/dark palette and actual radius values; no
  scripts, external assets or network).
