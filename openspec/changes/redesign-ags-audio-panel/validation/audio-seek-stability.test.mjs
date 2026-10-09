#!/usr/bin/env node
// Seek/relink stability: a stream that is destroyed and re-created must not
// change anything the user sees about the app.
//
// WHY THIS EXISTS
// ---------------
// Firefox tears down and recreates its PipeWire stream on every seek. Measured
// with a per-row trace (2026-10-07):
//
//   firefox:s1:1.000    stream alive
//   firefox:s0:1.000    stream GONE            ~30ms
//   firefox:s1:0.000:M  new stream, uninitialised (level 0, muted)
//   firefox:s1:1.000    real properties load
//
// Five separate symptoms came out of that one window, each found by the owner
// one at a time, each patched where it surfaced: the volume dipped (mean over
// transient streams), the mute glyph showed muted, the controls disabled, the
// route label fell back to "No current route", and the row name flipped
// "Firefox" -> "firefox".
//
// Those were five faces of one broken assumption: STREAM ABSENT MEANS APP
// ABSENT. This test pins the correct behaviour in one place, so the assumption
// is checked once rather than rediscovered per widget. If a future change makes
// a transient gap visible again in ANY of these fields, this fails.
//
// It deliberately goes through the real runtime AND the real projection, not
// either in isolation: the bug lived in what the projection was fed.

import assert from "node:assert/strict";
import { AudioSessionRuntime } from "../../../../dotfiles/config/ags/audio/application/runtime/audio-session-runtime.ts"
import { projectAudioPanel } from "../../../../dotfiles/config/ags/audio/presentation/audio-panel-view-model.ts"

class FakeObservation {
  listeners = new Set()
  constructor(initial) { this.initial = initial }
  async hydrate() { return { kind: "snapshot", session: this.initial } }
  subscribe(listener) { this.listeners.add(listener); return () => this.listeners.delete(listener) }
  emit(session) { for (const listener of this.listeners) listener({ kind: "snapshot", session }) }
}

const endpoint = (id, name) => ({ id, name, available: true, volume: { level: 0.5, muted: false } })
const APP = "firefox"
const identity = { id: APP, displayName: "Firefox", aliases: ["firefox"] }

const stream = (id, volume) => ({
  id, appId: APP, direction: "output", endpointId: "A", requestedEndpointId: null,
  routeIntent: { kind: "follow-preferred" }, volume, current: true,
})

const session = (streams) => ({
  preferredOutputId: "A", preferredInputId: null,
  outputs: [endpoint("A", "Speakers"), endpoint("B", "Headphones")],
  inputs: [], input: null,
  apps: streams.length ? [identity] : [],
  streams, players: [], appIntents: {}, appVolumes: {}, appLastIntents: {}, appEndpoints: {},
})

const PIPEWIRE = { setStreamTarget: async () => {}, setPreferredOutput: async () => {} }

// A real MPRIS player: this is what keeps the ROW alive across the gap, and
// omitting it was the first thing this test caught. With no stream and no
// player the projection produced no row at all -- a sixth face of the same bug,
// hidden in the live panel only because Firefox's MPRIS player is always there.
const PLAYER = {
  id: "firefox", appId: APP, current: true, playback: "playing",
  capabilities: { canPlay: true, canPause: true, canPlayPause: true, canGoNext: true, canGoPrevious: true, canSeek: true },
  media: { title: "Track", artist: "Artist", album: "", artworkUri: null, lengthUs: 200_000_000, positionUs: 0 },
}
class FakeMpris {
  listeners = new Set()
  async hydrate() { return { kind: "snapshot", players: [PLAYER] } }
  subscribe(listener) { this.listeners.add(listener); return () => this.listeners.delete(listener) }
  emit(event) { for (const listener of this.listeners) listener(event) }
}
const MPRIS = new FakeMpris()

const PLAYING = { level: 1, muted: false }
const UNINITIALISED = { level: 0, muted: true }   // what AstalWp reports first

const pw = new FakeObservation(session([stream("pw:1", PLAYING)]))
const runtime = new AudioSessionRuntime(pw, MPRIS, PIPEWIRE)
await runtime.start()

const row = () => {
  const rows = projectAudioPanel(runtime.current()).rows
  assert.equal(rows.length, 1, "the app keeps exactly one row throughout")
  return rows[0]
}

const before = row()
const baseline = {
  appName: before.appName,
  level: before.volume.level,
  muted: before.volume.muted,
  routeLabel: before.routeLabel,
}

assert.equal(baseline.appName, "Firefox")
assert.equal(baseline.level, 1)

// --- the seek: stream gone ------------------------------------------------
pw.emit(session([]))
const duringGap = row()
assert.equal(duringGap.appName, baseline.appName,
  "the name must not fall back to the raw appId while the stream is gone")
assert.equal(duringGap.volume.level, baseline.level,
  "the level must be held, not reported as 0")
assert.equal(duringGap.volume.muted, baseline.muted,
  "mute must be held; a missing stream is not 'muted'")
assert.equal(duringGap.routeLabel, baseline.routeLabel,
  "the route label must not reset to 'No current route'")

// --- the seek: stream recreated, reported uninitialised --------------------
pw.emit(session([stream("pw:2", UNINITIALISED)]))
const recreated = row()
assert.equal(recreated.appName, baseline.appName, "name survives the re-creation")
assert.equal(recreated.volume.level, baseline.level,
  "an uninitialised 0/muted re-creation must not drag the level down")
assert.equal(recreated.volume.muted, baseline.muted,
  "an uninitialised 0/muted re-creation must not read as muted")
assert.equal(recreated.routeLabel, baseline.routeLabel,
  "the route label survives the re-creation")

// --- the seek: real properties load ---------------------------------------
pw.emit(session([stream("pw:2", PLAYING)]))
assert.equal(row().volume.level, 1, "and the real value still arrives")

// A genuine user change must NOT be swallowed by the hold.
pw.emit(session([stream("pw:2", { level: 0.25, muted: false })]))
assert.equal(row().volume.level, 0.25,
  "a real change on a live stream is honoured, not overridden by the hold")
pw.emit(session([stream("pw:2", { level: 0.25, muted: true })]))
assert.equal(row().volume.muted, true,
  "a real mute on a live stream is honoured")

runtime.dispose()
console.log("audio-seek-stability: PASS (5 transient-gap fields held; real changes honoured)")
