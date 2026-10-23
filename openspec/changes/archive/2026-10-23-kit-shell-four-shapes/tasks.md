# Tasks

## 1. Icon contract — `IconSource` + fallback chain (AD-4, AD-7)

- [x] 1.1 Add the pure `kit/icon-source.ts`: `IconSource` tagged union, the
  `IconProvider` port, `IconRef<S>.fallback?`, the `iconByVariant` /
  `iconByStateKey` constructors, and `resolveIconSource(provider, ref, state)`
  implementing `provider table → ref.fallback → blank`.
  Verify: `grep -n "IconSource\|fallback?\|resolveIconSource" dotfiles/config/ags/kit/icon-source.ts`.
  - `kit/icon-source.ts` is new and PURE (no `gi://*`, no `ags/*`), so the chain
    is testable without the desktop stack. `iconByStateKey` now emits the state
    KEY; the chain maps `key → variant → art` (AD-7's `bar_mappings.states[v]`
    step), where the old constructor mapped it itself.
- [x] 1.2 Make `kit/icon.ts` the registry-backed facade: adapt `registry` to
  `IconProvider` (`resolve` returns `{kind:"file"}`), re-export the pure contract,
  and implement `resolveIcon(ref, state): IconSource | null` via the chain while
  keeping the current path-returning behavior.
  Verify: `make ags-typecheck` → PASS; `make bar-typecheck` → OK.
  - `make ags-typecheck` → `PASS (with GIR typings, 0 errors in the extracted bar
    tree …, 29 third-party, 16 in tests/, 0 exempt)`. `make bar-typecheck` →
    `OK: 0 errors in dotfiles/config/ags`.
  - Re-exports are explicit (`export { iconByStateKey, iconByVariant,
    resolveIconSource }`), not `export *`: the per-app `ags-symbol-check.mjs`
    does not follow star re-exports and failed `make per-app-drift-symbol-suites`
    with 5 `MISSING` imports until this was fixed.
- [x] 1.3 Adapt `BarWidgetButton` to the tagged union: `file` →
  `set_from_file(path)`, `name` → `set_from_icon_name(name)`, blank →
  `set_from_file("")`. The four live descriptors (btop, thunderbird, settings,
  power-menu) still typecheck and resolve the same paths.
  Verify: `make bar-typecheck` → `OK: 0 errors in dotfiles/config/ags`.
  - `dotfiles/config/ags/bar/Bar.tsx:46-49` renders the four descriptors through
    `BarWidgetButton` unchanged; `make bar-typecheck` is clean. Path resolution
    is preserved: e.g. `power-menu` key `default` → `states.default =
    power-menu-default` → `registry.resolve("power-menu","power-menu-default")`.

## 2. One Shell + four shapes (AD-8)

- [x] 2.1 Add the pure `kit/shapes.ts`: one `Shell<S>` and the four shapes
  (`DescriptorSpec`, `RichWidgetSpec`, `CollectionSpec`, `ForeignCollectionSpec`)
  extending it. Keep `BarWidgetSpec<S>` as the `DescriptorSpec<S>` alias so the
  four live descriptors are unchanged.
  Verify: `grep -n "interface Shell\|interface DescriptorSpec\|type BarWidgetSpec" dotfiles/config/ags/kit/shapes.ts`.
  - `kit/shapes.ts` is PURE; the rendered subtree is the type parameter `E`
    (default `unknown`) rather than `JSX.Element`, which keeps it free of the JSX
    runtime (a global `JSX.Element` stub under `dotfiles/config/ags/tests/`
    LEAKED into `ags-typecheck`'s app-wide program and broke gnim's namespace —
    658 errors — so it was removed).
- [x] 2.2 Add the rich `content: (state, ctx: BarContext) => E` field and a
  minimal injected `BarContext` naming `popup(...)` / `hub.control(...)` as
  capabilities — no `PopupSpec`/`ControlSpec` shape.
  Verify: `grep -n "content:\|interface BarContext\|popup" dotfiles/config/ags/kit/shapes.ts`.
  - `BarContext` carries only `popup` and `hub.control`; the full platform port
    (surfaces/notifier/preferences/theme) is future extraction work.
- [x] 2.3 Re-point `kit/widget.tsx` at the pure vocabulary and re-export it, so the
  public import path (`kit/widget`) is unchanged for callers. `widget.tsx` also
  specializes `E` to gnim's `JSX.Element` for the app (`BarContext`,
  `RichWidgetSpec`, `CollectionSpec`, `ForeignCollectionSpec`, `WidgetSpec`).
  Verify: `make bar-typecheck` → OK.
  - `make bar-typecheck` → `OK: 0 errors in dotfiles/config/ags`.

## 3. Unit tests

- [x] 3.1 Fallback-chain tests: table wins; tableless ref uses `ref.fallback`;
  blank when nothing resolves; blank when no variant is emitted; fallback not
  consulted when the provider resolves; fallback consulted when the table maps
  but `resolve` misses.
  Verify: `make ags-test` → `fail 0` and the new `kit-icon-source` suite passes.
  - `node --import ./resolve-hooks.mjs --test kit-icon-source.test.ts` →
    `tests 6, pass 6, fail 0`. `make ags-test` → `tests 75, pass 75, fail 0`.
- [x] 3.2 Shape / `Shell` typing tests: every shape is assignable to `Shell<S>`;
  `BarWidgetSpec` is realized from `DescriptorSpec`.
  Verify: `make ags-test` → `tsc --noEmit -p tests/tsconfig.tests.json` reports
  `0 type errors`.
  - `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.
  - Negative test: removing `extends Shell<S>` from `RichWidgetSpec` made
    `tsc -p tests/tsconfig.tests.json` fail (`TS2353`/`TS2739` in
    `kit-shapes.test.ts`); reverted.

## 4. Verify

- [x] 4.1 All gates green.
  Verify: `make ags-test` → 68+ tests, `fail 0`, 0 type errors;
  `make ags-typecheck` → PASS; `make bar-typecheck` → OK; `make gates-ci` → exit 0.
  - `make ags-test` → `tests 75, pass 75, fail 0`, 0 type errors.
  - `make ags-typecheck` → `PASS`.
  - `make bar-typecheck` → `OK: 0 errors in dotfiles/config/ags`.
  - `make gates-ci` → `EXIT=0`.
- [x] 4.2 The change validates and the tree is clean.
  Verify: `openspec validate kit-shell-four-shapes --type change` → valid;
  `git status --porcelain` → empty.
  - `openspec validate kit-shell-four-shapes --type change` → `Change
    'kit-shell-four-shapes' is valid`.
  - `git status --porcelain` → empty after the implementation commit.
