# extract-platform-in-place

## Why

Spine **AD-20** says the platform is extracted **in-place in `dotfiles-v3` first**,
proven with the existing gates, and only then published; that in-place extraction
is also the **"without deleting code" bridge**. Spine **AD-1** fixes the
dependency direction `contracts ← ags-platform ← ags-apps` and forbids app→app
imports; **AD-17** fixes the distribution shape (the framework is one unit found
by a bare specifier through a `node_modules` shortcut); **AD-2** forbids module
globals; **AD-19** requires every migration step to leave the tree green. Doc 101
§3 (repositories and packaging) and §13 step 8 ("Extract the platform — move the
ports + shared adapters + event client into `ags-platform`; make each app depend
on it; enforce apps → platform only") are this step.

Today the platform seams exist **in-place but scattered** across three sibling
directories, with no package identity and no public entry point:

- `dotfiles/config/ags/platform/{event-client,preferences,notifier,theme}.ts` —
  the pure ports (AD-4/AD-5/AD-11/AD-12/AD-13).
- `dotfiles/config/ags/lib/{event-bus,preferences,notifier,theme}.ts` — the Gio/
  Gtk adapters that bind those ports, and `lib/icon-registry.ts` — the
  `IconProvider` adapter.
- `dotfiles/config/ags/domains/{reactive,astal}.ts` — the injectable reactive
  port (AD-2) and its gnim binding.
- `dotfiles/config/ags/kit/{icon-source,icon}.ts` — the pure icon contract
  (AD-4/AD-7) and the registry-backed `IconProvider` facade.

Evidence:
`ls dotfiles/config/ags/platform dotfiles/config/ags/lib dotfiles/config/ags/domains`
→ the seams are spread across three directories;
`find dotfiles/config/ags -name package.json -o -name index.ts` → no matches
(no package identity, no entry point);
`grep -rn "lib/event-bus\|lib/theme\|kit/icon\|domains/reactive" dotfiles/config/ags --include=*.ts --include=*.tsx`
→ the bar reaches the seams through relative paths from a dozen files.

Verify:
`find dotfiles/config/ags -name package.json -o -name index.ts`;
`ls dotfiles/config/ags/platform dotfiles/config/ags/lib dotfiles/config/ags/domains`.

## What Changes

### One in-place `ags-platform` package (AD-17, AD-20)

The ports + shared adapters + the event client consolidate into **one package
root**: `dotfiles/config/ags/platform/`, carrying a package identity
(`package.json`, name `ags-platform`) and one public entry point (`index.ts`).
The package splits into the spine's two layers:

```
dotfiles/config/ags/platform/
  package.json                 # name ags-platform, exports the entry point
  index.ts                     # the public surface
  ports/                       # IconProvider contract, EventSource/EventHub,
                               #   Notifier, Preferences, Theme, the reactive port
  adapters/                    # icons (registry), events (Gio transport),
                               #   preferences, notifier, theme, the gnim binding
```

- **Moved into `ports/`:** `event-client.ts`, `preferences.ts`, `notifier.ts`,
  `theme.ts` (from `platform/`), `icon-source.ts` (from `kit/`), `reactive.ts`
  (from `domains/`).
- **Moved into `adapters/`:** `event-bus.ts`, `preferences.ts`, `notifier.ts`,
  `theme.ts`, `icon-registry.ts` (from `lib/`), `icon.ts` (from `kit/`),
  `astal.ts` (from `domains/`).

**The bar-specific ports stay in the bar** (AD-1): `LayoutProvider`
(`kit/layout.ts`, `bar/layout.default.ts`), `SurfaceSpec`/`SurfaceRegistry`/
`PopupHost` (`kit/surface.ts`, `kit/popup-host.tsx`), the Shell + four shapes
(`kit/widget.tsx`, `kit/shapes.ts`), the overlay coordinator (`kit/overlay.ts`),
and the app domain adapters (`domains/<domain>/{read-model,astal}.ts`) — these
are **not** platform.

### The bar consumes the package (AD-1, AD-20)

Every bar import of a moved seam is repointed at the package
(`../platform/adapters/…` / `../../platform/ports/…`). The bar is the only
consumer wired here; **no app imports another app**, and the platform package
imports nothing from the bar.

### Structurally consumable by the other apps (AD-17)

The package has a `package.json` whose `exports` map names its subpaths, so a
later `node_modules` shortcut (the `ags-consume-platform` step) can resolve
`ags-platform` and `ags-platform/adapters/*` by bare specifier from **every**
`config/ags*`. The other five apps (`src/gui-tools/**`) keep their own copies in
this change — migrating them is the `ags-apps` epic (AD-20 step 8). Nothing the
apps still need is deleted: their `lib/{event-bus-core,event-bus,theme,
icon-registry}.ts` copies are untouched (the "without deleting code" bridge).

### Registered for deployment, gates green (AD-17, AD-19)

Every new/relocated file is registered in `compositor_configs_skeleton_files`
and mirrored in the `verify` role; stale entries for the moved sources are
removed; the `ags/platform/adapters` destination directory is declared. A fresh
provision still resolves every import, and `make deploy-coverage`,
`make ags-test`, `make ags-typecheck`, `make bar-typecheck` and `make gates-ci`
stay green; `ags bundle dotfiles/config/ags/app.tsx … --gtk 4` exits 0.

## Out of scope

- **The five apps' migration** (`src/gui-tools/**`): their local copies stay;
  their consumption of `ags-platform` is the `ags-apps` epic (AD-20 step 8).
- **The versioned unit install + `node_modules` shortcut** (AD-17/AD-23): that is
  the `ags-consume-platform` provisioning step, not this in-place extraction.
  This change gives the package the identity the shortcut will point at.
- **The contract codegen** (AD-6): the event literals stay hand-pinned by the
  executed drift gate.
- **Baseline adapters** (`NoEventSource`, symbolic `IconProvider`; AD-18): a
  later platform step.
- **The per-domain read models** (`domains/<domain>/**`): they are app domain
  adapters per the spine, closed over at registration (AD-1/AD-2), not platform.

## Impact

- **New:** `dotfiles/config/ags/platform/{package.json,index.ts}`.
- **Moved (git mv):** `platform/{event-client,preferences,notifier,theme}.ts` →
  `platform/ports/`; `kit/icon-source.ts` → `platform/ports/`; `domains/reactive.ts`
  → `platform/ports/`; `lib/{event-bus,preferences,notifier,theme,icon-registry}.ts`
  → `platform/adapters/`; `kit/icon.ts` → `platform/adapters/`;
  `domains/astal.ts` → `platform/adapters/`.
- **Edited:** the bar importers of every moved seam (app.tsx, bar/registry.ts,
  bar/widgets/*, components/*, settings-panel/controls/*, services/*, kit/*,
  domains/<domain>/*, tests/*, `tests/tsconfig.tests.json`);
  `src/provisioning/ansible/roles/compositor_configs/vars/main.yml`,
  `src/provisioning/ansible/roles/verify/vars/main.yml`,
  `src/provisioning/tests/unit/{test_compositor_configs_role,test_verify_role}.py`.
- **No behaviour change:** every file is relocated and re-pointed, not rewritten.
