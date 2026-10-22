# Tasks — assets-repo-split

Execution order is fixed: S0 → S1 → S2 → S3 → S4 → S5 → S6 → S7. No slice starts
before its predecessor is merged on `master`.

## Status

Last updated: 2026-10-22, after S7's gates ran in `.worktrees/S7/`
(`ticket/S7-composition-closeout`).

| Slice | State | Evidence anchor |
| --- | --- | --- |
| S0 — birth `dotfiles-assets` (data-only, five classes, schemas, catalog) | done | assets `v0.1.0`; the sibling repo's birth checklist/gates are recorded in its own ticket |
| S1 — `icons` + `content` → assets `v0.2.0` | done (merged) | pin + fetch commit `899c3f1a`; deletion + guard `a0e4ada2`; `make deploy-coverage` exit 0 |
| S2 — `configs` → assets `v0.3.0` | done (merged) | consumer cut `a3220b80`; destructive-last deletion `7d0ad759`; byte-identical static import proven pre-deletion |
| S3 — `templates` → assets `v0.4.0` | done (merged) | render cut `b38cf302`; docs/parity `1f6c2f12`; test seeding `0a33a1da`; spine fixes `2f5ee95e` |
| S4 — `desktop` → assets `v0.5.0` | done (merged) | contract + deploy `3cb965f0`; deletion + guard `2318d1c3`; ticket record `872d3225` |
| S5 — schema support window + `assets/pinned` content | done (merged) | `854bac08`; fetch + verify asserts and two negative tests; `make deploy-coverage` exit 0 |
| S6 — extract the installer engine | done (merged) | `dotfiles-provision v0.1.0`; cutover + deletion `fca6552c`; bootstrap installs the pinned checkout editable; both composition gates read `.dev/dotfiles-provision-v0.1.0/` |
| S7 — composition closeout | done in worktree (this change) | pin table §4.1 + `assert_pin_set` + `assert_composition_only`; MIT `LICENSE`; `CHANGELOG.md`; docs corrected; gates below |

## S0 — birth (done)

- [x] Create the public data-only repo with the mu-strict harness.
- [x] Add the five class dirs, `catalog.yaml`, and one `schema_major` per
  schema-bearing class.
- [x] Add the validators (`validate-icons`, `validate-content`,
  `validate-templates`, `validate-desktop`, `lint`, `hermetic`).
- [x] Prove a generated artifact fails validation (AD-11).
- [x] Release annotated `v0.1.0`; verify the anonymous tag fetch.

## S1 — icons + content (done)

- [x] Import `icons/` + `content/` byte-identically; release `v0.2.0`.
- [x] Pin `assets.tag: v0.2.0`; mirror it in the assets role and verify.
- [x] Fetch once into `<install>/assets/<tag>/`, write `pinned`, deploy the
  classes from the checkout.
- [x] Prove the runtime reads the spine and the deploy is unchanged.
- [x] Delete `dotfiles/assets/` + the icon-mapping corpus and assert absence.

## S2 — configs (done)

- [x] Import the 25 static config files; release `v0.3.0`.
- [x] Point `compositor_configs` and `config_copies` at the pinned `configs/`
  class; add the two role pin mirrors.
- [x] Prove the imported files byte-identical before deletion.
- [x] Delete `dotfiles/config/{hypr,hyprpaper,nvim,rofi,starship}/` and assert
  absence.

## S3 — templates (done)

- [x] Import the Jinja sources + `*.vars.schema.json`; release `v0.4.0`.
- [x] Move the five render roles to `<install>/assets/<tag>/templates/`; add
  `<role>_assets_pinned_tag` + `<role>_assets_templates_dir`.
- [x] Add the required-var parity test (AD-8.4); prove every supplied value.
- [x] Delete the role `templates/` dirs and `dotfiles/config/{zsh,wlogout}`;
  prune the pre-S3 `style.css.tpl` residue; assert absence.

## S4 — desktop (done)

- [x] Import the six entries + `toggle-touchpad` + `desktop.yaml`; release
  `v0.5.0`.
- [x] Deploy them from the pinned `desktop/` class and resolve the contract
  before the copy (layer 2).
- [x] Add `verify`'s deployed-set/`Exec`/keybind assertions (layer 3).
- [x] Delete `dotfiles/applications/` + `dotfiles/scripts/` and assert absence.

## S5 — schema window + pinned content (done)

- [x] Add `assets_schema_support` to the manifest/role and mirror it in verify.
- [x] Assert every schema-bearing class's `schema_major` before the first copy;
  add two negative tests.
- [x] Make `verify` read `<install>/assets/pinned` and assert its content equals
  the manifest tag.
- [x] Assert manifest/repo/tag/mirror parity in `deploy-coverage`.

## S6 — installer engine (done)

- [x] Create/release `dotfiles-provision v0.1.0` (engine Python + `ansible/` +
  tests, history preserved).
- [x] Add `dotfiles/provisioning/installer.pin`; make `bootstrap.sh` read it and
  install the pinned checkout editable.
- [x] Add the composition seam (`--manifests-dir`, `--composition-root`,
  `--inventory`) and the engine's seam guard.
- [x] Re-point both composition gates at the cached checkout
  (`.dev/dotfiles-provision-<tag>/`).
- [x] Delete `src/provisioning/`; assert it absent; prove `make gates-ci`,
  `make deploy-coverage`, `make hermetic`.

## S7 — composition closeout (this change)

- [x] Finalize the pin set in one place: `ARCHITECTURE.md` §4.1 + `assert_pin_set`
  (installer ↔ bootstrap, assets ↔ mirrors, CLIs ↔ manifest/role/verify,
  runtime libs/contract git+semver).
- [x] Add the terminal composition catch-all: `assert_composition_only`
  (`src/` = runtime; `dotfiles/` = config + provisioning; retired roots absent;
  exactly one local `source:`; installer is a separate pin, not a tool entry).
- [x] Add MIT `LICENSE` and `CHANGELOG.md` citing the spine/slices/ledger.
- [x] Correct `ARCHITECTURE.md` (§1, §2, §4.1, §5, §6.1, §6.6, §9, §10, §11,
  §12), `AGENTS.md` and `docs/02-config-in-spine-pattern.md`.
- [x] `rg 'src/provisioning|dotfiles/assets/icon-templates' AGENTS.md ARCHITECTURE.md`
  → exit 1.
- [x] Run the terminal gates: `make gates-ci` (6), `make deploy-coverage`,
  `make hermetic`, `test ! -e src/provisioning`, `git ls-files src` → runtime,
  `rg 'path = "\.\.|editable = true' --glob pyproject.toml .` → exit 1.
- [x] Record the closure: archive this change + `POST-MIGRATION.md`; add
  R-15/R-16/R-17 to the residual ledger.

## S7 verification (worktree `ticket/S7-composition-closeout`)

| Command | Observed |
| --- | --- |
| `make gates-ci` | exit 0 — `contracts-check`, `runtime-architecture` (132 passed), `ansible-embedded-template-lint` (`PASS`), `deploy-coverage` (`PASS`), `ci-gates-parity` (`PASS`, 6 jobs), `per-app-drift-symbol-suites` (`OK`) |
| `make deploy-coverage` | exit 0 — `CHECK pinned installer engine v0.1.0 at …`; `pin set — installer dotfiles-provision v0.1.0 … assets dotfiles-assets v0.5.0, CLIs csg/itr/weg v0.2.0, runtime pins cli-invocation-contract v0.2.0, cli-output v0.1.0`; `COMPOSITION-ONLY …` |
| `make hermetic` | exit 0 — `hermetic: PASS` (no in-repo package sources) |
| `test ! -e src/provisioning` | exit 0 |
| `git ls-files src \| sed 's#^src/##; s#/.*##' \| sort -u` | `runtime` |
| `rg -n 'path = "\.\.|editable = true' --glob 'pyproject.toml' .` | exit 1 (no match) |
| `rg 'src/provisioning\|dotfiles/assets/icon-templates' AGENTS.md ARCHITECTURE.md` | exit 1 (no match) |
| negative controls | non-semver pin, literal tag in `bootstrap.sh`, CLI verify-mirror drift, `dotfiles/config/extra`, and a returned `src/provisioning/` each exit 1 with a named failure |

The full command/output record is
`openspec/changes/archive/2026-10-22-assets-repo-split/POST-MIGRATION.md`.
