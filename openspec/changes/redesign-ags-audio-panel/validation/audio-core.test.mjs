import test from "node:test"
import assert from "node:assert/strict"
import {
  canonicalAppKey, currentStreamsForApp, identitiesReferToSameApp, playerSupportsSeek,
  initialRouteIntent, routeIntentAfterExternalTargetChange, routeIntentAfterUserSelection,
  routeLabel, volumeState,
} from "../../../../dotfiles/config/ags/audio/domain/audio-model.ts"
import { setAppVolume, toggleAppMute, setAppRoute, seekPlayer } from "../../../../dotfiles/config/ags/audio/application/audio-actions.ts"

const endpoints = [
  { id: "A", name: "C-Media", available: true, volume: volumeState(0.7, false) },
  { id: "B", name: "USB DAC", available: true, volume: volumeState(0.5, false) },
]
const player = (overrides = {}) => ({
  id: "player:chrome:1", appId: "chrome", current: true, playback: "playing",
  capabilities: { canPlay: true, canPause: true, canPlayPause: true, canGoNext: false, canGoPrevious: false, canSeek: true },
  media: { title: "Track", artist: "Artist", album: "Album", artworkUri: "file:///cover", lengthUs: 60_000_000, positionUs: 4_000_000 },
  ...overrides,
})
const session = {
  preferredOutputId: "A", preferredInputId: "MIC", outputs: endpoints,
  inputs: [{ id: "MIC", name: "USB Mic", available: true, volume: volumeState(0.5, false) }],
  input: null,
  apps: [{ id: "chrome", displayName: "Chrome" }, { id: "firefox", displayName: "Firefox" }],
  streams: [
    { id: "chrome:1", appId: "chrome", direction: "output", endpointId: "A", requestedEndpointId: "A", routeIntent: { kind: "explicit", endpointId: "A" }, volume: volumeState(0.4, false), current: true },
    { id: "chrome:2", appId: "chrome", direction: "output", endpointId: "B", requestedEndpointId: null, routeIntent: { kind: "follow-preferred" }, volume: volumeState(0.8, true), current: true },
    { id: "chrome:mic", appId: "chrome", direction: "input", endpointId: "MIC", requestedEndpointId: null, routeIntent: { kind: "follow-preferred" }, volume: volumeState(0.2, false), current: true },
    { id: "chrome:old", appId: "chrome", direction: "output", endpointId: "A", requestedEndpointId: null, routeIntent: { kind: "unknown" }, volume: volumeState(0.3, false), current: false },
    { id: "firefox:1", appId: "firefox", direction: "output", endpointId: "A", requestedEndpointId: null, routeIntent: { kind: "follow-preferred" }, volume: volumeState(0.6, false), current: true },
  ], players: [player()],
}

function fakePorts(state = session) {
  const calls = []
  const record = (name) => (...args) => { calls.push([name, ...args]); return Promise.resolve() }
  return {
    calls,
    session: { current: () => state },
    pipewire: {
      setPreferredOutput: record("preferred"), setPreferredInput: record("preferredInput"), setStreamTarget: record("route"),
      setStreamVolume: record("streamVolume"), setOutputVolume: record("outputVolume"),
  setInputVolume: record("inputVolume"),
    },
    routeIntents: { record: record("intent"), recordApp: record("app-intent") },
    mpris: {
      play: record("play"), pause: record("pause"), playPause: record("playPause"),
      next: record("next"), previous: record("previous"), seek: record("seek"),
    }, artwork: { resolve: async () => null },
  }
}

test("route values and labels preserve intent independently of endpoint equality", () => {
  assert.deepEqual(initialRouteIntent({ isNew: true }), { kind: "follow-preferred" })
  assert.deepEqual(initialRouteIntent({ isNew: true, externallyRequestedTarget: "A" }), { kind: "explicit", endpointId: "A" })
  assert.deepEqual(initialRouteIntent({ isNew: false }), { kind: "unknown" })
  assert.deepEqual(initialRouteIntent({ isNew: false, authoritativeIntent: { kind: "explicit", endpointId: "A" } }), { kind: "explicit", endpointId: "A" })
  assert.deepEqual(routeIntentAfterUserSelection({ kind: "explicit", endpointId: "A" }), { kind: "explicit", endpointId: "A" })
  assert.deepEqual(routeIntentAfterUserSelection({ kind: "follow-preferred" }), { kind: "follow-preferred" })
  assert.deepEqual(routeIntentAfterExternalTargetChange("B"), { kind: "explicit", endpointId: "B" })
  assert.equal(routeLabel({ kind: "follow-preferred" }, "A", "A", endpoints), "Follow preferred · C-Media")
  assert.equal(routeLabel({ kind: "explicit", endpointId: "A" }, "A", "A", endpoints), "C-Media · Override")
  assert.equal(routeLabel({ kind: "unknown" }, "A", "B", endpoints), "USB DAC · Route unknown")
  assert.equal(routeLabel({ kind: "unknown" }, "A", null, endpoints), "Unknown route")
})

test("volume/mute values clamp gain and preserve it when toggling mute", async () => {
  assert.deepEqual(volumeState(3, true), { level: 1, muted: true })
  assert.deepEqual(volumeState(-2, false), { level: 0, muted: false })
  const ports = fakePorts()
  await toggleAppMute(ports, "chrome")
  assert.deepEqual(ports.calls.filter(([name]) => name === "streamVolume"), [
    ["streamVolume", "chrome:1", { level: 0.4, muted: true }],
    ["streamVolume", "chrome:2", { level: 0.8, muted: true }],
  ])
})

test("app volume and route actions isolate the app and cover all current streams", async () => {
  assert.deepEqual(currentStreamsForApp(session, "chrome").map((stream) => stream.id), ["chrome:1", "chrome:2"])
  const ports = fakePorts()
  await setAppVolume(ports, "chrome", 0.25)
  await setAppRoute(ports, "chrome", { kind: "explicit", endpointId: "A" })
  assert.deepEqual(ports.calls.filter(([name]) => name === "streamVolume"), [
    ["streamVolume", "chrome:1", { level: 0.25, muted: false }],
    ["streamVolume", "chrome:2", { level: 0.25, muted: true }],
  ])
  assert.deepEqual(ports.calls.filter(([name]) => name === "route"), [
    ["route", "chrome:1", "A"], ["route", "chrome:2", "A"],
  ])
  assert.deepEqual(ports.calls.filter(([name]) => name === "intent"), [
    ["intent", "chrome:1", { kind: "explicit", endpointId: "A" }],
    ["intent", "chrome:2", { kind: "explicit", endpointId: "A" }],
  ])
  assert.ok(!ports.calls.some(([, id]) => id === "firefox:1" || id === "chrome:old"))
})

test("preferred-output action selects the system default and leaves routes to the event runtime", async () => {
  const ports = fakePorts()
  const { selectPreferredOutput } = await import("../../../../dotfiles/config/ags/audio/application/audio-actions.ts")
  await selectPreferredOutput(ports, "B")
  assert.deepEqual(ports.calls.filter(([name]) => name === "route"), [])
  assert.deepEqual(ports.calls[0], ["preferred", "B"])
})

test("identity joining folds known aliases but avoids unrelated names", () => {
  assert.equal(canonicalAppKey("Mozilla Firefox"), "firefox")
  assert.equal(canonicalAppKey("Chromium"), "google-chrome")
  assert.equal(identitiesReferToSameApp({ id: "firefox" }, { id: "mozilla-firefox" }), true)
  assert.equal(identitiesReferToSameApp({ id: "chrome", processId: 10 }, { id: "firefox", processId: 10 }), true)
  assert.equal(identitiesReferToSameApp({ id: "unknown-one" }, { id: "unknown-two" }), false)
})

test("player capability projection requires a current seek-capable player and known duration", () => {
  assert.equal(playerSupportsSeek(player()), true)
  assert.equal(playerSupportsSeek(player({ current: false })), false)
  assert.equal(playerSupportsSeek(player({ media: { lengthUs: null } })), false)
  assert.equal(playerSupportsSeek(player({ capabilities: { ...player().capabilities, canSeek: false } })), false)
})

test("player actions target player identity and reject stale or unsupported seek", async () => {
  const ports = fakePorts()
  await seekPlayer(ports, "player:chrome:1", 90_000_000)
  assert.deepEqual(ports.calls, [["seek", "player:chrome:1", 60_000_000]])
  const missing = await seekPlayer(ports, "stale-player", 1)
  assert.equal(missing.reason, "missing-player")
  const unsupported = await seekPlayer(fakePorts({ ...session, players: [player({ capabilities: { ...player().capabilities, canSeek: false } })] }), "player:chrome:1", 1)
  assert.equal(unsupported.reason, "unsupported")
})
