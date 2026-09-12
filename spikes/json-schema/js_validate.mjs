#!/usr/bin/env node
// Neutral-schema validator (JS / Ajv 2020-12).
//
// Reads the SAME shared case corpus as python_validate.py and validates every
// case against the SAME JSON Schema document with the maintained ajv library.
// Exits non-zero if any case verdict disagrees with the corpus's `expected`.
// Writes a machine-readable verdict map so the conformance script can diff
// this validator's answers against the Python validator's.

import { readFileSync, writeFileSync } from "node:fs";
import Ajv2020 from "ajv/dist/2020.js";

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 2) {
    const key = argv[i].replace(/^--/, "");
    args[key] = argv[i + 1];
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
for (const required of ["schema", "cases", "out"]) {
  if (!args[required]) {
    console.error(`missing --${required}`);
    process.exit(2);
  }
}

const schema = JSON.parse(readFileSync(args.schema, "utf8"));
const corpus = JSON.parse(readFileSync(args.cases, "utf8"));

const ajv = new Ajv2020({ allErrors: true, allowUnionTypes: true, strict: false });
const validate = ajv.compile(schema);

const verdicts = {};
const expected = {};
const mismatches = [];

for (const testCase of corpus.cases) {
  const cid = testCase.id;
  const exp = Boolean(testCase.expected);
  const valid = validate(testCase.line) === true;
  verdicts[cid] = valid;
  expected[cid] = exp;
  const status = valid === exp ? "PASS" : "EXPECTED-MISMATCH";
  let detail = "";
  if (!valid) {
    detail =
      "  " +
      (validate.errors ?? [])
        .slice(0, 3)
        .map((e) => `${e.instancePath || "<root>"}: ${e.message}`)
        .join(" | ");
  }
  console.log(`[ajv]              ${status.padEnd(18)} ${cid}${detail}`);
  if (valid !== exp) {
    mismatches.push({ id: cid, schema_valid: valid, expected: exp, why: testCase.why ?? "" });
  }
}

const out = {
  validator: "ajv",
  ajv_version: schema.ajvVersion ?? null,
  schema: args.schema,
  cases: args.cases,
  verdicts,
  expected,
  mismatches,
};
writeFileSync(args.out, JSON.stringify(out, null, 2) + "\n", "utf8");

if (mismatches.length > 0) {
  console.log(`[ajv]              ${mismatches.length} expected-verdict mismatch(es)`);
  process.exit(1);
}
console.log(`[ajv]              all ${Object.keys(verdicts).length} cases match expected`);
