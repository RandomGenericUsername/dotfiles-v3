// End-to-end-ish smoke for ICME `icme.saved` (Phase 5, 5-4 follow-up).
//
// No live bus: the hub `Emit` call is mocked at the transport seam and the
// published topic/payload shape is asserted against the contract. This also
// pins that `EditorWindow.save()` is wired to the helper (structural check,
// since the GTK window cannot be imported under plain node).
//
//   node tests/icme-saved-smoke.mjs   (from the tool directory)

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  EMIT_METHOD,
  EVENTS_BUS_NAME,
  EVENTS_INTERFACE,
  ICME_SAVED_TOPIC,
  buildIcmeSavedEmit,
  publishIcmeSavedVia,
} from "../lib/event-contract.ts";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, "..", "..", "..", "..");
const contract = JSON.parse(
  readFileSync(join(repoRoot, "contracts", "event-contract.json"), "utf-8"),
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

// The emit shape is the contract topic + `{ path }` payload.
check("topic is icme.saved", ICME_SAVED_TOPIC, "icme.saved");
check("build emit topic", buildIcmeSavedEmit("/x/icons.yaml").topic, "icme.saved");
check("build emit payload", buildIcmeSavedEmit("/x/icons.yaml").payload, { path: "/x/icons.yaml" });
check("contract topic payload is {path:s}", contract.topics[ICME_SAVED_TOPIC].payload, { path: "s" });
check("Emit method is the contract method", contract.methods[EMIT_METHOD] !== undefined, true);
check("transport targets the hub", [EVENTS_BUS_NAME, EVENTS_INTERFACE], ["org.dotfiles.Events", "org.dotfiles.Events1"]);

// Mocked bus: a successful save publishes exactly one correct event.
{
  const calls = [];
  const bus = { emit(topic, payload) { calls.push([topic, payload]); } };
  publishIcmeSavedVia(bus, "/home/u/.config/dotfiles/icon-mappings.yaml");
  check("one emit on save", calls.length, 1);
  check("emit topic", calls[0][0], "icme.saved");
  check("emit payload", calls[0][1], { path: "/home/u/.config/dotfiles/icon-mappings.yaml" });
}

// An empty path is a no-op (no event published).
{
  const calls = [];
  publishIcmeSavedVia({ emit(topic, payload) { calls.push([topic, payload]); } }, "");
  check("empty path publishes nothing", calls.length, 0);
}

// EditorWindow.save() must call the helper with the saved manifest path.
{
  const source = readFileSync(join(here, "..", "ui", "EditorWindow.tsx"), "utf-8");
  check("EditorWindow.save publishes on save", source.includes("publishIcmeSaved(next.iconsYaml)"), true);
}

if (failures > 0) {
  console.error(`${failures} assertion(s) failed`);
  process.exitCode = 1;
} else {
  console.log("icme.saved smoke agrees");
}
