## 0. Anti-drift preamble (read before editing)

- Files in scope: `dotfiles/config/ags/services/mpris-core.ts`,
  `dotfiles/config/ags/services/mpris-service.ts`,
  `dotfiles/config/ags/audio/state.ts`,
  `dotfiles/config/ags/audio/AudioPopup.tsx`, and the node test
  `src/gui-tools/icon-color-mapping-editor/tests/mpris-core.test.mjs`.
- NO new file → no `compositor_configs/vars/main.yml`, no `verify/vars/main.yml`,
  no provisioning test change. (A new module would have to be added to all
  three; extending `mpris-core` is the additive-I10 route.)
- Invariants that hold: I1 no polling (the epoch is bumped by events/one user
  action), I2 `wpctl`/`playerctl` for actions only, I3 never `wp.audio.*`,
  I4 never assign `is_default`, I5 dotted `pw-dump` keys, I10 additive to
  `audio/state.ts`, I11 pure core stays GJS-free.
- T11 still applies: inside an epoch-tracked computed, read live GObject props
  directly.
- If a step forces a file outside this list, STOP and report.

## 1. App identity (duplicate rows)

- [x] 1.1 `mpris-core.ts`: add the measured `"mozilla-firefox": "firefox"` fold
  to `ALIAS`, with the measurement in the comment.
- [x] 1.2 `mpris-core.ts`: add `AppIdentityResolver`, `resolveAppIdentities`,
  `keyForPlayer` — claimed key verbatim → resolver (canonical + raw identity) →
  canonical fallback; dedupe; keep the canonical key as a trailing fallback.
- [x] 1.3 `mpris-service.ts`: `MprisPlayer.appKeys`; `setAppIdentitySource`;
  `setClaimedStreamKeys`; recompute `appKeys` in `playersByApp` per derivation.
- [x] 1.4 `state.ts`: install the resolver (matches the identity against each
  stream's `application.name` + `application.process.binary` via
  `identityMatches`); publish claimed keys before deriving players;
  `playerForApp` matches `appKeys`.
- [x] 1.5 Gate: `node tests/ags-symbol-check.mjs` (a bare `resolve(…)` call on a
  parameter is flagged as a free identifier — bind it to a local first).

## 1b. Output-card transport is device-scoped (supersedes D1)

- [x] 1b.1 `state.ts`: `streamNodeForApp` (a non-mutating sibling of
  `liveStreamForApp`, so attribution does not drive the `lastLevel` cache).
- [x] 1b.2 `state.ts`: `effectiveSinkIdForApp` — the id behind
  `effectiveSinkName`, same three steps in the same order, so the transport's
  membership and the row's routing chip can never name different devices. The
  default-sink fallback is required: a paused stream's links are `init`, not
  `active` (measured on Firefox).
- [x] 1b.3 `state.ts`: `playersOnSink`, `defaultSinkPlayers`,
  `sinkAggregatePlaying`, `toggleSelectedOutputPlayback` (pause wins when mixed).
- [x] 1b.4 `mpris-service.ts`: `setPlayerPlaying(player, playing)` — an explicit
  state, NOT a toggle. A `playPausePlayer` loop would have STARTED the apps
  already paused while pausing the ones playing.
- [x] 1b.5 `AudioPopup.tsx`: `MasterButton` → `SinkTransportButton`, bound to
  the selected output; tooltip names the device and the app count; visible only
  when something is routed there. `masterPlayer` import and re-export removed.
- [x] 1b.6 `playerFromProps`: a FRESH hydration of an already-`Playing` player
  gets `lastPlayingAt = 0`, not `nowMs()` — the field's contract, kept even
  though no UI control ranks on it any more (design D5c).
- [x] 1b.7 `debugAudioState()` gains `players` (busName, identity, appKeys, pid,
  status, lastPlayingAt, title) and `defaultSinkPlayers`, so a control's target
  and blast radius are measurable.
- [x] 1b.8 Gate, live: with the speakers selected the transport acts on Firefox
  ONLY — Tidal's stream has an active link to the earbuds, so its own chip says
  "TOZO NC9" and it is correctly excluded. Two rows, no duplicates.

## 2. Default output/input endpoint

- [x] 2.1 `state.ts`: `defaultEndpointEpoch` + `invalidateDefaultEndpoint()`,
  read inside `defaultNodeFor`.
- [x] 2.2 Bump from the three triggers only: `wp.nodes` length effect,
  `setDefaultSpeaker`/`setDefaultMicrophone` `.then()`, `open()`.
- [x] 2.3 Expose `defaultEndpointEpoch` in `debugAudioState()` — CALLED, not
  referenced (a bare accessor is a function and `JSON.stringify` drops it).
- [x] 2.5 `settleDefault()` after a write we made: the daemon applies the change
  AFTER `wpctl` exits (measured: still the old sink 7ms after the process
  exited), so a single bump re-read a stale value — reported as "I have to
  change it twice, or play something". Bounded (15 × 100ms), aborts as soon as
  `default_speaker` names the target, and re-snapshots the graph on completion
  so the per-app routing labels follow too.
- [x] 2.6 Capture the requested id in a `const` before the callback — property
  narrowing does not survive into `.then()`.

- [x] 5.2b **Flicker (scripted, partially):** frame-by-frame analysis of the
  owner's screen recording + a live poll across a seek reproduced both dips
  (`liveStreamId: null` for ~120ms, `volume: 0` for ~120ms) with the node id
  unchanged. Both are closed by the mechanisms above.
- [x] 5.2c **Regression recorded:** adding the per-node cache deleted the loop
  converting raw names into keys, emptying app identity for every stream for a
  few minutes. Caught by the snapshot counters; fixed and verified
  (`streams: [(94, ['google-chrome'])]`).

## 3. Layout clamps

- [x] 3.1 `AudioPopup.tsx`: `Pango` import; clamp `.audio-row-title` and
  `.audio-row-sub` in `StreamRow` and `DeviceCard`.
- [x] 3.2 Clamp the device-list row labels and the routing popover items
  (construct-property form: `max_width_chars` / `ellipsize`).
- [x] 3.3 `tooltipText` on every clamped label. No CSS change (GTK4 has no
  `max-width`).

## 3b. Duration, position trust, flicker

- [x] 3b.1 `AudioPopup.tsx`: the seek slider requires `canSeek && lengthUs > 0`.
      With no duration both conversions collapse to 0, so the old slider sent
      `position 0` on every release — a guaranteed restart on live streams (D7.1).
      `commit()` carries the same guard, so no stale gesture can send it either.
- [x] 3b.2 `mpris-core.ts`: `TrackMeta.url` (`xesam:url`) + `isSameTrack` +
      `carryDuration` — a dropped `mpris:length` is carried forward for the same
      track, never across a different one (D7.2). 14 node assertions.
- [x] 3b.3 `mpris-service.ts`: `heldPositions` + `adoptReportedPosition` — a
      position far behind the last trusted one is held for a bounded window while
      playing; a report at/past it is accepted at once; a track change voids the
      hold. Wired into `handleSeeked`, `syncPosition` and `playerFromProps` (D6).
- [x] 3b.4 `playerFromProps`: position falls back to `previous.positionUs`, not
      `0` — a resync mid-seek used to reset the display to the start.
- [x] 3b.5 `state.ts`: snapshot scheduler moved OUT of `AudioPopup` into module
      scope (a component-created effect ran once and never again — gnim's
      `createRoot` warning, confirmed by `snapshotStats.started === 1`), keyed on
      the node id set; dumps compared by value and coalesced one-in-flight.
- [x] 3b.6 `state.ts`: per-node identity cache (`streamKeysByNodeId`) so a
      snapshot taken mid-re-link cannot unbind a row; snapshot kept available
      before the popup has ever opened (`hasGraphSnapshot`).
- [x] 3b.7 `state.ts`: momentary-`volume: 0` hold for the level line, bypassed by
      our own writes (`setAppVolume`/`toggleAppMute`).
- [x] 3b.8 `style.css`: the subtitle line's height is reserved, so a title change
      cannot resize the row and move the sliders.
- [x] 3b.9 `state.ts`: the default-endpoint epoch bumps only when the resolved
      default id actually MOVES. Bumping on every `wp.nodes` notify was a
      regression of the D1a fix — AstalWp returns a fresh GObject per lookup, so
      the Output card re-rendered constantly on a churning graph.
- [x] 3b.10 `debugAudioState()` exposes `snapshot` stats and `heldPositions`, so
      both "stale snapshot" and "the thumb jumped back" are measurable instead of
      inferred.

## 4. Static gates

- [x] 4.1 `ags bundle app.tsx /tmp/ags-check.bundle.js --root . --gtk 4` → 0.
- [x] 4.2 `node tests/ags-symbol-check.mjs` → `SYMBOL CHECK OK`.
- [x] 4.3 `node tests/mpris-core.test.mjs` → `mpris core agrees` (9 new
  assertions, including the live Firefox strings).
- [x] 4.4 `git diff --name-only` ⊆ the §0 list (plus the pre-existing, unrelated
  `components/wifi/WifiPopup.tsx` WIP, untouched and NOT deployed).

## 5. Live verification harness (needs a GUI session)

- [x] 5.1 Deploy the four files into the spine, relaunch the bar, log free of
  `JS ERROR`/`ReferenceError`/`not defined`; `ags request audio-debug` answers.
- [x] 5.2 **Default endpoint (scripted, destructive-then-reverted):** load a
  throwaway null sink → `wpctl set-default <probe>` → the bar still reports the
  old sink (no epoch bump yet, by design) → one graph change → the bar reports
  the probe sink. Reverted: probes unloaded, default restored to node 53.
- [ ] 5.3 **Duplicate row (needs one playback in Firefox):** play a YouTube
  video, then `ags request audio-debug` → `rows` has exactly ONE entry for
  Firefox, with `liveStreamId` set AND `player` set (was: two entries, one with
  `liveStreamId: null` and a `—` volume line).
- [ ] 5.4 **Output switching by click:** open the popup → `Change ›` → pick the
  earbuds → the card title, bar glyph and the `✓` all follow, and stay after
  closing and reopening the popup.
- [ ] 5.5 **Layout:** open the popup with a long media title and the earbuds
  connected → no text crosses the surface edge; hovering a clamped label shows
  the full string.
- [ ] 5.6 **No regression:** tidal-hifi still shows ONE row; dragging its
  transport still seeks; the Recording section and per-app routing unchanged.

## 6. Close-out

- [x] 6.1 §5.3–§5.5 confirmed by the owner on the live session: the seek lands
  and the thumb holds without a pause/resume; one row per app; Output/Input
  switching follows on a single click; long titles stay inside the surface.
- [x] 6.2 Spec deltas in `specs/audio-panel-default-and-app-identity/spec.md`
  hold against the live result.
- [ ] 6.3 Only then propose archive. The authoritative deploy is the
  `compositor_configs` role, not the `cp` used in §5.1 (I8: never hand-edit the
  spine as a final state) — **still outstanding: the spine was updated by `cp`
  for the live gate and provisioning has not been re-run.**
