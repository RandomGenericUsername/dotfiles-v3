# assets-repo-split

## Why

`dotfiles-v3` still mixed four different kinds of thing in one repo: a
provisioning engine (Python + Ansible), a data corpus (icon templates,
wallpapers, config skeletons, Jinja sources, desktop entries), three console
CLIs with their shared libraries, and the runtime that drives the desktop. The
split moved the first three to pinned external repos and left `dotfiles-v3` as
the **composition repo**: manifests + runtime + gates.

Two forces made the corpus move non-negotiable:

- **The corpus had no version.** Icon templates, mappings, wallpapers, config
  skeletons, templates and desktop entries changed with the code, so a host
  could not say which corpus it was provisioned from. AD-3/AD-4 make one semver
  tag the deployment pin and separate it from the schema versions inside the
  corpus (AD-12).
- **`provisioning` could not be reused.** The engine's Python package, roles,
  playbooks and tests shipped in the same tree as the composition's pins and
  gates. AD-17 makes the engine a pinned external repo and the composition repo
  a consumer, with a seam (`--manifests-dir`, `--composition-root`,
  `--inventory`) rather than repo-relative path derivation.

The planning record lives in the spine and slices — there is no earlier
OpenSpec change for this migration. This change records what S0–S6 landed and
what S7 closed out, and it archives the resulting consumer contracts.

- Spine: `_bmad-output/planning-artifacts/architecture/architecture-assets-split-2026-10-21/ARCHITECTURE-SPINE.md` (AD-1…AD-17)
- Slices: same directory, `SLICES.md`
- Residual ledger: same directory, `RESIDUALS.md` (R-01…R-17)
- Closure record: `openspec/changes/archive/2026-10-22-assets-repo-split/POST-MIGRATION.md`

## What Changes

- **`dotfiles-assets` is born as a data-only repo** (S0, `v0.1.0`; populated to
  `v0.2.0`…`v0.5.0` across S1–S4): five class directories (`icons`,
  `templates`, `configs`, `content`, `desktop`), one `catalog.yaml`, one
  `schema_major` per schema-bearing class. No package, no console script, no
  engine, no generated artifacts.
- **The corpus is consumed through one pin**: `dotfiles/provisioning/assets.yaml`
  declares `repo` + `tag` + the class map; the assets role fetches once into
  `<install>/assets/<tag>/`, writes `pinned`, and every consumer role reads a
  class from that checkout. The role, verify and seven per-consumer mirrors are
  gate-locked (S1–S5).
- **The installer engine is extracted** (S6): `dotfiles/provisioning/installer.pin`
  pins `dotfiles-provision` `v0.1.0`; the in-repo provisioning tree is deleted;
  `bootstrap.sh` clones the tag and installs it editable (the wheel is not
  self-contained); the composition gates read the cached
  `.dev/dotfiles-provision-<tag>/`.
- **The composition repo is closed out** (S7): one documented pin set
  (`ARCHITECTURE.md` §4.1) validated by `deploy-coverage` (`assert_pin_set`),
  a terminal composition-only catch-all (`assert_composition_only`), MIT
  `LICENSE` + `CHANGELOG.md`, and docs that no longer claim an in-repo
  provisioning tree.

## Capabilities

### New Capabilities

- `assets-repo-consumption`: the pinned corpus — one data repo, five classes,
  one deployment tag, fetch-once/deploy-per-class, the schema support window,
  and the runtime-reads-spine rule.
- `assets-repo-boundaries`: what the corpus may never contain — a package or
  engine, generated/mutable artifacts, and the three permanently excluded
  corpora; destinations do not move.
- `installer-engine-extraction`: the engine as a pinned external repo, the
  composition seam, and the cached-checkout contract for the composition gates.
- `composition-closeout`: the semver pin set + mirror assertions, the
  composition-only tree allowlist, and the product metadata.

### Modified Capabilities

None. The per-package specs for the extracted CLIs and libraries live in their
own repos; historical archives and `_bmad-output/` are not rewritten.

## Non-goals

- No PyPI, registry or image publication: pins are git tags; images build at
  provision time (spine OPEN-2/OPEN-3).
- No runtime behavior change: the runtime keeps its argv/env/artifact contract;
  only its inputs' provenance moves to the spine (AD-13).
- No extraction of `dotfiles-runtime`; no per-app split of `ags-apps` (deferred).
- No rewrite of historical docs or archived OpenSpec changes (AD-15).
- No VM end-to-end run in this change; `incus` is unavailable (R-10).

## Impact

- **Composition repo**: `dotfiles/provisioning/{assets.yaml,cli-tools.yaml,installer.pin}`,
  `src/runtime/pyproject.toml`, `bootstrap.sh`, `scripts/deploy-coverage.py`,
  `ARCHITECTURE.md`, `AGENTS.md`, `docs/02-config-in-spine-pattern.md`, plus the
  new `LICENSE`/`CHANGELOG.md`. `src/provisioning/`, `dotfiles/assets/`,
  `dotfiles/applications/` and `dotfiles/scripts/` are deleted and gated.
- **Engine repo (`dotfiles-provision`)**: owns the Python orchestrator, 21
  roles, 23 playbooks, inventory and its own gates; consumes `cli-output` by
  tag and reads the composition manifests through the seam.
- **Assets repo (`dotfiles-assets`)**: owns the corpus and its validators
  (`validate-icons`, `validate-content`, `validate-templates`,
  `validate-desktop`, `lint`, `hermetic`).
- **Gates**: `gates-ci` stays six targets; `deploy-coverage` grows the pin-set
  and composition-only assertions; `ci-gates-parity` is unchanged.
