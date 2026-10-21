# cli-provisioning-addressing (delta)

## Purpose

Defines how provisioning addresses an extracted CLI — manifest entry, checkout, install, image tag and verification — so no deployed path depends on this repository's checkout.

## ADDED Requirements

### Requirement: The manifest is the single source of truth for extracted tools

`dotfiles/provisioning/cli-tools.yaml` SHALL be the single source of truth. After the last CLI slice every extracted CLI entry SHALL carry `name`, `repo` and `tag` (matching `^v\d+\.\d+\.\d+$`) and SHALL NOT carry a `source` key. `dotfiles-runtime -> src/runtime` SHALL remain the only in-repo `source` entry (OPEN-7); it is not extracted, and its install path and systemd units are unchanged.

#### Scenario: every extracted entry is repo + tag

- **WHEN** `dotfiles/provisioning/cli-tools.yaml` is read after S6
- **THEN** the csg, weg and itr entries carry `name`, `repo` and `tag`, and no `source` key

#### Scenario: the only local source left is dotfiles-runtime

- **WHEN** `rg -n 'source:' dotfiles/provisioning/cli-tools.yaml` is run after S6
- **THEN** exactly one match exists, `source: src/runtime` on the `dotfiles-runtime` entry; no extracted-package source path remains, and `make deploy-coverage` asserts the same scope

#### Scenario: a source-only entry is rejected

- **WHEN** an extracted CLI entry is given `source:` instead of `repo` + `tag`
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

`deploy-coverage` SHALL fail when an extracted manifest entry lacks `repo` or `tag`, when role/verify/manifest pins disagree, when a `path`/`editable` pin or a `src/cli-tools` asset source remains, or when a retired tree exists. Each slice SHALL add or extend the absence assertion for the tree it deletes; S6 SHALL add the terminal catch-all for `src/cli-tools/` and `src/shared/`.

#### Scenario: a missing pin key is caught

- **WHEN** an extracted entry loses `repo` or `tag`
- **THEN** `make deploy-coverage` exits non-zero and names the entry

#### Scenario: a stale local source is caught

- **WHEN** `src/cli-tools` still appears as an asset source or a runtime input fallback after the relevant slice
- **THEN** `make deploy-coverage` exits non-zero

#### Scenario: each slice asserts the tree it deleted

- **WHEN** `make deploy-coverage` runs after S1, S2, S3, S4 or S5
- **THEN** it exits 0 only while the tree that slice deleted (`src/shared/cli-output`, `src/shared/config-assembler-engine`, `src/shared/oci-runtime`, `src/cli-tools/icon-templates-renderer`, `src/cli-tools/wallpaper-effects-generator`) is absent, so a reappearance fails the gate at that slice's own guard

#### Scenario: the retired trees are absent

- **WHEN** `make deploy-coverage` runs after S6
- **THEN** it exits 0 and asserts that neither `src/cli-tools/` nor `src/shared/` exists
