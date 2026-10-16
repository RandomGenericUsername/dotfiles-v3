// Drift-guard tests for the generated key→widget map.
//   node tests/key-widgets-verify.mjs
//
// Task 2.2: the verifier passes on the committed artifact and fails when a
// module is perturbed (i.e. when the artifact drifts from the btop source).
import { spawnSync } from "node:child_process";
import { copyFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const tools = join(here, "..", "tools");
const artifact = join(here, "..", "lib", "key_widgets.json");
const draw = join(tools, "btop_draw.v1.4.7.cpp");
const theme = join(tools, "btop_theme.cpp");
const generator = join(tools, "key_widgets.py");

let failures = 0;
function check(name, condition, detail = "") {
  if (condition) {
    console.log(`ok ${name}`);
  } else {
    failures += 1;
    console.error(`FAIL ${name}${detail ? `\n  ${detail}` : ""}`);
  }
}

function verify(artifactPath) {
  return spawnSync("python3", [generator, draw, theme, artifactPath, "--verify"], {
    encoding: "utf8",
  });
}

const clean = verify(artifact);
check("verifier passes on the committed artifact", clean.status === 0, clean.stdout + clean.stderr);
check("verifier reports the 48-key count", /48 keys/.test(clean.stdout), clean.stdout);

const tmp = mkdtempSync(join(tmpdir(), "kw-verify-"));
try {
  const perturbed = join(tmp, "key_widgets.json");
  copyFileSync(artifact, perturbed);
  const data = JSON.parse(readFileSync(perturbed, "utf8"));
  data.keys.used_start.modules = ["net"]; // a deliberately wrong module
  writeFileSync(perturbed, JSON.stringify(data, null, 2));
  const drifted = verify(perturbed);
  check("verifier fails on a perturbed module", drifted.status !== 0, drifted.stdout + drifted.stderr);
  check("verifier names the drift", /drifted/.test(drifted.stdout + drifted.stderr), drifted.stdout + drifted.stderr);
} finally {
  rmSync(tmp, { recursive: true, force: true });
}

if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log("key-widgets drift-guard cases agree");
}
