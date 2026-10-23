# Changelog

Notable changes to `dotfiles-v3`, the **composition repo**: the provisioning
manifests, the pinned installer-engine entry point (`bootstrap.sh`), the pins and
the gates. The runtime is its own pinned repo. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This repo is not
released (it has no tags); the 0.x sections group the assets-split slices by the
commits that landed them, and the authoritative record is the planning set — not
this summary:

- spine: `_bmad-output/planning-artifacts/architecture/architecture-assets-split-2026-10-21/ARCHITECTURE-SPINE.md`
- slices: `…/SLICES.md`
- residual ledger: `…/RESIDUALS.md` (open items R-01…R-17)
- closure record: `openspec/changes/archive/2026-10-22-assets-repo-split/POST-MIGRATION.md`

## [Unreleased]

## [0.6.1] - 2026-10-23 — runtime-seed fix

### Fixed

- Installer engine pin `v0.1.7` → `v0.1.8`: the `runtime-seed` playbook no longer invokes the
  deleted `composition_root/src/runtime`; it runs the installed pinned `dotfiles-runtime` from
  the uv tool bin dir (BUG-001 in `dotfiles-provision`). Bootstrap/apply now reaches the seed
  step after the runtime extraction.

## [0.6.0] - 2026-10-23 — runtime repo consumption (REQ-002)

### Changed

- `dotfiles-runtime` is consumed as `{name, repo, tag}` at `v0.1.0`; the
  installer engine pin is `v0.1.7` (its role/verify mirrors carry the runtime
  entry). The CLI manifest now has **zero** local `source:` entries.
- `deploy-coverage` asserts the runtime's pinned shape, requires `src/` to be
  absent, and no longer validates a composition-owned `[tool.uv.sources]` or a
  vendored `contracts/` copy.
- The runtime-only gates (`contracts-check`, `runtime-architecture`,
  `contract-pin-check`) and their CI jobs moved to the runtime repo with the
  code. The composition keeps `ansible-embedded-template-lint`,
  `deploy-coverage`, `ci-gates-parity` and `per-app-drift-symbol-suites`.
- `AGENTS.md`, `README.md`, `ARCHITECTURE.md` and `docs/WORKSPACE.md` state the
  new boundary: the composition authors manifests and gates only.

### Removed

- `src/runtime/`, `contracts/` and `scripts/contract-pin-check.py` — the
  runtime and its conformance material live in `dotfiles-runtime`.

## [0.5.0] - 2026-10-22 — composition closeout (S7)

### Added

- The **composition pin set** as one documented table (`ARCHITECTURE.md` §4.1)
  and one executable assertion: `deploy-coverage`'s `assert_pin_set` requires
  every pin to be a semver tag and every mirror to agree — `installer.pin` ↔
  `bootstrap.sh`, the assets tag ↔ its role/verify mirrors, every CLI tag ↔
  manifest/role/verify, and every runtime `[tool.uv.sources]` a `git` + `tag`
  source (never `path`, `editable`, `rev` or `branch`).
- `assert_composition_only` — the terminal composition catch-all: `src/` holds
  `runtime/` only, `dotfiles/` holds `config/` + `provisioning/` (`config/` is
  exactly the mutable `btop/active-theme`), and `src/provisioning/`,
  `dotfiles/assets/`, `dotfiles/applications/` and `dotfiles/scripts/` are
  asserted absent.
- MIT `LICENSE` and this `CHANGELOG.md` (the metadata the closeout exposed).

### Changed

- `ARCHITECTURE.md`, `AGENTS.md` and `docs/02-config-in-spine-pattern.md` now
  describe the installer engine as the pinned external `dotfiles-provision`
  repo everywhere; no section claims an in-repo provisioning tree.
- `bootstrap.sh`'s semver error example is `vX.Y.Z`, not the current tag, so the
  shell really reads `dotfiles/provisioning/installer.pin` instead of repeating
  it.

## [0.4.0] - 2026-10-22 — installer engine extracted (S6)

### Changed

- The provisioning engine (the Python orchestrator **and** the Ansible tree) is
  the pinned external `dotfiles-provision` repo at `v0.1.0`
  (`dotfiles/provisioning/installer.pin`). `bootstrap.sh` clones the tag into
  `.dev/dotfiles-provision-<tag>/` and installs it editable, because the wheel
  packages `src/provisioning` only; `deploy-coverage` and
  `ansible-embedded-template-lint` read the same cached checkout.
- This repo keeps only the composition seam: declarative manifests, the runtime,
  the gates and `bootstrap.sh` (`dotfiles-provision --manifests-dir …`).

### Removed

- `src/provisioning/` — engine Python package, roles, playbooks, inventory and
  its tests. `deploy-coverage` asserts the root stays absent.

## [0.3.0] - 2026-10-22 — desktop class + schema window (S4–S5)

### Added

- `desktop/` class at assets `v0.5.0`: six `.desktop` entries,
  `toggle-touchpad`, and `desktop.yaml` (`requires`/`optional`). The
  `compositor_configs` role resolves the contract **before** the copy; `verify`
  re-asserts the deployed set and resolves every `Exec` binary.
- `assets_schema_support` on fetch and verify (AD-12): every schema-bearing
  class must be inside the consumer's supported `schema_major` window before the
  first copy, and `verify` rejects a corpus outside it.

### Removed

- `dotfiles/applications/` and `dotfiles/scripts/` (retired with an absence
  guard).

## [0.2.0] - 2026-10-22 — configs + templates (S2–S3)

### Added

- The pinned corpus's `configs/` (assets `v0.3.0`) and `templates/`
  (assets `v0.4.0`) classes. The 15 non-bar skeletons, the copied
  `nvim`/`starship`/wlogout `layout` files, and every Jinja source (zsh, kitty,
  btop, wlogout, display-manager) render from `<install>/assets/<tag>/…`.
- `<role>_assets_pinned_tag` + `<role>_assets_templates_dir` mirrors and the
  required-var parity test (AD-8.4).

### Removed

- `dotfiles/config/{hypr,hyprpaper,nvim,rofi,starship,zsh,wlogout}/` as authored
  sources (the last mutable file, `btop/active-theme`, stays by design).

## [0.1.0] - 2026-10-21 — corpus split begins (S0–S1)

### Added

- `dotfiles-assets`, a data-only pinned repo (no package, no console script),
  born at `v0.1.0` and populated to `v0.2.0`.
- The `icons/` and `content/` classes: icon templates, one group map, the icon
  vocabulary, and the wallpaper archive. `dotfiles/provisioning/assets.yaml`
  declares repo + tag + class map; the assets role and verify mirror it.

### Removed

- `dotfiles/assets/` and the in-repo icon mapping corpus, replaced by
  `<install>/assets/<tag>/` from the pin (`deploy-coverage` asserts absence).
