## Why

Three red tests, one root cause: the repo holds **three copies of the package list** and
they drift.

| copy | file | shape |
|---|---|---|
| logical manifest | `dotfiles/provisioning/packages.yaml` | flat distro-agnostic names |
| Arch map | `src/provisioning/ansible/group_vars/arch.yml` | `logical_key: pacman_name` (value may be a list) |
| Debian map | `src/provisioning/ansible/group_vars/debian-family.yml` | `logical_key: apt_name` (value may be a list) |

The test file hardcoded a snapshot of keys 2 and 3 and a snapshot of the manifest. Every
drift is one-directional: a package was added to the DATA and the test's expectation was
never updated.

```
FAILED tests/unit/test_ansible_scaffold.py::TestGroupVars::test_arch_packages_cover_exactly_logical_set
FAILED tests/unit/test_ansible_scaffold.py::TestGroupVars::test_debian_family_packages_cover_exactly_logical_set
FAILED tests/unit/adapters/test_yaml_manifest_reader.py::TestReadRealManifests::test_packages_manifest_has_verified_set
```

The drift is not cosmetic. Every missing key traces to a **real defect somebody already
fixed in the data** — a host-installed package that was never declared, so a fresh machine
silently lacks it (see design.md §1 for the per-key table). The bookkeeping lock was never
updated, so it has fired three times with nobody acting: a test that fires on a known-real
data set is noise, and noise is why it was ignored.

## What Changes

- **Per-key review, not a bulk accept.** Every drifted key was traced with `git log -S<key>`
  to its introducing commit, read, and recorded in design.md §1 with a verdict.
  `libva-utils` in particular was added by `e9beedc4`, the immediately preceding fix on this
  branch's base, and is called out explicitly rather than being passed off as pre-existing.
- **Re-snapshot the three hardcoded expectations** to the reviewed reality. The locks are
  KEPT: deleting the duplication would delete the signal.
- **Add machine-checkable invariants that catch real defects** the exact-set lock structurally
  cannot catch (empty rollups, blank values, one package under two keys, manifest entries no
  provisioning path installs) — design.md §4.
- No provisioning behaviour changes. No `roles/verify/**` change.

## Non-goals

- Not adding `speedtest` / `nm-connection-editor` to `packages.yaml`. They are **already there**
  (`packages.yaml:19` and `:91`, added by the bulk AGS import `496a0b4d`) and already in both
  group_vars maps. Only the test expectation lagged. Adding them would have created duplicate
  entries — the existing duplicate check would have failed. Nothing to fix in the data.
- Not fixing the three manifest entries nothing installs (`lf`, `hyprcursor`, `xdg-utils`).
  That is a real finding, reported in design.md §5 and pinned as an exact set so it cannot be
  absorbed silently — but closing it requires Debian package names that cannot be verified
  without a Debian host.
- Not restructuring into one list generated from another. Three copies with per-manager names
  is the NFR-3 distro-isolation design, not the bug.