# cli-provisioning-addressing Specification

## Purpose
Defines how provisioning addresses an extracted CLI — manifest entry, checkout, install, image tag and verification — so no deployed path depends on this repository's checkout.

## Requirements

### Requirement: The manifest is the single source of truth for extracted tools

`dotfiles/provisioning/cli-tools.yaml` SHALL be the single source of truth. Every entry, including `dotfiles-runtime`, SHALL carry `name`, `repo` and `tag` matching `^v\d+\.\d+\.\d+$` and SHALL NOT carry `source`.

#### Scenario: every extracted entry is repo + tag

- **WHEN** `dotfiles/provisioning/cli-tools.yaml` is read after the runtime slice
- **THEN** csg, weg, itr and dotfiles-runtime carry `name`, `repo` and `tag`, and no entry carries `source`

#### Scenario: the only local source left is dotfiles-runtime

- **WHEN** `rg -n 'source:' dotfiles/provisioning/cli-tools.yaml` is run after the runtime slice
- **THEN** it exits 1 with no matches — the historical last source (`dotfiles-runtime -> src/runtime`) is gone — and `make deploy-coverage` asserts the same scope

#### Scenario: a source-only entry is rejected

- **WHEN** an entry is given `source:` instead of `repo` + `tag`
- **THEN** the provisioning manifest gate fails and names the entry

#### Scenario: the tag format is exact

- **WHEN** an entry's `tag` does not match `^v\d+\.\d+\.\d+$`
- **THEN** the provisioning manifest gate fails

### Requirement: Role, manifest and verify pins agree

The `roles/cli_tools` vars SHALL mirror the manifest exactly, and `roles/verify` SHALL carry independent literal pins for the same repos and tags. A parity test SHALL assert all three agree.

#### Scenario: the role mirrors the manifest

- **WHEN** `uv run --directory src/provisioning pytest tests/unit/test_cli_tools_role.py -q` is run
- **THEN** it exits 0, including the parity test comparing the role list with the manifest

#### Scenario: verify does not drift from the role

- **WHEN** `roles/verify/vars/main.yml` is compared with the role and manifest pins
- **THEN** every `repo`/`tag` pair is equal, and a mismatch fails the provisioning suite

### Requirement: Provisioning clones at the tag and installs from that checkout

The role SHALL shallow-clone `repo@tag` into `<install>/cli-tools/<name>/<tag>/`, remove `.git`, write a `pinned` record, and install the tool from that checkout so the installed package records a tag-bearing path. The checkout HEAD SHALL equal the remote tag's commit. Asset steps that read a package tree SHALL depend on that fetch step.

#### Scenario: the checkout is version-addressed

- **WHEN** a provisioned machine's install root is inspected
- **THEN** it contains `cli-tools/<name>/<tag>/` without `.git`, and a `pinned` record naming the tag

#### Scenario: the checkout is the tag's commit

- **WHEN** `git -C <checkout> rev-parse HEAD` is compared with `git ls-remote <repo> 'refs/tags/vX.Y.Z^{}' | cut -f1`
- **THEN** the two SHAs are equal, so the installed source is the annotated tag's commit and not a branch head or a later commit

#### Scenario: the install is not a URL install

- **WHEN** the installed tool's PEP 610 `direct_url.json` is read after installing from `<install>/cli-tools/<name>/<tag>/`
- **THEN** its `url` is that tag-qualified checkout path with no `git+` prefix or repository URL, and it is not this repo's `src/`

#### Scenario: an asset cannot read a missing checkout

- **WHEN** the assets role copies the csg templates on a fresh provision
- **THEN** it reads `<install>/cli-tools/csg/<tag>/src/color_scheme_generator/defaults/templates/`, the fetch task list has already produced it, and the slice's `test_csg_templates_source_resolves_to_pinned_checkout` case asserts the source path

### Requirement: Image tags equal the pinned tag

Provisioning SHALL render `image_tag` from the pinned tag and SHALL verify the expected image exists at that exact tag. No container image for an extracted CLI SHALL be required at `latest`.

#### Scenario: the rendered settings carry the tag

- **WHEN** the csg and weg settings templates are rendered after their slices
- **THEN** `image_tag` equals the pinned `vX.Y.Z`, not `latest`, and the slice's `test_settings_role.py -k image_tag` case asserts the rendered value

#### Scenario: a nonexistent pin fails the build verb

- **WHEN** the build verb is invoked with `--image-tag v9.9.9` against a `v0.1.0` checkout
- **THEN** it exits non-zero and names the mismatch; it never tags an image with a pin that no tag produced

#### Scenario: verify fails on a missing tag-qualified image

- **WHEN** the expected image is absent at the pinned tag
- **THEN** `verify` fails even if an image at `latest` or a previous tag exists

### Requirement: `deploy-coverage` asserts the pin shape and the retired-tree absence

`deploy-coverage` SHALL fail when an entry lacks `repo` or `tag`, when role/verify/manifest pins disagree, when a `path`/`editable` pin or `src/cli-tools` source remains, or when a retired tree exists. It SHALL assert `src/runtime/` is absent and that no manifest entry carries `source`.

#### Scenario: a missing pin key is caught

- **WHEN** an entry loses `repo` or `tag`
- **THEN** `make deploy-coverage` exits non-zero and names the entry

#### Scenario: a stale local source is caught

- **WHEN** any manifest entry still carries `source`, or `src/cli-tools` appears as an asset source
- **THEN** `make deploy-coverage` exits non-zero

#### Scenario: each slice asserts the tree it deleted

- **WHEN** `make deploy-coverage` runs after S1–S6 and the runtime slice
- **THEN** it exits 0 only while each deleted tree — including `src/runtime/` — is absent, so a reappearance fails the gate at the guard that owns it

#### Scenario: the retired trees are absent

- **WHEN** `make deploy-coverage` runs after the runtime slice
- **THEN** it exits 0 and asserts that `src/cli-tools/`, `src/shared/` and `src/runtime/` do not exist
