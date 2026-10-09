# Design: fix-provisioning-suite-failures

## §1 Baseline — establish it, do not inherit it

Run the suite and capture the failures with their names:

```bash
uv run --directory src/provisioning pytest -q > /tmp/pytest.txt 2>&1
grep -E "^(FAILED|ERROR)" /tmp/pytest.txt
tail -3 /tmp/pytest.txt          # the pass/fail/skip counts
```

MEASURED on `master` @ `5531cde2`:

```
6 failed, 792 passed, 5 skipped in 1198.45s (0:19:58)
```

RE-MEASURED on this worktree's branch (`fix/provisioning-suite-failures`, based
on `master` @ `939454f0`, i.e. +2 commits since the handoff):

```
6 failed, 792 passed, 5 skipped in 1153.51s (0:19:13)
```

The six nodeids are byte-identical to `proposal.md`'s list. The handoff is
correct; no correction to the 6/792/5 counts is required. (The two intervening
commits — one OpenSpec docs, one battery-panel — do not touch the suite.)

The suite takes **19m13s**. That is part of the finding: a feedback loop that
does not fit in a sitting is part of why these went unwritten.

Confirm the list is unchanged before starting (rerun in the background), then for
each failure run it alone and capture the assertion:

```bash
uv run --directory src/provisioning pytest <nodeid> -q
```

**Record the list in this file before changing anything.** The proposal names
reported failures that are unverified; if the measured list differs, the measured
list wins and the proposal's note is corrected in place (house style —
`harden-capture-typecheck-config` did the same to its own reported blast radius).

## §2 The classification, and why it decides the fix

Every failure goes in exactly one bucket, and the bucket selects the fix:

| bucket | meaning | fix |
|---|---|---|
| **A — real defect** | the test asserts something true that the code does not do | fix the code; the test was right |
| **B — environment-dependent** | the test needs infrastructure a stock runner lacks (a pty, an X display, a GIR typelib, runtime icons) | make it hermetic, or skip it *explicitly* with a reason |
| **C — wrong test** | the test encodes an assumption that is no longer true | fix the test, and say what changed |

The buckets are not cosmetic. A is the only one that changes shipped behaviour; B
is the one that misleads CI; C is the one that hides a real regression behind a
stale expectation. Treating them uniformly — "just make the suite green" — is how
a real defect gets skipped along with the environmental noise.

### The measured shape

All six are named in `proposal.md`. The two `test_btop_theme_e2e` failures need a
real pty (theme loading and a visible repaint). The four `test_verify_role`
failures all fail through a done-criterion that expects **rendered runtime icons**
under a synthetic state-home, and the criterion's own message is informative:

```
the runtime icons output is missing: expected
  /tmp/.../state-home/dotfiles/current/icons/ as a directory with each of
  battery-0.svg, settings-panel-wifi.svg, volume-low.svg, ... bluetooth-off.svg
  present (done-criterion — runtime icons, Epic 4 current-only).
  Run `dotfiles-runtime wallpaper set`
```

Note what that says: the icons provisioning role is **deleted**, and runtime
icons are now produced by the wallpaper pipeline. So the four are not obviously a
test-fixture problem — they may be telling the truth about a criterion that
outlived the thing that fed it. That is why classification is a task and not an
assumption; read each one before assigning a bucket.

## §3 What "hermetic" means here, concretely

Bucket B has three honest endings, in order of preference:

1. **Supply the missing thing in the test's own fixture** — a tmp state-home with
   the icons the assertion needs, a fake pty, an injected clock. The test then
   proves the same thing everywhere.
2. **Skip with a machine-readable reason** (`@pytest.mark.skipif(...)` or
   `pytest.skip("needs a real pty: ...")`) so the skip *count* is visible and the
   reason is in the output. A silent `return` or a deleted test is not this.
3. **Move it behind an explicit marker** (e.g. `-m integration` deselect) when it
   genuinely cannot be made hermetic, with the marker documented in the suite's
   README/comment so CI's selection is a stated choice.

Deleting the test or weakening its assertion to pass is **not** an option in any
bucket. That is the failure mode the repo keeps hitting: a green signal that no
longer means anything.

## §4 Scope boundaries

- **Not** a provisioning behaviour change. If bucket A turns out non-empty, that
  is a real defect discovered *by* this change; it is fixed here and named in the
  report, or split out if it deserves its own change.
- **Not** a rewrite of the suite or a change to how it is invoked.
- **Not** the `INJECT_FACTS_AS_VARS` deprecation. Verified separately as not
  firing: `verify` emits zero warnings today because the tree's structural test
  forbids bare facts. Recorded so it is not swept in here.

## §5 Classification — measured, one bucket each

Every failure was run alone and its assertion captured. The classification is
against `939454f0`, after reading each failure's shipped code (not its prose):

| nodeid | bucket | one-line reason |
|---|---|---|
| `tests/integration/test_btop_theme_e2e.py::TestThemeApplication::test_btop_loads_and_paints_the_generated_theme` | **C** | stale helper: `ac0a3780` collapsed the three btop theme variants to one `colors.btop.theme` and updated `_SELECTED`, but `_Machine.seed_palette` still seeds `colors.btop-{minimal,balanced,full}.theme`; `btop.conf` selects `colors.btop.theme`, so btop falls back to `Default_theme` |
| `tests/integration/test_btop_theme_e2e.py::TestPalettePropagation::test_the_swap_is_visible_on_the_next_launch` | **C** | same stale helper / same silent `Default_theme` fallback |
| `tests/unit/test_verify_role.py::TestVerifyVars::test_icons_samples_include_the_settings_panel_glyphs` | **C** | the hardcoded expected list pins the pre-bluetooth 7 samples; `969974d6` added 3 bluetooth samples to `verify_icons_samples` without updating it |
| `tests/unit/test_verify_role.py::TestVerifyRuntime::test_verify_passes_on_a_provisioned_machine` | **C** | `_build_provisioned_layout` seeds 7 icon files, the role now requires 10, so verify fails at the icon gate (`tasks/main.yml:738`) — stale fixture, not the runner |
| `tests/unit/test_verify_role.py::TestVerifyRuntime::test_verify_fails_when_parse_gate_binary_fails` | **C** | same stale fixture: verify aborts at the icon gate, which precedes the parse gates, so the expected parse-gate message never appears |
| `tests/unit/test_verify_role.py::TestVerifyRuntime::test_verify_criterion_6_checks_current_only` | **C** | same stale fixture: the seeded run is expected to pass but dies at the icon gate |

**No bucket A, no bucket B.**

- No **A**: the shipped code is self-consistent. `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`
  defines the `bluetooth` group with outputs `bluetooth-on.svg`,
  `bluetooth-off.svg`, `settings-panel-bluetooth-signal-full.svg`;
  `src/runtime/adapters/consumer_path_spec.py` produces exactly
  `config/btop/themes/colors.btop.theme` → `current/colors.btop.theme`; the
  rendered `btop.conf` selects `colors.btop.theme`. The tests encoded the
  pre-collapse / pre-bluetooth world, not a defect in shipped behaviour.
- No **B**: none of the six reads ambient machine state. The `test_verify_role`
  ones already build their own tmp state-home (the fixture is hermetic); its
  icon set simply drifted from the role. The btop ones drive the swap at the
  seeder's own layer and only need the real `btop` binary, which is present.

The handoff's guess — "the two `test_btop_theme_e2e` failures need a real pty"
and the four are "environment-dependent" — is **not** what the measurement
shows. Both classes are test-fixture drift (bucket C).

## §6 Fix — bucket C, and its bite-proof

### `test_btop_theme_e2e.py` — align the helper with the collapsed runtime

- `_Machine.seed_palette` seeds the single `colors.btop.theme` (cache entry →
  `current/` → spine pointer), matching `ac0a3780`.
- `_THEME_BODY` becomes the surviving single body; `_theme_text(salt)` keeps the
  salt-swap check that proves content changed across a swap.
- the discovery / swap / dangling-pointer tests collapse their `_DIFFICULTIES`
  loops to the one real pointer.

### `test_verify_role.py` — teach the fixture the icons the role requires

- `test_icons_samples_include_the_settings_panel_glyphs` expects the 10 samples
  `verify_icons_samples` actually pins.
- `_build_provisioned_layout` seeds the three bluetooth SVG samples into its tmp
  state-home — the "supply it in the test's own fixture" shape from §3, applied
  to a fixture that had merely drifted.

**Bite-proofs** (each broken, observed, restored):

| break | observed |
|---|---|
| remove `bluetooth-off` from the fixture's seeded tuple | the 3 `TestVerifyRuntime` tests fail again (icon gate) |
| remove a sample from the role's `verify_icons_samples` | the structural `test_icons_samples_...` fails |
| make `seed_palette` seed `colors.btop-broken.theme` | both `TestThemeApplication`/`TestPalettePropagation` tests fail with the silent `Default_theme` fallback |

## §7 Final measurement — post-fix

Two consecutive full runs on this branch, same command:

```
run 1: 796 passed, 5 skipped in 1165.72s (0:19:25)   EXIT=0
run 2: 796 passed, 5 skipped in 1241.70s (0:20:41)   EXIT=0
```

Baseline before the fix was `6 failed, 792 passed, 5 skipped` = **798 non-skip
cases**. Post-fix is `796 passed, 0 failed, 5 skipped` = **796 non-skip cases**.

The two-case difference is **not** a deleted test.
`TestThemeDiscovery.test_meets_btops_discovery_predicates` was
`@pytest.mark.parametrize("difficulty", ("minimal", "balanced", "full"))` —
**three cases over a dimension `ac0a3780` deleted**. It is now one case over the
one real theme, asserting the identical predicate body. No test function was
removed; two phantom parametrizations were.

### Test diff, read in full — no deletions, no weakened assertions

- `test_verify_role.py`: **purely additive** — three expected samples, three
  seeded SVG samples, comments. No assertion changed shape.
- `test_btop_theme_e2e.py`: `seed_palette` seeds the single `colors.btop.theme`;
  `_THEME_BODY`/`_theme_text` reduce to the one surviving theme; the discovery /
  swap / dangling-pointer tests drop their `_DIFFICULTIES` loops. Every assertion
  *expression* is unchanged. Two tests were renamed to match the single-theme
  reality (`test_all_three_are_listed_in_the_themes_dir` →
  `test_the_generated_theme_is_listed_in_the_themes_dir`;
  `test_a_swap_updates_all_three_theme_files_in_place` →
  `test_a_swap_updates_the_theme_file_in_place`); the one 3-case
  parametrization collapsed to 1 because its parameter no longer exists.

## §8 The skip list — all five, with their reasons

**None added by this change.** All five are pre-existing, environment-gated
skips (`-rs` output):

| # | test | reason |
|---|---|---|
| 1 | `tests/integration/test_ansible_dryrun.py:198` | `packages.yaml` contains a `become:true` play — its `--check` fact-gathering runs as the become target and needs passwordless sudo or root; this host has neither |
| 2 | `tests/integration/test_ansible_dryrun.py:198` | `bootstrap.yaml` contains a `become:true` play — same root/passwordless-sudo requirement |
| 3 | `tests/integration/test_ansible_dryrun.py:231` | no root-capable context on this host (EUID 0 or passwordless sudo) — `packages.yaml`'s become play cannot run `--check` |
| 4 | `tests/integration/test_apply_verify_container.py:346` | the disposable target has **no container engine inside it**; the csg container-mode chain requires a **nested** engine |
| 5 | `tests/integration/test_apply_verify_container.py:379` | same nested-container-engine gate |

Suite runtime post-fix: **19m25s–20m41s** (baseline 19m13s / handoff 19m58s) —
no material change.
