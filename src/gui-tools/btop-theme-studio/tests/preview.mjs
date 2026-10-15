// Component tests for lib/preview.ts.
//   node tests/preview.mjs
//
// Task 3.5: the load control, fixed fill, and backdrop toggle each change the
// schematic appearance without altering any theme colour.
import {
  DEFAULT_CONTROLS,
  FIXED_FILL_LEVELS,
  NEUTRAL_BACKDROP,
  backdropColour,
  meterFill,
  previewAppearance,
} from "../lib/preview.ts";

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

check("fixed fill levels", FIXED_FILL_LEVELS, [0, 25, 50, 100]);
check("default load", DEFAULT_CONTROLS.load, 35);
check("default has no fixed fill", DEFAULT_CONTROLS.fixedFill, null);

// Load control.
check("load sets meter level", meterFill({ load: 20, fixedFill: null, backdrop: "theme" }, 20), 20);
check("load clamps high", meterFill({ load: 140, fixedFill: null, backdrop: "theme" }, 140), 100);
check("load clamps low", meterFill({ load: -5, fixedFill: null, backdrop: "theme" }, -5), 0);

// Fixed fill overrides the load control.
check("fixed 0 wins", meterFill({ load: 80, fixedFill: 0, backdrop: "theme" }, 80), 0);
check("fixed 25 wins", meterFill({ load: 80, fixedFill: 25, backdrop: "theme" }, 80), 25);
check("fixed 100 wins", meterFill({ load: 10, fixedFill: 100, backdrop: "theme" }, 10), 100);

// Backdrop toggle.
check("theme backdrop", backdropColour({ load: 35, fixedFill: null, backdrop: "theme" }, "#0b0b1a"), "#0b0b1a");
check("neutral backdrop", backdropColour({ load: 35, fixedFill: null, backdrop: "neutral" }, "#0b0b1a"), NEUTRAL_BACKDROP);

// Each control changes the appearance.
const themeBg = "#0b0b1a";
check("load changes appearance", previewAppearance({ load: 20, fixedFill: null, backdrop: "theme" }, themeBg), { fill: 20, backdrop: themeBg });
check("fixed fill changes appearance", previewAppearance({ load: 20, fixedFill: 50, backdrop: "theme" }, themeBg), { fill: 50, backdrop: themeBg });
check("backdrop changes appearance", previewAppearance({ load: 20, fixedFill: null, backdrop: "neutral" }, themeBg), { fill: 20, backdrop: NEUTRAL_BACKDROP });

// Controls never touch a theme colour: the helpers take no map, and the theme
// background is returned unchanged for the theme backdrop.
const map = Object.freeze({ main_bg: themeBg, meter_bg: "#575660" });
const snapshot = JSON.stringify(map);
previewAppearance({ load: 0, fixedFill: 100, backdrop: "neutral" }, map.main_bg);
check("theme map unchanged by preview controls", JSON.stringify(map), snapshot);
check("theme backdrop returns the theme colour verbatim", backdropColour({ load: 1, fixedFill: null, backdrop: "theme" }, map.main_bg), themeBg);

if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log("preview cases agree");
}
