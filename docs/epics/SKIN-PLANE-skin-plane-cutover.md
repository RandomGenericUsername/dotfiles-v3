# SKIN-PLANE — skin-plane cutover (epic)

> **id:** `SKIN-PLANE`
> **kind:** epic (container only; the composition branch is the rollup record)
> **status:** done
> **slug:** `skin-plane-cutover`
> **worktree:** `.worktrees/SKIN-PLANE/`
> **branch:** `ticket/SKIN-PLANE-skin-plane-cutover`
> **composition release:** tag `v0.1.36` (CHANGELOG `0.6.36`)

This is the composition-side close of the skin-plane program. The children below
live in their own repos, own their own gates and release tags, and are recorded
here as **done** with the ticket that produced each release. This epic edits only
`dotfiles-v3`: the pins, the composition gates, and the live docs.

## Final boundary (normative)

The skin plane is **appearance**, not structure:

- A skin is **palette/ink mapping + paint + rhythm/density** only.
- **Structure is app-owned.** A skin never describes layout trees, variants,
  ordering or presence.
- **Layout tokens are TSX-owned.** `panel-width`, `bt-list-spacing`,
  `bar-row-height` and `chip-min` are read through `skinValue()` /
  `createAppSkinValue`; templates never expand them into CSS.
- **Provider composition.** Exactly one `Gtk.CssProvider` consumes the skin per
  app. It composes the runtime palette role block + the expanded skin CSS, is
  added at **USER priority (800)**, and is **installed last** so it wins over
  app/theme providers.
- **No new refresh protocol.** Live apps answer the existing `palette-refresh`
  request; the **bar stays restart-only**. No `palette-refresh` handler was
  added to the bar.
- **Selection is runtime state.** The selected skin lives in runtime
  `desired.json` as `skin: "<name>"`; the default is `glass`. There is no
  per-app skin choice in v1.

## Cross-repo children (all done)

| Repo | Ticket(s) | Release tag(s) | Scope |
| --- | --- | --- | --- |
| `contracts` | `REQ-011-skin-plane-contract`, `REQ-012-skin-units`, `REQ-013-skin-artifact-interface`, `REQ-014-skin-hairline-layout-ownership` | `v0.5.0` → `v0.6.0` | Frozen skin-plane contract, units, artifact interface, hairline/layout ownership |
| `dotfiles-assets` | `req-009-skins-class`, `req-010-skins-parity`, `req-011-skins-value-types`, `req-012-skins-template-naming`, `req-013-skins-hairline-layout`, `req-014-skins-app-templates` | `v0.7.0` → `v0.11.0` | `skins/` class, parity, value types, `<configDir>` templates, hairlines, seven app templates |
| `ags-platform` | `REQ-014-skin-port-adapter`, `REQ-015-skin-token-validation`, `REQ-016-skin-app-scope` | `v0.6.0` → `v0.8.0` | Skin port/adapter, per-token validation, `createAppSkin({ configDir })` |
| `dotfiles-runtime` | `REQ-010-skins-derivation-layer`, `REQ-011-skins-interface-reconcile`, `REQ-012-skins-hairline-token` | `v0.7.0` → `v0.8.1` | Derivation, pointer/`skin.json` interface, 24-token vocabulary |
| `dotfiles-provision` | `REQ-020-skin-plane-deploy`, `REQ-021-skins-assets-v011`, `REQ-022-ags-platform-v08-mirror` | `v0.1.34`, `v0.1.35`, `v0.1.36` | Deploy `<install>/skins`, verify seven templates + vendored contracts, platform mirror `v0.8.0` |
| `ags-bar` | `REQ-003-skin-plane-pilot` | `v0.4.0` | Apply the bar skin last at USER priority; restart-only |
| `ags-clipboard` | `REQ-003-skin-consumption` | `v0.3.0` | App-scoped skin consumption |
| `ags-notifications` | `REQ-003-skin-consumption` | `v0.3.0` | App-scoped skin consumption |
| `ags-wallpaper-selector` | `REQ-002-skin-consumption` | `v0.3.0` | App-scoped skin consumption |
| `ags-capture-tool` | `REQ-015-skin-consumption` | `v0.5.0` | App-scoped skin consumption |
| `ags-icme` | `REQ-004-skin-consumption` | `v0.3.0` | App-scoped skin consumption |
| `ags-btop-theme-studio` | `REQ-003-skin-consumption` | `v0.3.0` | App-scoped skin consumption |

## Composition pins (this epic)

| Pin | Tag |
| --- | --- |
| `program-tuple.yaml` `ags-platform` | `v0.8.0` |
| `program-tuple.yaml` `contracts` | `v0.6.0` |
| `program-tuple.yaml` `dotfiles-assets` | `v0.11.0` |
| `cli-tools.yaml` `dotfiles-runtime` | `v0.8.1` |
| `installer.pin` | `v0.1.35` |
| `assets.yaml` `assets.tag` | `v0.11.0` (+ the `skins` class and data entry) |
| `apps.yaml` bar / notifications / capture / clipboard / wallpaper-selector / icme / btop-theme-studio | `v0.4.0` / `v0.3.0` / `v0.5.0` / `v0.3.0` / `v0.3.0` / `v0.3.0` / `v0.3.0` |

## Acceptance

- [x] Every exact pin above is in the composition manifest and its gate mirror.
- [x] `assets.yaml` lists the sixth `skins` class and the `<install>/skins` data entry, matching the engine.
- [x] The composition gates accept the final tuple/app inventory and reject drift.
- [x] Live docs state the data path, runtime artifacts, app factory, bar restart lane and `desired.json` selection.
- [x] Composition-only: no `bootstrap`, `apply`, install or live-desktop action was run by this epic.
- [ ] Release tag and fast-forward merge to `master` — **blocked** by the engine mirror below.

## Evidence / closeout

Composition branch: `ticket/SKIN-PLANE-skin-plane-cutover`. Files: the program
tuple, assets/CLI/app manifests, the composition gate class list + app release
inventory, and the live docs.

Commands run on 2026-11-05 (local cache prepopulated from the local engine tag;
no network, no deploy):

```text
$ make ci-gates-parity
ci-gates-parity: PASS -- every gates-ci target has a CI job and every CI job is a gates-ci target (modulo the declared tables)
rc=0

$ make ansible-embedded-template-lint
CHECK embedded templates in expression contexts (88 file(s) scanned under engine v0.1.35 ansible)
ansible-embedded-template-lint: PASS
rc=0

$ make per-app-drift-symbol-suites
OK: per-app contract drift + symbol suites green (no in-repo suites; all moved to the standalone app repos)
rc=0

$ make deploy-coverage
CHECK pinned installer engine v0.1.35 at .../.dev/dotfiles-provision-v0.1.35
FAIL: dotfiles/provisioning/program-tuple.yaml: ags-platform 'v0.8.0' is not resolved by ansible/roles/ags_platform/vars/main.yml `ags_platform_version` = 'v0.5.0'
rc=2
```

The failure is a real cross-repo skew, not a composition typo: engine
`v0.1.35` (REQ-020/REQ-021, assets v0.11.0) still mirrors
`ags_platform_version: v0.5.0` and `verify_ags_platform_version: v0.5.0`.
The final app tags need platform `v0.8.0` (`createAppSkin`), so pinning the
tuple back to `v0.5.0` would break the apps and the shared
`apps/node_modules/ags-platform` shortcut at apply time.

Diagnostic only (not a gate): with a temporary copy of the engine checkout whose
two platform mirrors were edited to `v0.8.0`, `make deploy-coverage` printed
`PASS` and the same final tuple/app/assets/skins inventory. That proves the
composition half is complete; the missing half is an engine release.

**Required external fix:** cut `dotfiles-provision` with
`ags_platform_version: v0.8.0` / `verify_ags_platform_version: v0.8.0`, then bump
`installer.pin` to that tag and rerun `make deploy-coverage`. Do not merge this
composition branch or tag it before that fix; the harness rule is that `master`
only takes green gates.

No `bootstrap`, `apply`, install, or live-desktop mutation was performed.
