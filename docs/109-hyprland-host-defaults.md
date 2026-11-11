# 109 — Hyprland settings as skin defaults

> **Status:** **delivered** (2026-11-10) — Hyprland host defaults Phase 1 live.
> This document remains the criteria record; implementation evidence is at the
> end.
> **Epic:** [`SKIN-CONSUMERS`](./epics/SKIN-CONSUMERS.md)
> **Granularity decision:** [`111`](./111-host-radius-granularity.md) delegates
> the rectangle roles (panel/card/control/cell) and keeps the pill explicit;
> inner pill shape stays skin-owned.
> **Baseline:** contracts `v0.8.0`, ags-platform `v1.0.1`,
> dotfiles-runtime `v1.0.8`, dotfiles-assets `v0.14.0`,
> dotfiles-provision `v0.1.50`, composition `v0.1.55`.
> **Prototype:** `/tmp/opencode/host_defaults_prototype.py`,
> `/tmp/opencode/HOST-DEFAULTS-REPORT.md` (ephemeral; reproduce with the
> checks below).

## Rectangle radii revision

The allowlist now delegates outer and inner rectangle radii:
`surface.panel.radius`, `surface.panel.border-width`, `surface.card.radius`,
`surface.control.radius`, `surface.cell.radius`. `surface.pill.radius` stays
explicit. Live `terminal-host` at host rounding 9 produced panel/card/control/
cell 9, rofi window/mainbox/inputbar/element 9, wlogout card 9, GTK card/control
9; terminal remained explicit. Composition `v0.1.66`.

The pill is the deliberate exception: a pill radius is a capsule/chip identity
(flat/paper `999`, glass `20`, terminal-host `2`), not a rectangle corner.
Replacing it with the host scalar would collapse capsules into rounded
rectangles and make mixed-height pills inconsistent. The contract allowlist,
the assets negative fixture and the design mockup therefore keep the pill
explicit; see [`111` §Pill decision and guards](./111-host-radius-granularity.md#pill-decision-and-guards)
and [`docs/design/terminal-host-radius.html`](./design/terminal-host-radius.html).

## Delivery evidence

- contracts `v0.9.0`: `[host]` policy, generation `host`/`intent.host`,
  `appearance.v3`.
- assets `v0.15.0`: glass/paper opt in; terminal/flat explicit.
- runtime `v1.1.0`: Hyprland adapter/resolver/hostHash, GC protection, doctor
  host drift; `v1.1.1` preserves the non-AGS wlogout stable link across prune.
- assets `v0.15.2`/`v0.15.3`: wlogout card mapping and correct focus/hover
  fills; panel radius/border follow the delegated host.
- assets `v0.16.0`: `terminal-host` skin opt-in; `terminal` remains explicit.
- engine `v0.1.58`; composition `v0.1.61`.
- runtime `v1.1.2`: strict `icons regenerate` idempotency (no new generation
  on cache hit).
- runtime `v1.2.0`: socket2 `configreloaded` watcher with 0.25s debounce;
  live `rounding 0→8` produced host radius 8 automatically in ~1.25s, then
  restored to 0. Composition `v0.1.63`.
- Live: `terminal-host` resolved host radius 0 / border 1; `terminal` stayed
  `host: None`; wlogout link survived both reconverges; doctor clean.
- engine `v0.1.53`: contracts v0.9.0/assets v0.15.1 mirrors; composition
  `v0.1.58`.
- Live: `glass` resolved `surface.panel.radius=0` / `border-width=1` from
  Hyprland (live `decoration:rounding=0`, `general:border_size=1`), with
  `host.fingerprint` recorded; `terminal` resolved `host: None` and kept its
  explicit values. `doctor` clean in both states; wlogout link survived both
  reconverges and GTK3 parsed the combined sheet.

## Decision

Add an **opt-in, per-skin host-default policy** that supports an explicit
allowlist. The skin manifest remains the source of authored design; the host
only supplies values the skin explicitly delegates.

```toml
[host]
inherit = ["surface.panel.radius", "surface.panel.border-width"]
fallback = "skin"          # "skin" (default) or "error"
```

Precedence, highest first:

1. an explicit value in the selected `mode.<mode>` override;
2. the live host value for a token listed in `inherit`;
3. the skin's concrete base value (headless/invalid-host fallback).

A token not listed in `inherit` is always the skin's explicit value. A host
value must never be injected into a token the skin did not delegate.

## Phase 1 scope (only these mappings)

| Skin token | Hyprland source | Why |
| --- | --- | --- |
| `surface.panel.radius` | `decoration:rounding` | outer window/panel corner |
| `surface.panel.border-width` | `general:border_size` | outer frame width |

Recommended built-in policy:

| Skin | Inherit radius | Inherit border | Reason |
| --- | ---: | ---: | --- |
| `glass` | yes | yes | default parity should follow compositor |
| `paper` | yes | yes | role-based skin; authored `mode.light` stays explicit |
| `terminal-host` | yes | yes | follows the rectangle roles while keeping the pill explicit |
| `terminal` | no | no | square/hairline identity is an explicit override |
| `flat` | no | no | zero-chrome identity is an explicit override |

Do **not** map `gaps_in`/`gaps_out` (window structure), padding, type or
colours. Notifications use `surface.card.radius`; full notification alignment
needs a future `surface.window` role, not overloading card radius. Host
rounding delegates the rectangle roles (panel/card/control/cell) through an
explicit skin opt-in; `surface.pill.radius` stays explicit because a pill is a
capsule/chip identity, not a rectangle corner. See
[`111` §Pill decision and guards](./111-host-radius-granularity.md#pill-decision-and-guards).

## Evidence that constrains the design

- Effective values must come from `hyprctl -j getoption`, not config text.
  Live config says rounding 8 / border 3, but the effective values are **0 / 1**
  because later Lua settings win.
- Hyprland 0.56.2 uses `general:border_size`; `decoration:border_size` does not
  exist.
- Without `HYPRLAND_INSTANCE_SIGNATURE`, `hyprctl -j instances` can discover a
  single instance; 0 or >1 instances must fall back rather than guess.
- `current/appearance/tokens.json` currently has no host block; the selected
  `terminal` skin's 0/1 values happen to match the live host, while `glass`
  would publish 12/1.5 against a 0/1 compositor.
- Prototype results: `glass` with the live host resolves radius 0 / border 1;
  `paper` light keeps its authored 6; the prototype generation hash matches the
  real runtime function for the same inputs; missing/invalid host values fall
  back to skin values.
- Schema guards: a `"host"` string as a numeric token is rejected, literal hex
  and structure groups are rejected, and the frozen schemas reject `[host]`
  until the additive contract change lands.

## Contract criteria (Phase 1)

- **H-1.1** Skin schema accepts an optional root `[host]` object with
  `additionalProperties: false`, required `inherit` (non-empty, unique, enum of
  supported token paths), optional `fallback` (`skin|error`, default `skin`).
  Existing manifests without `[host]` remain valid.
- **H-1.2** `appearance-manifest.schema.json` accepts the optional host policy;
  resolved `appearance-json` tokens remain concrete numbers/strings. No token
  type becomes `number | "host"`.
- **H-1.3** The generation manifest gains an optional `host` block (source,
  policy fingerprint, resolved values/provenance) and `intent.host`; when
  present it must equal the host fingerprint used by the appearance identity.
  The generation schema rejects a mismatch and rejects `host` when no delegated
  token participated.
- **H-1.4** The contract release is a new version (semver minor/bump as
  appropriate), with docs for precedence, allowlist, fallback and headless
  behavior; no existing tag is moved.
- **H-1.5** The assets schema/README document `[host]`; `glass` and `paper`
  opt in, `terminal` and `flat` remain explicit. `validate-skins` passes.

## Runtime criteria (Phase 1)

- **H-2.1** A host-defaults port exists and a Hyprland adapter reads effective
  values by `hyprctl -j getoption`; it discovers a single instance when the
  environment signature is absent and returns "unavailable" for 0/>1
  instances. No polling is used.
- **H-2.2** A pure resolver applies precedence (mode override > host > skin
  fallback) and reports provenance (`host`, `skin-fallback`, `mode-override`).
- **H-2.3** Validation accepts finite non-negative integers/floats in the
  supported ranges (radius 0..64, border 0..16), rejects booleans, strings,
  vectors, negatives, NaN/infinity, and unknown options; `fallback="error"`
  fails the generation before publishing.
- **H-2.4** Host reading and resolution happen once inside `converge.lock`;
  seed, reconcile, CLI intent hashing and `doctor` use the same snapshot.
  No per-app reads and no second lock.
- **H-2.5** Only delegated values enter `hostHash`; a host change that does not
  affect the selected skin/mode must **not** create a new generation. A change
  that does affect it must change the appearance/intent/generation identity.
- **H-2.6** `hostHash` (canonical JSON of version + participating values only)
  enters `appearance.v3`, the generation intent hash and the generation hash;
  instance signature, timestamps and `set` flags are excluded.
- **H-2.7** `doctor` compares the live host fingerprint to the committed
  manifest and reports drift when the delegated values changed; it must not
  report drift when only non-delegated settings changed.
- **H-2.8** Headless/non-Hyprland hosts resolve deterministically to skin
  fallbacks. `fallback="error"` is explicit and tested.
- **H-2.9** Existing generations/skins remain valid without `[host]`; no cache
  migration is required beyond normal GC.
- **H-2.10** A generation manifest with a host block is accepted by the
  platform consumer; refresh remains `appearance-refresh <genHash>` and the
  selected skin's rendered CSS is unchanged except for the resolved inherited
  values.

## Phase 2 / Phase 3 criteria (deferred)

Wlogout Phase 2b may consume the same delegated `surface.panel.radius` and
`surface.panel.border-width` for its action-card radius/border while taking the
card fill from `surface.card`. That is a consumer-template mapping, not a new
host token or a change to the host allowlist.

- **H-3.1** Additional mappings require a contract enum addition and a semantic
  match; opacity gets its own token, never an overloaded fill/ink alpha.
- **H-3.2** Blur/shadow mapping is considered only if a real GTK backdrop path
  exists; host shadow colour is never injected (no literal hex). A future
  `surface.window` role may cover notification outer cards; per
  [`111`](./111-host-radius-granularity.md) it is a separate proposal.
  Rectangle radii are delegated only through the explicit five-path allowlist;
  `surface.pill.radius` is never host-inheritable.
- **H-3.3** `gaps_in`/`gaps_out` remain structure and are never mapped to
  padding/rhythm.
- **H-3.4** A socket2 `configreloaded` watcher with a short debounce re-reads
  the host and converges only when the participating `hostHash` changes. No
  fixed sleep/poll. A direct `hyprctl keyword` is documented as “next converge”
  unless the event is verified.
- **H-3.5** The host source is pluggable: Hyprland first, with explicit
  unavailable behavior for other compositors; no hard dependency on Hyprland
  for the runtime.

## Verification matrix

- **Unit:** precedence, provenance, allowlist, `fallback=skin|error`, range/
  type rejection, headless discovery, hash participation, unchanged identity
  for non-delegated changes.
- **Contract:** additive schema positive/negative fixtures; old manifests
  validate; generation host/intent equality; no literal hex/structure.
- **Runtime:** `appearance.v3` hash matches the prototype for the same inputs;
  reconcile/seed/CLI/ledger/doctor wiring; no second lock.
- **Assets:** `validate-skins`; glass/paper opt-in, flat/terminal explicit;
  template output uses concrete resolved numbers.
- **Live/read-only:** compare `hyprctl -j getoption` values to the committed
  host block; simulate missing/invalid host; confirm a setting that does not
  participate causes no churn.
- **Phase 3:** socket2 event replay/debounce test; no polling.

## Risks and non-goals

- **No rollback rule:** a bad host-triggered generation must be fail-closed
  before publish, not published and rolled back.
- **Schema freeze:** this is a contract release; all consumers must pin in the
  planned order.
- **Hyprland key drift:** probe option names/versions and treat unknown keys as
  unavailable.
- **Structure leakage:** only the explicit `inherit` allowlist is legal.
- **Visual parity:** `glass` will follow a 0-radius host and lose its 12px
  authored rounding; that is intentional. `flat`/`terminal` opt out.
- **No palette changes:** host values never introduce colours or literal hex.

## Definition of done

1. Contract, runtime, assets and composition releases are staged in the
   approved order with all criteria above green.
2. A read-only live comparison proves the delegated values; non-delegated
   settings do not churn generations.
3. Headless fallback and `fallback="error"` are demonstrated.
4. Phase 2/3 mappings remain explicitly deferred or have their own approved
   criteria.
