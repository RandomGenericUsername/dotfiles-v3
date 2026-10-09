## Why

`uv run --directory src/provisioning pytest` does not finish green on a
provisioned desktop. The failure count has been carried as "known, pre-existing"
without ever being written down, so every change that touches provisioning
re-measures it from scratch and every reviewer has to take "pre-existing" on
trust.

**MEASURED** (confirmed, `master` @ `5531cde2`):

```
6 failed, 792 passed, 5 skipped in 1198.45s (0:19:58)
```

| # | failing test |
|---|---|
| 1 | `tests/integration/test_btop_theme_e2e.py::TestThemeApplication::test_btop_loads_and_paints_the_generated_theme` |
| 2 | `tests/integration/test_btop_theme_e2e.py::TestPalettePropagation::test_the_swap_is_visible_on_the_next_launch` |
| 3 | `tests/unit/test_verify_role.py::TestVerifyVars::test_icons_samples_include_the_settings_panel_glyphs` |
| 4 | `tests/unit/test_verify_role.py::TestVerifyRuntime::test_verify_passes_on_a_provisioned_machine` |
| 5 | `tests/unit/test_verify_role.py::TestVerifyRuntime::test_verify_fails_when_parse_gate_binary_fails` |
| 6 | `tests/unit/test_verify_role.py::TestVerifyRuntime::test_verify_criterion_6_checks_current_only` |

The reported split (2 btop + 4 verify) was correct. **The suite takes 19m58s**,
which is itself part of why the failures went unwritten — the loop cannot fit in
a sitting.

**The failures are not necessarily environmental.** Tests 4-6 fail through a
criterion that expects rendered runtime icons under a synthetic state-home:

```
the runtime icons output is missing: expected
  /tmp/.../state-home/dotfiles/current/icons/ as a directory with each of
  battery-0.svg, settings-panel-wifi.svg, volume-low.svg, ... bluetooth-off.svg
  present (done-criterion — runtime icons, Epic 4 current-only).
  Run `dotfiles-runtime wallpaper set`
```

That message names a real pipeline and says the icons role is **deleted** —
icons now come from the wallpaper path. Whether the *test* should seed them or
the *criterion* is over-reaching is exactly what classification decides; do not
assume "environment" and skip.

The reported shape is that the failures are **environment-dependent rather than
code defects**: tests that need a real pty (theme loading) and tests that expect
runtime icons to exist under a synthetic state-home. If that holds, the defect is
that the suite's success depends on ambient machine state rather than on the
repository — which is the same class as `harden-capture-typecheck-config` (an
app's ambient type surface depending on where a directory sat) and the
`bar-typecheck`/`capture-typecheck` symlink omissions.

## What Changes

- **Measure the list, then fix, don't re-guess it.** Phase 1 establishes exactly
  which tests fail, why, and whether each is a defect in the test, a defect in
  the code, or a legitimate environment dependency.
- **Classify each failure** as one of: the test asserts something true that the
  code does not do (a real defect → fix the code); the test needs infrastructure
  a stock runner lacks (→ make it hermetic, or skip it *explicitly* with a reason
  and a marker); or the test is simply wrong (→ fix the test).
- **Nothing is silenced by deletion.** A test that cannot run everywhere is
  skipped with a stated reason and a shape that CI can see, never removed and
  never weakened to pass.

## Capabilities

### New Capabilities

- `provisioning-suite-determinism`: the provisioning test suite's result depends
  on the repository, not on the ambient state of the machine it runs on — every
  skip and every failure is explained, and the count is written down.

### Modified Capabilities

- *(none — this change fixes test infrastructure, it does not change what
  provisioning does)*
