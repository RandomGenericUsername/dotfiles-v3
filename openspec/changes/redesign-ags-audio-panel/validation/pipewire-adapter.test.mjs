import test from "node:test"
import assert from "node:assert/strict"
import { parsePipeWireGraph, projectPipeWireSession } from "../../../../dotfiles/config/ags/audio/adapters/pipewire/project-pipewire-session.ts"

const dump = [
  { id: 10, type: "PipeWire:Interface:Node", info: { props: { "media.class": "Audio/Sink", "node.description": "USB DAC", "node.name": "sink-name" } } },
  { id: 11, type: "PipeWire:Interface:Node", info: { props: { "media.class": "Audio/Source", "node.description": "USB microphone" } } },
  { id: 20, type: "PipeWire:Interface:Node", info: { props: {
    "media.class": "Stream/Output/Audio", "application.name": "Mozilla Firefox",
    "application.process.binary": "firefox", "application.process.id": "123",
    "application.icon-name": "firefox", "media.name": "AudioStream", "target.object": "sink-name",
  } } },
  { id: 21, type: "PipeWire:Interface:Node", info: { props: {
    "media.class": "Stream/Input/Audio", "application.name": "Video Conference",
    "application.process.binary": "conference", "application.process.id": "456",
  } } },
  { id: 30, type: "PipeWire:Interface:Link", info: {
    state: "active", props: { "link.output.node": "20", "link.input.node": "10" },
  } },
  { id: 31, type: "PipeWire:Interface:Link", info: {
    state: "paused", props: { "link.output.node": "20", "link.input.node": "99" },
  } },
  { id: 32, type: "PipeWire:Interface:Link", info: {
    state: "active", props: { "link.output.node": "11", "link.input.node": "21" },
  } },
]

test("PipeWire graph parser uses active stream-to-sink links and retains stream properties", () => {
  const graph = parsePipeWireGraph(JSON.stringify(dump))
  assert.equal(graph.streamEndpoint.get(20), 10)
  assert.equal(graph.streamEndpoint.get(21), 11)
  assert.equal(graph.nodeName.get(10), "USB DAC")
  assert.equal(graph.streamProperties.get(20)["application.name"], "Mozilla Firefox")
})

test("session projection normalizes IDs, app identity, gain and observed route without guessing intent", () => {
  const session = projectPipeWireSession({
    nodes: [
      { id: 10, name: "sink-name", "media-class": 2, description: "USB DAC", volume: 0.8, mute: false },
      { id: 11, "media-class": 1, description: "USB microphone", volume: 0.4, mute: true },
      { id: 20, name: "firefox-stream", "media-class": 4, description: "AudioStream", volume: 0.6, mute: false },
      { id: 21, "media-class": 3, description: "Conference Audio", volume: 0.2, mute: false },
    ],
    defaultSpeakerId: 10,
    defaultMicrophoneId: 11,
    graph: parsePipeWireGraph(JSON.stringify(dump)),
  })
  assert.equal(session.preferredOutputId, "10")
  assert.equal(session.preferredInputId, "11")
  assert.deepEqual(session.outputs[0], { id: "10", name: "USB DAC", available: true, volume: { level: 0.8, muted: false } })
  assert.equal(session.input?.id, "11")
  assert.equal(session.inputs.length, 1)
  assert.equal(session.apps[0].id, "firefox")
  assert.equal(session.apps[0].processId, 123)
  assert.equal(session.streams[0].id, "pipewire:20:20")
  assert.equal(session.streams[0].appId, "firefox")
  assert.equal(session.streams[0].endpointId, "10")
  assert.equal(session.streams[0].requestedEndpointId, "10")
  assert.equal(session.streams[0].direction, "output")
  assert.equal(session.streams[1].endpointId, "11")
  assert.equal(session.streams[1].direction, "input")
  assert.deepEqual(session.streams[0].routeIntent, { kind: "unknown" })
  assert.equal(session.players.length, 0)
})
