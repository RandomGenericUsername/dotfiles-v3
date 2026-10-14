# Tasks

## 1. Icon contract — `IconSource` + fallback chain (AD-4, AD-7)

- [ ] 1.1 Add the pure `kit/icon-source.ts`: `IconSource` tagged union, the
  `IconProvider` port, `IconRef<S>.fallback?`, the `iconByVariant` /
  `iconByStateKey` constructors, and `resolveIconSource(provider, ref, state)`
  implementing `provider table → ref.fallback → blank`.
  Verify: `grep -n "IconSource\|fallback?\|resolveIconSource" dotfiles/config/ags/kit/icon-source.ts`.
- [ ] 1.2 Make `kit/icon.ts` the registry-backed facade: adapt `registry` to
  `IconProvider` (`resolve` returns `{kind:"file"}`), re-export the pure contract,
  and implement `resolveIcon(ref, state): IconSource | null` via the chain while
  keeping the current path-returning behavior.
  Verify: `make ags-typecheck` → PASS; `make bar-typecheck` → OK.
- [ ] 1.3 Adapt `BarWidgetButton` to the tagged union: `file` →
  `set_from_file(path)`, `name` → `set_from_icon_name(name)`, blank →
  `set_from_file("")`. The four live descriptors (btop, thunderbird, settings,
  power-menu) still typecheck and resolve the same paths.
  Verify: `make bar-typecheck` → `OK: 0 errors in dotfiles/config/ags`.

## 2. One Shell + four shapes (AD-8)

- [ ] 2.1 Add the pure `kit/shapes.ts`: one `Shell<S>` and the four shapes
  (`DescriptorSpec`, `RichWidgetSpec`, `CollectionSpec`, `ForeignCollectionSpec`)
  extending it. Keep `BarWidgetSpec<S>` as the `DescriptorSpec<S>` alias so the
  four live descriptors are unchanged.
  Verify: `grep -n "interface Shell\|interface DescriptorSpec\|type BarWidgetSpec" dotfiles/config/ags/kit/shapes.ts`.
- [ ] 2.2 Add the rich `content: (state, ctx: BarContext) => JSX.Element` field and
  a minimal injected `BarContext` naming `popup(...)` / `hub.control(...)` as
  capabilities — no `PopupSpec`/`ControlSpec` shape.
  Verify: `grep -n "content:\|interface BarContext\|popup" dotfiles/config/ags/kit/shapes.ts`.
- [ ] 2.3 Re-point `kit/widget.tsx` at the pure vocabulary and re-export it, so the
  public import path (`kit/widget`) is unchanged for callers.
  Verify: `make bar-typecheck` → OK.

## 3. Unit tests

- [ ] 3.1 Fallback-chain tests: table wins; tableless ref uses `ref.fallback`;
  blank when nothing resolves; blank when no variant is emitted; fallback not
  consulted when the provider resolves; fallback consulted when the table maps
  but `resolve` misses.
  Verify: `make ags-test` → `fail 0` and the new `kit-icon-source` suite passes.
- [ ] 3.2 Shape / `Shell` typing tests: every shape is assignable to `Shell<S>`;
  `BarWidgetSpec` is realized from `DescriptorSpec`.
  Verify: `make ags-test` → `tsc --noEmit -p tests/tsconfig.tests.json` reports
  `0 type errors`.

## 4. Verify

- [ ] 4.1 All gates green.
  Verify: `make ags-test` → 68+ tests, `fail 0`, 0 type errors;
  `make ags-typecheck` → PASS; `make bar-typecheck` → OK; `make gates-ci` → exit 0.
- [ ] 4.2 The change validates and the tree is clean.
  Verify: `openspec validate kit-shell-four-shapes --type change` → valid;
  `git status --porcelain` → empty.
