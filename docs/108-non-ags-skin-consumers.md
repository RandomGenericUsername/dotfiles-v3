# 108 — Non-AGS skin consumers (wlogout first)

> **Status:** proposed — criteria only. No production change, tag or live apply
> is part of this document.
> **Epic:** [`SKIN-CONSUMERS`](./epics/SKIN-CONSUMERS.md)
> **Baseline:** contracts `v0.8.0`, ags-platform `v1.0.1`,
> dotfiles-runtime `v1.0.6`, dotfiles-assets `v0.13.0`,
> dotfiles-provision `v0.1.49`, composition `v0.1.53`.
> **Investigation evidence:** generated wlogout sheet + GTK3/Broadway probes in
> `/tmp/opencode/wlogout-skin/` (ephemeral; reproduce with the checks below).

## Decision

Use **generic plumbing + consumer-specific templates**. Do not add a
`WlogoutAdapter` to the runtime.

A consumer is a name whose config directory owns an appearance target:

```text
skin template:  skins/templates/<consumer>.gtk.css.j2
runtime:        appearance/<consumer>.css
manifest:       appearance.targets += { configDir: <consumer>,
                                         path: appearance/<consumer>.css }
provisioning:   config/<consumer>/appearance.css -> state/current/appearance/<consumer>.css
app:            imports the generated sheet last; app-owned structure stays static
```

For CSS-shaped consumers this already fits the frozen v3 target schema:
`configDir` is the consumer config-directory name and the path pattern is
`appearance/<configDir>.css`. The runtime derives targets from the selected
skin's templates, not a fixed AGS app list.

## Scope

### In scope

- wlogout as the first worked example: palette parity today, then skin
  paint/rhythm.
- The generic target/stable-link/provisioning pattern for CSS consumers.
- Criteria for GTK3/GTK4 and the format-aware extension needed by
  rofi/btop/kitty.
- Validation and release sequencing.

### Out of scope

- AGS-only behavior changes; structure/layout ownership by skins.
- Moving tags or changing production pins in this document.
- A live-reload lane for wlogout: it reads CSS at launch; a generation change
  is visible on the next launch.
- Mapping compositor/window structure (Hyprland gaps, wlogout grid) into skin
  tokens.

## Facts that constrain the design

- wlogout `1.2.2`, GTK3; `style.css` is loaded by path; `layout` is app-owned.
- GTK3 supports `@import` and `@define-color`, including `alpha(@role, n)`;
  it does **not** support `var()` custom properties or `color-mix()`.
- GTK4 supports `var()` and `color-mix()`.
- wlogout palette parity already works: its static style imports
  `current/palette/colors.gtk.css`.
- A generated `appearance/wlogout.css` is already derivable with no runtime
  code change once a `wlogout.gtk.css.j2` exists.
- `config/wlogout` is a real directory, so AGS discovery ignores it.
- Rofi `.rasi` supports imports/variables but not `alpha(@role, n)` and cannot
  use role names containing `_`. btop themes are key/value only and have no
  rhythm/typography surface. Non-CSS formats cannot use the frozen `.css`
  target path.

## Phase 1 — wlogout palette parity (today)

**Goal:** confirm and document the existing palette-only path; no code change
required.

### Criteria

- **W-1.1** wlogout's static `style.css` imports the stable palette target and
  a new generation changes the palette seen on the next launch.
- **W-1.2** The palette import resolves through `state/current/palette/`, never
  a generation-specific path or app tag.
- **W-1.3** No AGS discovery treats `config/wlogout` as an AGS instance.
- **W-1.4** A GTK3 parse of the static style succeeds with the generated
  palette present, and fails clearly when the palette import is missing.

### Verification

- Inspect `config/wlogout/style.css` and `readlink -f` the palette path.
- Load the static sheet with GTK3 `CssProvider`; assert success.
- Negative: remove/rename the palette target in a temp copy; assert the GTK3
  parse reports a missing import.

## Phase 2 — wlogout skin paint/rhythm

**Goal:** add wlogout as a generic CSS consumer. No runtime production adapter;
no contract schema change.

### Criteria

- **W-2.1** `dotfiles-assets` ships
  `skins/templates/wlogout.gtk.css.j2` for every bundled skin, and
  `make validate-skins` passes with `wlogout` in the target set.
- **W-2.2** The template contains **only** paint/rhythm: `window` background
  colour, `button`/state colours, border, radius, padding, font. It must not
  contain `#` literals, `transition`, structure/variant tokens, layout IDs
  (`#lock`, `#logout`, …), icon URLs, wallpaper rules, or grid/margins.
- **W-2.3** The runtime test proves a skin with a wlogout template yields
  `config_dirs` including `wlogout`, an `appearance/wlogout.css` artifact, and a
  manifest target `{configDir: "wlogout", path: "appearance/wlogout.css"}`.
  No production runtime change is required; a regression test is mandatory.
- **W-2.4** A generation-manifest fixture with the wlogout target validates
  against `contracts/schemas/generation-manifest.schema.json`.
- **W-2.5** Provisioning adds a stable link
  `config/wlogout/appearance.css -> state/current/appearance/wlogout.css` and
  verify asserts the link names `current/appearance` and resolves.
- **W-2.6** The static wlogout style imports `appearance.css` **last**; its
  app-owned wallpaper, icon, layout and transition rules remain static. The
  generated sheet wins the cascade for paint.
- **W-2.7** GTK3 validation: generated, static and combined sheets parse with
  `Gtk.CssProvider`; a Broadway-backed wlogout run with a temporary
  `XDG_CONFIG_HOME` stays alive and emits no CSS warnings. Negative controls
  (`var()`, missing import) must emit warnings.
- **W-2.8** No live reload is added. Documentation states "next launch" for
  wlogout; if it is open during a generation change, it remains on the old
  style until relaunch.
- **W-2.9** Every bundled skin ships the template. If a skin omits it, the
  target disappears and wlogout's import would fail; the release gate must
  reject that skin/template combination.
- **W-2.10** The release records the one-time template-hash churn: adding the
  shared template changes every skin's entry hash and causes one full
  appearance refresh even when existing AGS CSS is unchanged.

### Verification

- Assets: `make validate-skins`.
- Contracts: fixture schema test.
- Runtime: targeted appearance/generation tests.
- Provisioning: state-link/verify role tests.
- Local UI: GTK3 `CssProvider` probes and Broadway wlogout smoke.
- Negative: missing target, missing import, literal hex, structure selector,
  `var()` on GTK3.

## Phase 3 — non-CSS / toolkit consumers

**Goal:** generalize only where the format is real; do not force every app into
a CSS target.

### Criteria

- **W-3.1** A contract proposal defines a format-aware target, e.g.
  `{consumer, path, format: css|rasi|theme|conf}`, or an equivalent; the current
  `.css`-only path regex is explicitly recognized as the blocker.
- **W-3.2** GTK3 and GTK4 get separate templates and consumer aliases
  (`gtk3`/`gtk4`) because `configDir` rejects `gtk-3.0` and the CSS dialects
  differ. Their static `gtk.css` imports the generated sheet last.
- **W-3.3** Rofi uses a generated `.rasi` fragment only with solid palette
  roles and valid role names (`on-surface`, not `on_surface`); it never uses
  `alpha(@role, n)`. Geometry/typography may be projected. Validation is
  `rofi -dump-theme` exit 0.
- **W-3.4** btop stays palette-only: key/value theme validation and the
  existing `SIGUSR2` reload; no rhythm/type projection is claimed.
- **W-3.5** kitty stays palette-only unless a `.conf` format target is
  approved; if added, validate with the existing `SIGUSR1` reload.
- **W-3.6** Hyprland/hyprpaper/hyprlock are explicitly out of scope for skin
  paint/rhythm; Hyprland palette/background behavior is unchanged.
- **W-3.7** Every new consumer declares its refresh lane: `live` (only where a
  real handler exists), `restart`, or `launch`. No false live lane is allowed.

## Release and collision rules

- Implement assets + provisioning + runtime-test slice first; do not edit
  composition pins until a cutover ticket.
- Separate worktree per repo; no cross-repo branch.
- Do not pin branches/SHAs in production; release tags are the synchronization
  boundary.
- Runtime work starts only after the one-lock/runtime line is released
  (`v1.0.6` baseline).
- Both wlogout and Hyprland host-default work touch `dotfiles-assets`; merge
  wlogout assets first, then the host-default contract work, or rebase the
  second branch after the first tag.
- No `apply` during the wlogout slice; validate with temp XDG state and
  Broadway.

## Definition of done

1. Assets, provisioning and runtime-test criteria above pass and are released.
2. wlogout renders the generated palette + skin on next launch with no CSS
   warnings; static layout/icons/wallpaper remain app-owned.
3. The contract and provisioning verify prove the target and stable link.
4. The template-hash churn and launch-time semantics are documented.
5. Phase 3 has an approved contract design or is explicitly deferred.
