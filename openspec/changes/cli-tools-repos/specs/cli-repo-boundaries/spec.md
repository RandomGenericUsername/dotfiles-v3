# cli-repo-boundaries (delta)

## Purpose

Defines the repository boundary for the six extracted packages: what each repo owns, where its package root sits, and which dependency edges may cross a repo boundary.

## ADDED Requirements

### Requirement: One package per repo, repo root is the package root

Each of the six repos SHALL contain exactly one `pyproject.toml` at its root and one import package at `src/<import_name>/`, with tests at `tests/`. A repo SHALL NOT contain a nested project root, a second `openspec/` root inside `src/`, or a copied sibling package.

#### Scenario: the repo root is the package root

- **WHEN** each of the six fresh checkouts is inspected
- **THEN** it contains one root `pyproject.toml` and one `src/<import_name>/`, and no `pyproject.toml` exists below that root

#### Scenario: no nested OpenSpec root survives in the source tree

- **WHEN** the six checkouts are searched for an `openspec/` directory under `src/`
- **THEN** no match exists; the only OpenSpec root is the repo-root one

#### Scenario: container assets exist only where a container mode exists

- **WHEN** the six checkouts are searched for `src/<import_name>/adapters/docker/`
- **THEN** only `color-scheme-generator` and `wallpaper-effects-generator` contain it; `icon-templates-renderer` contains none

### Requirement: Dependency direction is one-way and acyclic

`cli-output`, `config-assembler-engine` and `oci-runtime` SHALL depend on no sibling repo. The three CLIs SHALL depend only on those libs and the pinned `cli-invocation-contract`. No CLI SHALL import or invoke another CLI, and no repo SHALL declare a uv workspace over another repo.

#### Scenario: the shared libs are leaves

- **WHEN** each lib repo's `pyproject.toml` is read
- **THEN** it declares no dependency on `cli-output`, `config-assembler-engine`, `oci-runtime`, `icon-templates-renderer`, `wallpaper-effects-generator` or `color-scheme-generator`

#### Scenario: CLI edges match the spine

- **WHEN** the three CLI `pyproject.toml` files are read
- **THEN** csg and weg depend on `cli-output`, `config-assembler-engine`, `oci-runtime` and `cli-invocation-contract`; itr depends on `cli-output`, `config-assembler-engine` and `cli-invocation-contract`, not `oci-runtime`

#### Scenario: no CLI invokes another CLI

- **WHEN** the three CLI checkouts are searched for an import of, or a subprocess call to, another CLI's package or console script
- **THEN** no match exists

#### Scenario: no cross-repo workspace

- **WHEN** every `pyproject.toml` in the six repos is searched for `[tool.uv.workspace]` or a workspace member naming another repo
- **THEN** no match exists

### Requirement: dotfiles-v3 is a consumer, never an importer or vendor

`dotfiles-v3` SHALL consume the six packages as pinned tools and git dependencies. No runtime module SHALL import a CLI package, and after the last slice no in-tree copy of any of the six SHALL remain under `src/`.

#### Scenario: the runtime boundary is subprocess-only

- **WHEN** `src/runtime` is searched for `import` or `from` of `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine` or `oci_runtime`
- **THEN** no match exists

#### Scenario: no in-tree copy remains

- **WHEN** `git ls-files 'src/cli-tools/*' 'src/shared/*'` is run after the final slice
- **THEN** the output is empty

#### Scenario: the dotfiles tree is not a build context

- **WHEN** a csg or weg image is built after the final slice
- **THEN** the build context is the CLI repo checkout, and no Dockerfile in it contains `src/cli-tools` or `src/shared`
