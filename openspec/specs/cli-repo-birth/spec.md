# cli-repo-birth Specification

## Purpose
Defines the minimum a new repo must contain before it is a valid extraction target: the mu-strict harness, runnable verbs, hermetic tests, per-repo CI and a public, anonymously clonable pin channel, all present from the first commit.

## Requirements

### Requirement: The birth checklist is present from the first commit

A new repo SHALL contain the mu-strict harness before any package source is imported: an `AGENTS.md` carrying the evidence and worktree rules, a `CLAUDE.md` symlink, the `tickets/` framework, an executable `scripts/worktree-guard.sh`, the hash-pinned `.agents/skills/` + `skills-lock.json`, `_bmad/`, and an `openspec/` root. Harness files SHALL be copied from `mu`, not re-authored.

#### Scenario: the evidence contract is present

- **WHEN** a new repo's `AGENTS.md` is searched for `Evidence:` and `Verify:`
- **THEN** both appear at least once, alongside the worktree and planning-vs-code rules

#### Scenario: the worktree guard runs

- **WHEN** `bash scripts/worktree-guard.sh check-clean` is run on a clean checkout
- **THEN** it exits 0

#### Scenario: the harness matches `mu`

- **WHEN** `diff -u "$MU/scripts/worktree-guard.sh" scripts/worktree-guard.sh && diff -u "$MU/skills-lock.json" skills-lock.json` is run in the new repo
- **THEN** both exit 0 with no output, so every copied `computedHash` equals `mu`'s and the guard is byte-identical. `mu` ships no hash-recompute script, so byte-equality with the pinned source is the proof; no new hash tool is assumed.

#### Scenario: tickets and OpenSpec are usable

- **WHEN** `rg -c "Gate .*:" tickets/LIFECYCLE.md` and `openspec validate --specs` are run
- **THEN** the ticket lifecycle has at least six gate one-liners and the spec validation exits 0

### Requirement: Product metadata exists before the first tag

A new repo SHALL have a root `pyproject.toml` (hatchling, version, console script where applicable), a committed `uv.lock`, `README.md`, `CHANGELOG.md` and a `LICENSE` before its first tag. `docker/` SHALL exist only for csg and weg.

#### Scenario: the lock and build are reproducible

- **WHEN** `uv lock --check` and `uv build` are run on a fresh clone
- **THEN** both exit 0 and `dist/` contains an sdist and a wheel

#### Scenario: the public surface is documented

- **WHEN** `README.md` is read
- **THEN** it states the public surface and how `dotfiles-v3` pins the repo, and it names no path inside another repo

#### Scenario: only container CLIs carry Docker assets

- **WHEN** the repo roots are listed
- **THEN** only csg and weg contain `docker/` or `src/<import_name>/adapters/docker/`; `itr` contains none

### Requirement: Fresh-clone verbs and gates run

The repo SHALL provide `make` verbs `help`, `sync`, `test`, `lint`, `format`, `gates`, `build` and `install`, anchored on `$(CURDIR)`. `make gates` SHALL run the test, lint and hermetic-canary targets and SHALL pass on a fresh clone.

#### Scenario: the fresh-clone gate set passes

- **WHEN** `make sync && make gates && make hermetic && uv lock --check` is run on a fresh clone
- **THEN** every command exits 0

#### Scenario: verbs do not depend on the caller's directory

- **WHEN** `cd /tmp/opencode && make -C <repo> gates` is run and `rg -n '\$\(PWD\)|\$\(shell pwd\)' <repo>/Makefile` is searched
- **THEN** the make command exits 0 and the search exits 1, because every recipe anchors on `$(CURDIR)` rather than the caller's working directory

#### Scenario: no desktop or ad-hoc runner is required

- **WHEN** the `Makefile` is searched for `npx` or an absolute developer path
- **THEN** no match exists

### Requirement: Hermetic tests are part of the birth gate

Every extracted suite SHALL pass with `HOME` and `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME` pointed at empty temporary directories and an unrelated working directory. Each repo SHALL carry an autouse fixture and a canary test asserting the fixture is active.

#### Scenario: an empty environment cannot change the result

- **WHEN** a suite runs with the five variables empty and a foreign cwd
- **THEN** it exits 0 with the same test count as the ambient run

#### Scenario: a disabled fixture is detected

- **WHEN** the autouse fixture is removed or bypassed
- **THEN** the canary test fails

### Requirement: CI mirrors the local gate set

Each repo SHALL carry `.github/workflows/gates.yml` with one job per `make gates` target plus a `ci-gates-parity` check. The parity check SHALL fail when a Makefile gate has no CI job or a CI job has no gate.

#### Scenario: parity passes on the first push

- **WHEN** `make -C <repo> ci-gates-parity` runs before the first push (the repo copies `scripts/ci-gates-parity.py` from `dotfiles-v3`, the parser behind its `Makefile:93` target) and the first `.github/workflows/gates.yml` run completes
- **THEN** the local command reports PASS with every `make gates` target matched to a job, and the birth ticket records the first run's URL and conclusion. Proven by the copied script plus that recorded run — the push itself is not replayed locally.

#### Scenario: a gate added without CI is caught

- **WHEN** a target is added to `GATES` without a workflow job
- **THEN** `ci-gates-parity` exits non-zero and names the target

### Requirement: The repo is publicly and anonymously clonable before it is pinned

A new repo SHALL be `PUBLIC` before `dotfiles-v3` consumes any of its tags, and the released tag SHALL resolve over anonymous HTTPS with no credential helper and no terminal prompt. Visibility SHALL be read from GitHub and the anonymous clone SHALL be proven by execution for the tag being pinned — including the first tag. Neither SHALL be assumed from the repo's creation defaults.

#### Scenario: visibility is public, not assumed

- **WHEN** `gh repo view <owner>/<name> --json visibility --jq .visibility` is run (equivalent: `gh api repos/<owner>/<name> --jq .private`)
- **THEN** it prints `PUBLIC` (or `false`), and the birth ticket records that output verbatim

#### Scenario: the tag resolves anonymously

- **WHEN** `cd /tmp/opencode && GIT_TERMINAL_PROMPT=0 git -c credential.helper= ls-remote https://github.com/<owner>/<repo> 'refs/tags/<tag>'` is run right after the tag is pushed (`v0.1.0` for every repo except `oci-runtime`, which is `v0.5.0`)
- **THEN** it exits 0 and prints exactly one line, `<sha>\trefs/tags/<tag>` — the credential helper is cleared and terminal prompting is disabled, so it proves the same anonymous fetch provisioning performs

#### Scenario: a private repo is rejected rather than assumed public

- **WHEN** the visibility read prints `PRIVATE` (or `true`), or the anonymous `ls-remote` fails with `could not read Username`
- **THEN** the repo is not a valid pin target and the slice does not merge, because provisioning clones the pin from the provisioned host with no credential helper and the tag would be unresolvable there. The `ags-apps` precedent is the defect this gate exists to prevent: `gh api repos/RandomGenericUsername/ags-apps --jq .private` returns `true` while `src/provisioning/ansible/roles/ags_apps/tasks/main.yml:12-13` claims "the repo is public, so no `gh` credential helper is needed", and the same anonymous probe against `ags-apps` fails with `fatal: could not read Username`. A written claim without the two outputs is not evidence.

#### Scenario: private is an explicit alternative, never a silent default

- **WHEN** the visibility decision ever changes to private
- **THEN** provisioning gains credential handling (a `gh` credential helper, or a token/SSH pin URL) in the same slice, and the birth ticket names that as the chosen alternative; a private repo SHALL NOT be accepted silently, because anonymity is what lets the tag channel resolve on a host that holds no repository credentials.
