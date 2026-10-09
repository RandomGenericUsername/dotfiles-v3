# Tasks

## 0. Anti-drift preamble (read before editing)

- **Files in scope.** `dotfiles/config/ags/audio/**`,
  `dotfiles/config/ags/bar/widgets/audio.tsx`,
  `dotfiles/config/ags/bar/Bar.tsx`, `dotfiles/config/ags/app.tsx`,
  `dotfiles/config/ags/services/{mpris-service.ts,mpris-core.ts}`,
  `dotfiles/config/ags/tests/ts/**`, `dotfiles/config/ags/tests/tsconfig.tests.json`,
  `dotfiles/config/ags/tsconfig.bar.json`, `scripts/ags-typecheck.py`, the
  `compositor_configs` + `verify` provisioning surfaces and their unit tests, and
  this change's spec delta. A step that needs another file must STOP and report
  first.
- **Precondition.** `finish-audio-panel-redesign` is merged (it touches
  `AudioPopup.tsx` and the same `ags-audio-panel` capability). It was *not*
  merged when this was implemented — the panel work was present in the working
  tree but uncommitted — so this change was built on top of that state and must
  land after it.
- **Invariant.** The bar's visible behaviour does not change — same `volume`
  (level-aware) and `microphone` (on/off) glyphs, same left-click-to-open,
  scroll-to-nudge, right-click-to-`pavucontrol`, and the same live-dot backdrop
  behaviour. The panel's appearance does not change.
- **Invariant.** The runtime engine, the event contract, the icon manifest, and
  the provisioning pipeline's *behaviour* are untouched; only the provisioning
  *file manifests* change, to track the added/removed AGS sources.
- **Verify by execution.** Each task names its gate. Do not mark a task complete
  from reading the diff.

## 1. Extract UI state and the level vocabulary

- [x] 1.1 Create `dotfiles/config/ags/audio/ui-state.ts` with `popupVisible`,
  `audioIconX`/`setAudioIconX`, `open`/`close`/`toggle`, importing ONLY `ags`.
  *Done note:* the `activeSection`, audio `viewEpoch`, `showOutputDevices`,
  `showInputDevices`, `back`, `AudioSection` and `invalidateDefaultEndpoint`
  symbols in the legacy section block had **no consumer** after the redesign (the
  popup navigates with its own views), so they were **deleted**, not moved.
- [x] 1.2 Create `dotfiles/config/ags/audio/presentation/levels.ts` with the
  pure `levelVariant` and `clampVolume`. *Done note:* `clampVolume` was **fixed**
  while extracting — its comment claimed a NaN guard, but `Number(NaN ?? 0)` is
  still `NaN`; it now uses `Number.isFinite` and reads non-finite as 0. (`nodeLabel`
  sat in the same block with no consumer and was deleted.)
- [x] 1.3 Repoint `audio/AudioPopup.tsx` and `app.tsx` at the new modules.
  Verify: `make ags-typecheck`. ✅
- [x] 1.4 Register `audio/presentation/levels.ts` in
  `tests/tsconfig.tests.json` and add `tests/ts/levels.test.ts`. *Done note:* the
  config's explicit purity list resolved every path **one level too high**
  (`../../components/...` → a non-existent `dotfiles/config/components/...`), so
  the list was vacuous; the paths were corrected to `../...` while registering the
  new modules. Verify: `make ags-test`. ✅ (62 tests)

## 2. Add the bar-indicator projection

- [x] 2.1 Create `dotfiles/config/ags/audio/presentation/bar-indicators.ts` with
  the pure `projectBarIndicators(model)`. No `ags`, no GTK, no `gi://*`.
- [x] 2.2 Register the module and add `tests/ts/bar-indicators.test.ts`
  (null output → `muted`; level buckets; input mute → `mic-off`;
  `inputConsumers` non-empty → `live`). Verify: `make ags-test`. ✅

## 3. Repoint the bar widgets onto the binding

- [x] 3.1 `app.tsx` builds `audioPanelBinding()` once and passes it to
  `Bar(monitor, audioBinding)`; `Bar.tsx` threads it to `OutputIndicator` and
  `MicIndicator`. Verify: `make ags-typecheck`. ✅
- [x] 3.2 Rewrite `bar/widgets/audio.tsx` to derive glyphs from
  `projectBarIndicators(binding.model())`, dispatch the scroll nudge as
  `binding.actions.setOutputVolume(...)`, and import `open`/`setAudioIconX`/
  `toggle` from `audio/ui-state.ts`; remove every legacy binding import
  (incl. `useEndpointEpoch`). Right-click `pavucontrol` and the backdrop ring
  unchanged. Verify: `make ags-typecheck`, `make bar-typecheck`. ✅
- [ ] 3.3 Confirm the live-dot backdrop path on a running desktop session. Needs
  a session; not run.

## 4. Retire the legacy graph-state module

- [x] 4.1 `git grep "audio/state"` → only this change's own docs. ✅
- [x] 4.2 Delete `audio/state.ts`; drop the legacy `audio-debug` route in
  `app.tsx` (the `audio-panel-debug` dump already carries the binding's view).
  Verify: `make ags-typecheck`, `make ags-test`. ✅
- [x] 4.3 `git grep "AstalWp"` → only `audio/adapters/**`. Verify:
  `make audio-panel-gates`. ✅

## 5. Delete the dead `mpris-service`

- [x] 5.1 `git grep "mpris-service"` → only the deleted module itself + comments. ✅
- [x] 5.2 Delete `services/mpris-service.ts`; keep `services/mpris-core.ts` (the
  `mpris-adapter` imports it). Refresh the stale `mpris-core.ts` header comment.
  Verify: `make audio-core-test`, `make ags-typecheck`. ✅

## 5b. Provisioning file manifests (scope added during implementation)

The AGS config deploys **file-by-file** via `compositor_configs`, with an
exact-list unit test, and `verify` mirrors it. The added/removed sources must be
tracked or a fresh provision deploys an import that is not there.

- [x] 5b.1 `compositor_configs/vars/main.yml`: add `audio/ui-state.ts`,
  `audio/presentation/levels.ts`, `audio/presentation/bar-indicators.ts`; remove
  `audio/state.ts` and `services/mpris-service.ts`.
- [x] 5b.2 `verify/vars/main.yml`: same add/remove (mirror of the manifest).
- [x] 5b.3 `test_compositor_configs_role.py`: update the exact-list `expected`,
  the provisioned-layout fixture, and the count assertion (83 → 84, +3 −2).
  Verify: `pytest tests/unit/test_compositor_configs_role.py` ✅ (25 passed).
- [x] 5b.4 `test_verify_role.py`: update the service tuple and the audio fixture.
  Verify: `pytest tests/unit/test_verify_role.py` — 69 passed, **2 failures
  reproduced on a clean tree** (see the close-out note).
- [x] 5b.5 `scripts/ags-typecheck.py`: drop the now-dead `state.ts` exemption.
- [x] 5b.6 `audio-icons.test.mjs`: read `levelVariant` from its new home
  (`presentation/levels.ts`) instead of the deleted `state.ts`.

## 6. Reconcile and verify

- [x] 6.1 Reread the `ags-audio-panel` delta against the implemented tree; no
  further drift. ✅
- [x] 6.2 `make audio-panel-gates` green. ✅ (EXIT 0: core, presentation,
  pipewire-adapter, session-runtime, panel-render 6/6, icons, seek-stability,
  mock parity, typecheck)
- [ ] 6.3 Live check on a session (default-output swap, scroll nudge, mic live
  dot). Not run — no desktop session here.
- [ ] 6.4 `make gates-ci` green. Not run.

## Close-out note (pre-existing, not caused by this change)

`TestVerifyRuntime::test_verify_passes_on_a_provisioned_machine` and
`::test_verify_criterion_6_checks_current_only` fail. The cause is that
`_build_provisioned_layout` never writes the audio **hexagon** files
(`composition.ts`, `domain/`, `application/`, `adapters/`,
`presentation/audio-panel-view-model.ts`) that `redesign-ags-audio-panel` added
to `verify_compositor_skeleton_files`; the verify assert then trips
`selectattr('isreg')` on a missing file. This is a fixture-completeness gap that
predates this change (the same 2 failures are recorded as pre-existing in
`finish-audio-panel-redesign/validation/spec-reconciliation.md`), and this change
kept the list↔fixture pair consistent for the files it touched (+3 −2). Fixing
the broader fixture gap is out of scope here.
