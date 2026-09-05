## ADDED Requirements

### Requirement: Dev harness location and entry point
The repository SHALL provide the Incus/QEMU dev harness under top-level `dev/` with `./dev/vm` as the executable entry point dispatching `fresh|up|down|console|shell|destroy|status`.

#### Scenario: Invoke via new path
- **WHEN** running `./dev/vm status` from the repo root
- **THEN** the dispatcher executes without path errors and reports VM state

#### Scenario: Old path is gone
- **WHEN** inspecting the repo tree
- **THEN** `scripts/dev/vmtest/` does not exist and `dev/vm`, `dev/vm-fresh.sh`, `dev/run-vm.sh`, `dev/provision-in-vm.sh`, `dev/install.sh`, `dev/vm-continue.sh` exist and are executable

### Requirement: Repo-root resolution from new depth
`dev/run-vm.sh` and `dev/vm-fresh.sh` SHALL resolve `REPO_ROOT` to the repository root (the directory containing `bootstrap.sh`) via one-level traversal from `dev/`.

#### Scenario: 9p share points at repo root
- **WHEN** `dev/run-vm.sh` computes `REPO_ROOT`
- **THEN** `$REPO_ROOT/bootstrap.sh` exists and the QEMU `virtfs` share mounts that root at `/repo`

### Requirement: Makefile delegation
`Makefile` `vm-fresh|vm-up|vm-down|vm-console|vm-shell|vm-destroy|vm-status` targets SHALL delegate to `./dev/vm <verb>`.

#### Scenario: make help works
- **WHEN** running `make vm-help`
- **THEN** usage for `./dev/vm` is displayed and `make -n vm-status` shows `./dev/vm status`

### Requirement: Git-ignored VM artifacts follow the move
`.gitignore` SHALL ignore `/dev/.images/` (downloaded cloud image, working disk, SSH key, seed) and SHALL NOT reference the old `/scripts/dev/vmtest/.images/` path.

#### Scenario: Fresh clone stays clean after harness run
- **WHEN** the harness populates `dev/.images/`
- **THEN** `git status --short` shows no untracked entries under `dev/.images/`
