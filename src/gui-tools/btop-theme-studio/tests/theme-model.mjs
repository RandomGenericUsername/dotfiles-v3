// Unit tests for lib/theme-model.ts — picker scopes, pending edits/diff/revert,
// one-click fixes, gradient editor, diagnosis, and the theme library.
//   node tests/theme-model.mjs
import {
  GRADIENT_LIMIT_NOTE,
  addMiddleColour,
  applyPick,
  canDelete,
  createTheme,
  deleteTheme,
  diagnose,
  diffEdits,
  duplicateTheme,
  effectiveMap,
  fixReserveSurface,
  fixTransparentMeters,
  forkTheme,
  generatedDefaultMap,
  isTwoStop,
  markActive,
  parseTheme,
  resolveHex,
  revert,
  scopeKeys,
  serializeTheme,
} from "../lib/theme-model.ts";
import { THEME_KEYS } from "../lib/theme-keys.ts";

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

const PALETTE = {
  background: "#0b0b1a",
  foreground: "#c2c2c5",
  cursor: "#c2c2c5",
  ramp: ["#0b0b1a", "#575660", "#5a5a6f", "#2d6596", "#557690", "#9a7268", "#549ec8", "#dbab67", "#c2c2c5"],
  colors: ["#0b0b1a", "#575660", "#575660", "#5a5a6f", "#2d6596", "#2d6596", "#557690", "#557690", "#9a7268", "#9a7268", "#549ec8", "#549ec8", "#dbab67", "#dbab67", "#c2c2c5", "#c2c2c5"],
};

// ── resolution ──────────────────────────────────────────────────────────────
check("ramp token", resolveHex("ramp[3]", PALETTE), "#2d6596");
check("named background", resolveHex("background", PALETTE), "#0b0b1a");
check("named foreground", resolveHex("foreground", PALETTE), "#c2c2c5");
check("color token", resolveHex("color4", PALETTE), "#2d6596");
check("literal hex", resolveHex("#abcdef", PALETTE), "#abcdef");
check("transparent", resolveHex("", PALETTE), "");

// ── picker scopes (task 4.6) ────────────────────────────────────────────────
const base = generatedDefaultMap();
check("this key scope", scopeKeys("used_start", "key", base), ["used_start"]);
check("same role scope size", scopeKeys("used_start", "role", base).length, 9);
check("all keys scope", scopeKeys("used_start", "all", base).length, 48);

const thisKey = applyPick(new Map(), "used_start", "#111111", "key", base);
check("this-key pick touches one key", thisKey.size, 1);
const sameRole = applyPick(new Map(), "used_start", "#222222", "role", base);
check("same-role pick touches every _start", sameRole.size, 9);
check(
  "same-role pick set every *_start",
  [...sameRole.keys()].every((k) => k.endsWith("_start")),
  true,
);
const allKeys = applyPick(new Map(), "used_start", "#333333", "all", base);
check("all-keys pick touches 48", allKeys.size, 48);
check("effectiveMap applies edits", effectiveMap(base, thisKey).used_start, "#111111");

// ── diff + revert (task 5.2) ────────────────────────────────────────────────
check("diff empty at rest", diffEdits(base, new Map()), []);
const diff = diffEdits(base, thisKey);
check("diff has one entry", diff.length, 1);
check("diff entry", diff[0], { key: "used_start", from: base.used_start, to: "#111111" });
check("diff empty after revert", diffEdits(base, revert()), []);
check("revert discards edits", revert().size, 0);

// ── one-click fixes (task 4.7) ──────────────────────────────────────────────
const reserved = fixReserveSurface(base);
check("reserve surface: meter_bg = main_bg", reserved.meter_bg, base.main_bg);
check("reserve surface: used floor raised", reserved.used_start, base.used_mid);
check("reserve surface keeps 48 keys", Object.keys(reserved).length, 48);
const transparent = fixTransparentMeters(base);
check("transparent meters: meter_bg empty", transparent.meter_bg, "");

// ── gradient editor (task 4.5) ──────────────────────────────────────────────
check("download is two-stop", isTwoStop(base, "download"), true);
const three = addMiddleColour(base, "download");
check("add middle colour sets download_mid", three.download_mid, base.download_start);
check("download is now three-stop", isTwoStop(three, "download"), false);
check("three-stop limit stated", /three stops/.test(GRADIENT_LIMIT_NOTE), true);
check("limit states keys cannot be added", /cannot be added/.test(GRADIENT_LIMIT_NOTE), true);

// ── diagnosis (task 5.1) ────────────────────────────────────────────────────
const collision = diagnose({ ...base, used_start: "#575660", meter_bg: "#575660" }, PALETTE);
check("collision reported", collision.some((d) => d.level === "error" && /SAME colour/.test(d.message)), true);
check("collision mentions vanishing", collision.some((d) => /vanish into the empty meter/.test(d.message)), true);

const competing = diagnose({ ...base, meter_bg: "#dbab67", main_bg: "#0b0b1a", used_start: "#549ec8" }, PALETTE);
check("meter_bg vs background reported", competing.some((d) => d.level === "warn" && /differs from the background/.test(d.message)), true);

const quiet = diagnose({ ...base, meter_bg: "#0b0b1a", main_bg: "#0b0b1a", used_start: "#549ec8" }, PALETTE);
check("clean meter_bg is ok", quiet.some((d) => d.level === "ok" && /sits against the background/.test(d.message)), true);
check("no collision when meter_bg is transparent", diagnose({ ...base, meter_bg: "" }, PALETTE).some((d) => d.level === "error"), false);

// ── theme library (tasks 3.3/8.2) ───────────────────────────────────────────
const generated = { id: "generated", name: "colors.btop", kind: "generated", active: true, map: base };
const authored = createTheme("t1", "btop-dusk", base);
check("generated cannot be deleted", canDelete(generated), false);
check("authored can be deleted", canDelete(authored), true);
const lib = { themes: [generated, authored] };
check("delete refuses generated", deleteTheme(lib, "generated").themes.length, 2);
check("delete removes authored", deleteTheme(lib, "t1").themes.length, 1);

const forked = forkTheme(generated, "t2", "colors.btop-fork", PALETTE);
check("fork is authored", forked.kind, "authored");
check("fork freezes literal colours", forked.map.main_bg, "#0b0b1a");
check("fork has 48 keys", Object.keys(forked.map).length, 48);
const dup = duplicateTheme(authored, "t3", "btop-dusk-copy");
check("duplicate is authored", dup.kind, "authored");
check("duplicate keeps the map", dup.map.main_bg, base.main_bg);

const activated = markActive(lib, "t1");
check("exactly one active", activated.themes.filter((t) => t.active).length, 1);
check("chosen theme active", activated.themes.find((t) => t.id === "t1").active, true);
check("unknown id is a no-op", markActive(lib, "nope"), lib);

// ── serialization ───────────────────────────────────────────────────────────
const text = serializeTheme(forked.map);
check("serialize has 48 lines", text.trim().split("\n").length, 48);
check("serialize line shape", text.includes('theme[main_bg]="#0b0b1a"'), true);
check("parse round-trips", parseTheme(text), forked.map);
check("generated default has 48 keys", Object.keys(base).length, 48);
check("generated default download_mid empty", base.download_mid, "");
check("generated default keys are all real", THEME_KEYS.every((k) => k in base), true);

if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log("theme-model cases agree");
}
