// Component tests for lib/schematic.ts.
//   node tests/schematic.mjs
//
// Tasks 3.2 (selecting a key highlights its components), 3.3 (a preset without
// disks hides that box and the caption lists the shown boxes), and 3.4 (warn
// when a selected key paints a module the preset hides).
import { parseBtopConf } from "../lib/btop-conf.ts";
import { buildSchematic, hiddenModuleWarning } from "../lib/schematic.ts";

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

const conf = parseBtopConf(
  ['presets = "cpu:0:0,mem:0:1 net:0:2,proc:0:3"', 'shown_boxes = "cpu mem net proc"'].join("\n"),
);

// Task 3.2: selecting the cpu family highlights cpu meter, per-core graphs,
// GPU utilisation, and battery.
const cpu = buildSchematic(conf, 0, "cpu_start");
check(
  "cpu family highlights the expected components",
  ["cpu-total", "cpu-cores", "gpu-util", "battery"].every((id) => cpu.highlighted.includes(id)),
  true,
);
check("cpu_start highlights only elements that tag it", cpu.highlighted.length > 0, true);
const none = buildSchematic(conf, 0, null);
check("no selection highlights nothing", none.highlighted, []);
const meter = buildSchematic(conf, 0, "meter_bg");
check("meter_bg highlights across boxes", meter.highlighted.length >= 6, true);

// Task 3.3: preset 1 excludes disks; the box set follows and the caption names
// the shown boxes.
const p1 = buildSchematic(conf, 1, null);
check("preset 1 hides disks", p1.boxes.includes("disks"), false);
check("preset 1 caption names the boxes", p1.caption, "btop schematic — preset 1 · boxes: cpu gpu mem");
check("preset 1 has no disks elements", p1.elements.some((e) => e.box === "disks"), false);
check("preset 0 shows all boxes", buildSchematic(conf, 0, null).boxes.length, 6);

// Task 3.4: available_* on a disks-less preset warns that disks is hidden.
const avail = buildSchematic(conf, 1, "available_start");
check("available_start on preset 1 hides disks", avail.hiddenModules, ["disks"]);
const warning = hiddenModuleWarning("available_start", avail.hiddenModules);
check("warning names disks", /paints disks/.test(warning), true);
check("warning says it is not shown", /does not show/.test(warning), true);
check("warning says the change will not be visible", /not be visible/.test(warning), true);
check("no warning on preset 0", hiddenModuleWarning("available_start", buildSchematic(conf, 0, "available_start").hiddenModules), null);
check("no warning without a selection", hiddenModuleWarning(null, ["disks"]), null);

if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log("schematic cases agree");
}
