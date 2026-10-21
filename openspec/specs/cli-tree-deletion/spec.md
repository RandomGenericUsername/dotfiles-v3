# cli-tree-deletion Specification

## Purpose
Defines when and how an in-tree package may be removed: only after its pinned replacement is proven by execution, with the full reference blast radius retired and an absence guard that makes reappearance fail.

## Requirements

### Requirement: Deletion is destructive-last and per target

Per target, work SHALL proceed in this order: create and tag the repo → rewire `dotfiles-v3` to the pin → prove the new wiring by execution → delete the in-tree copy in the same slice → merge. The next target SHALL NOT start before the previous slice is merged.

#### Scenario: proof precedes deletion

- **WHEN** a target slice is inspected with the `src/gui-tools` evidence pattern (S4 §5.2–5.4): `git show --stat <deletion-commit>` and `git diff --stat <merge>^1 <merge>`
- **THEN** the deletion commit carries the tree removal, its retired references and the new guard in one commit, and the merge adds nothing beyond that payload. The pin/rewire and execution-proof evidence precede it in the same slice — this is a process obligation proven by the recorded commit SHAs, not by a code assertion.

#### Scenario: the next slice waits for the merge

- **WHEN** a later target starts work
- **THEN** `git merge-base --is-ancestor <previous-merge> <next-first-commit>` exits 0, and the previous slice's merge commit SHA is recorded in the next slice's ticket before its first commit. Process obligation, evidenced by the recorded SHAs.

#### Scenario: an unproven deletion is rolled back

- **WHEN** the pinned replacement fails an execution gate after the tree is deleted
- **THEN** the deletion commit is reverted, the tree returns from the merge base, and the consumer pin is bumped back or removed

### Requirement: Deletion retires every orphaned reference

The deletion commit SHALL remove the package tree and every reference the deletion orphans: lock entries, runtime repo-relative fallbacks, asset and manifest sources, `.gitignore` entries, architecture-test forbidden sets, and prose that names the path.

#### Scenario: no functional reference survives

- **WHEN** `rg -n "src/cli-tools/icon-templates-renderer" src dotfiles scripts Makefile .github docs --glob '!**/uv.lock'` is run after S4
- **THEN** it exits 1; only `_bmad-output/` and `openspec/changes/archive/` may still name the path

#### Scenario: the runtime has no fallback to the deleted tree

- **WHEN** the runtime's input resolution is searched for `src/cli-tools/...`
- **THEN** no candidate remains and the spine candidate is the only one

#### Scenario: no gate points at a moved suite

- **WHEN** the dotfiles `Makefile` and `scripts/` are searched for the extracted suites
- **THEN** no gate invokes them; the five `GATES` entries are unchanged and none targets the moved tests

### Requirement: The deletion adds an absence guard

Each deletion SHALL add or extend an executable assertion in `scripts/deploy-coverage.py` naming the removed tree (the `src/gui-tools` precedent: the guard lands in the deletion commit). The final slice SHALL add a terminal catch-all asserting that both `src/cli-tools/` and `src/shared/` are absent.

#### Scenario: a per-package absence is asserted

- **WHEN** a target's slice is complete
- **THEN** `test ! -e <deleted-path> && echo "ABSENT"` prints `ABSENT`, and `make deploy-coverage` names that same tree in its absence assertion

#### Scenario: the terminal guard covers both trees

- **WHEN** `make deploy-coverage` runs after S6
- **THEN** it exits 0 while asserting `src/cli-tools/` and `src/shared/` do not exist

#### Scenario: reappearance fails the gate

- **WHEN** any file is added under a retired tree
- **THEN** `make deploy-coverage` exits non-zero and names the tree — at that slice's own guard, or at the S6 catch-all after the last slice

### Requirement: Rollback never deletes or moves a published tag

Rollback SHALL be a pin bump to a previous tag plus a `git revert` of the deletion commit. A published tag SHALL remain resolvable at its original commit.

#### Scenario: the old artifact still resolves

- **WHEN** a rollback moves a consumer back to the previous tag
- **THEN** the previous tag still resolves to its released commit and the consumer installs that version

#### Scenario: the deleted tree is recoverable

- **WHEN** the deletion commit is reverted
- **THEN** the tree returns from the merge base, and no retag or history rewrite is required

#### Scenario: a deletion and its pin are reverted together

- **WHEN** a slice's deletion is reverted while its pin remains
- **THEN** the slice is rejected: the pin and the deletion move as one unit
