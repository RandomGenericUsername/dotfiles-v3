#!/usr/bin/env node
// JS/TS runtime enforcement for the generated contracts.
//
// Compiles the GENERATED JSON Schemas with Ajv (2020-12) and validates the same
// fixtures as validate_py.py. Exit 0 only when every verdict is as expected.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const load = (name) => JSON.parse(readFileSync(join(HERE, "generated", name), "utf8"));
const ajv = new Ajv2020({ allErrors: true, strict: false });

const history = ajv.compile(load("history.schema.json"));
const events = ajv.compile(load("events.schema.json"));

const failures = [];

function check(validate, value, expected, label) {
  const ok = validate(value) === true;
  if (ok !== expected) {
    const detail = ok ? "" : ` (${(validate.errors ?? []).map((e) => `${e.instancePath || "<root>"}: ${e.message}`).join(" | ")})`;
    failures.push(`${label} expected=${expected ? "valid" : "invalid"} got=${ok ? "valid" : "invalid"}${detail}`);
  }
}

const lines = readFileSync(join(HERE, "fixtures", "history.good.jsonl"), "utf8").trim().split("\n");
lines.forEach((l, i) => check(history, JSON.parse(l), true, `history.good.jsonl:${i + 1}`));
const linesBad = readFileSync(join(HERE, "fixtures", "history.bad.jsonl"), "utf8").trim().split("\n");
linesBad.forEach((l, i) => check(history, JSON.parse(l), false, `history.bad.jsonl:${i + 1}`));

JSON.parse(readFileSync(join(HERE, "fixtures", "events.good.json"), "utf8")).forEach((e, i) =>
  check(events, e, true, `events.good.json:${i + 1}`),
);
JSON.parse(readFileSync(join(HERE, "fixtures", "events.bad.json"), "utf8")).forEach((e, i) =>
  check(events, e, false, `events.bad.json:${i + 1}`),
);

if (failures.length > 0) {
  console.log(`[ajv] FAIL (${failures.length} unexpected verdict(s))`);
  for (const f of failures) console.log(`  - ${f}`);
  process.exit(1);
}
console.log("[ajv] PASS: history + events fixtures match expected verdicts");
