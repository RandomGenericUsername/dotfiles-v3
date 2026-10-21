# cli-pin-consumption (delta)

## Purpose

Defines how `dotfiles-v3` and the extracted repos consume each other's releases: immutable git tags, one shared contract tag, and pins that are proven by running the installed artifact.

## ADDED Requirements

### Requirement: Sibling dependencies are git sources at an immutable tag

A dependency on a sibling repo SHALL be declared as a git source at a tag plus a compatibility range, with a committed lock that records the resolved commit. It SHALL NOT use `path =`, `editable = true`, a submodule or a cross-repo workspace. A published tag SHALL never be moved or deleted. The per-slice check SHALL be scoped to the package that slice migrates (`cli-output` in S1, `config-assembler-engine` in S2, `oci-runtime` in S3); the unscoped catch-all SHALL run only after S3.

#### Scenario: the migrated package has no path or editable pin

- **WHEN** the slice-scoped search is run after its slice — `rg -n 'cli-output = \{ path = "\.\./shared/cli-output"' src --glob 'pyproject.toml'` (S1), the `config-assembler-engine` equivalent (S2), or the `oci-runtime` equivalent (S3)
- **THEN** it exits 1 with no matches for that package. A sibling that has not had its own slice MAY still carry a path/editable source; it is not this slice's failure.

#### Scenario: no path or editable pin remains after the last shared lib

- **WHEN** `rg -n 'path = "\.\./shared|editable = true' src --glob 'pyproject.toml'` is run after S3
- **THEN** it exits 1 with no matches

#### Scenario: the lock records the tag's commit

- **WHEN** a consumer's `uv.lock` is read
- **THEN** the sibling entry names the git source and a commit, and `uv lock --check` exits 0

#### Scenario: a fix is a new tag, not a moved tag

- **WHEN** a released repo needs a change
- **THEN** a new annotated `vMAJOR.MINOR.PATCH` tag is published and consumers bump their pin; the previous tag still resolves to its original commit

### Requirement: One contracts tag is shared by every consumer

The runtime, csg, weg, itr and `roles/verify` SHALL pin the same `cli-invocation-contract` tag, not merely a compatible range. Changing the contract SHALL require a new `contracts` tag that every consumer re-pins in the same slice.

#### Scenario: four pyprojects name one tag

- **WHEN** `rg -n 'cli-invocation-contract = .*contracts", tag = "v0\.1\.0"' src --glob 'pyproject.toml'` is run after S0b
- **THEN** it reports exactly four matches: runtime, csg, weg and itr

#### Scenario: verify mirrors the contract pin

- **WHEN** `roles/verify/vars/main.yml` is read
- **THEN** it carries the same `contracts` tag as the runtime's `pyproject.toml`

#### Scenario: a contract change is a coordinated re-pin

- **WHEN** the contract record changes
- **THEN** a new `contracts` tag exists and all four consumers' pins and locks are updated in the same slice

### Requirement: Pins are proven by execution

A pin SHALL be verified by observing the installed artifact, not by reading a range or a successful binary lookup. The check SHALL observe the checkout HEAD equal to the remote tag's commit, the checkout path containing the tag, the installed package version equal to the tag with the leading `v` removed, the CLI's reported contract version, and for container CLIs the tag-qualified image.

#### Scenario: the installed version equals the tag

- **WHEN** a provisioned machine's installed tool is inspected
- **THEN** its package version equals the pinned tag without the leading `v`, its checkout path contains that tag, and the checkout HEAD equals the tag's commit

#### Scenario: the version handshake reports both versions

- **WHEN** `itr --version`, `weg --version` and `csg --version` are run after S0b
- **THEN** each prints `<package-version> contract <contract-version>`, and the contract token equals the pinned `contracts` tag with the leading `v` removed

#### Scenario: images are tag-qualified

- **WHEN** the container images for a container-mode CLI are listed after its slice
- **THEN** the expected image exists at the tag-qualified tag (for example `:v0.1.0`) and no `:latest` image satisfies the check

### Requirement: The tag chain is a slice invariant

A slice SHALL consume only tags produced by an earlier, merged slice. The first tags SHALL be `contracts v0.1.0`, `cli-output v0.1.0`, `config-assembler-engine v0.1.0`, `oci-runtime v0.5.0`, and `itr` / `weg` / `csg` `v0.1.0`.

#### Scenario: a consumer never points at an unproduced tag

- **WHEN** the tag-chain gate runs after each slice:
  `for r in contracts cli-output config-assembler-engine oci-runtime icon-templates-renderer wallpaper-effects-generator color-scheme-generator; do printf '%s: ' "$r"; git ls-remote --tags --refs "$CLI_REPO_BASE/$r" | sed 's#.*refs/tags/##' | tr '\n' ' '; echo; done`
- **THEN** every tag that slice consumes is listed by the dependency's remote, was produced by an earlier merged slice, and each `--refs` line is exactly one per tag. At S6 the full set is `contracts`, `cli-output`, `config-assembler-engine`, `itr`, `weg`, `csg` at `v0.1.0` and `oci-runtime` at `v0.5.0`

#### Scenario: versions move forward only

- **WHEN** `oci-runtime` is extracted from in-tree version 0.4.0
- **THEN** its first tag is `v0.5.0`, because the build-context API ships in that tag and versions never move backwards
