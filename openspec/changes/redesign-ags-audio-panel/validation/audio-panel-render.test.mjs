#!/usr/bin/env node
// Render gate for the redesigned audio panel.
//
// Added 2026-10-03 after the first implementation pass shipped a popup that
// rendered no controls at all. Every other gate in this change stayed green
// through that: the domain, adapter, and presentation suites all pass because
// they exercise modules directly, and `ags bundle` compiles an unwired popup
// without complaint. Nothing asked the only question that mattered -- does the
// panel actually show its body?
//
// This gate answers it statically, from the source, so it runs in CI without
// a display server. It asserts the composition root is wired, not that a
// particular widget tree was instantiated:
//
//   1. app.tsx passes a binding to AudioPopup (it did not).
//   2. AudioPopup's `binding` parameter is required (it was optional).
//   3. The "Audio controls are connecting" fallback is gone (it masked the
//      defect by rendering a plausible loading state forever).
//   4. audio-panel.css is actually imported by something (it was not).
//   5. Nothing outside the new boundary still imports ./state (the second
//      global audio model design.md forbids).
//   6. The new layers are reachable from app.tsx rather than orphaned.
//
// Static only. A green run means the panel is wired, not that it looks right --
// that is 7.7's live smoke and 7.8/7.9's visual review.

import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "../../../..");
const AGS = join(REPO, "dotfiles/config/ags");
const AUDIO = join(AGS, "audio");

const read = (p) => readFileSync(p, "utf8");

/**
 * Strip comments before scanning.
 *
 * A check like "the connecting fallback is gone" must not be satisfied or
 * defeated by prose about it: AudioPopup.tsx documents that the placeholder
 * existed and why, in a comment. Scanning raw text made that documentation read
 * as the defect it describes. Block and line comments are removed; string
 * literals are left alone, since the placeholder ships inside one.
 */
function stripComments(text) {
  let out = "";
  for (let i = 0; i < text.length; i++) {
    const two = text.slice(i, i + 2);
    if (two === "/*") {
      const end = text.indexOf("*/", i + 2);
      i = end === -1 ? text.length : end + 1;
      continue;
    }
    if (two === "//") {
      const end = text.indexOf("\n", i);
      i = end === -1 ? text.length : end;
      continue;
    }
    out += text[i];
  }
  return out;
}

const appTsx = stripComments(read(join(AGS, "app.tsx")));
const popupSrc = stripComments(read(join(AUDIO, "AudioPopup.tsx")));
const styleSrc = existsSync(join(AGS, "style.css")) ? read(join(AGS, "style.css")) : "";

const checks = [];
const check = (name, fn) => {
  try {
    fn();
    checks.push({ name, ok: true });
  } catch (err) {
    checks.push({ name, ok: false, err });
  }
};

const grep = (needle, path) => {
  try {
    return read(path).includes(needle);
  } catch {
    return false;
  }
};

check("app.tsx passes a binding to AudioPopup", () => {
  const call = appTsx.match(/AudioPopup\([^)]*\)/);
  assert.ok(call, "no AudioPopup(...) call found in app.tsx");
  assert.match(
    call[0],
    /AudioPopup\(\s*[^,()]+,\s*[A-Za-z_$][\w$]*\s*\)/,
    `AudioPopup is called with no binding: ${call[0]}. The panel renders nothing.`
  );
});

check("AudioPopup's binding parameter is required", () => {
  const sig = popupSrc.match(/export function AudioPopup\(([^)]*)\)/);
  assert.ok(sig, "AudioPopup signature not found");
  assert.ok(
    !/binding\?\s*:/.test(sig[1]),
    `binding is optional in AudioPopup(${sig[1]}). Make it required so an ` +
      "unwired panel is a typecheck error instead of a silent empty state."
  );
});

check('the "Audio controls are connecting" fallback is removed', () => {
  assert.ok(
    !popupSrc.includes("Audio controls are connecting"),
    "AudioPopup still renders the connecting fallback; an unwired panel is " +
      "indistinguishable from a starting one."
  );
  assert.ok(
    !/binding\s*\?/.test(popupSrc),
    "AudioPopup still branches on binding presence; it must render " +
      "AudioPanelContent unconditionally."
  );
});

check("audio-panel.css is imported by the AGS stylesheet", () => {
  const referenced =
    grep("audio-panel.css", join(AGS, "style.css")) ||
    grep("audio-panel.css", join(AGS, "app.tsx")) ||
    grep("audio-panel.css", popupSrc);
  assert.ok(
    referenced,
    "audio-panel.css is imported by nothing, so the 345-line approved theme " +
      "is dead and the popup falls back to pre-existing .audio-* rules."
  );
  assert.ok(styleSrc.length > 0, "style.css could not be read");
});

check("no consumer outside the new boundary imports ./state", () => {
  // app.tsx, bar widgets, and settings-panel are the real consumers. Modules
  // inside audio/ may still reference it mid-migration; task 6.0f retires it.
  const consumers = [
    join(AGS, "app.tsx"),
    join(AGS, "bar/widgets/audio.tsx"),
    join(AGS, "settings-panel/settings.tsx"),
  ];
  const offenders = consumers.filter((p) => existsSync(p) && grep('from "./state"', p));
  assert.deepEqual(
    offenders,
    [],
    `these consumers still read the old state.ts model: ${offenders.join(", ")}`
  );
});

check("the new boundary is reachable from app.tsx", () => {
  // Reachability, not a literal import in app.tsx: the composition root is
  // expected to assemble the layers, so follow the import graph transitively
  // from app.tsx rather than demanding app.tsx name each one.
  const seen = new Set();
  const queue = [join(AGS, "app.tsx")];
  const LAYERS = [
    "audio/domain/audio-model.ts",
    "audio/application/ports.ts",
    "audio/application/audio-actions.ts",
    "audio/application/runtime/audio-session-runtime.ts",
    "audio/adapters/pipewire/pipewire-observation.ts",
    "audio/adapters/mpris/mpris-adapter.ts",
    "audio/presentation/audio-panel-view-model.ts",
  ];
  const IMPORT_RE = /from\s+["']([^"']+)["']/g;
  while (queue.length) {
    const file = queue.pop();
    if (seen.has(file) || !existsSync(file)) continue;
    seen.add(file);
    const src = stripComments(read(file));
    for (const m of src.matchAll(IMPORT_RE)) {
      const spec = m[1];
      if (!spec.startsWith(".")) continue; // ags/, gi://, node builtins
      // Extensionless relative imports, as AGS/GJS writes them.
      const base = resolve(dirname(file), spec);
      const target = existsSync(base)
        ? base
        : [base + ".ts", base + ".tsx", join(base, "index.ts")].find((c) =>
            existsSync(c)
          );
      if (target) queue.push(target);
    }
  }
  const missing = LAYERS.filter(
    (rel) => !seen.has(join(AGS, rel))
  );
  assert.deepEqual(
    missing,
    [],
    `unreachable from app.tsx: ${missing.join(", ")}. These modules exist but ` +
      "nothing imports them, so the panel has no data source -- orphaned " +
      "architecture that compiles and renders nothing."
  );
});

let failed = 0;
for (const { name, ok, err } of checks) {
  console.log(`${ok ? "ok  " : "FAIL"} ${name}`);
  if (!ok) {
    failed++;
    console.log(`       ${err.message.split("\n").join("\n       ")}`);
  }
}

console.log(
  `\n${checks.length - failed}/${checks.length} render checks passed` +
    (failed ? ` — ${failed} FAILED` : "")
);
if (failed) {
  console.log(
    "\nThe panel is not wired. It will compile and bundle, and it will render " +
      "nothing.\nSee tasks.md 6.0."
  );
}
process.exit(failed ? 1 : 0);
