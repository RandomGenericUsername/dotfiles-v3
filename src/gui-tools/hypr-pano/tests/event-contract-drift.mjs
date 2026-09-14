// Cross-language contract drift + clipboard consumer core for hypr-pano.
//
// Executes the machine definitions (`contracts/event-contract.json` and
// `.xml`) against this tool's baked constants, then exercises the
// subscribe-before-read hydration state machine with a scripted fake
// transport (no live bus) and the pure clipboard item helpers.
//
// Run with the tool's Makefile:  make -C src/gui-tools/hypr-pano test

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as core from "../lib/event-bus-core.ts";
import * as clip from "../lib/clipboard-types.ts";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..", "..", "..");
const contractJson = JSON.parse(
  readFileSync(join(repoRoot, "contracts", "event-contract.json"), "utf-8"),
);
const contractXml = readFileSync(
  join(repoRoot, "contracts", "event-contract.xml"),
  "utf-8",
);

let failures = 0;
function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    failures += 1;
    console.error(`FAIL ${name}\n  expected: ${e}\n  actual:   ${a}`);
  } else {
    console.log(`ok ${name}`);
  }
}

// ── Drift: every baked constant is a machine-definition value ────────────

check("bus name", core.EVENTS_BUS_NAME, contractJson.well_known_name);
check("object path", core.EVENTS_OBJECT_PATH, contractJson.object_path);
check("interface", core.EVENTS_INTERFACE, contractJson.interface);
check("DomainEvent signal", contractJson.signals[core.DOMAIN_EVENT_SIGNAL] !== undefined, true);
check("JobsCleared signal", contractJson.signals[core.JOBS_CLEARED_SIGNAL] !== undefined, true);
check("Control method", contractJson.methods[core.CONTROL_METHOD] !== undefined, true);
check("GetTopicState method", contractJson.methods[core.HYDRATION_METHOD] !== undefined, true);
check(
  "GetTopicState returns reserved _epoch/_seq",
  contractJson.methods.GetTopicState.out,
  ["state:a{sv}"],
);

check(
  "clipboard.update is a contract topic",
  contractJson.topics[core.CLIPBOARD_UPDATE_TOPIC] !== undefined,
  true,
);
check(
  "clipboard.state is a contract topic",
  contractJson.topics[core.CLIPBOARD_STATE_TOPIC] !== undefined,
  true,
);
check(
  "clipboard.update payload keys",
  Object.keys(contractJson.topics["clipboard.update"].payload).sort(),
  ["hash", "path", "preview", "type"],
);
check(
  "clipboard.update type enum",
  contractJson.topics["clipboard.update"].enum.type,
  ["text", "image", "link", "code", "color", "emoji"],
);
check(
  "clipboard.state payload keys",
  Object.keys(contractJson.topics["clipboard.state"].payload).sort(),
  ["job_id", "state"],
);
check(
  "clipboard.state enum",
  contractJson.topics["clipboard.state"].enum.state,
  ["idle", "running", "paused"],
);
check("xml declares the hub interface", contractXml.includes(core.EVENTS_INTERFACE), true);

// ── Subscribe-before-read hydration state machine (fake transport) ───────

function fakeTransport(states) {
  const calls = [];
  const signals = { onDomainEvent: null, onJobsCleared: null, onHubRestart: null };
  let state = { ...states };
  const transport = {
    startSignals(onDomainEvent, onJobsCleared, onHubRestart) {
      calls.push("startSignals");
      signals.onDomainEvent = onDomainEvent;
      signals.onJobsCleared = onJobsCleared;
      signals.onHubRestart = onHubRestart;
    },
    getTopicState(topic) {
      calls.push(`getTopicState:${topic}`);
      return topic in state ? state[topic] : null;
    },
    control(jobId, action) {
      calls.push(`control:${jobId}:${action}`);
    },
  };
  return { transport, calls, signals, setState: (next) => { state = { ...next }; } };
}

// Hydration on subscribe delivers the last payload immediately.
{
  const fake = fakeTransport({
    "clipboard.state": { state: "paused", job_id: "job-9", _epoch: 3, _seq: 12 },
  });
  const bus = new core.DomainEventBusCore(fake.transport);
  const seen = [];
  bus.subscribe(core.CLIPBOARD_STATE_TOPIC, (_t, payload) => seen.push(payload));
  check("subscribe starts signals before hydrating", fake.calls[0], "startSignals");
  check("subscribe hydrates", fake.calls[1], "getTopicState:clipboard.state");
  check("hydrated payload delivered", seen, [{ state: "paused", job_id: "job-9" }]);
  check("hydrated pair recorded", bus.hydratedPair("clipboard.state"), [3, 12]);
}

// A stale (epoch, seq) signal is dropped; a newer one is delivered once.
{
  const fake = fakeTransport({
    "clipboard.update": { type: "text", hash: "h0", path: "", preview: "old", _epoch: 2, _seq: 5 },
  });
  const bus = new core.DomainEventBusCore(fake.transport);
  const seen = [];
  bus.subscribe(core.CLIPBOARD_UPDATE_TOPIC, (_t, payload) => seen.push(payload.hash));
  fake.signals.onDomainEvent([
    "clipboard.update",
    ":1.1",
    4, // seq <= baseline 5 → stale
    2,
    { type: "text", hash: "stale", path: "", preview: "x" },
  ]);
  check("stale signal dropped", seen, ["h0"]);
  fake.signals.onDomainEvent([
    "clipboard.update",
    ":1.1",
    6,
    2,
    { type: "text", hash: "fresh", path: "", preview: "y" },
  ]);
  check("newer signal delivered", seen, ["h0", "fresh"]);
  check("baseline advanced", bus.hydratedPair("clipboard.update"), [2, 6]);
}

// Control routes through the transport (the single control path).
{
  const fake = fakeTransport({});
  const bus = new core.DomainEventBusCore(fake.transport);
  bus.subscribe(core.CLIPBOARD_STATE_TOPIC, () => {});
  bus.control("job-9", "pause");
  check("control issued", fake.calls.includes("control:job-9:pause"), true);
}

// ── Pure clipboard item helpers ──────────────────────────────────────────

check(
  "parseHistory skips malformed records",
  clip.parseHistory(JSON.stringify({ version: 1, items: [{ hash: "a", kind: "text", timestamp: 2 }, 7] }))
    .map((item) => item.hash),
  ["a"],
);
check("parseHistory tolerates corrupt JSON", clip.parseHistory("{ nope"), []);
check(
  "parseHistory sorts newest first",
  clip
    .parseHistory(
      JSON.stringify({
        version: 1,
        items: [
          { hash: "old", kind: "text", timestamp: 1 },
          { hash: "new", kind: "text", timestamp: 5 },
        ],
      }),
    )
    .map((item) => item.hash),
  ["new", "old"],
);
const imageItem = clip.itemFromPayload({ type: "image", hash: "h", path: "/tmp/i.png", preview: "" });
check("itemFromPayload maps an image", [imageItem.kind, imageItem.hash, imageItem.text, imageItem.path], ["image", "h", null, "/tmp/i.png"]);
check("unknown kind falls back to text", clip.itemFromPayload({ type: "bogus", hash: "h", path: "", preview: "p" }).kind, "text");
check("matchesQuery is case-insensitive", clip.matchesQuery({ hash: "h", kind: "text", timestamp: 1, favorite: false, text: "Hello World", path: null }, "hello"), true);
check("matchesQuery excludes non-matches", clip.matchesQuery({ hash: "h", kind: "text", timestamp: 1, favorite: false, text: "Hello", path: null }, "zzz"), false);
check("kindIcon differs per kind", clip.kindIcon("image") !== clip.kindIcon("link"), true);

if (failures > 0) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
console.log("\nall checks passed");
