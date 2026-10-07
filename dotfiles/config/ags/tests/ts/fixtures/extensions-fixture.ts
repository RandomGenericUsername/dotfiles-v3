// Extensionless-import fixture for the resolve-hook test.
//
// This module exists so `resolve-hooks.test.ts` can import it the way AGS
// sources import each other -- `./extensions-fixture`, no suffix -- and prove
// the hook does what its header claims. Without a real fixture the hook would
// be untested infrastructure, which is exactly the kind of thing that silently
// stops working after an unrelated refactor and takes a whole suite with it.
//
// It is deliberately trivial. Its only job is to be imported.

export const FIXTURE_VALUE = "resolved-without-a-suffix"