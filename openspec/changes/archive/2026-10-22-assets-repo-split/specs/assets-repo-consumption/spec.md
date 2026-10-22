# assets-repo-consumption (delta)

## Purpose

Defines how the composition repo consumes the pinned `dotfiles-assets` corpus:
one data repo, five class directories, one semver deployment tag, a fetch-once /
deploy-per-class shape, a schema support window independent of the repo tag, and
a runtime that reads the install spine only.

## ADDED Requirements

### Requirement: One corpus, one tag, five class directories

The corpus SHALL be consumed from one repo at one semver tag declared in
`dotfiles/provisioning/assets.yaml` (`assets.repo`, `assets.tag`,
`assets.classes`). The classes SHALL be exactly `icons`, `templates`, `configs`,
`content` and `desktop`, and every consumer SHALL read its files from
`<install>/assets/<tag>/<class>/`.

#### Scenario: the manifest is the single source

- **WHEN** `make deploy-coverage` runs
- **THEN** it exits 0 only if `assets.tag` is a semver tag, the role mirror
  (`assets_repo`, `assets_pinned_tag`, `assets_classes`) and the verify mirror
  (`verify_assets_pinned_tag`, the five class dirs) agree with the manifest, and
  it prints the tag and the five class dirs it proved

#### Scenario: a half-bumped pin fails

- **WHEN** `assets.tag` is bumped without moving the role or verify mirror
- **THEN** `make deploy-coverage` exits 1 naming the mirror that still carries
  the old tag

#### Scenario: a class source points back into the repo

- **WHEN** an assets manifest entry or an assets-role copy resolves its `source`
  from `dotfiles/…` instead of the pinned checkout
- **THEN** `make deploy-coverage` exits 1, because the pin — not a repo path — is
  the corpus

### Requirement: Fetch once per tag, then deploy per class

The `assets` role SHALL clone `repo@tag` at most once into
`<install>/assets/<tag>/`, remove the checkout's `.git`, write
`<install>/assets/pinned`, and every other role SHALL read its class from that
checkout.

#### Scenario: the pinned record names the deployed tag

- **WHEN** provisioning has converged
- **THEN** `verify` asserts `<install>/assets/pinned` contains exactly the
  manifest tag and the five class dirs exist under `<install>/assets/<tag>/`

#### Scenario: the runtime reads the spine, not a checkout

- **WHEN** the runtime resolves its render inputs after provisioning
- **THEN** every provenance value is `spine` (or a post-`runtime_seed` artifact),
  never `repo`

### Requirement: Schema versions are separate from the repo tag

Each schema-bearing class SHALL declare a `schema_major`, and consumers SHALL
declare one support window (`assets_schema_support`) applied at fetch and at
verify. A corpus outside the window SHALL be refused before the first copy.

#### Scenario: an out-of-window corpus is refused

- **WHEN** the pinned corpus carries a `schema_major` the consumer does not
  support
- **THEN** the fetch assert fails naming the schema file and the expected window,
  and no class is copied

#### Scenario: the window is equal on both sides

- **WHEN** the role's `assets_schema_support` and verify's
  `verify_assets_schema_support` disagree
- **THEN** `make deploy-coverage` exits 1, so the fetch cannot accept a corpus
  that verify would reject (or the reverse)

### Requirement: The split moves the source, never the destination

Every deployed path, file mode, `become` flag and supplied value SHALL remain
unchanged by the corpus move.

#### Scenario: byte-identical static imports

- **WHEN** the S2/S3 classes are imported before their in-tree copies are deleted
- **THEN** the per-file hashes are identical, and the render tasks keep the same
  `dest`, `mode` and values

#### Scenario: the deployed desktop set is unchanged

- **WHEN** the desktop class deploys
- **THEN** the six `.desktop` entries and `toggle-touchpad` land at the same
  `$XDG_DATA_HOME/applications/` and user-bin paths as before the split, and
  `verify` re-asserts that set
