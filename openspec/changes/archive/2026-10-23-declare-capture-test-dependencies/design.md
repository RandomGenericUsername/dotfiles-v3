# Design: declare-capture-test-dependencies

## 1. The gap, measured

Reproduced on a clean clone of the branch (`/tmp/opencode/pristine`, with
`typescript@5.9` installed at the root so the guard is satisfied):

```
$ npx tsc --noEmit -p src/gui-tools/capture-tool/tests/tsconfig.tests.json
error TS2688: Cannot find type definition file for 'node'.
  The file is in the program because:
    Entry point of type library 'node' specified in compilerOptions
EXIT=2
```

And the resulting green-but-empty run, straight from `make capture-test`:

```
ℹ tests 115
ℹ pass 115
ℹ fail 0
ℹ skipped 0
ℹ skipped 0
NOTE: typescript not installed, skipping the test-file typecheck.
      (run 'make capture-typecheck' once to install it; the tests above still ran)
```

Note what that output claims: 115 tests, 0 skipped, and a typecheck that did not
happen. The gate's own `ℹ skipped 0` line is about the *runtime* suite; the skip
lived in the console NOTE and in the `ℹ skipped 1` that a developer with
typescript installed but not `@types/node` would see. Both are the same defect.

**This is not environmental.** It is not a missing system tool, not a CI-only
artifact, and not a pre-existing failure unrelated to the change under review. It
is a missing entry in the dependency list of a gate that already had a
dependency list — it just installed one of the two and let the other be a wish.

## 2. Install-on-demand, not a committed package.json

Two options, both workable.

**A `package.json` in `tests/`.** Honest and conventional. Rejected for three
repo-specific reasons.

- The capture tool has **no `package.json` anywhere, by design**, and the
  `capture-test` target's own comment says why: "No bundler, no browser, no GTK,
  no network, no package.json, and no dependency to drift." The offline-capable,
  dependency-free property of this suite is a stated design goal. A
  `package.json` plus a lockfile is a new thing to drift.
- It would need a `devDependencies` pin for `typescript` too, or the two
  mechanisms coexist and the next reader cannot tell which is authoritative.
- The capture tool's **placement is per-file** (`gui_tools_app_files`), and its
  README calls that out. A `package.json` inside `tests/` is exactly the sort of
  unregistered-but-present file that layout punishes.

**Install-on-demand, matching `capture-typecheck`.** Chosen. `capture-typecheck`
already establishes the precedent, in the same Makefile, for the same kind of
tool:

```make
	@if [ ! -x node_modules/.bin/tsc ]; then \
		echo "==> installing typescript (npm install --no-save, ignored by git)"; \
		npm install --no-save --no-package-lock typescript@5.9 >/dev/null || exit 1; \
	fi
```

`capture-test-deps` is that block plus one, with the same flags, the same echo,
the same `|| exit 1`. The consistency is the point: a developer who has read one
target has read the other, and there is one answer to "how does a gate here
declare a dependency" rather than two.

Both installs are guarded, so the network round-trip happens once and every
subsequent run is free. This is also why it works in CI unchanged: the job runs
`make capture-test` and the target does the rest. The `--prefix` on the
`@types/node` install is what keeps it out of the root npm project — see §4.

### A measured trap this design avoids

`npm install --no-save X` **prunes previously `--no-save`d packages in the tree
it is pointed at.** The `harden-capture-typecheck-config` change already records
being bitten: an intermediate `@types/node@20` install at the repo root removed
`typescript`, the following `npx tsc` printed "This is not the tsc command you
are looking for" and exited 1, and `grep -c 'error TS'` read that as **0 errors** —
a false green produced by a missing compiler.

If both packages were installed at the root, the second install could delete the
first's binary and re-create exactly that false green. Using `--prefix` for
`@types/node` makes it a separate npm project, so the two installs cannot prune
each other. This is a correctness argument, not a style one, and it is why the
`--prefix` is in the recipe rather than left to the default.

## 3. Where `@types/node` goes, and why that location is load-bearing

**Under `src/gui-tools/capture-tool/tests/`.** Not the repo root. Not the
capture-tool root.

The app runs under **GJS**, not Node: no `process`, no `Buffer`, no
`require`. Commit `65c3cb35` pinned `"types": []` on `tsconfig.capture.json` so
an `@types/node` reachable from the app's typeRoots could not put Node globals in
scope for GJS code. Two independent guards now hold that line:

1. **The pin.** `"types": []` in `tsconfig.capture.json`, so the app admits no
   ambient types regardless of what is installed where.
2. **The location.** `tests/` is *below* the app config's own directory, so
   TypeScript's default upward `typeRoots` walk never descends into it at all.

The task of this change is #1's companion. Installing at the root or at
`capture-tool/` would leave only the pin standing — a single accidentally-reverted
line away from Node globals in a GJS program. Both guards cost nothing to keep
and are measured below.

### Measured, both directions

On the clean clone, with `typescript@5.9` at the root and the app config otherwise
as committed:

| arrangement | `@types/node` files in the GJS app program |
|---|---|
| `tests/node_modules/@types/node` only, `"types": []` | **0** |
| repo-root `node_modules/@types/node`, `"types": []` | **0** |
| repo-root `node_modules/@types/node`, pin **removed** | **66** |

The third row is the reason for the location rule. With the pin deleted, 66 of its
files enter the app program from the repo root — one line of a JSONC file away.

And the tests config is satisfied by the chosen location, with the app config
untouched:

```
$ npm install --no-save --no-package-lock --prefix src/gui-tools/capture-tool/tests @types/node@24
added 2 packages in 252ms
$ npx tsc --noEmit -p src/gui-tools/capture-tool/tests/tsconfig.tests.json
EXIT=0
```

`--prefix` with `--no-save --no-package-lock` writes **only**
`node_modules/` — no `package.json`, no `package-lock.json`. Verified in an empty
scratch directory:

```
$ npm install --no-save --no-package-lock --prefix pkgdir @types/node@24
added 2 packages in 255ms
$ find . -maxdepth 3 -not -path '*/@types/*'
.
./pkgdir
./pkgdir/node_modules
./pkgdir/node_modules/.package-lock.json
./pkgdir/node_modules/@types
./pkgdir/node_modules/undici-types
```

The only extra artifact is `node_modules/.package-lock.json`, which lives inside
the gitignored `node_modules/`. Nothing else reaches the working tree, so nothing
else can reach a commit.

> Without `--no-save`, the same command also writes `pkgdir/package.json` and
> `pkgdir/package-lock.json`. That is the whole reason the flags are there.

## 4. The self-skip, removed rather than relocated

`tests/ts/typecheck-config.test.ts` case 4 is the only test in the suite that
measures the real compiler (`tsc --noEmit --listFiles` over the app project,
asserting zero `@types/node` files in the program). It also had the only skip:

```ts
  if (!tsc) {
    console.log("NOTE: typescript not resolvable, skipping the tsc --listFiles evidence check. ...")
    return t.skip("typescript not installed")
  }
```

Its comment said it "mirrors the `capture-test` target's own behaviour" — which
was true, and was the problem. The skip was a faithful copy of an already-broken
target behaviour, so the two defects reinforced each other instead of surfacing.

Once `capture-test-deps` installs `typescript` unconditionally, the condition the
skip guarded cannot arise inside the gate. So it becomes a hard failure with the
fix in the message:

```ts
  assert.ok(
    tsc,
    "tsc is not resolvable at node_modules/.bin/tsc, so the compiler-evidence " +
      "check cannot run. Run `make capture-test`, which installs typescript and " +
      "@types/node on demand (capture-test-deps). This gate does not skip when a " +
      "declared dependency is missing.",
  )
```

The task instruction anticipated the case where a skip still applies (e.g.
`typescript` genuinely absent) and asked for it to be handled explicitly rather
than left quiet. It does not apply: the dependency is installed, so an absent
`tsc` inside this gate means the install failed or someone bypassed the target.
Both are failures, and both are now reported as failures with a named cause.

**What this is not.** No case was deleted and none was made conditional. Cases
1–3 are untouched. Case 4 keeps the zero-`@types/node` check and the
`status ∈ {0, 2}` check, and `ℹ tests 115` is unchanged — 115/0 means the same 115
cases now all execute. The only thing gone is the branch that declined to run
them.

## 4a. The other problem: case 4 could not have run in CI even with tsc present

Removing the skip is necessary but not sufficient. With `typescript` and
`@types/node` both installed, case 4 runs — and on a runner with no generated
`@girs/`, it **fails**, on a different assertion:

```
$ npx tsc --noEmit -p src/gui-tools/capture-tool/tsconfig.capture.json 2>&1 \
    | grep 'error TS' | grep -c 'src/gui-tools/capture-tool/'
344
```

344, against 0 on this machine. All 344 are unresolved `ags/gtk4`,
`gi://GLib?version=2.0` and `./style.css` specifiers — the app cannot resolve its
own imports without the 168 machine-specific `.d.ts` files `ags types` generates
from *this host's* GTK/Astal. Measured distribution: 335 in `ui/`, 5 in
`adapters/`, 3 in `app.tsx`, 1 in `lib/`, and **0** in `domain/`, `ports/` or
`types.ts`.

So case 4 as written was **desktop-only**, and the skip was masking that too, not
just the missing dependency. Had CI simply installed TypeScript, the job would have
gone red on 344 spurious errors — which is a worse outcome than the skip, and a
plausible excuse to skip again.

The fix scopes the assertion to what this gate can honestly judge, and *strengthens*
it in the process:

| assertion | before | after |
|---|---|---|
| app program has 0 `@types/node` files | yes | yes, unchanged |
| accepted exit status | yes | yes, unchanged |
| non-vacuity | program has >10 files | **positive control**: the identical measurement over the tests config MUST find `@types/node` |
| 0 app errors | whole program (needs `@girs`) | `domain/`, `ports/`, `types.ts` only — desktop-free, measured 0 both ways |

The old `>10 files` guard was weak: a program of any size satisfies it, and it
cannot distinguish "Node types correctly excluded from the GJS app" from "this
compiler cannot see `@types/node` at all". The positive control fixes that by
running the **same `tsc --noEmit --listFiles` + the same regex** over
`tsconfig.tests.json`, which names `"node"`, and requiring a non-zero result. It
is strictly stronger, it is what makes the app-side assertion falsifiable, and it
doubles as a precise tripwire for the install this change adds:

```
✖ app program contains no @types/node files (real compiler evidence)
  AssertionError: the tests project must typecheck cleanly — it declares
  "types": ["node"] and make capture-test installs @types/node for it —
  but tsc exited 2
```

The dropped whole-program check is **not** lost coverage. `make capture-typecheck`
asserts it, and asserts it *harder* — it fails on any error under
`src/gui-tools/capture-tool/` **and** on any error in neither the capture tool nor
the known ags runtime, where the test ignored that third bucket. That gate is a
developer gate by design and by necessity, and it is where the full app typecheck
belongs.

Verified on a simulated CI runner (clean clone, no `@girs/`, no `env.d.ts`, no
`node_modules/` anywhere):

```
==> capture-test: installing typescript (npm install --no-save, ignored by git)
==> capture-test: installing @types/node under src/gui-tools/capture-tool/tests/ (gitignored)
ℹ pass 115   ℹ fail 0   ℹ skipped 0
    OK: 0 type errors in the domain unit tests
```

The gate's own tsc step gets the same treatment: the `if [ -x ... ]` guard and its
NOTE are deleted, so `make capture-test` runs `tsc --noEmit` over
`tsconfig.tests.json` and exits non-zero if it reports anything.

## 5. Why CI needs no new step

`.github/workflows/gates.yml`'s `capture-test` job already had the right
dependency-free shape; only its *comment* encoded the wrong reasoning, and the
comment was load-bearing — it told the next reader that installing TypeScript
would surface a failure that was somebody else's problem. That is how a
known-broken gate stays broken.

The job is unchanged. The comment now says what is true: `make capture-test`
declares its own dependencies and installs them on demand, in the same shape
`capture-typecheck` uses, and CI therefore runs the identical 115 assertions and
the identical tsc pass a developer runs. A clean runner is not a *reduced*
runner; it is a runner that has just done its first-run install.

Note the asymmetry this removes. Previously CI proved `node --test` worked and
nothing else; whether the typecheck worked was unknown on every push since the
job was added. Now the answer is on every push.

## 6. Scope boundaries

| thing | touched | why |
|---|---|---|
| `Makefile` | **yes** | the gate must declare its dependencies |
| `typecheck-config.test.ts` | **yes** | the self-skip is the defect's hiding place |
| `tsconfig.tests.json` | comment only | it was already correct; it was unsatisfiable |
| `tsconfig.capture.json` | comment only | the pin is correct and stays; two stale numbers fixed |
| case 4's whole-program 0-errors check | **yes, scoped** | needs `@girs/`, so it is desktop-only; `capture-typecheck` asserts it harder |
| `.gitignore` | comment only | the ignored path is unchanged; the reasoning was stale |
| `gates.yml` | comment only | the job is correct once the target installs |
| the 28 third-party `/usr/share/ags/js` errors | no | pre-existing and tolerated by path |
| `capture-typecheck` | no | already declares its own dependency |
| what any gate ASSERTS | no | case 4 gained a failure path, not lost an assertion |

The two stale numbers, corrected in the app config's comment: it claimed 83
`@types/node` files join the program. Measured at this revision, with
`typescript@5.9` and `@types/node@24`, it is **66**. The `harden-capture-typecheck-config`
proposal recorded 83 for a different `@types/node` version; the number is
version-dependent, and a comment asserting 83 is a comment that will be wrong
again. `66` is what this tree measures today.

## 7. Verification

- **Before** (clean clone): TS2688; `make capture-test` prints the NOTE and
  typechecks nothing; a developer with tsc but no `@types/node` gets 114/1-skip.
- **After** (clean clone, `node_modules/` and `tests/node_modules/` removed):
  both packages install on demand, `ℹ pass 115`, `ℹ fail 0`, `ℹ skipped 0`, and
  the tsc pass reports `OK: 0 type errors in the domain unit tests`.
- **App typecheck unaffected**: `make capture-typecheck` → 28 tolerated
  third-party, **0 in `src/gui-tools/capture-tool/`**, and
  `tsc --listFiles | grep -c '@types'` → **0**.
- **Regressions**: hexagonal gate PASS (check 6: 33 used / 28 styled); capture
  pytest 97 passed; provisioning `tests/unit` 720 passed, 0 failed.

## 8. Risk

Low, and bounded to one Makefile target. The worst realistic failure is an
unreachable npm registry on first run, which surfaces as a non-zero exit from
`capture-test-deps` naming the package — a red gate that says why, which is
strictly better than today's green gate that says nothing. The two guards on the
`@types/node` location are both verified in the direction that fails, so the
risk of a Node-global leak is lower after this change than before it, not higher.
