# LESSONS — the `ags-apps` migration (seven apps → one pinned unit)

> Operational lessons from moving the bar + six apps out of `dotfiles-v3` into
> the `ags-apps` monorepo and consuming it as **one pinned unit**. Scope: the
> seven consumption slices (`bar-v0.1.0` → `v0.3.8`, 2026-10-16 → 2026-10-19).
> For the plan and its per-slice evidence see
> `openspec/changes/ags-apps-bar-first/tasks.md` (branch
> `ticket/appsplan-bar-first-proposal` only); for the roadmap see
> `docs/HANDOFF-ags-platform.md` §2/§5.
>
> Evidence convention: each claim carries a commit (`dtf:` = `dotfiles-v3`,
> `apps:` = `ags-apps`) or a `file:line`. Where a run was not preserved, the
> claim says so.

---

## 1. A seed of deployed-file state must be unconditional

**What broke.** Bumping the unit pin left the new unit's `bar/colors.css`
missing. The seed that should have created it was gated on the live-bar path
being a **real directory** *and* a legacy `colors.css` existing. Once
`<install>/config/ags` is already a symlink — the normal steady state after the
first migration — the whole block was skipped on every subsequent deploy.

**What the user saw.** `wlogout`'s `@import` failed → GTK dropped the whole
stylesheet → the power menu opened with no wallpaper and no icons; the bar
logged `CSS Error :1:1 Expected a valid selector`. A cosmetic-looking
regression with a deployment-shaped root cause.

**Fix** (`dtf:4b25cbf5`, commit `e4fd11d0` "seed the runtime colors.css pointer
on EVERY deploy"): replace the gated `cp -a` with an **unconditional,
idempotent** `file state=link force=true` ensure that runs on every deploy. The
target is the pre-existing pointer's target (read by a read-only `readlink`
probe *before* the legacy dir is moved/repointed, so a version bump inherits the
old unit's target) and falls back to the runtime state pointer on a fresh host.

**Where it lives now.** `src/provisioning/ansible/roles/ags_apps/tasks/main.yml:245-268`
(the unconditional ensure, with the regression documented in the comment block
above it); pointer derivation `ags_apps/vars/main.yml:140-151`
(`ags_apps_state_root`, `ags_apps_runtime_colors_pointer`).

**Lesson.** Gate the *migration* of a legacy directory; never gate the *ensure*
of a pointer or file that post-migration state depends on. If a task's
precondition is "this is still the pre-migration layout", it is a one-shot task
and must not also be the thing that guarantees steady-state correctness.
`file state=link force=true` gives you unconditional + idempotent + check-mode
safe in one task; prefer it over `cp`/`command` with `when:` guards.

**Proof that the guards work.** The fix shipped with two execution tests (fresh
host, version bump); the version-bump test **fails on the old code** — a real
negative control, not a structural assertion dressed up as one
(`src/provisioning/tests/unit/test_ags_apps_role.py`, +169/−48 in
`dtf:4b25cbf5`). The earlier structural test had locked in the wrong shape
(it pinned the gate as correct).

---

## 2. Nested worktrees hide npm's project-root walk-up

**What broke.** `make gates-ci` in a `.worktrees/<id>/` checkout failed with
"tsc is not resolvable", while the same target passed in the main checkout.

**Root cause** (`dtf:1f2f222d`, commit `3f66ce88`): `capture-test-deps` ran a
bare `npm install --no-save … typescript@5.9` with **no `--prefix`**. npm walks
*up* from the cwd looking for a project root; from
`.worktrees/<id>/` it found `node_modules` in
`/home/inumaki/Development/dotfiles-v3` (the main checkout), installed nothing
into the worktree, and left the `node_modules/.bin/tsc` guard false. `npx` had
the same walk-up behaviour.

**Fix.** Anchor every path to `$(CURDIR)`: `--prefix "$(CURDIR)"` /
`--prefix "$(CURDIR)/$(CAPTURE_DIR)/tests"` for the installs, and invoke
`$(CURDIR)/node_modules/.bin/tsc` directly so `npx` cannot walk up either.
Proof in the commit: `rm -rf node_modules` then `make gates-ci` → exit 0 with
capture-test "OK: 0 type errors", and the main repo's `git status --short`
clean with `node_modules` md5/mtime unchanged.

**Honest caveat.** The `capture-test-deps` target was later **retired** with the
in-repo capture GUI (slice 5); the dotfiles `Makefile` no longer contains it.
So the fix is historical — the *lesson* is not:
**`npm` in a repo gate must be told which tree it is installing into.** Any
future gate that shells out to `npm`/`npx` in this worktree-based repo repeats
the trap. `npm prefix` from a worktree reports the *main* checkout — that is the
tell.

---

## 3. Re-homed tests carry the old layout's path math (and the nested worktree
launders the bug)

**What broke.** `apps:e99a176` "correct the re-homed test's repo-root path
math". The capture-tool test kept `REPO_ROOT = resolve(CAPTURE_TOOL, "../../..")`
— correct in `dotfiles-v3`, where the app sat at `src/gui-tools/capture-tool`.
In `ags-apps` the app sits at `<repo>/capture-tool`, so the repo root is
`resolve(CAPTURE_TOOL, "..")`.

**The trap, in two layers.** The defect was **masked by the nested worktree**: from
`.worktrees/cap5/capture-tool`, `"../../.."` still lands on the real repo root
(which carries `node_modules/.bin/tsc`), so the compiler-evidence case passed
*there*. From the non-nested clone `"../../.."` lands **above** the repo and
`tsc` is not resolvable — the gate fails only where nobody was looking.

**Lesson.** A file move changes path depth; re-derive `ROOT`/fixture paths from
the new layout, don't carry the old ones. Then **prove it from a non-nested
checkout** — worktrees are one level deeper by construction, so they are a
false-positive generator for upward path math. `apps:e99a176` also audited
`capture-tool/tests/ts/` for other stale math and found none: the audit is part
of the fix, not optional.

---

## 4. AD-24 is conditional — a perf win on one app is a hypothesis, not a mandate

**What happened.** The "surface before content" open path (`overlayLifecycle` /
`contentSignature`) was measured on **hypr-pano** with 141 clipboard items:
`map → first frame` **447–504 ms**, of which the card rebuild was 426–451 ms
(`readHistory` only 0.3–0.6 ms). After the pattern: **5.5 ms cold**, **~1.0 ms
warm**. That is a real, large win — and it was generalized too far.

**The correction.** AD-24 was rewritten from an obligation to a **conditional**
rule (`dtf:7fbe3ea5`, `ARCHITECTURE-SPINE.md:204`): adopt only where the
*measured* open-path build is tens of ms or more; a light surface keeps its
direct path. `docs/GUIDE-ags-overlay-performance.md` §2 carries the same
measure-first instruction.

**Outcome: only hypr-pano adopted it.**

| Surface | Measured open path | Decision | Evidence |
|---|---|---|---|
| hypr-pano | 447–504 ms → 5.5 ms cold / ~1.0 ms warm | adopted | `apps:725ffdf` (spine AD-24 evidence) |
| bar | 2–15 ms | adopted, then **reverted** | `apps:0cfccf3` (= tag `v0.3.3`) "drop the forced overlay-lifecycle adoption (surfaces are light; AD-24 is conditional)" |
| capture-tool | ~8 ms recurring (one-time first show 85–95 ms is process/layer-shell warm-up) | **not** adopted, direct path kept | `apps:bc3c154` (first in `v0.3.5`) |
| notifications | light | same conclusion | recorded in `apps:bc3c154`'s rationale |

**Lesson.** The measurement is the deliverable, not the primitive. Also note the
sub-shape: capture-tool's scary number (85–95 ms) was a **one-time per-process
surface warm-up**, not a per-open content build — dividing "first show" from
"recurring open" is what turns a scary number into a wrong optimization.
Forcing the indirection on the bar was pure churn: a per-surface controller, a
content signature and a deferred tick to save nothing.

---

## 5. Process lessons that held up

- **One unit, one gate.** `dotfiles-v3` asserts the consumption shape **once**
  (`make deploy-coverage`) instead of tracking 7 apps × N files: at `3a8bcb84`
  it prints "per-file non-bar sources in the manifest: 0" plus one line per
  external unit and "PASS" (exit 0). Retiring per-file registries is what makes
  the seven-app end state tractable.
- **Tag, then bump the pin, in one change.** The pin ladder is monotonic and
  every step is a merge the tree survives
  (`bar-v0.1.0 → bar-v0.1.1 → v0.2.0 → … → v0.3.8`); rollback is a pin bump
  back, not a code revert. See `docs/HANDOFF-ags-platform.md` §2.1.
- **Gates move with the code.** `bar-typecheck` / `ags-typecheck` / `ags-test`
  no longer exist in the dotfiles `Makefile`; they live in `ags-apps`
  (`Makefile:143, 198`) and the root `gates-ci` (`:890`) aggregates all seven
  apps. A retired gate must be *deleted*, not left pointing at a tree this repo
  no longer owns (the same warning is now written into the dotfiles `Makefile`
  around the retired `capture-test-deps`, `Makefile:97-103`).
- **Bookkeeping lags code.** All seven slices are merged and tagged while
  `ags-apps/tickets/INDEX.md:11-16` still reports REQ-001…REQ-006 as `proposed`,
  REQ-007 as `in-progress`, and `EPIC-001` as `0/7 children done`. Status fields
  are not gates, so nothing failed — that is exactly why it drifted.

---

## 6. Open items (not lessons — carry-over)

- `ags-apps` ticket roll-up (§5 above): mechanical, unstarted.
- Fresh-host verification of the unit (`verify` + `ags bundle`) was **not**
  re-run in this pass; the shape is asserted by `deploy-coverage`, runtime
  health by the gates. Unverified ≠ verified.
- Per-app repo split: still deferred; GUIDE §7 exit gate unmet
  (`docs/HANDOFF-ags-platform.md` §2).
