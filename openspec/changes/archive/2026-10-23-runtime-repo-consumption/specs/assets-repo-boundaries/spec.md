# assets-repo-boundaries (delta)

## MODIFIED Requirements

### Requirement: The composition repo authors no package sources

The composition repo SHALL author only the provisioning manifests and the composition gates; `src/` SHALL be absent. No extracted library, CLI, engine or runtime SHALL be pinned by `path`, `editable`, `rev`, `branch` or a workspace.

#### Scenario: a path or editable pin fails the gate

- **WHEN** a `pyproject.toml` in this repo pins a dependency by `path`, `editable = true`, `rev` or `branch`
- **THEN** `make deploy-coverage` exits 1; a library or contract is a `git` + semver `tag` source in its owning repo

#### Scenario: the only local source is the runtime

- **WHEN** `dotfiles/provisioning/cli-tools.yaml` is inspected
- **THEN** it carries zero `source:` entries; every entry, including the runtime, is `{name, repo, tag}`, so the historical "runtime is the one local source" exception is gone
