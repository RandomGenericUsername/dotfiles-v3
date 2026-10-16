import assert from "node:assert/strict"
import { test } from "node:test"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"
import {
  iconByStateKey,
  resolveIconSource,
  type IconProvider,
} from "ags-platform/ports/icon-source"
import {
  volumeStateKey,
  microphoneStateKey,
} from "../../audio/presentation/bar-indicators.ts"
import {
  POWER_MODES,
  UNLISTED_MODE,
  powerModeStateKey,
} from "../../components/battery/presentation.ts"

/**
 * The uniform icon contract (spine AD-7; doc 101 §7, §13 step 3).
 *
 * Code emits a STATE KEY; the manifest's `bar_mappings.states` maps it to a
 * variant; the registry maps the variant to art. This suite is PURE (no GTK, no
 * `ags`) and resolves through the REAL committed manifest, so it also pins the
 * AD-21 single-manifest claim: every key the migrated call sites emit names a
 * variant that actually exists, and a key that does not blanks rather than
 * throwing.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const AGS = join(HERE, "..", "..")
const manifest = JSON.parse(readFileSync(join(AGS, "icons.json"), "utf8")) as Record<
  string,
  unknown
>

interface ManifestGroup {
  variants: Array<{ name: string; output: string }>
  bar_mappings?: { states: Record<string, string> }
}

/** The group entry for `name`, or null when the key is not a group (e.g. the reserved version). */
function group(name: string): ManifestGroup | null {
  const value = manifest[name]
  return value !== null && typeof value === "object" ? (value as ManifestGroup) : null
}

/** An `IconProvider` backed by the real manifest tables — the same shape `icon.ts` adapts. */
function manifestProvider(): IconProvider {
  return {
    barMappings: (name) => {
      const bm = group(name)?.bar_mappings
      return bm ? { states: bm.states } : null
    },
    resolve: (name, variant) => {
      const entry = group(name)?.variants.find((v) => v.name === variant)
      return entry ? { kind: "file", path: entry.output } : null
    },
  }
}

test("the manifest carries a numeric schemaVersion alongside its groups", () => {
  assert.equal(typeof manifest.schemaVersion, "number")
})

test("volumeStateKey emits the volume group's state keys", () => {
  assert.equal(volumeStateKey(false, 0.9), "volume-max")
  assert.equal(volumeStateKey(false, 0.3), "volume-low")
  assert.equal(volumeStateKey(true, 0.9), "volume-muted")
  assert.equal(volumeStateKey(false, 0), "volume-muted")
})

test("microphoneStateKey emits the microphone group's state keys", () => {
  assert.equal(microphoneStateKey("mic-on"), "microphone-mic-on")
  assert.equal(microphoneStateKey("mic-off"), "microphone-mic-off")
})

test("powerModeStateKey emits the power-mode group's state keys", () => {
  assert.equal(powerModeStateKey(POWER_MODES[0]), "power-mode-powersave")
  assert.equal(powerModeStateKey(POWER_MODES[1]), "power-mode-balanced")
  assert.equal(powerModeStateKey(POWER_MODES[2]), "power-mode-performance")
  assert.equal(powerModeStateKey(UNLISTED_MODE), "power-mode-unknown")
})

test("each migrated state key resolves through the real manifest to art", () => {
  const provider = manifestProvider()
  const cases: Array<[string, string, string]> = [
    ["volume", "volume-medium", "volume-medium.svg"],
    ["microphone", "microphone-mic-off", "microphone-mic-off.svg"],
    ["power-mode", "power-mode-powersave", "power-mode-powersave.svg"],
  ]
  for (const [groupName, key, output] of cases) {
    const ref = iconByStateKey(groupName, () => key)
    assert.deepEqual(
      resolveIconSource(provider, ref, undefined),
      { kind: "file", path: output },
      `${groupName}/${key} should resolve to ${output}`,
    )
  }
})

test("an unknown state key blanks, never throws", () => {
  const provider = manifestProvider()
  const unknown = iconByStateKey("volume", () => "volume-does-not-exist")
  assert.equal(resolveIconSource(provider, unknown, undefined), null)

  // The undeclared power tier's key is deliberately absent: it blanks.
  const unlisted = iconByStateKey("power-mode", () => powerModeStateKey(UNLISTED_MODE))
  assert.equal(resolveIconSource(provider, unlisted, undefined), null)
})

test("every declared state key names a variant that exists in its group", () => {
  for (const name of ["volume", "microphone", "power-mode"]) {
    const g = group(name)
    assert.ok(g?.bar_mappings, `${name} must declare bar_mappings`)
    const variantNames = new Set(g.variants.map((v) => v.name))
    for (const [key, variant] of Object.entries(g.bar_mappings.states)) {
      assert.ok(
        variantNames.has(variant),
        `${name}: state key ${key} maps to missing variant ${variant}`,
      )
    }
  }
})
