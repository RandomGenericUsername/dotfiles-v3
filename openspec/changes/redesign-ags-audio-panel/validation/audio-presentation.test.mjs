import test from "node:test"
import assert from "node:assert/strict"
import { projectAudioPanel } from "../../../../dotfiles/config/ags/audio/presentation/audio-panel-view-model.ts"

const endpoint = (id, name) => ({ id, name, available: true, volume: { level: 0.8, muted: false } })
const app = { id: "firefox", displayName: "Firefox", desktopId: "firefox.desktop", aliases: ["firefox"] }
const media = (overrides = {}) => ({
  title: "Cowboy Bebop Study Music", artist: "Musically Chill", album: "", artworkUri: "file:///cover.jpg",
  lengthUs: 120_000_000, positionUs: 3_000_000, ...overrides,
})
const player = (overrides = {}) => ({
  id: "mpris:firefox#1", appId: "firefox", current: true, playback: "playing",
  capabilities: { canPlay: true, canPause: true, canPlayPause: true, canGoNext: false, canGoPrevious: false, canSeek: true },
  media: media(), ...overrides,
})
const stream = (overrides = {}) => ({
  id: "pw:42", appId: "firefox", direction: "output", endpointId: "A", requestedEndpointId: null,
  routeIntent: { kind: "follow-preferred" }, volume: { level: 0.6, muted: false }, current: true,
  ...overrides,
})
const session = (overrides = {}) => ({
  preferredOutputId: "A", preferredInputId: "mic", outputs: [endpoint("A", "C-Media"), endpoint("B", "USB DAC")],
  inputs: [endpoint("mic", "USB Microphone")], input: endpoint("mic", "USB Microphone"), apps: [app],
  streams: [stream()], players: [player()], appIntents: {}, ...overrides,
})

test("joins aliases into one app row and prefers live MPRIS metadata over generic stream names", () => {
  const model = projectAudioPanel(session({
    apps: [{ ...app, id: "mozilla-firefox" }],
    streams: [stream({ appId: "Mozilla Firefox", mediaName: "AudioStream" })],
    players: [player({ appId: "firefox" })],
  }))
  assert.equal(model.rows.length, 1)
  assert.equal(model.rows[0].id, "firefox")
  assert.equal(model.rows[0].title, "Cowboy Bebop Study Music")
  assert.equal(model.rows[0].artist, "Musically Chill")
  assert.equal(model.rows[0].routeLabel, "Follow preferred · C-Media")
  assert.equal(model.rows[0].artworkUri, "file:///cover.jpg")
  assert.equal(model.rows[0].artworkPath, null)
})

test("keeps a player-only row and gates stream writes separately from player actions", () => {
  const row = projectAudioPanel(session({ streams: [], players: [player()] })).rows[0]
  assert.equal(row.hasCurrentPlayer, true)
  assert.equal(row.hasCurrentStream, false)
  assert.deepEqual(row.streamIds, [])
  assert.equal(row.canSeek, true)
  assert.equal(row.playerId, "mpris:firefox#1")
})

test("keeps a stream-only row, falls back honestly to app identity, and disables transport", () => {
  const row = projectAudioPanel(session({ streams: [stream()], players: [] })).rows[0]
  assert.equal(row.title, "Firefox")
  assert.equal(row.artist, "")
  assert.equal(row.hasCurrentStream, true)
  assert.equal(row.hasCurrentPlayer, false)
  assert.equal(row.playerId, null)
  assert.equal(row.canSeek, false)
  assert.equal(row.durationUs, null)
})

test("aggregates multiple app streams explicitly without losing stream identities or per-stream state", () => {
  const row = projectAudioPanel(session({ streams: [
    stream({ id: "pw:1", volume: { level: 0.2, muted: false } }),
    stream({ id: "pw:2", endpointId: "B", routeIntent: { kind: "explicit", endpointId: "B" }, volume: { level: 0.8, muted: true } }),
  ] })).rows[0]
  assert.deepEqual(row.streamIds, ["pw:1", "pw:2"])
  assert.equal(row.volume.level, 0.5)
  assert.equal(row.volume.muted, false)
  assert.equal(row.mixedLevel, true)
  assert.equal(row.mixedMuted, true)
  assert.equal(row.observedEndpointId, null)
  assert.equal(row.routeIntent, null)
  assert.equal(row.routeLabel, "Multiple routes · Mixed intent")
})

test("projects explicit route separately from effective endpoint and microphone consumers", () => {
  const model = projectAudioPanel(session({ streams: [
    stream({ routeIntent: { kind: "explicit", endpointId: "A" }, endpointId: "B" }),
    stream({ id: "pw:mic", direction: "input", endpointId: "mic" }),
  ] }))
  assert.equal(model.rows[0].routeLabel, "C-Media · Override")
  assert.equal(model.rows[0].observedEndpointId, "B")
  assert.deepEqual(model.inputConsumers, [{ id: "pw:mic", appId: "firefox", appName: "Firefox", iconName: "firefox" }])
  assert.deepEqual(model.inputs.map((input) => input.id), ["mic"])
})

test("row identity and display fields stay unchanged when only seek position changes", () => {
  const before = projectAudioPanel(session()).rows[0]
  const after = projectAudioPanel(session({ players: [player({ media: media({ positionUs: 17_000_000 }) })] })).rows[0]
  assert.equal(after.id, before.id)
  assert.equal(after.title, before.title)
  assert.equal(after.positionUs, 17_000_000)
})

test("seek is gated by current capability and a usable duration", () => {
  assert.equal(projectAudioPanel(session({ players: [player({ capabilities: { ...player().capabilities, canSeek: false } })] })).rows[0].canSeek, false)
  assert.equal(projectAudioPanel(session({ players: [player({ media: media({ lengthUs: null }) })] })).rows[0].canSeek, false)
  assert.equal(projectAudioPanel(session({ players: [player({ current: false })] })).rows.length, 1) // stream still owns row
})
