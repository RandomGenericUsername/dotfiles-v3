// Cross-check: every named import in the AGS source tree must exist as an
// export in the module it is imported from. Catches the `ReferenceError: X is
// not defined` class that `ags bundle` exit 0 does NOT catch (dispatch contract
// trap T2 — it has twice killed the whole Bar window at runtime).
//
// Run from anywhere: ROOT is resolved relative to this file.
import fs from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const HERE = path.dirname(fileURLToPath(import.meta.url))
// tests/ -> icon-color-mapping-editor/ -> gui-tools/ -> src/ -> repo root
const REPO = path.resolve(HERE, "..", "..", "..", "..")
const ROOT = path.join(REPO, "dotfiles/config/ags")
const files = []
function walk(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name)
    if (e.isDirectory()) walk(p)
    else if (/\.(ts|tsx)$/.test(e.name)) files.push(p)
  }
}
walk(ROOT)

const exportsOf = new Map()
for (const f of files) {
  const src = fs.readFileSync(f, "utf8")
  const names = new Set()
  for (const m of src.matchAll(/export\s+(?:async\s+)?(?:function|const|let|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)/g)) names.add(m[1])
  for (const m of src.matchAll(/export\s*\{([^}]*)\}/g))
    for (const part of m[1].split(",")) {
      const seg = part.trim()
      if (!seg) continue
      const as = seg.split(/\s+as\s+/)
      names.add((as[1] ?? as[0]).trim())
    }
  exportsOf.set(path.resolve(f), names)
}

let problems = 0
for (const f of files) {
  const src = fs.readFileSync(f, "utf8")
  for (const m of src.matchAll(/import\s*\{([^}]*)\}\s*from\s*["'](\.[^"']+)["']/g)) {
    const spec = m[2]
    let target = path.resolve(path.dirname(f), spec)
    const candidates = [target + ".ts", target + ".tsx", path.join(target, "index.ts")]
    const resolved = candidates.find((c) => fs.existsSync(c))
    if (!resolved) continue
    const avail = exportsOf.get(path.resolve(resolved))
    for (const part of m[1].split(",")) {
      const seg = part.trim().replace(/^type\s+/, "")
      if (!seg) continue
      const name = seg.split(/\s+as\s+/)[0].trim()
      if (!avail.has(name)) {
        console.log(`MISSING: ${name} imported by ${f} from ${spec}`)
        problems++
      }
    }
  }
}
console.log(problems === 0 ? "SYMBOL CHECK OK" : `${problems} PROBLEM(S)`)
process.exit(problems === 0 ? 0 : 1)
