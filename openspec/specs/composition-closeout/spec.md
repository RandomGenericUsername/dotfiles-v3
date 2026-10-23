# composition-closeout Specification

## Purpose
Defines the finished composition repo: one documented and executable pin set,
a terminal composition-only tree allowlist, and the product metadata the
closeout exposed.

## Requirements

### Requirement: The composition pin set is one semver, mirrored set

The repo SHALL declare its pins in one documented set (`ARCHITECTURE.md` §4.1) and validate them as a set: installer tag ↔ `bootstrap.sh`, assets tag ↔ role/verify mirrors, every CLI tag ↔ manifest/role/verify, and every pin a semver tag. The runtime's library/contract pins live in `dotfiles-runtime`.

#### Scenario: every pin is semver

- **WHEN** `make deploy-coverage` runs
- **THEN** `installer.pin`, `assets.tag` and every CLI `tag` match `vX.Y.Z`; a branch, `latest`, a SHA, `rev`, `branch`, `path` or `editable` source fails

#### Scenario: a CLI verify mirror drifts

- **WHEN** verify's `verify_<name>_version` (or its checkout/pin path) disagrees with the manifest tag
- **THEN** `make deploy-coverage` exits 1 naming the verify variable

#### Scenario: a library pin is not a tag

- **WHEN** a `[tool.uv.sources]` entry is sought under this repo
- **THEN** none exists; `cli-output` and `cli-invocation-contract` are pinned by `dotfiles-runtime`, whose own gates lock them as `git` + semver tags

### Requirement: The repo is composition-only

The repo SHALL author only the provisioning manifests and the composition gates. `src/` SHALL be absent. `dotfiles/` SHALL hold `config/` and `provisioning/`, and `dotfiles/config/` SHALL hold exactly the mutable `btop/active-theme`. `src/runtime/`, `src/provisioning/`, `dotfiles/assets/`, `dotfiles/applications/` and `dotfiles/scripts/` SHALL be absent.

#### Scenario: a new authored tree fails

- **WHEN** any directory appears under `src/`, or a directory beyond the allowlist appears under `dotfiles/`
- **THEN** `make deploy-coverage` exits 1; the fix is to extend the pinned repo and bump its tag, not to author here

#### Scenario: a retired root returns

- **WHEN** `src/runtime/`, `src/provisioning/`, `dotfiles/assets/`, `dotfiles/applications/` or `dotfiles/scripts/` reappears (even empty or ignored)
- **THEN** the terminal catch-all fails naming that root; absence guards read the filesystem, not `git ls-files`

#### Scenario: the live docs do not claim an in-repo engine

- **WHEN** `rg 'the only in-repo Python|authored here|src/provisioning' AGENTS.md ARCHITECTURE.md README.md docs/WORKSPACE.md` runs
- **THEN** it exits 1, and `test ! -e src` proves the tree is gone; historical archives, `_bmad-output/` and `docs/investigation/` are excluded from this rule

### Requirement: The composition repo carries product metadata

The repo SHALL carry an MIT `LICENSE` and a `CHANGELOG.md` whose 0.x entries
summarize the split and cite the spine, the slices and the residual ledger.

#### Scenario: metadata exists and points at the record

- **WHEN** `test -f LICENSE && test -f CHANGELOG.md` runs and the changelog is
  read
- **THEN** it exits 0 and the changelog names the spine, the slices, the residual
  ledger and the archived closure record
