// Unit tests for lib/btop-conf.ts.
//   node tests/btop-conf.mjs
//
// Task 3.1: the parsed preset set matches btop's OWN `--default-config`
// output. btop is the authority for the presets string, so the test reads it
// from the binary rather than transcribing it.
import { spawnSync } from "node:child_process";
import {
  ALL_BOXES,
  parseBtopConf,
  parsePresets,
  parseShownBoxes,
  presetAt,
  presetBoxes,
  presetCaption,
} from "../lib/btop-conf.ts";

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

// ── parser unit cases ───────────────────────────────────────────────────────
check("preset 0 is all boxes", Object.keys(parsePresets("")[0].boxes).sort(), [...ALL_BOXES].sort());
const parsed = parsePresets("cpu:0:0,mem:0:1 net:0:2,proc:0:3");
check("one preset per group plus preset 0", parsed.length, 3);
check("preset 1 label", parsed[1].label, "Preset 1 — cpu:0:0,mem:0:1");
check("gpu mirrors cpu when absent", parsed[1].boxes.gpu, parsed[1].boxes.cpu);
check("preset 2 boxes", Object.keys(parsed[2].boxes).sort(), ["net", "proc"]);
check("shown boxes parse", parseShownBoxes("cpu mem net proc"), ["cpu", "mem", "net", "proc"]);

const conf = parseBtopConf(
  ['color_theme = "colors.btop.theme"', 'shown_boxes = "cpu mem net proc"', 'presets = "cpu:0:0 net:0:1"', "save_config_on_exit = false"].join("\n"),
);
check("conf color_theme", conf.color_theme, "colors.btop.theme");
check("conf shown", conf.shown_boxes, ["cpu", "mem", "net", "proc"]);
check("conf preset count", conf.presets.length, 3);
check("presetBoxes mirrors gpu onto cpu", presetBoxes(conf, 1), ["cpu", "gpu"]);
check("presetCaption", presetCaption(conf, 1), "cpu gpu");
check("presetAt falls back to 0", presetAt(conf, 99).index, 0);

// ── authority: btop's own --default-config ─────────────────────────────────
const btop = spawnSync("btop", ["--default-config"], { encoding: "utf8" });
if (btop.error || btop.status !== 0) {
  console.log("skip btop --default-config (btop not available)");
} else {
  const stock = parseBtopConf(btop.stdout);
  const groups = stock.presets_raw.trim().split(/\s+/).filter(Boolean);
  check("one parsed preset per stock group", stock.presets.length, groups.length + 1);
  check("stock preset 0 is all boxes", Object.keys(stock.presets[0].boxes).sort(), [...ALL_BOXES].sort());
  check("stock shown_boxes is non-empty", stock.shown_boxes.length > 0, true);
  console.log(`btop stock: ${stock.presets.length} presets, shown_boxes=${stock.shown_boxes.join(" ")}`);
}

if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log("btop-conf cases agree");
}
