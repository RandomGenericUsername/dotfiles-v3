# Design — default-output resolution + app-identity unification

## D1 — Why the default endpoint needs a locally-owned epoch

`defaultNodeFor(mediaClass)` returns a `createComputed`. Today its only reactive
input is `allNodes()` (the `wp.nodes` binding). The measurements in the proposal
say that input does not move when the default does:

```
wpctl set-default 82   →  wp.default_speaker.id === 82   (immediately)
wp.nodes               →  [82, 54, 64, 90, 53]           (unchanged)
notify::default-speaker→  0 emissions
```

A `GObject` property read is always live, so the *value* is available; what is
missing is a *signal* telling the computed to look again. Hence an epoch:

```ts
const [defaultEndpointEpoch, bumpDefaultEndpoint] = createState(0)
export function invalidateDefaultEndpoint(): void
```

bumped by exactly three things, all of them events or one user action (I1 —
no timer):

| trigger | why it is the right seam |
|---|---|
| `setDefaultSpeaker` / `setDefaultMicrophone` `.then()` → `settleDefault()` | our own write is the one moment we KNOW a default moved |
| any `wp.nodes` notify (a `createEffect` on its length) | a sink appearing/leaving re-points WirePlumber's default (measured: disconnecting the configured Bluetooth sink fell back to the analog one) |
| `open()` | picks up a default changed outside the panel — pavucontrol, a keybind, `wpctl`, hotplug |

`defaultNodeFor` reads `defaultEndpointEpoch()` first. Nothing else changes:
the fallback chain (default id → first node of the class) is untouched, so a
missing `default_speaker` behaves exactly as before.

### D1a — The write has to SETTLE, not fire once

Bumping the epoch the instant `wpctl` exits is too early. WirePlumber applies
the change in its own daemon, after the client process is gone; measured on
this machine, **7ms after the `wpctl` process exited `wp.default_speaker` still
named the old sink**, and the flip landed ~20ms later. The re-resolve therefore
read a stale value and the card stayed on the old device until some later
trigger arrived — reported as *"I have to change it twice, or play something,
before it updates, even though the audio actually switched"*.

`settleDefault(kind, targetId)` re-resolves on a short timer and **aborts as
soon as the default really is the requested node**, with a bounded budget
(15 × 100ms = 1.5s, far above the measured ~20ms) so a change WirePlumber
refuses (e.g. an ineligible virtual source) cannot leave a timer running. On
completion it re-snapshots the graph, because changing the default re-links
every stream and the per-app routing labels are resolved from that `pw-dump`
snapshot — without it the cards updated while the rows still advertised the old
device until the next popup open.

This is not polling: it is a bounded re-resolution started by a user action,
which reads the same binding the UI already renders. It is the same shape
`routeStreamTo` already uses (a 600ms one-shot re-snapshot after a routing
write).

Deliberately NOT done: a `setTimeout`-based read of `default_speaker` from the
render path, or subscribing to `notify::default-speaker` (it provably never
fires — subscribing would be dead code that looks correct).

## D2 — One row per app: resolve, do not enumerate

The two naming sources are both legitimate; the defect is that they were
canonicalised in isolation. The seam is deliberately a **callback**, not a
table:

```ts
export type AppIdentityResolver = (identity: string) => string[]
export function resolveAppIdentities(player, taken, resolve?): string[]
```

- a player whose canonical key is in `taken` (a live stream already claims it)
  is used verbatim — the resolver is not even called, so the common case cannot
  be perturbed by it;
- otherwise the resolver is asked, with BOTH the canonical form and the raw
  root `Identity`, and the stream's key is returned first with the canonical key
  kept as a fallback;
- with no resolver, or no answer, the canonical key is returned — a player-only
  row (D8) still appears and is never folded into an unrelated app.

Why a callback and not a longer `ALIAS` table: `ALIAS` is a spelling list, and
the reported bug is precisely that an unlisted spelling produced a second row.
The table stays for the cases that must fold *in the absence of a stream*
(icon resolution for a paused player) and gains the one measured entry
(`mozilla-firefox`); the resolver makes the table non-critical for row identity.

Ownership: `mpris-core` stays GJS-free (I11) and owns the rule; `mpris-service`
owns the plumbing (`appKeys` per derivation, `setAppIdentitySource`,
`setClaimedStreamKeys`); `audio/state.ts` owns the graph and installs the
resolver. `applicationRows` publishes the claimed keys BEFORE deriving players,
because "is this key already claimed?" is only answerable once the streams are
known.

Read-side rule: `playerForApp` matches `player.appKeys.includes(app)`, never
`player.canonical === app`. Matching the canonical form would drop the transport
off the unified row and resurrect the phantom row by the back door.

## D5 — The Output-card transport is DEVICE-scoped (supersedes D1)

**Owner ruling, 2026-09-30.** D1 ("the master button controls the most recently
active player") is withdrawn. The complaint that produced it was that the button
acted on an app the UI never showed — press once and a different app started,
press again and yet another paused ("it alternated"). The fix is not a better
recency heuristic but a different subject: the button belongs to the **selected
output device**.

> With the headphones selected, pressing pause pauses **every app routed through
> that interface** — and that holds whether the other apps sit on other
> interfaces or share this one.

So the Output card's transport is the mirror of the per-app rows: same action,
opposite scope (one app / one device). Its subject is always the device whose
name the card is already displaying, so there is nothing invisible about it, and
the tooltip states the blast radius (`Pause 3 apps on TOZO NC9`).

### D5a — Attribution is the SAME resolution the routing chip already shows

Membership is decided by `effectiveSinkIdForApp`, the id behind the existing
`effectiveSinkName`, with the same three steps in the same order: explicit
AstalWp target → link-resolved sink → **the default sink**. One resolution, two
consumers, so the button's blast radius can never disagree with the chip on a
row: the transport always acts on exactly the rows that name that device.

The fallback step is load-bearing, not a convenience. Measured live: Firefox's
links to the speakers are `state: "init"`, not `"active"`, while it is paused —
an active-link-only rule would exclude it, and the card would offer to pause
"nothing" while the row beneath it displays the speakers. This is why the fix is
a shared resolver rather than a second, stricter link lookup.

A player with no live stream at all cannot be attributed and is not touched: it
is not demonstrably routed through that device, and guessing would reintroduce
exactly the invisible target this change removes.

### D5b — The aggregate states a target, it does not toggle

Pausing a device means *every* app on it stops; resuming means every app on it
plays. A `playPausePlayer` loop would therefore be wrong — it would START the
apps already paused while pausing the ones that were playing. `setPlayerPlaying`
performs an explicit state with the same optimistic bookkeeping the per-app path
uses, and the glyph reflects the aggregate with **pause winning when mixed**, so
one press silences the device rather than half-restarting it.

### D5c — `lastPlayingAt` stays honest

`activePlayer` is no longer a UI target, so the recency ranking is no longer load
bearing; the `0`-on-fresh-hydration rule is kept because the field's contract is
independent of its consumers. A fresh hydration of an already-`Playing` player
still gets **no** stamp: it was playing before we looked at it, and a bus name
that leaves and reappears is re-hydrated from scratch. Both re-registrations are
measured on this machine (Firefox's MPRIS interface leaves the session bus
entirely after an MPRIS seek while the process keeps running; Tidal came back
under a new pid mid-session). `audio-debug` dumps each player's `status` /
`lastPlayingAt` / `appKeys` plus the transport's own membership, so the target of
a control is measurable instead of inferred.

## D6 — The panel's own commit outranks a stale app report

Once seeking actually worked, the remaining defect was that the display kept
trusting a broken clock. Measured, one Firefox session while a video played,
sampled once a second:

```
0.000005 → 265.000006 → 0.000007 → 0.000007 → 268.000007 → 270.000006
```

Roughly every other report was **zero**, which is the whole of "the slider resets
to 0". The same collapse happened on the transition to `Playing` and right after a
seek, while *paused* the app reports the true absolute position, and Firefox was
also seen reporting the **previous** seek's target — one seek behind, so a single
re-read cannot declare the app wrong either.

The invariant available to us: **a playing media's clock cannot legitimately jump
backwards**, and a zero reported after a position the app already reported is a
broken clock, not a restart. So a position far behind the last trusted one is held
for a bounded window (4 s, 2.5 s tolerance) while a report at or past it is
accepted immediately — a healthy app agrees at once, so the hold is invisible in
the normal case. A **track change voids it instantly**, so a live stream genuinely
restarting still works and the hold can never outlive its media. The position the
user commits by dragging is seeded as trusted, since the video visibly moved there.

This is the same rule as D5c applied to the field it came from, and the same
shape three times over in this change: hold what the panel knows, accept the app
the moment it agrees, never let a hold outlive what it described.

## D7 — A duration belongs to the track, not to the announcement

Two defects, one cause: the seek slider's visibility depended on `canSeek` alone.

1. **Live stream / unknown duration.** `usToStep` and `stepToUs` both collapse to
   `0` when the duration is unknown, so the slider rendered *pinned at the start*
   and every release committed an absolute seek to **0** — a guaranteed restart
   manufactured by our own arithmetic, with no app defect involved. An absolute
   seek is meaningless without a duration, so the control now requires
   `canSeek && lengthUs > 0` (D9 already renders elapsed-only in that case).
2. **A dropped `mpris:length`.** Firefox published `mpris:length = 1043000000`
   for a track, then re-announced the **same** track — identical `xesam:url` and
   title — with the key simply absent. Read literally that is "duration unknown",
   so the slider vanished mid-playback and only pausing/resuming brought it back.
   A duration is a property of the track, so it is carried forward while the
   re-announcement still names that track: keyed on `xesam:url`, with the title
   only as a fallback when no url is published. A genuinely different track
   inherits nothing — the slider can never end up on another video's timeline.

`mpris:trackid` cannot do this job: it is a per-player dummy
(`/org/mpris/MediaPlayer2/firefox`) that is identical for every track a tab plays.

## D8 — The snapshot, and why the flicker was ours

Slicing the owner's screen recording frame by frame showed one Applications row
alternating between three renderings across *consecutive* frames: stream-bound
("Firefox" / "AudioStream" / 100%), player-only ("Mozilla firefox" / track title /
`—`), and a muted 0% variant. Polling across a seek reproduced it exactly:

```
22× [[streamId 76, volume 1]]   ← normal
 1× [[null,          volume 1]] ← row unbound from its stream
 1× [[76,            volume 0]] ← level line blinked to 0%
56× [[76,            volume 1]]
```

The node id never changed, so four distinct defects were behind it:

| # | defect | fix |
|---|---|---|
| 1 | the refresh effect lived inside the `AudioPopup` **component**; gnim warns `effects created outside a createRoot will never be disposed`, and measured behaviour matched — it ran **once** at bar start and never again, so the snapshot predated the first playback | the scheduler moved to `state.ts` at module scope; "when to snapshot" is a state concern, not a view one |
| 2 | every dump published a **new** snapshot object, and gnim notifies on identity, so identical snapshots re-rendered every row | snapshots are compared **by value** before publishing; `snapshotStats` counts started/published/skipped/coalesced |
| 3 | one `pw-dump` per notification, results landing in arbitrary order — a stale parse could overwrite a fresher one | one in flight, at most one queued |
| 4 | the trigger counted streams, so a re-link (same count, new node) was missed | the trigger is the node **id set** |

Plus two more from the same recording: a **per-node identity cache** (the snapshot
lags by one round-trip, so a node id that has already been named keeps its
identity across the gap), and a **short hold on a momentary `volume: 0`** — a real
drop to zero persists, so a 500 ms hold on an implausible fall is invisible, and
our own writes bypass it so dragging to zero is never second-guessed. Finally the
conditionally-rendered subtitle line was **reserving no height**, so its
appearance resized the row and dragged the sliders with it; the second line is now
reserved.

One regression is recorded here deliberately because it shipped for a few minutes:
adding that cache initially deleted the loop converting raw names into keys, so
app identity was empty for every stream and rows rendered player-only. It was
caught by the snapshot counters added in the same round — a reminder that the
diagnostics are what make such a defect visible rather than merely plausible.

## D3 — The seek is an application limitation, not a panel defect

Measured on the reported app, with the panel's own call path:

| action | result |
|---|---|
| `playerctl -p firefox.instance_1_209 position 3605` (its current position) | position → `0.000000` |
| `Seek(x, +3605000000)` on the same interface | no movement |
| `SetPosition(o, 3605000000)` | applied, then the interface left the session bus |

So the app mishandles absolute seeks on that media session. The panel's
obligation is only that the row the user aims at is the row that owns the
playback — which D2 delivers. Inventing a rollback/hold UX for an app that
accepts no seek would be speculative; it is explicitly a non-goal.

## D4 — Clamp, do not rename

Long text is a layout problem, so it is fixed in the layout. `maxWidthChars` +
`ellipsize` is the pattern already documented in `WifiContent.tsx` ("an
unwrapped Gtk.Label reports its FULL text width as natural width … `hexpand`
alone does not help") and the only one GTK4 CSS can express (no `max-width`).
Widths are derived from the popup's real geometry: 356px surface − 22px padding
− 3px border, minus the icon (20), two gaps (9 each), the mute button (17) and
the routing chip (14 chars ≈ 90px), leaving ≈160px for the meta block →
`maxWidthChars={20}` at 13px and `{28}` at 11px. Device rows and the routing
popover get their own, wider budgets. The full text is always reachable as
`tooltipText`, so nothing is lost — it is only hidden until asked for.
