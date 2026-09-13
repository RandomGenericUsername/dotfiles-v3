# Gate 2 Review — P5‑1‑1 (Daemon `run` Skeleton + Supervised Unit)

Status: APPLIED — Items 1–4 resolved and verified (runtime 1057 passed,
2 skipped; layering green; provisioning role+bootstrap green;
runtime-daemon --check green; ruff/mypy no new).

## Verification (DEV)

- Runtime full suite: 1054 passed, 2 skipped (13 new daemon tests incl. one
  real-SIGTERM test with watchdog).
- Layering (`tests/architecture/test_layering.py`): 75 passed (90 with the
  daemon suite in one run).
- Provisioning: `test_bootstrap_playbook.py` 6 passed (17 imports);
  `runtime-daemon.yaml --check` dry-run green; syntax-check green.
- Provisioning unit suite: 515 passed, 1 failed (`test_packages_role`
  distro-branching — proven pre-existing via stash, unrelated).
- `ruff check`/`format` on touched files: clean (tree-wide failures
  byte-identical on stash). `mypy src`: 6 errors, all pre-existing
  (3 new `IBusNameOwner` name-errors found and fixed during DEV).
- Pre-existing dirt (NOT mine, untouched): `shared-data-contract.md` (+6)
  and Phase 5 `ARCHITECTURE-SPINE.md` (1 word).

## Panel

- Blind Hunter (correctness): 2 majors, 4 minors.
- Edge Hunter (edges): 2 blockers (both the same two bugs), 3 majors, 6 minors.
- Acceptance Auditor: AC1 MET, AC2 MET (deferred-client note), AC3 PARTIAL
  (2 test gaps), AC4 MET, AC5 MET (content unpinned), AC6 MET (docstring
  inaccuracy), AC7 MET. No out-of-scope leak. Creep: SIGINT handling
  (defensible, keep), seeded-idle test detail (harmless).

## Findings → ballot items

### Item 1 (provisioning correctness — 2 real bugs + hardenings)

- **StartLimit\* in the wrong section (Blind #1 / Edge blocker #1):**
  `StartLimitIntervalSec`/`StartLimitBurst` are `[Unit]` directives;
  in `[Service]` systemd ignores them, so the intended 3/60s bound is
  fiction (manager defaults apply). **Patch:** move both into `[Unit]`.
- **Deferred daemon crash-loops unbounded until P5‑1‑2 (Edge blocker #2):**
  `acquire()` always raises → exit 1 → `Restart=always`/5s forever (made
  worse by the bug above). Fixing Item 1 bounds it (3 attempts, then
  `failed (start-limit-hit)` until reset/login). No code beyond Item 1;
  record the expected-failed-until-5‑1‑2 state in the story (Item 4).
- **Enablement gate missing `default(1)` (Blind #4):** the `systemd` task
  uses bare `.rc`; add `| default(1)` like its siblings (skipped-probe
  robustness).
- **Dead var (Blind #6a):** `runtime_daemon_repo_root` is defined, never
  referenced — delete it.
- **Symlink not convergent (Blind #6b):** add `force: true` to the
  `wants/` link task.
- **ExecStart quoting + binary precondition (Edge #9):** quote the
  executable (`"{{ bin }}/dotfiles-runtime" daemon run`) and add a
  `stat`+`assert` that the binary exists before enabling (fail loud on
  out-of-order runs).

### Item 2 (runtime correctness)

- **Name leak on `RuntimeError`/`OSError` load path (Blind #2 / Edge #5):**
  only `ValueError` releases; `PermissionError`/generic `OSError`
  (and constructor validation) exit 1 holding the name.
  **Patch:** release on all load failures.
- **Handlers installed after `acquire()`+`load_current()` (Edge #6):**
  SIGTERM in that window kills without orderly release. **Patch:** install
  before `acquire()` (safe — the port requires release to tolerate
  never-owned) + restore-first-on-half-install guard.
- **Stale docstring (Blind #5 / Auditor AC6):** adapter claims
  `signal.pause()`; code uses `threading.Event.wait()`. One-line fix.

### Item 3 (tests)

- **New `test_runtime_daemon_role.py` (Edge #3 / Auditor AC5):** every
  other role has one; render the `.j2` and assert section placement
  (`StartLimit*` under `[Unit]`, `Type`/`BusName`/`Restart`/`ExecStart`
  under `[Service]`, `WantedBy` under `[Install]`), no `become`, probe
  flags, `wants/` fallback. (Would have caught Item 1.)
- **SIGTERM assertion `>= 2` (Edge #4):** the watchdog `stop()` masks a
  dead signal path at `>= 1`; the working path yields handler + `finally`
  = 2.
- **`wait`-raises test (Edge #7):** fake raising from
  `wait_until_terminated` → exit 1 + handlers restored.
- **Seeded real-signal test (Edge #8):** duplicate the killer-thread test
  with a saved minimal state.
- **Bad-config/`OSError` path test (Auditor AC3 gap):** unreadable store
  (e.g. `state_root` as a file) → exit 1 + name released.
- **Rename `test_daemon_run_exists_and_parks`** (Auditor AC1 caveat): it
  mocks `_run_daemon_run`, so it proves wiring only — rename to say so.

### Item 4 (docs)

- Story: note the expected `failed (start-limit-hit)` unit state until
  P5‑1‑2 wires the client; accept SIGINT handling as intended (Ctrl-C
  releases → exit 0); tick nothing new (all 7 boxes already `[x]`).
  Mark status done + Gate 2 outcome at commit time.

### Declined with rationale (no action unless you object)

- `HOME`-undefined default (Edge #10): `cli_tools` uses the identical
  undecorated pattern — consistency wins; marginal trigger.
- Guarding the `finally` release (Edge #7 second half): the port contract
  already requires best-effort/idempotent release; adapters must not raise.
- CLI-level exit-0-after-real-SIGTERM test (Auditor AC2 note): covered
  compositionally (real-signal return-None + CLI exit-0 via immediate
  fakes); a threaded real-signal CLI test adds hang risk for no new signal.
- `reactive`/hub/converge absence: confirmed not leaked (grep clean).

## Ballot (Approve / Request-changes PER ITEM — nothing applied yet)

- Item 1 (provisioning correctness batch)?
- Item 2 (runtime correctness batch)?
- Item 3 (test batch)?
- Item 4 (doc updates at commit time)?
