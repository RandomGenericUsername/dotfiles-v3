// Unit tests for lib/diff.ts. Run with plain node:
// `node tests/diff.mjs` from the tool directory.
import {
  escapeMarkup,
  parseDiffLines,
  renderDiffMarkup,
} from "../lib/diff.ts";

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

const DIFF =
  "--- /icons.yaml\n+++ /icons.yaml\n@@ -1,2 +1,3 @@\n ctx\n-old\n+new\n\\ No newline at end of file";

const kinds = parseDiffLines(DIFF).map((line) => line.kind);
check("line kinds", kinds, ["file", "file", "hunk", "ctx", "del", "add", "ctx"]);

check("escape", escapeMarkup('<a href="x&y">it\'s</a>'), "&lt;a href=&quot;x&amp;y&quot;&gt;it&#39;s&lt;/a&gt;");

const markup = renderDiffMarkup("- COLOR: old\n+ COLOR: new");
check("del colored", markup.includes('<span foreground="#e08585">- COLOR: old</span>'), true);
check("add colored", markup.includes('<span foreground="#7bc47f">+ COLOR: new</span>'), true);
check("empty stays empty", renderDiffMarkup(""), "");

if (failures > 0) {
  console.error(`${failures} case(s) mismatched`);
  process.exitCode = 1;
} else {
  console.log("diff cases agree");
}

// semantic pending rows
import {
  describePending,
  renderPendingMarkup,
} from "../lib/diff.ts";

const SHOW = {
  groups: [
    {
      group: "battery",
      variants: [
        {
          variant: "battery-0",
          mappings: [
            { placeholder: "COLOR_ACCENT", token: "color12", origin: "group" },
            { placeholder: "COLOR_FOREGROUND", token: "foreground", origin: "vocabulary" },
          ],
        },
      ],
    },
  ],
};
const EMPTY = new Map();

// group edit on an existing group entry: plain old -> new
{
  const pending = new Map([["k1", { group: "battery", variant: null, placeholder: "COLOR_ACCENT", token: "color10" }]]);
  const rows = describePending(SHOW, "battery", "battery-0", pending, EMPTY);
  check("group edit row", rows.length, 1);
  check("group edit html", rows[0].html, "  COLOR_ACCENT: <s>color12</s> → <b>color10</b>");
  check("group edit header", rows[0].header, "battery.color_mappings");
}

// first-time override over a vocabulary default: old source named
{
  const pending = new Map([["k2", { group: "battery", variant: null, placeholder: "COLOR_FOREGROUND", token: "color13" }]]);
  const rows = describePending(SHOW, "battery", "battery-0", pending, EMPTY);
  check(
    "vocab fallback names source",
    rows[0].html,
    "  COLOR_FOREGROUND: <s>foreground</s> (vocabulary default) → <b>color13</b>",
  );
}

// variant edit reports under its variant header
{
  const pending = new Map([["k3", { group: "battery", variant: "battery-0", placeholder: "COLOR_ACCENT", token: "color3" }]]);
  const rows = describePending(SHOW, "battery", "battery-0", pending, EMPTY);
  check("variant edit header", rows[0].header, "battery.variants[battery-0].color_mappings");
  check("variant edit html", rows[0].html, "  COLOR_ACCENT: <s>color12</s> → <b>color3</b>");
}

// markup colors the strike red and the new token green
{
  const pending = new Map([["k4", { group: "battery", variant: null, placeholder: "COLOR_ACCENT", token: "color10" }]]);
  const markup = renderPendingMarkup(describePending(SHOW, "battery", "battery-0", pending, EMPTY));
  check("old is red", markup.includes('<span foreground="#e08585"><s>color12</s></span>'), true);
  check("new is green", markup.includes('<span foreground="#7bc47f"><b>color10</b></span>'), true);
  check("header is blue", markup.includes('<span foreground="#6ea8fe">battery.color_mappings</span>'), true);
}

// vocab edit row
{
  const vocab = new Map([["COLOR_ACCENT", { placeholder: "COLOR_ACCENT", token: "color3" }]]);
  const rows = describePending(SHOW, "battery", "battery-0", EMPTY, vocab);
  check("vocab row header", rows[0].header, "defaults");
  check("vocab row html", rows[0].html, "  COLOR_ACCENT: <s>color12</s> → <b>color3</b>");
}
