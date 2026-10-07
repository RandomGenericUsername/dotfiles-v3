#!/usr/bin/env node
// Icon-variant gate: every `system-*` volume variant the code can request must
// exist in icons.json.
//
// Added 2026-10-07 after a real defect that no other gate could see. The app
// rows built their mute/level glyph as:
//
//     `system-${level < 0.34 ? "low" : level < 0.67 ? "medium" : "high"}`
//
// but the registry's variants are lowest/low/medium/MAX/muted -- there is no
// `system-high`. For any volume >= 67% (i.e. almost always) icon() returned
// undefined, setImageOnce skips falsy paths, and the image never updated. Every
// row therefore showed whatever it first drew: the muted glyph, permanently.
// It muted correctly, so it looked like a state bug, not a naming bug.
//
// A missing icon name fails silently by construction, so it needs a mechanical
// check rather than care. This asserts the vocabulary in state.ts's
// levelVariant() -- the shared source used by the panel, the settings Sound card
// and the VolumeSlider -- resolve to real files.
//
// Static, no desktop stack needed.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "../../../..");
const AGS = join(REPO, "dotfiles/config/ags");

const icons = JSON.parse(readFileSync(join(AGS, "icons.json"), "utf8"));
const stateSrc = readFileSync(join(AGS, "audio/state.ts"), "utf8");

// The vocabulary the shared helper can produce. Read from the source rather
// than restated, so adding a case there without shipping art fails here.
const helper = stateSrc.slice(stateSrc.indexOf("export function levelVariant"));
const returned = [...helper.matchAll(/return "([a-z]+)"/g)].map((m) => m[1]);
assert.ok(returned.length >= 4, `could not read levelVariant's vocabulary (got ${returned.join(",")})`);

const volume = icons.volume;
assert.ok(volume?.variants, "icons.json has no volume group");

const available = new Set(volume.variants.map((v) => v.name));
const expected = returned.map((name) => `system-${name}`);

const missing = expected.filter((name) => !available.has(name));
assert.deepEqual(
  missing,
  [],
  `levelVariant() can request variants that do not exist in icons.json: ${missing.join(", ")}. ` +
    `Available: ${[...available].sort().join(", ")}. ` +
    "A missing icon resolves to nothing and the image silently keeps its previous glyph."
);

// The specific historical defect, pinned.
assert.ok(
  !available.has("system-high"),
  "system-high now exists -- the vocabulary and the art have converged; remove this note"
);

console.log(
  `audio-icons: PASS (${expected.length} level variant(s) checked: ${expected.join(", ")})`
);
