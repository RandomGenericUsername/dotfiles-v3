// Resolve hook for the ags config's pure-module unit tests.
//
// WHY THIS EXISTS. `ags bundle` resolves extensionless relative imports
// (`./presentation`), because the app is BUNDLED and the bundler does the
// resolving. `node --test` runs the `.ts` files directly through Node's
// built-in type stripping, and Node's ESM resolver does no extensionless
// lookup at all -- hence the explicit `.ts` suffixes the test FILES use
// (`tsconfig.tests.json` sets `allowImportingTsExtensions` for exactly that).
//
// WITHOUT this hook, the modules UNDER TEST are also unreachable in AGS style:
// a pure module written the way ags sources are written imports its siblings
// as `./other`, and that specifier dies at runtime under `node --test`.
//
// Two honest ways out, and this picks the same one the capture tool's
// resolve-hooks.mjs picks:
//
//   a) rewrite intra-module imports as `./other.ts`. That would make the APP
//      source look like the tests, and would need `allowImportingTsExtensions`
//      in whatever config typechecks the app, weakening it to serve the runner;
//   b) teach the test runner the one thing the bundler already does. The app
//      keeps idiomatic extensionless imports, and the workaround stays in
//      test-only infrastructure where it belongs.
//
// (b) is this file: it appends `.ts` to a relative specifier that misses and
// otherwise defers entirely to Node. It is NOT part of the bundled app and is
// deliberately absent from `compositor_configs_skeleton_files` -- placement
// there is per-file, so an unregistered file simply never deploys.
//
// Registered via `module.registerHooks` (synchronous, same thread) rather than
// the deprecated async `module.register`.

import { registerHooks } from "node:module"
import { fileURLToPath } from "node:url"
import { existsSync } from "node:fs"

const HAS_EXTENSION = /\.[cm]?[jt]sx?$/

registerHooks({
  resolve(specifier, context, nextResolve) {
    if ((specifier.startsWith("./") || specifier.startsWith("../")) && !HAS_EXTENSION.test(specifier)) {
      try {
        const resolved = nextResolve(`${specifier}.ts`, context)
        // Guard against a bare nextResolve() that returns a URL without having
        // verified existence.
        if (resolved.url.startsWith("file:")) {
          const path = fileURLToPath(resolved.url)
          if (existsSync(path)) return resolved
        }
      } catch {
        // fall through to the default resolution below
      }
    }
    return nextResolve(specifier, context)
  },
})