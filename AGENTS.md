# AGENTS.md — dotfiles-v3 operating contract

Canonical agent instructions for this repo (Claude, OpenCode, and any BMAD/OpenSpec
skill must follow this). This repo is the dotfiles host: provisioning, the Python
runtime, the AGS bar, the CLI tools (csg / weg / itr), and the shared harness.

## 1. Worktree discipline — NEVER work on `master`

All planning and implementation happens in a **worktree inside this repo** — never
in a sibling directory, never on `master`.

- `scripts/worktree-guard.sh check-clean` — aborts if `master` is dirty.
- `scripts/worktree-guard.sh create <id> <slug>` — creates `.worktrees/<id>/` on
  branch `ticket/<id>-<slug>`. Worktrees live **inside the repo** (`.worktrees/`,
  gitignored); they never appear as `../dotfiles-v3-*` siblings.
- Do the work in the worktree; merge back to `master` **only when the gates are
  green**. `master` stays a clean, working fallback at all times.

## 2. Gates — verify by execution, not by reading diffs

Run them:

- `make gates-ci`, `make deploy-coverage`, and the per-file gate the change
  touches. The bar's own gates (`bar-typecheck`, `ags-test`) now live in the
  `ags-apps` repo; this repo keeps `gates-ci` (provisioning shape, per-app drift,
  capture) and `deploy-coverage`.

**New skeleton source files MUST be registered** in
`src/provisioning/ansible/roles/compositor_configs/vars/main.yml`
(`compositor_configs_skeleton_files`) **and** the `verify` role mirror — otherwise
a fresh provision deploys an unresolvable import. This applies to the **non-bar**
skeletons (hypr / hyprpaper / rofi). Every GUI app now deploys WHOLE from the
`ags-apps` unit, so this repo has NO in-repo GUI per-app source manifests (the
old `gui_tools_*_app_files` lists are retired and `src/gui-tools/` is gone):
extend the unit instead of re-adding a per-file GUI list.

The **bar is exempt**: it deploys **whole** as the pinned external `ags-apps`
unit (the `ags_apps` role symlinks the unit's `bar/` subdir as the live
`<install>/config/ags`), so there are no per-file bar sources to register.
`make deploy-coverage` asserts that provisioning shape instead — it catches a
**stale per-file bar entry** (which would template into the unit tree through the
live-bar link and diverge the live bar from the pinned tag) plus a missing unit /
live-bar link / resolution shortcut. It is not optional.

**CLI tools and shared libraries deploy from pinned repos — this repo authors NO
in-repo package sources.** `csg`, `weg` and `itr` are consumed as
`{name, repo, tag}` entries in `dotfiles/provisioning/cli-tools.yaml`
(+ its `roles/cli_tools/vars/main.yml` mirror); `cli-output`,
`config-assembler-engine`, `oci-runtime` and `cli-invocation-contract` are consumed
as git-tag pins in each `pyproject.toml`. The in-repo `cli-tools/` and `shared/`
package roots are retired and their absence is gated. The only in-repo Python is
`src/runtime/` and `src/provisioning/`; `dotfiles-runtime -> src/runtime` is the
ONE permitted local `source:` in that manifest. Do NOT re-add a per-file GUI/CLI source list or a
`path`/`editable` pin — extend the pinned unit/repo and bump the tag. Because
`HERMETIC_PACKAGES` is empty, `make hermetic` prints an explicit PASS (the six
extracted packages run `make hermetic` in their own repos).

## 3. Evidence rule

Every non-trivial claim carries evidence: a command + its observed result (exit
code + key output), or a file path + line range. If evidence does not exist yet,
say so rather than stating the claim as fact.

## 4. Planning vs implementation

Keep planning edits (proposals/specs/tasks) and code changes in **separate
commits**.
