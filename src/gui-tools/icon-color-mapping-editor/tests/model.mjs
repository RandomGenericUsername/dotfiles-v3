// Unit tests for lib/model.ts. Run with plain node:
// `node tests/model.mjs` from the tool directory.
import {
  pendingKeyOf,
  pendingTargetLabel,
  previewMappings,
  scopeOf,
  upsertPending,
  vocabularyKeyOf,
} from "../lib/model.ts";

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

const ENTRIES = [
  { placeholder: "COLOR_ACCENT", token: "color12", origin: "group" },
  { placeholder: "COLOR_FG", token: "foreground", origin: "vocabulary" },
];
const EMPTY = new Map();

// no pending edits: table mirrors entries
check(
  "plain table",
  previewMappings(ENTRIES, "battery", "battery-0", EMPTY, EMPTY),
  { COLOR_ACCENT: "color12", COLOR_FG: "foreground" },
);

// group-scope pending retargets across variants
const groupPending = upsertPending(EMPTY, {
  group: "battery",
  variant: null,
  placeholder: "COLOR_ACCENT",
  token: "color10",
});
check(
  "group edit applies to sibling variant",
  previewMappings(ENTRIES, "battery", "battery-50", groupPending, EMPTY).COLOR_ACCENT,
  "color10",
);

// variant-scope wins over group-scope
const both = upsertPending(groupPending, {
  group: "battery",
  variant: "battery-0",
  placeholder: "COLOR_ACCENT",
  token: "color3",
});
check(
  "variant edit wins on its variant",
  previewMappings(ENTRIES, "battery", "battery-0", both, EMPTY).COLOR_ACCENT,
  "color3",
);
check(
  "group edit still applies elsewhere",
  previewMappings(ENTRIES, "battery", "battery-50", both, EMPTY).COLOR_ACCENT,
  "color10",
);

// vocabulary-scope retargets vocabulary origins only
const vocab = new Map([["COLOR_FG", { placeholder: "COLOR_FG", token: "color15" }]]);
check(
  "vocab edit retargets vocabulary origin",
  previewMappings(ENTRIES, "battery", "battery-0", EMPTY, vocab).COLOR_FG,
  "color15",
);
check(
  "vocab edit does not touch group origins",
  previewMappings(ENTRIES, "battery", "battery-0", EMPTY, vocab).COLOR_ACCENT,
  "color12",
);

// other groups are unaffected
check(
  "foreign group untouched",
  previewMappings(ENTRIES, "network", "wifi", both, vocab),
  { COLOR_ACCENT: "color12", COLOR_FG: "color15" },
);

// key helpers
check(
  "keys distinguish scopes",
  pendingKeyOf({ group: "g", variant: null, placeholder: "P" }) !==
    pendingKeyOf({ group: "g", variant: "v", placeholder: "P" }),
  true,
);
check(
  "scope of group edit",
  scopeOf({ group: "g", variant: null, placeholder: "P", token: "t" }),
  "group",
);
check(
  "scope of variant edit",
  scopeOf({ group: "g", variant: "v", placeholder: "P", token: "t" }),
  "variant",
);
check(
  "group target label",
  pendingTargetLabel({ group: "g", variant: null, placeholder: "P", token: "t" }),
  "g.color_mappings.P",
);
check(
  "variant target label",
  pendingTargetLabel({ group: "g", variant: "v", placeholder: "P", token: "t" }),
  "g.variants[v].color_mappings.P",
);
check("vocab key", vocabularyKeyOf({ placeholder: "P", token: "t" }), "defaults\0P");

if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log("model cases agree");
}
