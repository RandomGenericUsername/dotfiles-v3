# installer-engine-extraction (delta)

## Purpose

Defines the installer engine as a pinned external repo, the composition seam it
reads through, and the cached-checkout rule the composition gates follow.

## ADDED Requirements

### Requirement: The installer engine is a separate semver pin

The engine SHALL be consumed from the external `dotfiles-provision` repo at the
tag in `dotfiles/provisioning/installer.pin`. The pin file SHALL be the only
declaration: `bootstrap.sh` reads it and re-checks the semver shape, and no file
repeats the tag as a literal. The in-repo provisioning tree SHALL be absent.

#### Scenario: a missing or non-semver pin fails

- **WHEN** `installer.pin` is missing, empty, a branch, `latest` or a SHA
- **THEN** `bootstrap.sh` and both composition gates fail before any install or
  playbook step, naming the pin file and the `vX.Y.Z` shape it requires

#### Scenario: the tag is repeated in the shell

- **WHEN** `bootstrap.sh` contains the literal engine tag
- **THEN** `make deploy-coverage` exits 1, because a shell-side duplicate can
  diverge from the tag the Python gates resolve

#### Scenario: the in-repo engine tree returns

- **WHEN** `src/provisioning/` exists
- **THEN** `make deploy-coverage` exits 1 and names the pinned engine repo, so a
  stale in-tree copy cannot become a second source of truth

### Requirement: The engine consumes the composition through an explicit seam

The engine SHALL accept the composition manifests, the composition root and the
inventory as explicit inputs (`--manifests-dir`, `--composition-root`,
`--inventory`) and SHALL NOT derive any path from `playbook_dir` or a checkout
above it.

#### Scenario: a foreign manifests dir provisions

- **WHEN** the engine runs with `--manifests-dir <composition>/dotfiles/provisioning`
  and `--composition-root <composition>`
- **THEN** the playbooks resolve every manifest and the runtime/corpus paths from
  those extra-vars, not from the engine's own directory

#### Scenario: a repo-relative derivation fails the engine gate

- **WHEN** an engine YAML value or Jinja template derives from `playbook_dir`
- **THEN** the engine's `test_composition_seam.py` fails, because the engine must
  run from any checkout/tag

### Requirement: Composition gates read the cached pinned checkout

`deploy-coverage` and `ansible-embedded-template-lint` SHALL read the engine's
Ansible tree from `.dev/dotfiles-provision-<tag>/` (or
`$DOTFILES_PROVISION_CACHE_DIR`), SHALL validate that the checkout's HEAD is the
pin, and SHALL fail loudly — never fall back to an in-repo copy — when the
checkout is absent and cannot be fetched.

#### Scenario: a cold checkout with network fetches once

- **WHEN** the cache is absent and the repo is reachable
- **THEN** the gate clones the pin's tag into the cache and proceeds; the printed
  `CHECK pinned installer engine <tag> at <path>` line names both

#### Scenario: an offline cold checkout fails loudly

- **WHEN** the cache is absent and the fetch fails
- **THEN** the gate exits 1 naming the pin, the cache path and the offline
  remedy; it does not fall back to a stale or in-repo tree

#### Scenario: a stale cache cannot pass silently

- **WHEN** the cached checkout's HEAD is not the pinned tag
- **THEN** the gate replaces it (or fails, when fetching is disabled) rather than
  reading the stale tree
