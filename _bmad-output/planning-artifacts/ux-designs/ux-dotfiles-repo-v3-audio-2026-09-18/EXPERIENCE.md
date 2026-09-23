---
name: AGS Audio Control
description: Behavioral contract for the audio bar indicators and the follower-anchored audio popup — information architecture, dynamic stream lifecycle, routing interaction, states, and accessibility floor.
status: final
updated: 2026-09-21
sources:
  - docs/linux-wayland-pipewire-ags-audio-control.md
  - _bmad-output/planning-artifacts/gui-unification-ux-spec.md
  - openspec/changes/add-ags-settings-panel/
  - _bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-audio-2026-09-18/mockups/key-bar-indicators.html
  - _bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-audio-2026-09-18/mockups/key-audio-popup.html
design: DESIGN.md
---

# AGS Audio Control — Experience Spine

## Foundation

Desktop surface of the Hyprland dotfiles environment, rendered by AGS (GTK4) on Wayland. Two surfaces: a pair of **bar indicators** in the always-on status bar, and a **follower-anchored audio popup** that opens under the output indicator. The audio data comes exclusively from the **AstalWp** binding over WirePlumber (`speakers`, `microphones`, `streams`, `recorders`, `devices`, each with `*-added` / `*-removed` signals). There is no polling and no `wpctl` parsing in the UI. Visual identity is defined in `DESIGN.md`; it inherits the AGS settings-panel primitives (`PanelCard`, `LevelSlider`, catcher window, in-place subview navigation). Primary monitor only. Single user; no accounts, no network, no persistence beyond what WirePlumber already keeps.

## Information Architecture

| Surface | Reached from | Purpose |
|---|---|---|
| Output bar indicator | Always in the bar (`volume` icon group) | Master output level + live percentage; left-click opens the popup, right-click opens pavucontrol, scroll adjusts volume |
| Mic bar indicator | Always in the bar (`microphone` icon group) | Mic mute state; live dot while a recording stream is active; left-click opens the popup focused on Input |
| Audio popup — Output | Output indicator, or the Input subview's back | Default output: mute glyph, device name, level slider; `Change ›` opens the device subview |
| Audio popup — Output devices (subview) | `Change ›` in Output | List of sinks from `wp.speakers`; active device checked; selecting sets the default output; `‹` returns |
| Audio popup — Applications | Popup | One row per `wp.streams` entry: app icon, name/subtitle, mute, level, routing select; a transport line (`⏮ ▶/⏸ ⏭ · seek · time`) appears on rows whose stream has an MPRIS player |
| Audio popup — Input | Popup, or mic indicator (focus) | Default microphone: mute glyph, name, level slider |
| Audio popup — Recording | Popup | One row per `wp.recorders` entry; header carries the live dot |

Sections with zero content collapse. Popup is one panel deep; the device subview is the only navigation, and it swaps in place with a back arrow. No modal stacks.

→ Composition reference: `mockups/key-bar-indicators.html`, `mockups/key-audio-popup.html`. Spine wins on conflict.

## Voice and Tone

Microcopy only; brand voice lives in `DESIGN.md`.

| Do | Don't |
|---|---|
| "Output", "Applications", "Input", "Recording" | "Sound Settings", "Audio Devices" |
| "No output device" | "Error: sink enumeration failed" |
| "Muted" (badge) | "Volume: 0" / "Sound disabled" |
| Device names verbatim from WirePlumber (`Headphones`, `USB Microphone`) | Humanised guesses ("Your headphones") |
| App name + stream media name (`YouTube` / `Chrome`) | Merged labels ("Chrome (YouTube + 1 more)") at v1 |
| "Change ›" | "Select output device…" |

Tone is terse and factual. The popup reports the graph; it does not congratulate or apologise.

## Component Patterns

Behavioral rules. Visual specs live in `DESIGN.md.Components`.

| Component | Use | Behavioral rules |
|---|---|---|
| Output bar indicator | Bar | Glyph variant tracks volume through the same five thresholds as the settings panel: muted (0%), lowest (1–25%), low (26–50%), medium (51–75%), max (76–100%). Shows the rounded percentage. Left-click opens the popup; right-click launches `pavucontrol`; scroll-up/down adjusts default-speaker volume by the standard step. |
| Mic bar indicator | Bar | `mic-off` icon when the default microphone is muted, `mic-on` otherwise. The live dot shows **iff** `wp.recorders` is non-empty. Left-click opens the popup focused on Input; does not toggle mute on the bar (mute is deliberate, in the popup). |
| Level row | Output, Applications, Input, Recording | Leading mute/level glyph click toggles mute for that node. Title + subtitle; subtitle is the app name for streams, the device description for devices. Slider writes `volume`. Percentage updates live. |
| Routing select | Applications rows | Trailing control listing the live `wp.speakers`. Selecting a sink sets `stream.target-endpoint` for that stream only. The menu is regenerated from the collection each open; never cached. |
| Transport line | Applications rows with an MPRIS player | Rendered **iff** the stream links to a player (identity match on `application.name` slug + `application.process.binary`, aliased). `▶/⏸` sends `PlayPause`; prev/next shown only when the player reports `CanGoPrevious`/`CanGoNext` and send `Previous`/`Next`; seek slider shown only when `CanSeek`, and commits its absolute position on **release**, never per tick. Elapsed time interpolates locally between MPRIS syncs; the tick runs only while the popup is open and the player is Playing — no polling. |
| Master play/pause | Output card | Bordered `▶/⏸` between the name/meta block and `Change ›`. Drives the **most recently active player** (the one that most recently reported Playing; a stopped player never outranks a live one). Glyph is `pause` while that player is Playing, else `play`. Hidden when no player exists. Tooltip names the target. |
| Active-device check | Output devices subview | The current default sink carries `✓` and the active-row fill. Selecting another row calls `setDefaultSpeaker` (the `wpctl set-default` action path) and returns. Existing routed streams are unaffected. |
| Device subview | Output card | `Change ›` swaps panel content to the sink list; `‹` returns. Selecting a row sets `wp.default-speaker` and returns. Panel dimensions stay stable across the swap. |
| Section card | Popup | Rendered iff its backing collection is non-empty. Empty → the card is absent, not disabled or placeholder-filled. |
| Live dot | Mic indicator, Recording header | Purely additive signal; no text, no count. Absent when no recorder is active. |

## State Patterns

| State | Surface | Treatment |
|---|---|---|
| No output device | Output | Card shows a muted line "No output device"; slider disabled. Does not collapse — the user needs to see there is no output. |
| Output muted | Output + bar | Mute badge on the row; glyph dimmed; slider fill dimmed but volume value retained. The bar shows the `muted` glyph. Volume is never hidden by mute. |
| No playback streams | Applications | Card collapses entirely. |
| No recording streams | Recording + mic dot | Card collapses; mic dot absent. |
| No microphone | Input | Card shows "No input device"; slider disabled. |
| Stream appears while popup open | Applications | Row is created by the `stream-added` signal; popup grows. |
| Stream disappears | Applications | Row is destroyed by `stream-removed`; popup shrinks. No confirmation, no toast. |
| Two streams, one app | Applications | Two independent rows keyed by stream id; each has its own volume, mute, and routing. |
| Browser tabs | Applications | Not assumed. A browser may expose one stream for many tabs; the UI never claims per-tab control. |
| Stream has no MPRIS player | Applications | Row is volume-only, exactly as before transport existed (e.g. Discord). No placeholder, no disabled transport line. |
| Stream paused (has player) | Applications transport | Transport line dims (fill + labels), knob frozen, glyph flips to `play`. |
| Player quits mid-session | Applications transport | The transport line disappears with the player (`NameOwnerChanged`); the stream row and its volume/routing stay. No toast. |
| No players at all | Output card | Master button is hidden; all rows are volume-only. |
| Generic media name | Applications subtitle | Subtitle is suppressed when `media.name` is the generic `"Playback"` (case-insensitive); a real title is shown otherwise. |
| Device hotplug | Output devices subview / Output | `speaker-added` / `speaker-removed` add or remove rows live; if the default device disappears WirePlumber picks the next default and the Output card follows. |
| WirePlumber/AstalWp unavailable | Bar + popup | Indicators render but inert; popup sections collapse. No crash, no error dialog (console log only). Mirrors the settings panel's reduced-functionality posture. |

## Interaction Primitives

**Mouse-first, keyboard-supported.**

- Left-click output indicator — open the audio popup under the indicator.
- Right-click output indicator — launch `pavucontrol` (the doc's conventional GUI, kept as the debugging surface).
- Scroll on output indicator — adjust default output volume up/down.
- Left-click mic indicator — open the popup with Input focused.
- Click a mute glyph — toggle mute for that node.
- Drag/click a slider — set volume for that node.
- Click `Change ›` / `‹` — enter/leave the output device subview.
- Click a routing select — open the sink menu for that stream.
- Click a transport glyph — `Previous` / `PlayPause` / `Next` for that row's player (prev/next only where the player allows).
- Drag the transport seek slider — scrub; the position commits on release.
- Click the master button in Output — play/pause the most recently active player.
- `Esc` or click-outside — dismiss the popup (catcher window, same as the settings panel).

**Banned:** opening the popup on hover; auto-hiding it on a timer; spawning `wpctl` per frame; rebuilding the whole popup on every signal (only the affected row updates).

## Accessibility Floor

Behavioral; visual contrast lives in `DESIGN.md` and is additionally guarded at render time by the runtime icon-contrast guard for both bar indicators (`volume`, `microphone` are in the `BAR_GROUPS` allowlist).

- Every interactive element has a tooltip naming its action and target ("Mute Headphones", "Route YouTube to Speakers", "Open audio settings").
- Mute state is conveyed by icon **and** text badge, never colour alone (the green live dot is additive, never the sole indicator of state).
- Slider values are exposed numerically; keyboard focus reaches every slider and button.
- `Esc` always closes the popup, including from the device subview (returns to main view first, then closes).
- The popup does not trap focus; the catcher is `Keymode.ON_DEMAND`.
- Volume change is immediate and continuous; no confirmation, no undo (reversible by adjusting back).

## Inspirations & Anti-patterns

- **Lifted from the AGS settings panel:** the glass panel, the in-place subview with a back arrow, capability glyphs that carry state, and the catcher/Esc dismissal.
- **Lifted from the GUI-unification spec:** two accents with fixed meanings, cards-as-surfaces, selection as ink+fill, imagery gets a ring not a paint.
- **Lifted from the PipeWire control document:** dynamic discovery over hard-coding; physical devices vs application streams kept distinct; `wpctl` for diagnosis, never for the reactive UI.
- **Rejected — a per-app fixed list / database:** the file explicitly forbids maintaining a list of applications; the graph is the list.
- **Rejected — polling `wpctl status`:** process-spawning polling is explicitly called out as the wrong architecture.
- **Rejected — assuming browser-tab streams:** the doc warns most browsers expose a single mixed stream; the UI must not promise per-tab control.
- **Rejected — a custom audio daemon or a second mixer state:** AGS presents WirePlumber's state; it does not own it.

## Key Flows

### Flow 1 — Quick mute (juan david, mid-meeting, 10:14am)

1. juan david is on a call with music playing through Spotify and a browser tab open.
2. He clicks the output indicator in the bar; the popup drops under it. Output shows `Headphones 72%`, Applications lists `YouTube/Chrome 68%` and `Spotify 42%`.
3. He clicks the mute glyph on the Spotify row. The row's glyph dims, a `Muted` badge appears, the slider fill dims, but `42%` stays visible.
4. **Climax:** the bar indicator keeps showing his master `72%` while Spotify is muted — he can still hear the call, and the popup told him exactly which stream went quiet without him leaving the surface. He clicks `Esc`; the popup vanishes and the bar stays.

Failure: the recorder hub is unavailable → the row still mutes through WirePlumber (popup is direct over AstalWp); only the mic dot would be unavailable.

### Flow 2 — Move one app to another output (juan david, evening, 21:40)

1. Speakers are the default, but he wants Spotify on headphones while a video keeps playing on the speakers.
2. He opens the popup, finds the Spotify row in Applications, and clicks its routing select.
3. The menu lists the live sinks — `Headphones`, `Speakers`, `HDMI / DisplayPort` — with the current target checked.
4. He picks `Headphones`. **Climax:** the Spotify row's routing label flips to `Headphones` and audio moves, with no change to Spotify's `42%` or its mute state; the master Output card still says `Speakers`, because the default did not change. Two streams, two targets, one surface.
5. He plugs in a USB headset; the routing menu next time it opens already contains it, because the list is the live `wp.speakers` collection.

Failure: the sink disappears while the menu is open → the menu is rebuilt from the collection on next open; no stale entry.

### Flow 3 — Verify the mic is live (juan david, before recording, 14:05)

1. juan david starts OBS. The bar mic indicator gains the green dot the moment OBS opens a recording stream; no interaction needed.
2. He clicks the mic indicator. The popup opens focused on Input — `USB Microphone 74%` — and the Recording card lists `OBS Studio`.
3. **Climax:** he can confirm both the input level and that the right app holds the mic before he speaks, in one glance from the bar — no `pavucontrol` detour. He reaches for `pavucontrol` (right-click on the output indicator) only when he wants the full routing matrix.

Failure: OBS opens the stream but the mic is muted → Input shows the `Muted` badge, so he unmutes in the popup before recording.

### Flow 4 — Pause the track from the popup (juan david, mid-focus, 16:22)

1. Tidal is playing through headphones while juan david has a Chrome tab open on a separate stream; both rows in Applications carry a transport line, and the Output card shows the master `⏸`.
2. A message arrives and he wants the music to stop without reaching for the keyboard. He opens the popup and clicks the `⏸` on the tidal row.
3. The glyph flips to `▶`, the row dims, the knob freezes, and the time stops advancing.
4. **Climax:** the audio stops on the exact beat he clicked and the popup reflects it immediately — one click from the surface he was already looking at, no window switching, no media-key muscle memory. He clicks `Esc`; the popup vanishes and the bar stays.

Failure: he pauses from the master button instead → it targets the **most recently active** player, not necessarily the one he is looking at; the tooltip names which player it will hit, so the target is never a guess.

### Flow 5 — Skip to the next track (juan david, 22:05)

1. Tidal is playing an intro he does not want; its transport line shows `⏮ ▶/⏸ ⏭` because the player exposes a playlist (`CanGoNext` true).
2. He opens the popup and clicks `⏭` on the tidal row.
3. The track changes; within a moment the row's title, duration, and elapsed time update — MPRIS pushes the new metadata and the position re-syncs on the track change, so the seek bar does not lie.
4. **Climax:** the next track starts from the same surface that shows him which app is playing and how loud — transport, volume, and routing are one gesture away together. A player with no playlist simply omits the `⏮`/`⏭` glyphs rather than showing dead controls.

Failure: the player quits or goes Stopped between opening the popup and clicking → the transport line disappears (event-driven `NameOwnerChanged`); the row stays volume-only and nothing errors.
