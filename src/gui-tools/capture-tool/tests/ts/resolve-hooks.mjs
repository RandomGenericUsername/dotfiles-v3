// Resolve hook for the domain unit tests (workstream A4's runner, extended in
// A6 for `domain/cli-args.ts`).
//
// WHY THIS EXISTS. `ags bundle` resolves extensionless relative imports
// (`./ui-state`), because the app is BUNDLED and the bundler does the
// resolving. `node --test` runs the `.ts` files directly through Node's
// built-in type stripping, and Node's ESM resolver does no extensionless
// lookup at all — hence the explicit `.ts` suffixes the test FILES use
// (`tsconfig.tests.json` sets `allowImportingTsExtensions` for exactly that).
//
// Until A6 the domain modules only imported each other's TYPES, which
// type-stripping erases, so nothing was left to resolve at runtime. A6's
// `domain/cli-args.ts` calls `isGif()` and reads `GIF_SIZE_ARG` — real value
// imports — so the extensionless `./ui-state` import inside the domain now
// has to survive Node's resolver.
//
// Two honest ways out, and this picks one:
//
//   a) rewrite intra-domain imports as `./ui-state.ts`. That would make the
//      APP source look like the tests, and would need `allowImportingTsExtensions`
//      in tsconfig.capture.json, weakening the app's own config to serve the
//      test runner;
//   b) teach the test runner the one thing the bundler already does. The app
//      keeps idiomatic extensionless imports, and the workaround stays in
//      test-only infrastructure where it belongs.
//
// (b) is this file. It appends `.ts` to a relative specifier that misses and
// otherwise defers entirely to Node. Scratch-only concern: it is NOT part of
// the bundled app and does not appear in `gui_tools_app_files`.
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
