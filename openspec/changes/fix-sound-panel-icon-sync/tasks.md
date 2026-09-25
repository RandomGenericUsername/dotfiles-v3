## 0. Anti-drift preamble (read before editing)

- Single mutable file: `dotfiles/config/ags/audio/AudioPopup.tsx`.
- Pattern to copy: `bar/widgets/audio.tsx:69-81` (`OutputIndicator`).
- T11 rule: inside epoch computeds read `nodeOf(endpoint())?.volume/mute`
  DIRECTLY; never `defaultSpeakerVolume()` / `defaultMicrophoneMute()` etc.
- Semantics table is design.md D2 — Recording rows stay per-stream only.
- If any step forces a second file, STOP and report; do not widen scope.

## 1. Implement `DeviceCard` liveness

- [x] 1.1 In `AudioPopup.tsx::DeviceCard`, first line of body:
  `const epoch = useEndpointEpoch(endpoint);`
- [x] 1.2 Replace `level`/`muted` computeds with epoch + direct live reads:

```ts
const level = createComputed(() => {
  epoch()
  return clampVolume(nodeOf(endpoint())?.volume ?? 0)
})
const muted = createComputed(() => {
  epoch()
  return nodeOf(endpoint())?.mute === true
})
```

- [x] 1.3 Do NOT change: `glyphVariant`, `micIcon`, `subtitle`, `toggleMute`,
  badge, `LevelLine` props, output/input `Change ›` buttons, `MasterButton`,
  JSX structure, call sites at popup bottom (`:1079-1093`).
- [x] 1.4 Keep `volume`/`muteRaw` props on the signature (may be unused);
  only rename to `_volume`/`_muteRaw` if typecheck/lint fails. Do NOT remove
  the props from call sites in this change. (Kept as-is: no lint/tsc gate
  exists for the bar; `ags bundle` strips types and passed.)
- [x] 1.5 Confirm `useEndpointEpoch` is already imported (`AudioPopup.tsx:55`).
  Do not add new imports. (Confirmed; no imports added.)

## 2. `RecorderRow` audit only (default: no edit)

- [x] 2.1 Re-read `RecorderRow` (`:880-927`). Confirm it still uses
  `createBinding(stream, "volume"/"mute")` and per-stream `node.mute` toggle.
  (Re-read at post-edit `:890-937`; confirmed unchanged: `createBinding` on
  both props, `if (node) node.mute = !node.mute` toggle, no default-mic OR.)
- [x] 2.2 FORBIDDEN: OR-ing with `defaultMicrophoneMute` /
  `defaultMicrophone().mute`; adding `Muted` badge to Recording rows; changing
  `MuteGlyph iconWhenOn` art. (Audit pass — none present; no edit made.)
- [ ] 2.3 Only if manual §V.4 proves same-stream mute glyph frozen on a live
  object: add `useEndpointEpoch` on that stream and read `nodeOf(stream)` —
  still per-stream only. Note the decision in this checkbox text.
  (Not attempted: §5 blocked — needs live session. Default decision: no edit.)

## 3. Static gates (must pass before §V)

- [x] 3.1 `git diff --stat` shows ONLY
  `dotfiles/config/ags/audio/AudioPopup.tsx` (openspec task checkboxes aside).
  (`1 file changed, 12 insertions(+), 2 deletions(-)`; untracked openspec
  change dir only.)
- [x] 3.2 Forbidden grep (must be empty of NEW hits outside DeviceCard):

```bash
# DeviceCard body must not read shared inner accessors for level/mute
rg -n "defaultSpeakerVolume\(|defaultSpeakerMute\(|defaultMicrophoneVolume\(|defaultMicrophoneMute\(" \
  dotfiles/config/ags/audio/AudioPopup.tsx
# Allowed: import lines + call-site props at the popup bottom only.
rg -n "useEndpointEpoch\(endpoint\)" dotfiles/config/ags/audio/AudioPopup.tsx  # must hit DeviceCard
rg -n "defaultMic|default_microphone" dotfiles/config/ags/audio/AudioPopup.tsx  # no new OR logic
```

- [x] 3.3 Typecheck/bundle: `ags bundle` (or repo `make` target that runs it)
  exit 0. (`ags bundle dotfiles/config/ags/app.tsx /tmp/ags-check.bundle.js
  --root . --gtk 4` → exit 0; no root Makefile target for the bar.)
- [x] 3.4 Do NOT run `make bootstrap` as a substitute for §V; do NOT edit
  `state.ts`, bar, sliders, CSS, icons, provisioning to "make it work".
  (Neither run nor touched.)

## 4. Forbidden surface list (hard fail if touched)

- [x] 4.0 `git status --porcelain` / `git diff --name-only` must not include:
  - `dotfiles/config/ags/audio/state.ts`
  - `dotfiles/config/ags/bar/widgets/audio.tsx`
  - `dotfiles/config/ags/components/sliders/VolumeSlider.tsx`
  - `dotfiles/config/ags/lib/icon-registry.ts`, `icons.json`, `style.css`
  - anything under `src/provisioning/`, `dotfiles/assets/`
  - `openspec/specs/**` (archive happens only after owner accept)

## 5. Manual verification harness (live session, owner or agent with GUI)

> **Status: blocked: needs live session (visual).** Static gates §3–§4 all
> pass; no §5 scenario was executed or faked — boxes stay unchecked for the
> owner/agent with GUI access.

Prep: open popup under bar output icon; `ags request audio-debug` once before
and after each block; keep `endpointEpoch {runs,subscribes,bumps}` in notes.

- [ ] 5.1 Bug1 — Input mute sync:
  - `wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 1`
  - THEN bar mic = `mic-off`, Input glyph = `mic-off`, Input `Muted` badge
    visible, Recording rows STILL `mic-on` without badge.
  - Unmute → all flip back; badge hidden.
- [ ] 5.2 Bug2 — Output level sync (popup stays open, no drag required):
  - `wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.15` → Output glyph
    `system-lowest`, bar `volume-lowest`, card ≈15%
  - `0.4` → `system-low`; `0.6` → `system-medium`; `0.9` → `system-max`
  - `wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle` → `system-muted`, badge on,
    `LevelLine` muted class; toggle back.
- [ ] 5.3 Click contracts:
  - Click Input glyph → only default source mute flips (`wpctl get-volume
    @DEFAULT_AUDIO_SOURCE@`).
  - Click Output glyph → only default sink mute flips.
  - Click one Recording glyph → only that stream mute flips; sibling row and
    Input card unchanged.
  - Click bar mic → popup opens (does not toggle).
- [ ] 5.4 No regression: Applications row mute/volume still live; rapid
  slider drag on any LevelLine → no GTK assert / bar death; popup open/close
  clean.
- [ ] 5.5 `ags request audio-debug` after 5.1–5.2: `endpointEpoch.bumps`
  increased; `runs`/`subscribes` > 0.

## 6. Close-out

- [ ] 6.1 Spec scenarios in `specs/audio-popup-icon-liveness/spec.md` all
  hold (map each §V result to a scenario).
- [ ] 6.2 Owner confirms; only then propose archive (`/opsx-archive` or
  equivalent). Fast suites alone do NOT close this change.
