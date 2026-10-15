// Component tests for lib/targets.ts.
//   node tests/targets.mjs
//
// Task 7.1: each target names its resolved path (component test). Task 8.2:
// the generated theme is fork-only and the Installed target warns for it.
import {
  actionLabel,
  divergenceCaveat,
  generatedInstalledWarning,
  mustFork,
  resolvedPath,
  targetHint,
} from "../lib/targets.ts";

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

const ctx = { repoRoot: "/repo", installDir: "/install" };
const authored = { id: "t1", name: "btop-dusk", kind: "authored", active: true, map: {} };
const generated = { id: "g", name: "colors.btop", kind: "generated", active: false, map: {} };

check("repo authored path", resolvedPath(authored, "repo", ctx), "/repo/dotfiles/assets/btop-themes/btop-dusk.theme");
check("repo generated path", resolvedPath(generated, "repo", ctx), "/repo/dotfiles/config/btop/theme-map.yaml");
check("installed authored path", resolvedPath(authored, "installed", ctx), "/install/config/btop/themes/btop-dusk.theme");
check("installed generated path is the pointer", resolvedPath(generated, "installed", ctx), "/install/config/btop/themes/colors.btop.theme (pointer)");

check("repo action label", actionLabel("repo"), "Save to repo");
check("installed action label", actionLabel("installed"), "Save to installed");
check("repo hint mentions bootstrap", /bootstrap/.test(targetHint("repo")), true);
check("installed hint mentions drift", /Drifts from the repo/.test(targetHint("installed")), true);
check("installed caveat warns of divergence", /drifts from the repo/.test(divergenceCaveat("installed")), true);
check("repo has no divergence caveat", divergenceCaveat("repo"), null);

check("generated must be forked", mustFork(generated), true);
check("authored need not be forked", mustFork(authored), false);
check("installed generated warns", /palette-linked pointer/.test(generatedInstalledWarning(generated, "installed")), true);
check("repo generated does not warn", generatedInstalledWarning(generated, "repo"), null);
check("installed authored does not warn", generatedInstalledWarning(authored, "installed"), null);

if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log("targets cases agree");
}
