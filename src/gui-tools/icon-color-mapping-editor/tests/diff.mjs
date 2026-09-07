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
