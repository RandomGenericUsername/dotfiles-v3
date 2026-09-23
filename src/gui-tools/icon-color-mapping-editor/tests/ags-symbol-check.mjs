// Cross-check, two directions: (1) every named import in the AGS source tree
// must exist as an export in the module it is imported from; (2) every
// free identifier USED in a file must be defined or imported there. Catches the
// `ReferenceError: X is not defined` class that `ags bundle` exit 0 does NOT
// catch (dispatch contract trap T2 — it has repeatedly killed the whole Bar
// window at runtime; direction (2) caught the `playbackStreams` import drop).
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
// Direction (2): identifiers used in a file must be defined or imported.
// Heuristic scope is intentionally narrow to avoid false positives: collect
// top-level definitions (functions/consts/classes/types/enums/interfaces),
// named + default + namespace imports, JSX component names are covered by
// their function definitions, and property accesses (a.b) only count `a`.
const GLOBALS = new Set([
  "console", "JSON", "Math", "Number", "String", "Boolean", "Array", "Object",
  "Map", "Set", "Promise", "Error", "RegExp", "Date", "undefined", "NaN",
  "Infinity", "parseInt", "parseFloat", "isNaN", "isFinite", "setTimeout",
  "clearTimeout", "setInterval", "clearInterval", "queueMicrotask",
  "TextDecoder", "TextEncoder", "URL", "URLSearchParams", "fetch", "performance",
  "structuredClone", "Blob", "FormData", "Headers", "Request", "Response",
  "Uint8Array", "Uint16Array", "Uint32Array", "Int8Array", "ArrayBuffer",
  "DataView", "BigInt", "Proxy", "Reflect", "WeakMap", "WeakSet", "Symbol",
  // TypeScript utility types (appear in annotations, never values).
  "Record", "Partial", "Pick", "Omit", "Exclude", "Extract", "ReturnType",
  "Parameters", "Awaited", "NonNullable", "Readonly",
])
const JSX_RUNTIME = new Set(["Astal", "Gtk", "Gdk", "GLib", "Gio", "Wp"])
const TS_KEYWORDS = new Set(
  ("const,let,var,function,return,if,else,for,while,do,switch,case,break,continue," +
    "new,typeof,instanceof,in,of,try,catch,finally,throw,await,async,import,export," +
  "from,default,null,true,false,this,super,void,delete,as,satisfies,interface,type,enum," +
  "implements,extends,static,get,set,string,number,boolean,any,unknown,never,object," +
  "symble,symbol,bigint,undefined").split(","),
)

for (const f of files) {
  const raw = fs.readFileSync(f, "utf8")
  // Strip block comments, template literals, strings, THEN line comments — in
  // that order, so `//` inside a string (e.g. `gi://AstalBattery`) never eats
  // the rest of the line including the import itself. JSX text between tags is
  // left in place (it rarely contains bare identifiers, and a missed one is
  // safer than noise).
  const src = raw
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/`(?:\\.|[^`\\])*`/g, "``")
    .replace(/'(?:\\.|[^'\\\n])*'/g, "''")
    .replace(/"(?:\\.|[^"\\\n])*"/g, '""')
    // Regex literals: only a `/` in EXPRESSION position (after `(`, `=`, `,`,
    // `:`, `return`, `[`, `!`, `&`, `|`, `?`, `;`, `{`, `}`) can start one —
    // division follows an operand. Their contents (`GDBus`, char-class
    // fragments like `Za`) are not identifier uses. `//` comments (slash
    // followed by slash, or `Node/Port`-style slashes inside comments) never
    // match because `/` is not in the predecessor set.
    .replace(/(^|[(=,:;{\[!&|?]\s*)\/(?![*/])(?:\\.|[^\n\\/[]|\[[^\]\n]*\])+\/[gimsuy]*/gm, "$1 ")
    .replace(/\/\/[^\n]*/g, " ")
  const defined = new Set(GLOBALS)
  const params = new Set()
  const addParamList = (list) => {
    for (const p of list.split(",")) {
      const name = p.trim().split(/[\s=:]+/)[0].replace(/[{}\[\]]/g, "")
      if (/^[A-Za-z_$][\w$]*$/.test(name)) params.add(name)
    }
  }
  for (const m of src.matchAll(/^\s*(?:export\s+(?:default\s+)?)?(?:async\s+)?(?:function|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)/gm)) defined.add(m[1])
  // Object-method shorthand (`requestHandler(...) {...}`) and indented
  // function declarations: a name at line start (after optional `async`)
  // whose parens close into `{` is a definition, not a call. Control keywords
  // are excluded so `if (x) {` never masks a use of `x`.
  for (const m of src.matchAll(/^\s*(?:(?:private|public|protected|static|async|readonly|override)\s+)*(?:get\s+)?([A-Za-z_$][\w$]*)\s*\(([^;{}]*)\)\s*(?::\s*[^{};]+?)?\s*[\{;]/gm)) {
    if (/^(if|for|while|switch|catch|with|else)$/.test(m[1])) {
      addParamList(m[2].replace(/^(?:const|let|var)\s+/, ""))
      continue
    }
    defined.add(m[1])
    addParamList(m[2])
  }
  // Top-level AND function-scope const/let (indented), including destructured
  // `const { a, b } = …` and `const [a, setA] = …` forms (createState pairs!).
  for (const m of src.matchAll(/^\s*(?:export\s+)?(?:const|let)\s+([\{[][^}\]]*[\}\]]|[A-Za-z_$][\w$]*)/gm)) {
    const head = m[1].trim()
    if (head.startsWith("{") || head.startsWith("[")) {
      for (const part of head.slice(1, -1).split(",")) {
        const nm = part.trim().split(/\s+as\s+/).pop().split(/[:=]/)[0].trim()
        if (/^[A-Za-z_$][\w$]*$/.test(nm)) defined.add(nm)
      }
    } else defined.add(head)
  }
  // NOTE: string literals are stripped above, so the `from` path is empty here;
  // `[^"']*` (not `+`) is required or no import is ever matched.
  for (const m of src.matchAll(/import\s*\{([^}]*)\}\s*from\s*["'][^"']*["']/g))
    for (const part of m[1].split(",")) {
      const seg = part.trim().replace(/^type\s+/, "")
      if (!seg) continue
      const bits = seg.split(/\s+as\s+/)
      defined.add((bits[1] ?? bits[0]).trim())
    }
  for (const m of src.matchAll(/import\s+([A-Za-z_$][\w$]*)\s+from\s*["'][^"']*["']/g)) defined.add(m[1])
  for (const m of src.matchAll(/import\s+\*\s+as\s+([A-Za-z_$][\w$]*)/g)) defined.add(m[1])
  for (const m of src.matchAll(/import\s+([A-Za-z_$][\w$*]*)\s*,\s*\{/g)) if (m[1] !== "*") defined.add(m[1])
  // `function f(a, b)` params (the method-shorthand loop above already covered
  // those) and `(a, b) =>` arrows (including `_`-prefixed throwaway params).
  // The `=>` MUST follow the parens — otherwise call arguments would be masked.
  for (const m of src.matchAll(/function\s+[A-Za-z_$][\w$]*\s*\(([^)]*)\)/g)) addParamList(m[1])
  for (const m of src.matchAll(/\(([^()]*)\)\s*=>/g)) addParamList(m[1])
  // `for (const x of …)` / `for (let i …)` loop variables are bindings.
  for (const m of src.matchAll(/for\s*\(\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s+(?:of|in)\b/g)) params.add(m[1])
  // Destructured params (`{ visible }`, `{ a, b: c }`): harvest every
  // identifier inside braces as in-scope (they are bindings, not uses).
  for (const m of src.matchAll(/\(\s*\{([^}]*)\}\s*[^)]*\)\s*(?::\s*[^{};]+?)?\s*(?:=>|\{)/g)) {
    for (const ident of m[1].matchAll(/([A-Za-z_$][\w$]*)/g)) {
      if (!TS_KEYWORDS.has(ident[1])) params.add(ident[1])
    }
  }
  // Direction (2), deliberately narrow: flag CALL expressions `name(` whose
  // callee is not defined, imported, a parameter, or a known global. Every
  // runtime ReferenceError this codebase has hit (`nodeName`,
  // `streamAppIconPathForIdentity`, `playbackStreams`) was a call — while JSX
  // tags, props (`visible=`, `onClicked=`), object keys, and type positions
  // are never followed by `(`, so they produce zero noise. Bare (uncalled)
  // references are covered indirectly: direction (1) pins every import, and a
  // value passed without ever being called is rare in this codebase.
  // `new X(` is included (a missing class is the same defect).
  for (const m of src.matchAll(/(^|[^\w$.])([A-Za-z_$][\w$]*)\s*\(/gm)) {
    const name = m[2]
    if (defined.has(name) || params.has(name) || JSX_RUNTIME.has(name)) continue
    if (TS_KEYWORDS.has(name)) continue
    console.log(`UNDEFINED CALL: ${name} in ${f}`)
    problems++
  }
}
console.log(problems === 0 ? "SYMBOL CHECK OK" : `${problems} PROBLEM(S)`)
process.exit(problems === 0 ? 0 : 1)
