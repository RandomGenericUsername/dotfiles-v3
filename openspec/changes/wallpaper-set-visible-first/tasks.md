## 1. Runtime: visible-first orchestration

- [x] 1.1 `application/`: new `SwapVisibleUseCase` (validate → import
  wallpaper → save wallpaper-only `current.json` → repoint wallpaper
  symlinks → hyprpaper reload) reusing `CacheSeeder`/`HyprpaperReloader`;
  `ApplyWallpaperUseCase` keeps derivation-only responsibility (takes the
  imported wallpaper + hash instead of re-importing)
- [x] 1.2 `cli/main.py::_run_wallpaper_set`: compose swap → emit `visible`
  → derive/converge → history → `done`; mutex held across both phases;
  second set fails busy (non-zero, no mutation, `error` event with empty hash);
  preserve `suppress_history`/`client` parameters and the Phase-5 converge
  composition byte-for-byte in behavior (converge already observes
  applying→done; `visible` flows through the same unconditional emission
  path — add a converge-composition regression test)
- [x] 1.3 Crash-safety: kill between `visible`/`done` reconverges via
  existing reconcile (wallpaper layer present, layers nullable) — cover
  with an integration test (write wallpaper-only state, run set/reconcile)
- [x] 1.4 Post-visible failure semantics: palette failure ⇒ `error` event
  carrying live hash + wallpaper stays; effects/icons ⇒ `done` degraded
  (existing graceful policy); unit + integration tests per spec scenarios

## 2. Contract + consumers

- [x] 2.1 `contracts/event-contract.json` (extend the `wallpaper.state`
  `state` enum at ~line 88 with `visible` — additive, stays on
  `org.dotfiles.Events1`) + `contracts/event-contract.md` producer table
  (~line 112) and § notes: `visible` = swapped, theming in flight;
  `done`/`error` meanings unchanged
- [x] 2.2 Consumer audit: GUI + Phase-5 converge + daemon treat unknown
  `visible` as busy (no unlock, no crash); contract-drift tests updated
- [x] 2.3 CLI output: `wallpaper set` summary shows swap + theming phases
  (e.g. `visible in 0.4s · themed in 6.2s`); `--format` object gains
  `visible_at`/`themed_at` (additive)

## 3. Verification

- [x] 3.1 `src/runtime` full suite green + `make contracts-check` green
- [ ] 3.2 Manual: cold-cache set shows pixels in <1s with `visible` in event
  log; `done` follows after derivation; double-invocation fails busy
  (NOT run — needs a live desktop with hyprpaper; runtime-side evidence:
  `test_success_publishes_applying_visible_then_done` pins the event
  order, `test_busy_second_set_fails_without_mutation` pins the
  double-invocation path, integration tests prove swap precedes cold
  derivation with `csg.calls == 1` after `visible`)
- [ ] 3.3 GUI busy gate against a real in-flight set (covered by change C's
  busy scenario; cross-link the evidence here) — runtime-side cross-link:
  `TestVisibleConsumerAudit` (selector event path has no unlock site;
  bar tracks no wallpaper topic; daemon converge ignores the topic) +
  `test_busy_second_set_fails_without_mutation`; GUI-side scenario stays
  with change C (GUI sources untouched per change boundary)
