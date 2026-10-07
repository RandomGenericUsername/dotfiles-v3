# Design: enable-ci-gates

## Establishing which gates can run on `ubuntu-latest`

The split is not a judgement call about what *should* be in CI — it is a measurement of what
each gate actually needs. Stated as requirements, verified in the table below.

### The three stdlib gates

`wifi-mock-parity`, `speedtest-mock-parity` and `speedtest-no-new-architecture` each import
only `argparse`, `re`, `sys` and `pathlib`:

```
$ grep -n '^import\|^from' scripts/{wifi,speedtest}-{mock-parity,no-new-architecture}.py
scripts/wifi-mock-parity.py:36:import argparse
scripts/wifi-mock-parity.py:37:import re
scripts/wifi-mock-parity.py:38:import sys
scripts/wifi-mock-parity.py:39:from pathlib import Path
... (identical shape in the other two)
```

They read committed text files (mock HTML, TSX sources) and compare tokens. No desktop, no
network, no package manager. `ubuntu-latest` has `python3`. Unconditionally safe.

### `capture-hexagonal-gate`

Imports `argparse`, `json`, `re`, `subprocess`, `sys`, `pathlib`. The one `subprocess` call is
not a desktop dependency:

```python
# scripts/capture-hexagonal-gate.py:259
proc = subprocess.run(
    ["git", "-C", str(root), "check-ignore", "-z", "--stdin"],
    ...
)
```

That is `git`, which `actions/checkout` guarantees, and the call is wrapped in
`except (OSError, ValueError): return set()` so it degrades to "nothing ignored" if git is
unavailable rather than failing. It parses no compiler output and reads no generated types.
Safe.

### `contracts-check`

`uv run --directory src/runtime pytest <4 files> -q` — 34 tests. Dependencies are
`typer`, `cli-output` (a local path dep in this repo), `fastjsonschema`, `jeepney`, `Pillow`,
`pytest`. All are pure-Python or have manylinux wheels; `jeepney` talks to D-Bus over a socket
but these four test modules are conformance/drift tests over committed schemas and do not open
a bus. The job needs `astral-sh/setup-uv`, which is already in the workflow. Network is
available on a hosted runner, which is all `uv` needs to materialise the venv. Safe.

### `capture-test`

This is the one that had to be checked rather than assumed, because its Makefile comment makes
a strong claim ("DOES NOT NEED THE DESKTOP STACK — unlike capture-typecheck").

The recipe is `node --test --import ./resolve-hooks.mjs tests/ts/*.test.ts` over `.ts` files.
That requires:

1. **Node ≥ 22.18** — Node's built-in TypeScript type-stripping is only *unflagged* from 22.18.
   Below that it needs `--experimental-strip-types`. This is a **real** constraint and it is
   why the workflow pins `actions/setup-node` at `node-version: '24'` instead of inheriting the
   runner's preinstalled Node. Assuming the runner's Node is new enough is exactly the kind of
   guess that produces a red first push.
2. **No `gi://*` or `ags/*` import in `tests/ts/`** — verified: `tests/tsconfig.tests.json`
   states it explicitly and `tsconfig.tests.json` sets `"types": ["node"]` with no
   `typeRoots`, so nothing walks into `/usr/share/ags/js`. The `typecheck-config.test.ts`
   tests *assert* that the app config keeps `"types": []`.
3. **No bundler, no network, no package.json, no dependency to drift.**

All satisfiable on a stock runner. Safe.

**One caveat, stated precisely.** On a clean checkout `node_modules/` does not exist, and two
things self-skip — deliberately, loudly, and in both cases by pre-existing design that this
change does not touch:

- the `capture-test` target's optional `tsc --noEmit` over the test files, guarded by
  `if [ -x node_modules/.bin/tsc ]`, which prints `NOTE: typescript not installed, skipping`;
- one test in `typecheck-config.test.ts`, *"app program contains no @types/node files (real
  compiler evidence)"*, which calls `t.skip("typescript not installed")` after printing its
  own `NOTE`.

So the CI run is **114 pass / 1 skip**, while the developer run with TypeScript installed is
**115 pass / 0 skip**. That is a visible reduction in what CI executes, not a silent one: the
skip is named in the output. Installing TypeScript on the runner to close the gap is *not* an
option today, because it fails — see "The `@types/node` defect" below. Closing the gap means
fixing that defect first, which is a different change.

### Why `capture-typecheck` cannot run in CI

`make capture-typecheck` depends on `capture-types`, whose entire body is:

```sh
ags types -d "$(CURDIR)/$(CAPTURE_DIR)" -u || exit 1;
```

Three independent reasons this cannot work on `ubuntu-latest`:

1. **No `ags`.** It is an Arch AUR package built against a specific GJS/Astal stack. The
   workflow's other jobs have no AUR and no reason to.
2. **No Astal, and no GTK4/Astal GIR typelibs to describe.** `ags types` exists to introspect
   the installed Astal libraries and emit `.d.ts` for them. With nothing installed it has
   nothing to introspect, and the typecheck that follows would be checking against an empty or
   absent type surface — which is not stricter, it is *meaningless*.
3. **The result is machine-specific and enormous.** The Makefile documents it: 168 `.d.ts`
   files, ~49 MB, describing *this host's* GTK/Astal version, all gitignored, rebuilt from
   scratch on demand. CI would spend minutes regenerating a description of a machine it is not
   running on.

And the failure mode is worse than "missing binary". `capture-typecheck`'s tolerated-error
bucket is keyed to the literal path `/usr/share/ags/js/`:

```sh
thirdparty=$$(grep 'error TS' "$$log" | grep -F '/usr/share/ags/js/' || true)
other=$$(grep 'error TS' "$$log" | grep -vF "$(CAPTURE_DIR)/" | grep -vF '/usr/share/ags/js/' || true)
if [ -n "$$other" ]; then ... exit 1
```

On a runner that path does not exist, so all 28 third-party errors would land in `other` and
the gate would exit 1 — a red X on a gate that never examined anything real. `ags types -u`
would also fail first and `|| exit 1` would stop the target.

So the honest structure is: **this gate does not run in CI.** Not "it runs and passes", not
"it is skipped with a green tick". `speedtest-no-new-architecture.py`'s own docstring warns
about exactly this shape — a check that no-ops is worse than a check that is absent, because
absence is visible.

## The chosen split

```make
GATES := contracts-check wifi-mock-parity speedtest-mock-parity \
         speedtest-no-new-architecture capture-test capture-typecheck \
         capture-hexagonal-gate
gates: $(GATES)

gates-ci: $(filter-out capture-typecheck,$(GATES))
```

**Why this shape rather than `ifneq ($CI)` conditionals inside `gates`.** Three reasons:

1. **A gate's assertions must not depend on a variable's value.** `capture-typecheck` becoming
   conditional on an environment variable means its behaviour is a function of where it runs.
   The moment someone runs `CI=true make gates` locally they get a different gate suite, and a
   different gate suite behind a green tick is precisely the failure mode
   `speedtest-no-new-architecture.py` is written to catch.
2. **Named targets are greppable and testable.** `$(GATES)` and `$(filter-out ...)` state the
   split in one place; `make -n gates-ci | grep 'ags types'` returning nothing is a mechanical
   proof that no desktop-dependent command leaked into the CI set. A conditional is invisible
   to that check.
3. **`make gates` stays unconditional and complete.** All seven, every time, for a developer on
   a provisioned desktop. One command still runs every gate.

**Why the workflow does not call `make gates-ci` in one job.** The workflow's own header says
why — *"one job per gate, so a failure names the gate that broke instead of hiding behind a
combined command's exit code."* That is a better property than the convenience of a single
`make gates-ci` step, so the workflow keeps per-gate jobs and `gates-ci` serves as the
documented, locally-runnable reproduction of a CI run. It is referenced from both the Makefile
and the workflow header so the two cannot drift apart unnoticed.

## The `@types/node` defect (found, not fixed here)

`tsconfig.tests.json` sets `"types": ["node"]`, but nothing in the repo installs `@types/node`.
`make capture-typecheck` installs `typescript` only:

```
$ npx tsc --noEmit -p src/gui-tools/capture-tool/tests/tsconfig.tests.json
error TS2688: Cannot find type definition file for 'node'.
```

This means `make capture-test`'s `tsc` sub-step **cannot pass anywhere** — not just in CI. It
is masked locally because the sub-step only runs when `node_modules/.bin/tsc` happens to exist,
and it fails when it does.

This change does not fix it, because fixing it means changing what `capture-test` requires and
possibly what it asserts — a different gate, a different change. It is recorded here because it
is the reason the CI job deliberately does not `npm install`, and because closing the
114/115 gap in CI depends on it being fixed first.

## Verification performed

- `make gates-ci` run in a **clean simulated checkout** — tracked files only, no
  `node_modules/`, no `.venv` — exit **0**.
- `make -n gates-ci | grep -cE 'ags types|npm install'` → **0**.
- The workflow YAML parses and its job graph is inspected programmatically (6 jobs, all
  `ubuntu-latest`, no inter-job dependencies).
- All seven gates run green on this machine, including the desktop-only one.

## Verification NOT performed

**No GitHub Actions run was observed.** This environment has no SSH key and no push access to
`origin`, so the repaired trigger has never been exercised by GitHub. Specifically unverified:

- that `actions/setup-node@v4` with `node-version: '24'` resolves to a Node that strips `.ts`
  unflagged (reasoned from the 22.18 floor; the local machine has v26.10.0 and was used for the
  clean-checkout run, not v24);
- `astral-sh/setup-uv@v5` fetching Python 3.14 + wheels on a hosted runner (the deps resolved
  locally, but from this machine's cache and network, not a fresh runner);
- `actions/checkout` + `git check-ignore` interaction in `capture-hexagonal-gate`'s check 5
  (degrades safely by design if git is missing, but untested on the runner).

Everything above is stated as a limitation rather than implied to be covered.
