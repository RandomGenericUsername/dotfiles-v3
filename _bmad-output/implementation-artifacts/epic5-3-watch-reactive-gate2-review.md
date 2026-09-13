# Gate 2 Review — Epic 5‑3 (Watch & Reactive Reconcile; also lands P5‑1‑3)

Verdict: **APPROVED-WITH-FOLLOWUPS** — the transport/decision split, the
AD‑39 allowlist, the loop-safety backstop, the `desired.json` relocation,
and the single-`reactive`-line composite are all real and green. No blocking
findings. Follow-ups concern the auto-prune on every reactive converge, the
default observe-only shipping state, and a symlink-policy asymmetry in the
input hasher.

Artifact: `epic5-3-watch-reactive.md` (status "done"; states "nothing
committed" — actually committed in `b1674aa`). P5‑1‑3's reactive-converge
content is folded in here (`p5-1-3` has no standalone artifact). Reviewed at
`b1674aa`, clean tree.

## Verification (executed by reviewer)

| Check | Result |
| --- | --- |
| `pytest tests/unit/test_watch_roots.py test_watch_coordinator.py test_converge_inputs.py test_converge_backstop.py test_reactive_converge.py test_cli_reactive_converge.py test_history_writer_triggers.py tests/integration/test_inotify_watch_source.py` | all passed (part of a 145-test scoped run) |
| Full suite / layering / contracts-check | **1372 passed, 2 skipped** / 100 / 22 |
| `make contracts-check` | green |

Verified claims:

- **AD‑39 explicit allowlist, no repo resolution.** `enumerate_watch_roots`
  hardcodes the five spine locations with bounded depths
  (`watch_roots.py:36‑65`); `compute_watch_input_hash` hashes exactly those,
  bounded to the same depth (`converge_inputs.py:51‑99`).
- **No polling.** `InotifyWatchSource.read_event` blocks in `select` on the
  inotify fd + stop pipe (`inotify_watch_source.py:203‑229`); the
  coordinator never sleeps/stats (`application/watch.py`), asserted by a
  textual guard test (`test_watch_coordinator.py:162‑173`).
- **Coalesce / overflow / registration-loss rebuild.** `WatchAccumulator`
  (`watch.py:52‑91`), `WatchCoordinator.serve_events` (`:110‑143`), tested
  at `test_watch_coordinator.py:58‑139`.
- **Composite order + exactly one `reactive` line.** `converge.py:72‑98`;
  inner seeders suppressed (`seeder.py` `suppress_history`, verified in the
  `b1674aa` diff); `_append_reactive` writes one line at `cli/main.py:1127‑1138`.
- **Repo guard for triggers.** AST scan of every `append_history(trigger=…)`
  call site against `HISTORY_TRIGGERS`, and asserts the `reactive`/`prune`
  writers exist (`test_history_writer_triggers.py:20‑58`).
- **Loop-safety backstop.** `LastConvergedBackstop` under `state_root`,
  atomic write, symlink-refused, corrupt⇒changed
  (`converge_backstop.py:59‑133`); unchanged⇒no-op
  (`test_reactive_converge.py:71‑79`).
- **`desired.json` relocation** to `$XDG_CONFIG_HOME/dotfiles/desired.json`
  with explicit-path reader (`desired_state_reader.py:41‑59`); all four call
  sites in `cli/main.py` use the resolver (`:674`, `:1146`, `:1637`,
  `:1774`).
- **Live inotify smoke** (`tests/integration/test_inotify_watch_source.py`,
  3 tests) passed on this Linux host.

## Findings (all non-blocking)

- **N1 — an active reactive converge performs a real prune
  (`dry_run=False`).** `_run_reactive_converge` wires
  `prune=lambda: _run_prune(dry_run=False, keep=_keep(), prune_pinned=False)`
  (`cli/main.py:1150`). With `daemon run --activate`, every triggered
  converge deletes cache entries (beyond `keep`/pins) without an explicit
  user prune. The story pins this, but it is a surprise-deletion surface
  relative to the AD‑30 floor; consider gating auto-prune behind config or
  defaulting the reactive prune to dry-run. `_keep()` falls back to 5 on a
  corrupt intent (`cli/main.py:1120‑1125`), which is safe.
- **N2 — the shipped daemon is observe-only end-to-end.** `daemon run`
  defaults observe-only and `--activate` is not added by the provisioned
  unit (the 5‑3 artifact lists unit `--activate`/`WatchdogSec`/`sd_notify`
  as a follow-up, `epic5-3-watch-reactive.md:143‑145`, `:156‑159`). Accurate
  per AD‑35/AD‑41, but "continuous reconciliation" is not enabled by the
  committed provisioning; flag it so Phase 5 sign-off does not assume it is.
- **N3 — symlink-policy asymmetry in the hasher.** `_file_component` rejects
  symlinked file roots via `lstat` (`converge_inputs.py:33‑48`), but
  `_bounded_dir_component` calls `hash_file` directly, which follows
  symlinks (`hashing.py:89‑105`). A symlinked file inside a watched
  directory is hashed by target content while inotify reports the symlink
  entry. Low risk (spine is read-only), but inconsistent; consider an
  `O_NOFOLLOW`/`lstat` guard for directory entries too.
- **N4 — pending-burst flush on shutdown is intentionally skipped**
  (`watch.py:130‑132`). A change arriving during shutdown is caught by
  converge-on-start. Acceptable; documented.
- **N5 — `_bounded_dir_component` uses `os.walk` with default
  `followlinks=False`**, while the watcher repeats the same walk/install —
  the two are consistent on depth and on not descending symlinked dirs.
  Verified, no action.
- **N6 — bookkeeping:** the artifact says "nothing committed"
  (`epic5-3-watch-reactive.md:7`) and its exact-suite claims predate
  `b1674aa`; all modules are committed. Stale status text.

## Panel notes

- Blind Hunter: no correctness blockers in the coordinator, composite,
  backstop, or hasher. Confirmed the "one reactive line" property via the
  suppression flag + AST trigger guard.
- Edge Hunter: overflow without rebuild, registration-loss rebuild,
  file-root parent absence, corrupt/symlink backstop, unseeded no-op,
  observe-only no-op — all handled and tested.
- Acceptance Auditor: AC1–AC8 MET by code + tests. AC3's "exactly one
  reactive line" is MET; note that an active converge also emits one
  `prune` line (by design), so a single active trigger yields two history
  lines (N1 context).

## Follow-ups

1. Decide the reactive-prune policy (N1) before enabling `--activate` in
   provisioning.
2. Land the unit `--activate`/watchdog wiring (N2) as the remaining 5‑3
   slice.
3. Harmonise the symlink policy in `converge_inputs` (N3).
