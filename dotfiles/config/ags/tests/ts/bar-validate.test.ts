import assert from "node:assert/strict"
import { test } from "node:test"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"
import {
  checkSchemaVersion,
  EXPECTED_SCHEMA_VERSION,
  sanitizeLayout,
  validateIcons,
  validateLayout,
  type BarIssue,
  type IssueCode,
} from "../../bar/validate.ts"
import type { BarLayout } from "../../kit/layout.ts"
import type { CapabilityDecl, IconGroupDecl } from "../../bar/bar-manifest.ts"
import { BAR_MANIFEST } from "../../bar/bar-manifest.ts"
import { DEFAULT_LAYOUT } from "../../bar/layout.default.ts"

/**
 * The shared validators (spine AD-15; ags-bar-validation task 1.2).
 *
 * One unit test per `IssueCode`, over the DECLARATIONS — never over runtime
 * `Capability` objects. Importing the module under test under plain
 * `node --test` IS the purity check: `validate.ts` carries only `import
 * type`, so a runtime GJS/GTK/`ags` edge introduced there fails here with a
 * resolve error on a stock runner. The final two pins run the validators over
 * the real declarations + artifacts, so drift between them fails here first.
 */

function codes(issues: readonly BarIssue[]): IssueCode[] {
  return issues.map((i) => i.code)
}

test("a clean layout validates", () => {
  const decls: CapabilityDecl[] = [
    { id: "workspaces", params: [], multi: false },
    { id: "clock", params: [], multi: false },
  ]
  const layout: BarLayout = {
    sections: { start: [{ id: "workspaces" }], center: [{ id: "clock" }] },
  }
  const result = validateLayout(layout, decls)
  assert.equal(result.ok, true)
  assert.deepEqual(result.issues, [])
})

test("unknown-widget: a layout id with no declaration is an error", () => {
  const decls: CapabilityDecl[] = [{ id: "clock", params: [], multi: false }]
  const layout: BarLayout = { sections: { center: [{ id: "clok" }] } }
  const result = validateLayout(layout, decls)
  assert.equal(result.ok, false)
  assert.deepEqual(codes(result.issues), ["unknown-widget"])
  assert.equal(result.issues[0].severity, "error")
  assert.equal(result.issues[0].widgetId, "clok")
})

test("unknown-param: a param outside the closed set is an error", () => {
  const decls: CapabilityDecl[] = [{ id: "clock", params: [], multi: false }]
  const layout: BarLayout = {
    sections: { center: [{ id: "clock", params: { format: "12h" } }] },
  }
  const result = validateLayout(layout, decls)
  assert.equal(result.ok, false)
  assert.deepEqual(codes(result.issues), ["unknown-param"])
  assert.equal(result.issues[0].severity, "error")
  assert.equal(result.issues[0].widgetId, "clock")
  assert.equal(result.issues[0].param, "format")
})

test("unknown-param: a declared param passes", () => {
  const decls: CapabilityDecl[] = [
    { id: "clock", params: ["format"], multi: false },
  ]
  const layout: BarLayout = {
    sections: { center: [{ id: "clock", params: { format: "12h" } }] },
  }
  const result = validateLayout(layout, decls)
  assert.equal(result.ok, true)
})

test("duplicate-widget: a repeated single-instance id is an error", () => {
  const decls: CapabilityDecl[] = [{ id: "clock", params: [], multi: false }]
  const layout: BarLayout = {
    sections: { start: [{ id: "clock" }], center: [{ id: "clock" }] },
  }
  const result = validateLayout(layout, decls)
  assert.equal(result.ok, false)
  assert.deepEqual(codes(result.issues), ["duplicate-widget"])
  assert.equal(result.issues[0].severity, "error")
  assert.equal(result.issues[0].widgetId, "clock")
})

test("duplicate-widget: multi:true allows repeats", () => {
  const decls: CapabilityDecl[] = [{ id: "tag", params: [], multi: true }]
  const layout: BarLayout = {
    sections: { start: [{ id: "tag" }], end: [{ id: "tag" }] },
  }
  const result = validateLayout(layout, decls)
  assert.equal(result.ok, true)
})

function artifact(): Record<string, unknown> {
  return {
    volume: {
      variants: [{ name: "max", output: "volume-max.svg" }],
      bar_mappings: { states: { "volume-max": "max" } },
    },
    btop: {
      variants: [{ name: "btop", output: "btop.svg" }],
    },
  }
}

test("missing-icon-key: a declared state absent from the table is an error", () => {
  const groups: IconGroupDecl[] = [{ name: "volume", states: ["volume-max", "volume-muted"] }]
  const result = validateIcons(artifact(), groups)
  assert.equal(result.ok, false)
  assert.deepEqual(codes(result.issues), ["missing-icon-key"])
  assert.equal(result.issues[0].severity, "error")
  assert.equal(result.issues[0].iconGroup, "volume")
  assert.equal(result.issues[0].iconState, "volume-muted")
})

test("missing-icon-key: a state mapping to a missing variant is an error", () => {
  const groups: IconGroupDecl[] = [{ name: "volume", states: ["volume-max"] }]
  const broken = {
    volume: {
      variants: [{ name: "max", output: "volume-max.svg" }],
      bar_mappings: { states: { "volume-max": "renamed" } },
    },
  }
  const result = validateIcons(broken, groups)
  assert.equal(result.ok, false)
  assert.deepEqual(codes(result.issues), ["missing-icon-key"])
  assert.equal(result.issues[0].iconState, "volume-max")
})

test("missing-icon-key: groups declaring no states are exempt", () => {
  const groups: IconGroupDecl[] = [{ name: "btop", states: [] }]
  assert.equal(validateIcons(artifact(), groups).ok, true)
  // Even a wholly absent artifact entry is fine for an exempt group.
  assert.equal(validateIcons({}, groups).ok, true)
})

test("missing-icon-key: a wholly absent group reports every declared state", () => {
  const groups: IconGroupDecl[] = [
    { name: "microphone", states: ["microphone-mic-on", "microphone-mic-off"] },
  ]
  const result = validateIcons({}, groups)
  assert.equal(result.ok, false)
  assert.deepEqual(codes(result.issues), ["missing-icon-key", "missing-icon-key"])
})

test("missing-icon-key: undeclared artifact groups are out of scope", () => {
  const groups: IconGroupDecl[] = [{ name: "volume", states: ["volume-max"] }]
  const withExtra = { ...artifact(), "power-mode": { bogus: true } }
  assert.equal(validateIcons(withExtra, groups).ok, true)
})

test("the repo-default layout validates against the real declarations", () => {
  const result = validateLayout(DEFAULT_LAYOUT, BAR_MANIFEST.capabilities)
  assert.deepEqual(result.issues, [])
  assert.equal(result.ok, true)
})

const HERE = dirname(fileURLToPath(import.meta.url))
const iconsJson = JSON.parse(
  readFileSync(join(HERE, "..", "..", "icons.json"), "utf8"),
) as Record<string, unknown>

test("the real icons.json validates against the real declarations", () => {
  const result = validateIcons(iconsJson, BAR_MANIFEST.iconGroups)
  assert.deepEqual(result.issues, [])
  assert.equal(result.ok, true)
})

test("unknown-schema-version: the deployed shape version passes silently", () => {
  assert.deepEqual(checkSchemaVersion({ schemaVersion: EXPECTED_SCHEMA_VERSION }, "icons.json"), [])
})

test("unknown-schema-version: a missing version warns, never errors", () => {
  const issues = checkSchemaVersion({}, "icons.json")
  assert.equal(issues.length, 1)
  assert.equal(issues[0].severity, "warning")
  assert.equal(issues[0].code, "unknown-schema-version")
})

test("unknown-schema-version: an unrecognised version warns and names both versions", () => {
  const issues = checkSchemaVersion({ schemaVersion: 99 }, "icons.json", 1)
  assert.equal(issues.length, 1)
  assert.equal(issues[0].severity, "warning")
  assert.equal(issues[0].code, "unknown-schema-version")
  assert.match(issues[0].message, /99/)
  assert.match(issues[0].message, /expected 1/)
})

test("unknown-schema-version: a corrupt artifact warns instead of throwing", () => {
  for (const broken of [null, 42, "icons", [{ schemaVersion: 1 }]]) {
    const issues = checkSchemaVersion(broken, "icons.json")
    assert.equal(issues.length, 1)
    assert.equal(issues[0].code, "unknown-schema-version")
  }
})

test("sanitizeLayout: a broken layout degrades to its valid entries, never throws", () => {
  const decls: CapabilityDecl[] = [
    { id: "workspaces", params: [], multi: false },
    { id: "clock", params: ["format"], multi: false },
  ]
  const layout: BarLayout = {
    sections: {
      start: [{ id: "workspaces" }, { id: "nope" }],
      center: [{ id: "clock", params: { format: "12h", bogus: true } }, { id: "clock" }],
    },
  }
  const { layout: clean, warnings } = sanitizeLayout(layout, decls)
  assert.deepEqual(clean, {
    sections: {
      start: [{ id: "workspaces" }],
      center: [{ id: "clock", params: { format: "12h" } }],
      end: undefined,
    },
  })
  assert.equal(warnings.length, 3)
  assert.match(warnings[0], /unknown widget "nope" skipped/)
  assert.match(warnings[1], /unknown param\(s\) "bogus".*stripped/)
  assert.match(warnings[2], /duplicate widget "clock" skipped/)
})

test("sanitizeLayout: multi:true repeats survive", () => {
  const decls: CapabilityDecl[] = [{ id: "tag", params: [], multi: true }]
  const layout: BarLayout = {
    sections: { start: [{ id: "tag" }], end: [{ id: "tag" }] },
  }
  const { layout: clean, warnings } = sanitizeLayout(layout, decls)
  assert.deepEqual(clean.sections.start, [{ id: "tag" }])
  assert.deepEqual(clean.sections.end, [{ id: "tag" }])
  assert.deepEqual(warnings, [])
})

test("sanitizeLayout: a clean layout passes through unchanged with no warnings", () => {
  const { layout: clean, warnings } = sanitizeLayout(DEFAULT_LAYOUT, BAR_MANIFEST.capabilities)
  assert.deepEqual(clean, DEFAULT_LAYOUT)
  assert.deepEqual(warnings, [])
})

test("sanitizeLayout: an absent section stays absent", () => {
  const decls: CapabilityDecl[] = [{ id: "clock", params: [], multi: false }]
  const { layout: clean } = sanitizeLayout({ sections: { center: [{ id: "clock" }] } }, decls)
  assert.equal(clean.sections.start, undefined)
  assert.equal(clean.sections.end, undefined)
  assert.deepEqual(clean.sections.center, [{ id: "clock" }])
})
