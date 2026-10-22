# assets-repo-boundaries Specification

## Purpose
Defines what the `dotfiles-assets` repo is and is not: a data corpus with five
classes, no importable package, no executable surface, no generated or mutable
artifacts, and three corpora that are permanently excluded.

## Requirements

### Requirement: The assets repo is data-only

`dotfiles-assets` SHALL contain no importable package, no console script and no
engine. It SHALL validate as data (`validate-icons`, `validate-content`,
`validate-templates`, `validate-desktop`, `lint`, `hermetic`) and SHALL reject a
generated artifact committed to the tree.

#### Scenario: no executable surface

- **WHEN** the assets repo is installed or inspected
- **THEN** it exposes no console script and no importable package; consumers
  only copy or render files from the checkout

#### Scenario: a generated artifact fails validation

- **WHEN** `icons/mappings/icons.json` (a generated mapping) is committed
- **THEN** the assets `validate` gate fails, because generated outputs belong to
  the runtime or the consumer, not to the corpus

### Requirement: Three corpora are permanently excluded

`dotfiles-assets` SHALL NOT absorb the GUI apps (`ags-apps`), the platform
(`ags-platform`) or the installer engine (`dotfiles-provision`). Each stays in
its own repo or pinned unit.

#### Scenario: the corpus tree names no app or engine source

- **WHEN** the assets tree is inspected
- **THEN** it contains no app source (bar, notifications, capture-tool,
  wallpaper-selector, icme, btop-theme-studio, hypr-pano) and no engine
  (roles/playbooks/Python orchestrator)

#### Scenario: an excluded corpus returns to the composition repo

- **WHEN** a retired GUI, CLI, corpus or engine tree reappears under `src/` or
  `dotfiles/`
- **THEN** `make deploy-coverage` exits 1 (the per-tree guard or the terminal
  `assert_composition_only` sweep)

### Requirement: The composition repo authors no package sources

The composition repo SHALL author only `src/runtime/` and the provisioning
manifests. No extracted library, CLI or engine SHALL be pinned by `path`,
`editable`, `rev`, `branch` or a workspace.

#### Scenario: a path or editable pin fails the gate

- **WHEN** a `pyproject.toml` in this repo pins a dependency by `path`,
  `editable = true`, `rev` or `branch`
- **THEN** `make deploy-coverage` exits 1; a library or contract is a `git` +
  semver `tag` source

#### Scenario: the only local source is the runtime

- **WHEN** `dotfiles/provisioning/cli-tools.yaml` is inspected
- **THEN** it carries exactly one `source:` entry — `dotfiles-runtime:
  src/runtime` — and every other entry is `{name, repo, tag}`
