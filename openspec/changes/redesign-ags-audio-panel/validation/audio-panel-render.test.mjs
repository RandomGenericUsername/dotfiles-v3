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
import { execFileSync } from "node:child_process";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "../../../..");
const AGS = join(REPO, "dotfiles/config/ags");
const AUDIO = join(AGS, "audio");

const read = (p) => readFileSync(p, "utf8");

const appTsx = read(join(AGS, "app.tsx"));
const popupSrc = read(join(AUDIO, "AudioPopup.tsx"));
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
  const layers = [
    "application/runtime/audio-session-runtime",
    "presentation/audio-panel-view-model",
  ];
  const missing = layers.filter((l) => !appTsx.includes(l));
  assert.deepEqual(
    missing,
    [],
    `app.tsx never references: ${missing.join(", ")}. The composition root ` +
      "does not construct them, so they are orphaned code."
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
