import assert from "node:assert/strict"
import { test } from "node:test"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"
import { BAR_MANIFEST } from "../../bar/bar-manifest.ts"
import { DEFAULT_LAYOUT } from "../../bar/layout.default.ts"

/**
 * The pure `bar-manifest` (spine AD-14; ags-bar-validation task 1.1).
 *
 * This suite importing the manifest under plain `node --test` IS the purity
 * check: `bar-manifest.ts` carries zero imports, so a GJS/GTK/`ags` edge
 * introduced there fails here with a resolve error on a stock runner — long
 * before the bar tries to bundle it. The structural pins below keep the
 * declarations and the artifacts they describe in agreement.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const AGS = join(HERE, "..", "..")
const iconsJson = JSON.parse(readFileSync(join(AGS, "icons.json"), "utf8")) as Record<
  string,
  unknown
>

interface ArtifactGroup {
  bar_mappings?: { states: Record<string, string> }
}

function artifactGroup(name: string): ArtifactGroup | null {
  const value = iconsJson[name]
  return value !== null && typeof value === "object" ? (value as ArtifactGroup) : null
}

function defaultLayoutIds(): string[] {
  return [
    ...(DEFAULT_LAYOUT.sections.start ?? []),
    ...(DEFAULT_LAYOUT.sections.center ?? []),
    ...(DEFAULT_LAYOUT.sections.end ?? []),
  ].map((entry) => entry.id)
}

test("the manifest declares a unique non-empty id per capability", () => {
  const ids = BAR_MANIFEST.capabilities.map((c) => c.id)
  assert.ok(ids.length > 0)
  for (const id of ids) assert.notEqual(id, "")
  assert.equal(new Set(ids).size, ids.length)
})

test("every default-layout widget is a declared capability", () => {
  const ids = new Set(BAR_MANIFEST.capabilities.map((c) => c.id))
  for (const id of defaultLayoutIds()) {
    assert.ok(ids.has(id), `default layout id ${id} has no manifest capability`)
  }
})

test("no capability takes params today, and none repeats", () => {
  for (const capability of BAR_MANIFEST.capabilities) {
    assert.deepEqual(capability.params, [], `${capability.id} declares params`)
    assert.equal(capability.multi, false)
  }
})

test("every capability icon group is a declared icon group", () => {
  const groups = new Set(BAR_MANIFEST.iconGroups.map((g) => g.name))
  for (const capability of BAR_MANIFEST.capabilities) {
    if (capability.iconGroup !== undefined) {
      assert.ok(
        groups.has(capability.iconGroup),
        `${capability.id} names undeclared icon group ${capability.iconGroup}`,
      )
    }
  }
})

test("every declared icon group exists in icons.json", () => {
  for (const group of BAR_MANIFEST.iconGroups) {
    assert.ok(artifactGroup(group.name) !== null, `${group.name} is not an icons.json group`)
  }
})

test("declared states agree with the artifact bar_mappings tables", () => {
  for (const group of BAR_MANIFEST.iconGroups) {
    const artifact = artifactGroup(group.name)
    assert.ok(artifact !== null)
    const table = artifact.bar_mappings?.states ?? {}
    assert.deepEqual(
      [...group.states].sort(),
      Object.keys(table).sort(),
      `${group.name}: manifest states drifted from icons.json bar_mappings`,
    )
  }
})
