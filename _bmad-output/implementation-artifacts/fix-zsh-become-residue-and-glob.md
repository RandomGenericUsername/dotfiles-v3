---
baseline_commit: 0a33a1dafc2b68eba7857c01eadc0ecc34c49b6e
---

# Fix ticket: zsh become gate, `.zshrc.j2` residue, assets schema glob

Status: done

## Context

Three defects surfaced by the S2/S3 host runs (assets split + template render).
All three are convergence bugs on an already-provisioned host, not new
features:

1. **`zsh_config` escalated unconditionally.** The "Ensure zsh is the login
   shell" task carried `become: true` even when `getent passwd <user>` already
   reported `/usr/bin/zsh` (verified on this host). An unattended run has no
   sudo password, so it died with `sudo: a password is required` on a host that
   needed no change.
2. **Pre-S3 `.zshrc.j2` residue survived in the spine.** Before S3,
   `config_copies` copied the whole zsh directory into
   `<install>/config/zsh/`, including the Jinja source. zsh reads `.zshrc`
   through `ZDOTDIR` and never the `.j2`; the stale template is residue and
   `verify` did not notice it.
3. **The assets manifest declared the wrong schema glob.** `assets.yaml`
   declared `**/vars.schema.json`, but the corpus ships
   `<name>.vars.schema.json` (the pinned `catalog.yaml:41` declares
   `templates/**/*.vars.schema.json`).

## Scope

- `zsh_config` role: unprivileged `getent passwd` probe + fact; `become` only on
  an `ansible.builtin.user` mutation gated on
  `current_shell != /usr/bin/zsh` and `not ansible_check_mode`; role/playbook
  headers updated to state the conditional escalation.
- `zsh_config` role: idempotent `state: absent` prune of
  `<spine>/config/zsh/.zshrc.j2`, mirroring the S3 wlogout prune.
- `verify` role: stat + assert that the zsh residue is absent, mirroring the
  wlogout residue gate.
- `assets.yaml` + `assets` role mirror: `templates` schema glob becomes
  `**/*.vars.schema.json`.
- Unit tests prove: already-zsh run never invokes become; wrong shell still
  reaches the gated mutation; prune removes the residue; verify asserts its
  absence; the manifest/role globs match the corpus naming.

## Non-goals

- No new provisioning slice, no pin bumps, no host-wide cleanup beyond the
  three convergence fixes.
- The pre-existing `TestVerifyRuntime` fixture failure on master (the fixture
  predates the pinned itr/weg/csg checkout assertions) is out of scope; the
  authoritative proof is the real host `verify` run.

## Acceptance

- `zsh-config` run WITHOUT `--skip-tags` on this host exits 0 (no sudo prompt).
- Host login shell remains `/usr/bin/zsh`.
- `<spine>/config/zsh/.zshrc.j2` is absent after the run; `verify` exits 0.
- Targeted unittest modules, `make deploy-coverage`, `make gates-ci`,
  `make hermetic` pass; evidence recorded in the fixes commit.

## Evidence (2026-10-22)

- Before: `getent passwd inumaki | cut -d: -f7` → `/usr/bin/zsh`;
  `<spine>/config/zsh/.zshrc.j2` → 3531 bytes (the pre-S3 residue).
- `zsh-config` from this worktree WITHOUT `--skip-tags`: exit 0,
  `ok=12 changed=1 failed=0 skipped=5`; the residue was the one change and the
  "Ensure zsh is the login shell" task was skipped (no sudo prompt).
- Re-run: exit 0, `changed=0`; login-shell task skipped; `getent` still
  `/usr/bin/zsh`.
- After: `.zshrc.j2` absent; `verify` exit 0,
  `ok=161 changed=0 failed=0 skipped=2`, with both pre-S3 residue stat/assert
  pairs green.
- Targeted pytest (zsh_config + assets + manifest reader + verify structural):
  205 passed, 9 deselected (the pre-existing `TestVerifyRuntime` fixture failure
  reproduces on baseline master).
- `make deploy-coverage gates-ci hermetic`: all green.
