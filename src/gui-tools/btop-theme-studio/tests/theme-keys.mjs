// Unit tests for lib/theme-keys.ts. Plain node:
//   node tests/theme-keys.mjs
import {
  BOXES,
  GRADIENT_FAMILIES,
  KEY_GROUPS,
  THEME_KEYS,
  familyOf,
  gradientStops,
  hasAllKeys,
  isGradientKey,
  isGradientStop,
  isTwoStop,
  roleSuffix,
  sameRoleKeys,
} from "../lib/theme-keys.ts";

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

check("48 keys", THEME_KEYS.length, 48);
check("no duplicate keys", new Set(THEME_KEYS).size, 48);
check("groups sum to 48", KEY_GROUPS.reduce((n, g) => n + g.keys.length, 0), 48);
check(
  "groups partition the keys",
  KEY_GROUPS.flatMap((g) => g.keys).sort(),
  [...THEME_KEYS].sort(),
);
check("includes download_mid", THEME_KEYS.includes("download_mid"), true);
check("includes upload_mid", THEME_KEYS.includes("upload_mid"), true);
check("includes followed_fg", THEME_KEYS.includes("followed_fg"), true);
check("boxes", BOXES, ["cpu", "gpu", "mem", "net", "disks", "proc"]);
check("9 gradient families", GRADIENT_FAMILIES.length, 9);

check("roleSuffix start", roleSuffix("used_start"), "_start");
check("roleSuffix mid", roleSuffix("download_mid"), "_mid");
check("roleSuffix none", roleSuffix("main_bg"), null);
check("familyOf", familyOf("used_start"), "used");
check("familyOf passthrough", familyOf("main_bg"), "main_bg");
check("isGradientStop", isGradientStop("cpu_end"), true);
check("isGradientKey known family", isGradientKey("cpu_end"), true);
check("isGradientKey unknown family", isGradientKey("nope_end"), false);
check("gradientStops", gradientStops("used"), ["used_start", "used_mid", "used_end"]);

check("sameRoleKeys counts", sameRoleKeys("used_start").length, 9);
check("sameRoleKeys all _start", sameRoleKeys("used_start").every((k) => k.endsWith("_start")), true);
check("sameRoleKeys non-gradient", sameRoleKeys("main_bg"), ["main_bg"]);

check("isTwoStop true", isTwoStop({ download_mid: "" }, "download"), true);
check("isTwoStop false", isTwoStop({ download_mid: "#fff" }, "download"), false);
check("hasAllKeys on a full map", hasAllKeys(Object.fromEntries(THEME_KEYS.map((k) => [k, "#000"]))), true);
check("hasAllKeys on a partial map", hasAllKeys({ main_bg: "#000" }), false);

if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log("theme-keys cases agree");
}
