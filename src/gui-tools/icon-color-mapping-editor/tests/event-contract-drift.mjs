// Cross-language contract drift + bar hydration core (Phase 5 follow-up).
//
// Executes the machine definitions (`contracts/event-contract.json` and
// `.xml`) against the GJS/bar and ICME baked constants, then exercises the
// bar's subscribe-before-read hydration state machine with a scripted fake
// transport (no live bus). This replaces the Python textual literal scan for
// these two consumers with an executed, import-based gate.
//
// Run with plain node via the existing runner:
//   node tests/event-contract-drift.mjs   (from the tool directory)
//
// Cross-package note: the bar has no node test runner of its own, so its
// pure core (`dotfiles/config/ags/lib/event-bus-core.ts`) is imported here and
// executed by the existing ICME node runner instead of inventing a second one.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as bar from "../../../../dotfiles/config/ags/lib/event-bus-core.ts";
import * as icme from "../lib/event-contract.ts";
import * as icmeConsumer from "../lib/event-bus-core.ts";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..", "..", "..");
const contractJson = JSON.parse(
  readFileSync(join(repoRoot, "contracts", "event-contract.json"), "utf-8"),
);
const contractXml = readFileSync(join(repoRoot, "contracts", "event-contract.xml"), "utf-8");

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

function xmlInterfaceName(xml) {
  const match = xml.match(/<interface\s+name="([^"]+)"/);
  return match ? match[1] : null;
}

function xmlTopLevelNames(xml, tag) {
  const names = [];
  const re = new RegExp(`<${tag}\\s+name="([^"]+)"`, "g");
  let match;
  while ((match = re.exec(xml)) !== null) names.push(match[1]);
  return names;
}

const xmlMethods = xmlTopLevelNames(contractXml, "method");
const xmlSignals = xmlTopLevelNames(contractXml, "signal");

// ── Drift: every baked constant is a machine-definition value ────────────

check("xml interface matches json", xmlInterfaceName(contractXml), contractJson.interface);

for (const [label, mod] of [
  ["bar", bar],
  ["icme", icme],
]) {
  check(`${label} bus name`, mod.EVENTS_BUS_NAME, contractJson.well_known_name);
  check(`${label} object path`, mod.EVENTS_OBJECT_PATH, contractJson.object_path);
  check(`${label} interface`, mod.EVENTS_INTERFACE, contractJson.interface);
}

check("bar DomainEvent signal is a contract signal", contractJson.signals[bar.DOMAIN_EVENT_SIGNAL] !== undefined, true);
check("bar JobsCleared signal is a contract signal", contractJson.signals[bar.JOBS_CLEARED_SIGNAL] !== undefined, true);
check("bar DomainEvent in xml signals", xmlSignals.includes(bar.DOMAIN_EVENT_SIGNAL), true);
check("bar JobsCleared in xml signals", xmlSignals.includes(bar.JOBS_CLEARED_SIGNAL), true);
check("bar DomainEvent carries topic/seq/epoch", contractJson.signals.DomainEvent.slice(0, 4), ["topic:s", "producer:s", "seq:u", "epoch:u"]);
check("bar Control is a contract method", contractJson.methods[bar.CONTROL_METHOD] !== undefined, true);
check("bar GetTopicState is a contract method", contractJson.methods[bar.HYDRATION_METHOD] !== undefined, true);
check("bar Control in xml methods", xmlMethods.includes(bar.CONTROL_METHOD), true);
check("bar GetTopicState in xml methods", xmlMethods.includes(bar.HYDRATION_METHOD), true);
check("bar hydration returns reserved _epoch/_seq", contractJson.methods.GetTopicState.out, ["state:a{sv}"]);

check("bar capture.state is a contract topic", contractJson.topics[bar.CAPTURE_STATE_TOPIC] !== undefined, true);
check("bar speedtest.finished is a contract topic", contractJson.topics[bar.SPEEDTEST_FINISHED_TOPIC] !== undefined, true);
check("capture.state payload keys", Object.keys(contractJson.topics["capture.state"].payload).sort(), ["elapsed_seconds", "state"]);
check("capture.state enum", contractJson.topics["capture.state"].enum.state, ["idle", "recording", "paused"]);

check("icme Emit is a contract method", contractJson.methods[icme.EMIT_METHOD] !== undefined, true);
check("icme Emit in xml methods", xmlMethods.includes(icme.EMIT_METHOD), true);
check("icme.saved is a contract topic", contractJson.topics[icme.ICME_SAVED_TOPIC] !== undefined, true);
check("icme.saved payload is {path:s}", contractJson.topics["icme.saved"].payload, { path: "s" });

// ── Drift: ICME's domain-event CONSUMER constants ────────────────────────
// The editor consumes `wallpaper.state` for the live palette refresh, so its
// copied consumer core must agree with the same machine definition.
check("icme consumer bus name", icmeConsumer.EVENTS_BUS_NAME, contractJson.well_known_name);
check("icme consumer object path", icmeConsumer.EVENTS_OBJECT_PATH, contractJson.object_path);
check("icme consumer interface", icmeConsumer.EVENTS_INTERFACE, contractJson.interface);
check("icme consumer DomainEvent signal is a contract signal", contractJson.signals[icmeConsumer.DOMAIN_EVENT_SIGNAL] !== undefined, true);
check("icme consumer DomainEvent in xml signals", xmlSignals.includes(icmeConsumer.DOMAIN_EVENT_SIGNAL), true);
check("icme consumer JobsCleared signal is a contract signal", contractJson.signals[icmeConsumer.JOBS_CLEARED_SIGNAL] !== undefined, true);
check("icme consumer Control is a contract method", contractJson.methods[icmeConsumer.CONTROL_METHOD] !== undefined, true);
check("icme consumer GetTopicState is a contract method", contractJson.methods[icmeConsumer.HYDRATION_METHOD] !== undefined, true);
check("icme consumer GetTopicState in xml methods", xmlMethods.includes(icmeConsumer.HYDRATION_METHOD), true);
check("icme consumer wallpaper.state is a contract topic", contractJson.topics[icmeConsumer.WALLPAPER_STATE_TOPIC] !== undefined, true);
check("wallpaper.state payload keys", Object.keys(contractJson.topics["wallpaper.state"].payload).sort(), ["state", "trigger", "wallpaper_hash"]);
check("wallpaper.state optional", contractJson.topics["wallpaper.state"].optional, ["trigger"]);
check("wallpaper.state enum", contractJson.topics["wallpaper.state"].enum.state, ["applying", "visible", "done", "error"]);
check("wallpaper.state trigger enum", contractJson.topics["wallpaper.state"].enum.trigger, ["set", "regenerate", "reconcile", "reactive"]);

// ── Bar hydration core (scripted fake transport, no bus) ─────────────────

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
  return {
    transport,
    calls,
    signals,
    setState(next) {
      state = { ...next };
    },
  };
}

// (1) subscribe installs signal match rules BEFORE reading topic state.
{
  const fake = fakeTransport({});
  const bus = new bar.DomainEventBusCore(fake.transport);
  bus.subscribe("capture.state", () => {});
  check("subscribe-before-read order", fake.calls, ["startSignals", "getTopicState:capture.state"]);
}

// (2) hydration delivers the current payload immediately (bar starts mid-recording).
{
  const fake = fakeTransport({
    "capture.state": { _epoch: 4, _seq: 7, state: "recording", elapsed_seconds: 12, job_id: "job-1" },
  });
  const bus = new bar.DomainEventBusCore(fake.transport);
  const seen = [];
  bus.subscribe("capture.state", (topic, payload) => seen.push([topic, payload]));
  check("hydration delivers payload", seen.length, 1);
  check("hydration payload topic", seen[0][0], "capture.state");
  check("hydration payload state", seen[0][1].state, "recording");
  check("hydration payload elapsed", seen[0][1].elapsed_seconds, 12);
  check("hydrated pair", bus.hydratedPair("capture.state"), [4, 7]);

  // (3) a signal at or below the hydrated pair is dropped; above is delivered.
  const dispatch = (topic, seq, epoch, payload) => fake.signals.onDomainEvent([topic, "producer", seq, epoch, payload]);
  dispatch("capture.state", 7, 4, { state: "paused", elapsed_seconds: 99 });
  check("stale equal pair dropped", seen.length, 1);
  dispatch("capture.state", 6, 4, { state: "paused", elapsed_seconds: 99 });
  check("stale lower seq dropped", seen.length, 1);
  dispatch("capture.state", 8, 4, { state: "paused", elapsed_seconds: 13 });
  check("newer pair delivered", seen.length, 2);
  check("newer payload state", seen[1][1].state, "paused");
  check("baseline advanced", bus.hydratedPair("capture.state"), [4, 8]);

  // (4) an epoch bump wins even with a lower seq (seq resets per epoch).
  dispatch("capture.state", 1, 5, { state: "recording", elapsed_seconds: 1 });
  check("epoch bump wins over lower seq", seen.length, 3);
  check("epoch bump baseline", bus.hydratedPair("capture.state"), [5, 1]);

  // (5) JobsCleared resets the UI then re-hydrates (stale epoch ignored).
  let restarts = 0;
  bus.onRestart(() => {
    restarts += 1;
  });
  fake.setState({ "capture.state": { _epoch: 6, _seq: 2, state: "recording", elapsed_seconds: 3 } });
  fake.signals.onJobsCleared([5]); // not newer than lastEpoch 5 -> ignored
  check("duplicate JobsCleared ignored", restarts, 0);
  fake.signals.onJobsCleared([6]);
  check("JobsCleared notifies restart", restarts, 1);
  check("JobsCleared re-hydrates current state", seen[seen.length - 1][1].state, "recording");
  check("JobsCleared baseline", bus.hydratedPair("capture.state"), [6, 2]);
}

// (6) an empty/absent GetTopicState delivers nothing and baselines (0,0).
{
  const fake = fakeTransport({});
  const bus = new bar.DomainEventBusCore(fake.transport);
  const seen = [];
  bus.subscribe("capture.state", (topic, payload) => seen.push([topic, payload]));
  check("absent state delivers nothing", seen.length, 0);
  check("absent state baseline", bus.hydratedPair("capture.state"), [0, 0]);
}

// (7) the NameOwnerChanged fallback resets and re-hydrates like JobsCleared.
{
  const fake = fakeTransport({
    "capture.state": { _epoch: 1, _seq: 1, state: "recording", elapsed_seconds: 5 },
  });
  const bus = new bar.DomainEventBusCore(fake.transport);
  const seen = [];
  let restarts = 0;
  bus.subscribe("capture.state", (topic, payload) => seen.push(payload.state));
  bus.onRestart(() => {
    restarts += 1;
  });
  fake.setState({ "capture.state": { _epoch: 2, _seq: 0, state: "idle", elapsed_seconds: 0 } });
  fake.signals.onHubRestart();
  check("NameOwnerChanged notifies restart", restarts, 1);
  check("NameOwnerChanged re-hydrates", seen[seen.length - 1], "idle");
}

// (8) parseTopicState splits reserved members and coerces wire values.
check(
  "parseTopicState splits reserved",
  bar.parseTopicState({ _epoch: 9, _seq: 3, state: "idle", elapsed_seconds: 0 }),
  { epoch: 9, seq: 3, payload: { state: "idle", elapsed_seconds: 0 } },
);
check("asUint floors positive", bar.asUint(3.7), 3);
check("asUint rejects negatives", bar.asUint(-1), 0);
check("isNewer epoch beats seq", bar.isNewer([4, 9], 5, 1), true);
check("isNewer equal is stale", bar.isNewer([4, 9], 4, 9), false);

// ── ICME consumer core (same copied state machine, wallpaper.state) ──────
{
  const fake = fakeTransport({});
  const bus = new icmeConsumer.DomainEventBusCore(fake.transport);
  bus.subscribe("wallpaper.state", () => {});
  check(
    "icme subscribe-before-read order",
    fake.calls,
    ["startSignals", "getTopicState:wallpaper.state"],
  );
}
{
  const fake = fakeTransport({
    "wallpaper.state": { _epoch: 2, _seq: 1, state: "done", wallpaper_hash: "abc" },
  });
  const bus = new icmeConsumer.DomainEventBusCore(fake.transport);
  const seen = [];
  bus.subscribe("wallpaper.state", (topic, payload) => seen.push([topic, payload]));
  check("icme hydration delivers wallpaper.state", seen.length, 1);
  check("icme hydrated pair", bus.hydratedPair("wallpaper.state"), [2, 1]);
  const dispatch = (topic, seq, epoch, payload) =>
    fake.signals.onDomainEvent([topic, "producer", seq, epoch, payload]);
  dispatch("wallpaper.state", 1, 2, { state: "error", wallpaper_hash: "" });
  check("icme stale wallpaper.state dropped", seen.length, 1);
  dispatch("wallpaper.state", 2, 2, { state: "done", wallpaper_hash: "def" });
  check("icme newer wallpaper.state delivered", seen.length, 2);
  check("icme newer state payload", seen[1][1].state, "done");
}

if (failures > 0) {
  console.error(`${failures} assertion(s) failed`);
  process.exitCode = 1;
} else {
  console.log("event-contract drift + bar hydration agree");
}
