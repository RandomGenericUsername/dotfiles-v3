// Unit tests for lib/key-map.ts and the generated artifact.
//   node tests/key-map.mjs
//
// Task 2.3: the studio loads the artifact; a sample key (`used`) matches the
// artifact. Also pins the generated TS module equal to the canonical JSON.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import {
  KEY_WIDGET_MAP,
  hasCompleteCoverage,
  isUnreferenced,
  modulesFor,
  sitesFor,
} from "../lib/key-map.ts";
import { KEY_WIDGETS } from "../lib/key-widgets.generated.ts";
import { THEME_KEYS } from "../lib/theme-keys.ts";

const here = dirname(fileURLToPath(import.meta.url));
const json = JSON.parse(readFileSync(join(here, "..", "lib", "key_widgets.json"), "utf8"));

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

check("TS module equals canonical JSON", KEY_WIDGETS, json);
check("complete 48-key coverage", hasCompleteCoverage(), true);
check("map has 48 entries", Object.keys(KEY_WIDGET_MAP.keys).length, 48);
check(
  "every key in the map is a real theme key",
  Object.keys(KEY_WIDGET_MAP.keys).every((k) => THEME_KEYS.includes(k)),
  true,
);

// Task 2.3 sample: the `used` gradient family (`used_start`) paints
// cpu, disks, gpu, mem (Mem::draw paints mem AND disks; used also appears in
// Cpu/Gpu gradient args). `used` itself is a gradient FAMILY, not a theme key.
check("used_start modules", modulesFor("used_start"), ["cpu", "disks", "gpu", "mem"]);
check("download_start is net", modulesFor("download_start"), ["net"]);
check("cpu_box is its own box", modulesFor("cpu_box"), ["cpu"]);
check("proc_box is its own box", modulesFor("proc_box"), ["proc"]);
check("main_bg is unreferenced", isUnreferenced("main_bg"), true);
check("main_bg paints all boxes", modulesFor("main_bg").length, 6);
check("used_start sites cite the family", sitesFor("used_start"), ["gradient of used"]);
check("unknown key is empty", modulesFor("nope"), []);

if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log("key-map cases agree");
}
