## Why

The AGS config had **no unit-test harness at all**, and the battery panel is the
first feature that puts a meaningful amount of *decision* logic into it.

Everything in `dotfiles/config/ags/` was previously either a widget (untestable
without GTK, which is honest) or a one-line lookup. The battery panel is neither:
how a duration reads, which word tells the user whether that duration is a
countdown or a charge target, which glyph a power-profile row shows, and which
row carries the `.sel` class are all **pure functions of their arguments** —
they just happened to have nowhere to live, so the natural home was the widget,
where none of them could be checked.

That is the whole gap. `make capture-test` runs 144 assertions over the capture
TOOL's domain and zero over the ags config's own logic.

Separately, the panel needs three power-mode glyphs, and the three owner-supplied
SVGs would each have rendered **invisibly**: all three are hardcoded near-black
and the panel sits on dark glass (`alpha(@color_00, 0.94)` over a transparent
window).

## What Changes

Two workstreams, one change. **Workstream A is this agent's; workstream B
(panel widget, popup windows, CSS, `app.tsx` wiring, registration of the widget
files, mock parity) is a second agent's** and is scoped but not implemented in
`tasks.md` / `design.md`.

### Workstream A — foundation (implemented)

- **A1 — Three power-mode glyph templates** under
  `dotfiles/assets/icon-templates/power-mode/{powersave,balanced,performance}/default/icon.svg`,
  with every hardcoded near-black fill rewritten to `{{COLOR_FOREGROUND}}` and
  **geometry left byte-identical**.
- **A2 — A `power-mode` group** in the ITR manifest with exactly three variants,
  registered in the regenerated `dotfiles/config/ags/icons.json`.
- **A3 — `ags-test`**: a `node --test` harness for the ags config's pure modules,
  modelled on `make capture-test`, wired into `gates-ci` and `.github/workflows/gates.yml`.
- **A4 — `components/battery/presentation.ts`**: the pure presentation logic,
  with 28 unit tests over every branch.

### Workstream B — panel UI (scoped, not implemented here)

The battery status panel widget, its two popup windows, the `style.css` rules,
the `app.tsx` registration, the `bar/widgets/battery.tsx` integration and mock
parity.

## Non-goals

- **No `system-*` duplicate variants for `power-mode`, and no `BAR_GROUPS`
  entry.** Both would actively break the glyphs. See `design.md` § "Why
  `power-mode` is not a bar group" — this is the one decision in this change
  that a reasonable reader would get backwards, so the reasoning is recorded
  there in full and repeated in the manifest's own comment.
- Not deriving the profile list from the daemon's response at runtime
  (`design.md` § "Why the profile list is explicit").
- Not clamping an implausible duration to 24h and displaying it as a precise
  value (`design.md` § "The >24h bound").
- Not typechecking the ags config's **widget** files. That is `capture-typecheck`'s
  problem and it is still a developer gate; the new harness covers pure modules
  only, which is what makes it runnable in CI.

## Impact

- **New:** `dotfiles/config/ags/tests/` (tsconfig, resolve hook, 2 test files,
  1 fixture), `dotfiles/config/ags/components/battery/presentation.ts`,
  3 icon templates, the `power-mode` manifest group.
- **Changed:** `Makefile` (`ags-test`, `ags-test-deps`, `GATES`, `gates-ci`),
  `.github/workflows/gates.yml` (one job), `.gitignore` (one path),
  `dotfiles/config/ags/icons.json` (regenerated), the
  `compositor_configs` role vars (one file registered — placement is per-file, so
  an unregistered source **never deploys**), and the provisioning role's
  skeleton-file test (65 → 66).
- **No behaviour change** to anything already deployed. `icons.json` gains one
  group; see `design.md` § "Regenerating icons.json" for the pre-existing
  staleness the regeneration also corrected.