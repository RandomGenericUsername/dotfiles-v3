// Contract drift gate for the wallpaper selector's baked constants.
//
// Executes the machine definitions (`contracts/event-contract.json` and
// `.xml`) against the selector's baked core constants (same pattern as the
// ICME/hypr-pano drift tests): every literal the selector depends on must
// be a machine-definition value.
//
// Run with plain node via the existing runner:
//   node tests/event-contract-drift.mjs   (from the tool directory)

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import * as core from "../lib/event-bus-core.ts";

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

check("xml interface matches json", xmlInterfaceName(contractXml), contractJson.interface);
check("bus name", core.EVENTS_BUS_NAME, contractJson.well_known_name);
check("object path", core.EVENTS_OBJECT_PATH, contractJson.object_path);
check("interface", core.EVENTS_INTERFACE, contractJson.interface);
check("DomainEvent is a contract signal", contractJson.signals[core.DOMAIN_EVENT_SIGNAL] !== undefined, true);
check("JobsCleared is a contract signal", contractJson.signals[core.JOBS_CLEARED_SIGNAL] !== undefined, true);
check("DomainEvent in xml signals", xmlSignals.includes(core.DOMAIN_EVENT_SIGNAL), true);
check("JobsCleared in xml signals", xmlSignals.includes(core.JOBS_CLEARED_SIGNAL), true);
check("Control is a contract method", contractJson.methods[core.CONTROL_METHOD] !== undefined, true);
check("GetTopicState is a contract method", contractJson.methods[core.HYDRATION_METHOD] !== undefined, true);
check("Control in xml methods", xmlMethods.includes(core.CONTROL_METHOD), true);
check("GetTopicState in xml methods", xmlMethods.includes(core.HYDRATION_METHOD), true);

check("wallpaper.state is a contract topic", contractJson.topics[core.WALLPAPER_STATE_TOPIC] !== undefined, true);
check(
  "wallpaper.state payload keys",
  Object.keys(contractJson.topics["wallpaper.state"].payload).sort(),
  ["state", "trigger", "wallpaper_hash"],
);
check("wallpaper.state optional", contractJson.topics["wallpaper.state"].optional, ["trigger"]);
check("wallpaper.state enum", contractJson.topics["wallpaper.state"].enum.state, [
  "applying",
  "visible",
  "done",
  "error",
]);
check("wallpaper.state trigger enum", contractJson.topics["wallpaper.state"].enum.trigger, [
  "set",
  "regenerate",
  "reconcile",
  "reactive",
]);

if (failures > 0) {
  console.error(`${failures} failure(s)`);
  process.exit(1);
}
console.log("drift: all green");
