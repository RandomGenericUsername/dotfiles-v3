## Why

Four defects in the AGS audio panel, all reported together and all reproduced
on this machine before a line was changed. Each root cause below is a measured
fact, not an inference.

1. **The main Output never changes — it is always the speakers.** Selecting a
   device in `Change ›` runs `wpctl set-default`, but the Output card, the
   Input card, the bar indicator and the `✓` in the device list all resolve the
   default through `defaultNodeFor()` (`audio/state.ts`), a `createComputed`
   whose ONLY dependency is `wp.nodes` membership. Measured with a throwaway
   null sink (created → set default → removed):

   | fact | measurement |
   |---|---|
   | `wp.default_speaker.id` after `wpctl set-default` | updates **immediately, in-process** |
   | `wp.nodes` | **unchanged** — both sinks stay enumerated |
   | `notify::default-speaker` / `notify::default_speaker` | **never fire** (0 emissions; generic `notify` fired 10×) |

   So the computed never re-evaluates and the card stays pinned to whichever
   sink resolved first, forever. Per-app routing was unaffected because it goes
   through `target_endpoint` + a fresh `pw-dump` snapshot — which is exactly the
   asymmetry that was reported.

2. **The same app is listed twice** (Firefox). The Applications list is the
   union of two naming sources that were canonicalised independently. Measured
   live: stream node 90 `application.name = "Firefox"`,
   `application.process.binary = "firefox"` → key `firefox`; MPRIS
   `org.mpris.MediaPlayer2.firefox.instance_1_209` with root
   `Identity = "Mozilla firefox"` → key `mozilla-firefox`. Two keys, one
   playback. The first row carried the volume/mute/routing and no transport; the
   second carried the transport and a dead `—` volume line. Tidal looked correct
   only because its spellings already fold onto one key.

3. **Dragging the phantom row's progress bar resets the video.** The transport
   was bound to the phantom row, so the user aimed at an entry with no stream.
   Reproduced on the app itself: a seek to the player's *current* position
   (`playerctl -p firefox.instance_1_209 position 3605`, the exact call path the
   panel uses) drove the position to `0.000000`, and the following
   `SetPosition` made the Firefox MPRIS interface **leave the session bus
   entirely** while Firefox kept running — the YouTube media session is torn
   down. Raw `Seek(offset)` does not work either. This one is an application
   limitation (see Non-goals); what the panel owns is that there is only ever
   ONE row to aim at, and that row is the one carrying the playback.

4. **Long names break the layout.** `C-Media(R) Audio Analog Stereo` is the raw
   ALSA `node.description` (the sink is also at 125%). The routing chip was
   already clamped, but `.audio-row-title` / `.audio-row-sub` were not: an
   unwrapped `Gtk.Label` reports its FULL text as natural width and `hexpand`
   does not make it yield, so a long media title demanded more than the 356px
   surface and spilled past the window edge — the whole card read as broken.

## What Changes

- `services/mpris-core.ts` — add the measured `"mozilla-firefox" → firefox`
  fold, plus a pure `resolveAppIdentities` / `keyForPlayer` seam: for a player
  whose canonical key no live stream claims, the host is asked which stream
  claims that identity and the player is listed under the STREAM's key.
- `services/mpris-service.ts` — carry `MprisPlayer.appKeys` (recomputed per
  derivation), and accept the host's identity resolver + claimed stream keys.
- `audio/state.ts` — install the identity resolver, publish the claimed keys
  before deriving players, match `playerForApp` on `appKeys`, and add
  `defaultEndpointEpoch` so the default endpoint re-resolves on the three
  events that can move it (our own `set-default` write, any `wp.nodes` change,
  and the popup opening). Expose the epoch in `ags request audio-debug`.
- The Output-card transport becomes **device-scoped** (owner ruling,
  supersedes D1): it acts on every app whose effective sink is the selected
  output, resolved through the same `effectiveSinkIdForApp` the per-app routing
  chip already displays, and performs an explicit play/pause per app rather than
  a toggle.
- `audio/AudioPopup.tsx` — clamp row title/subtitle, device-list rows and the
  routing popover items with the house `maxWidthChars` + `ellipsize` pattern,
  each with the full text as tooltip.

## Non-goals

- Not making Firefox/YouTube seek work. The app mishandles MPRIS
  `SetPosition`/`Seek` (measured); no panel change can fix that. No
  optimistic-hold/rollback UX is invented for it.
- No friendly device-name table ("Speakers", "Earbuds"). The PipeWire
  description stays the single source of truth; only the layout is fixed.
- No `wpctl`-backed re-read loop, no polling of the default endpoint (I1).
- No change to `bar/widgets/audio.tsx`, `components/sliders/VolumeSlider.tsx`,
  the icon registry, `icons.json`, CSS, provisioning, or the runtime.
- Not renaming the D6 "generic media name" filter (`Playback`); a second
  generic name (`AudioStream`) was observed live and is left for a separate,
  deliberate decision.
