# composition-closeout Specification

## Purpose
Defines the finished composition repo: one documented and executable pin set,
a terminal composition-only tree allowlist, and the product metadata the
closeout exposed.

## Requirements

### Requirement: The composition pin set is one semver, mirrored set

The repo SHALL declare its pins in one documented set (`ARCHITECTURE.md` §4.1)
and SHALL validate them as a set: the installer tag ↔ `bootstrap.sh`, the assets
tag ↔ its role/verify mirrors, every CLI tag ↔ manifest/role/verify, and every
runtime library/contract source a `git` + semver `tag`.

#### Scenario: every pin is semver

- **WHEN** `make deploy-coverage` runs
- **THEN** `installer.pin`, `assets.tag` and every CLI `tag` match `vX.Y.Z`; a
  branch, `latest`, a SHA, `rev`, `branch`, `path` or `editable` source fails

#### Scenario: a CLI verify mirror drifts

- **WHEN** verify's `verify_<name>_version` (or its checkout/pin path) disagrees
  with the manifest tag
- **THEN** `make deploy-coverage` exits 1 naming the verify variable, because
  provisioning and verification would assert different tags

#### Scenario: a library pin is not a tag

- **WHEN** a `[tool.uv.sources]` entry under `src/` is not an `https` git remote
  at a semver tag
- **THEN** `make deploy-coverage` exits 1; the runtime's `cli-output` and
  `cli-invocation-contract` pins are the only composition-owned library pins

### Requirement: The repo is composition-only

The repo SHALL author only `src/runtime/` and the provisioning manifests:
`src/` SHALL hold `runtime/`, `dotfiles/` SHALL hold `config/` and
`provisioning/`, and `dotfiles/config/` SHALL hold exactly the mutable
`btop/active-theme`. `src/provisioning/`, `dotfiles/assets/`,
`dotfiles/applications/` and `dotfiles/scripts/` SHALL be absent.

#### Scenario: a new authored tree fails

- **WHEN** a directory other than the allowlisted ones appears under `src/` or
  `dotfiles/`
- **THEN** `make deploy-coverage` exits 1; the fix is to extend the pinned repo
  and bump its tag, not to author here

#### Scenario: a retired root returns

- **WHEN** `src/provisioning/`, `dotfiles/assets/`, `dotfiles/applications/` or
  `dotfiles/scripts/` reappears (even empty or ignored)
- **THEN** the terminal catch-all fails naming that root; absence guards read the
  filesystem, not `git ls-files`

#### Scenario: the live docs do not claim an in-repo engine

- **WHEN** `rg 'src/provisioning|dotfiles/assets/icon-templates' AGENTS.md ARCHITECTURE.md`
  runs
- **THEN** it exits 1; historical archives and `_bmad-output/` are excluded from
  this rule

### Requirement: The composition repo carries product metadata

The repo SHALL carry an MIT `LICENSE` and a `CHANGELOG.md` whose 0.x entries
summarize the split and cite the spine, the slices and the residual ledger.

#### Scenario: metadata exists and points at the record

- **WHEN** `test -f LICENSE && test -f CHANGELOG.md` runs and the changelog is
  read
- **THEN** it exits 0 and the changelog names the spine, the slices, the residual
  ledger and the archived closure record
