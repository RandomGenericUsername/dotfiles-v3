// Contract runner: asserts lib/substitute.ts produces the shared fixtures'
// expected outputs. Run with plain node (type stripping handles the .ts
// import): `node tests/contract.mjs` from this directory.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { substitute } from "../lib/substitute.ts";

const root = dirname(fileURLToPath(import.meta.url));
const fixtures = JSON.parse(
  readFileSync(join(root, "fixtures", "substitution.json"), "utf-8"),
);

let failures = 0;
for (const kase of fixtures.cases) {
  const actual = substitute(kase.svg, kase.mappings, kase.scheme);
  if (actual !== kase.expected) {
    failures += 1;
    console.error(`FAIL ${kase.name}\n  expected: ${kase.expected}\n  actual:   ${actual}`);
  } else {
    console.log(`ok ${kase.name}`);
  }
}
if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log(`${fixtures.cases.length} cases agree`);
}
