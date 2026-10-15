import { describe, it } from "node:test"
import assert from "node:assert/strict"

import { createTheme, type CssSink } from "../../platform/ports/theme.ts"

/**
 * The `Theme` port (spine AD-13), driven by a fake CSS sink. These prove the
 * decision the port exists for: the adapter applies the STABLE palette pointer,
 * never a generation path (review F9), and it does so through the sink rather
 * than a direct `app.apply_css`.
 */

function fakeSink() {
  const applied: string[] = []
  const sink: CssSink = {
    apply(path) {
      applied.push(path)
    },
  }
  return { sink, applied }
}

describe("theme port", () => {
  it("applies the stable palette pointer through the sink", () => {
    const fake = fakeSink()
    const theme = createTheme("/cfg/ags/colors.css", fake.sink)
    theme.apply()
    assert.deepEqual(fake.applied, ["/cfg/ags/colors.css"])
  })

  it("applies exactly the path it was constructed with, not a generation path", () => {
    const fake = fakeSink()
    const theme = createTheme("/cfg/ags/colors.css", fake.sink)
    theme.apply()
    assert.equal(fake.applied[0].includes("current/"), false)
  })
})
