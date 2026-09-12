# Review — single-source codegen for runtime↔shell contracts (Option C)

Prototype: `spikes/codegen/`. Single source: `spikes/codegen/contract.json`.
Generator: `spikes/codegen/gen.py`. Check: `spikes/codegen/check.sh`.
Companion options: `reviews/schema-evaluation.md` (A/B/C fit), `reviews/schema-dbus-xml.md` (B).

## Verdict

**C works, and C does not win.** The executable claim holds: one source generates
JSON Schema + Python + TypeScript, drift is caught by running `check.sh`, and both
runtime validators pass. But at this repo's contract count the generator is more
code than the duplication it removes, and it still cannot give the AGS/GJS side
runtime validation. The hybrid already recommended (D‑Bus introspection XML for the
wire surface, JSON Schema for payload internals, a single **code constant** for the
history trigger enum) is cheaper and equally executable. Keep C as a contingency,
not a pipeline.

## What runs (evidence)

```
bash spikes/codegen/check.sh        # pass
```

```
1/6 drift check BEFORE regeneration ...... no drift
2/6 regenerate from contract.json ........ 4 files
3/6 drift check AFTER regeneration ....... no drift
4/6 ensure JS toolchain
5/6 Python runtime validation (jsonschema) PASS: history + events fixtures match expected verdicts
6/6 JS runtime validation (ajv) + TypeScript (tsc --noEmit)  PASS / [tsc] PASS
ALL CHECKS PASSED
```

Hand-edit of `generated/contract.ts` (`prune` → `prne`) then `check.sh`:

```
== 1/6 drift check BEFORE regeneration (catches hand-edited artifacts) ==
-export const HISTORY_TRIGGERS = [..., "prune"] as const;
+export const HISTORY_TRIGGERS = [..., "prne"] as const;
DRIFT: generated/ differs from the tracked baseline (hand edit?).
exit 1
```

Additive evolution probe (append `"reactive"` to `contract.json`, regenerate):

```
typecheck.ts(40,13): error TS2322: Type '"reactive"' is not assignable to type 'never'.
tsc exit=2
```

All three are real: every verdict comes from executing `jsonschema`, `ajv`, `tsc`,
and `git diff`, not from reading a doc.

## What the prototype actually covers

Single source `contract.json` (93 lines) covers exactly two things:

- **History line**: 7 pinned fields + optional typed `details`, trigger enum, with
  per-trigger `details` shapes (`prune`/`regenerate`/`doctor`) and a guard that
  forbids `details` on triggers that declare none.
- **Event interface**: bus/path/interface names, 9 methods (in/out member
  signatures), 5 signals, 6 typed errors, 3 topic payloads with an enum on
  `capture.state.state`.

Generated (1,269 lines total): `history.schema.json` (233), `events.schema.json`
(780), `contract.py` (143), `contract.ts` (113).

Runtime enforcement is asymmetric, exactly as `schema-evaluation.md` predicted:

- **Python** — `jsonschema` validates against the generated schema on every fixture
  (good passes, bad fails). Pure-Python, one added dep.
- **JS/TS** — `ajv` compiles the **same** generated schema and validates the same
  fixtures; `tsc --noEmit` compiles the generated types plus `typecheck.ts`. This is
  a **CI/developer check only**. `dotfiles/config/ags/` has no `package.json`/
  `tsconfig.json`; `ags bundle`/`ags run` strip types at startup. The bar gets zero
  runtime validation from generated TS and would still need `Gio.DBusNodeInfo`
  (Option B) for that.

## Does it beat (a) hand-written schema?

**History line: marginally, and not via the generator.** The value is collapsing a
live four-place duplication into one definition. The trigger enum today is:

- `reconcile.py:68` `_VALID_TRIGGERS` = 6 values, **missing `prune`** (live bug),
- `inspect.py:71` `_VALID_HISTORY_TRIGGERS` = 7 values,
- `seeder.py:818` docstring = 7 values,
- `shared-data-contract.md:45` = 7 values (working tree; the committed file says 4).

`contract.json` is authoritative on 7. But a plain Python constant
(`runtime/domain/contracts.py`) fixes all four with **no generator and no new
format**, is importable/executable, and can be asserted against a hand-written JSON
Schema. `spikes/json-schema/` already proved that JSON Schema + `jsonschema` + `ajv`
+ a runtime-parity test works. Codegen adds ~500 lines of `gen.py` to save ~10
duplicated lines. Not repaid for one contract.

**Event interface: no.** Names/signatures are already single-sourced by
introspection XML, which is a real interchange format with native parsers on both
sides (`Gio.DBusNodeInfo.new_for_xml` in GJS; `dbus-fast` in Python — both proven in
`reviews/schema-dbus-xml.md`). `contract.json` is a bespoke IDL that **neither**
runtime consumes; it must be generated *back* into both. The hard part — `a{sv}`
payload internals, enums, required keys (review-contract H4) — is hand-authored in
the JSON Schema regardless. Generating Python/TS constants on top saves little.

## Does it beat (b) full codegen?

No, and the prototype is deliberately not full codegen. A real "full codegen"
adoption would still need to add:

1. generated validators (not just schemas/types) wired into the Python hub,
2. a GJS-side validator — impossible from npm (`ajv` is unreachable in GJS), so
   still XML + `Gio`,
3. a build/provisioning hook so `generated/` cannot be stale,
4. deterministic formatting so generated Python passes the repo's own gates.

That last point is already violated by this prototype: `uvx ruff check --select
E,F,I,N,W,UP,B` on `generated/contract.py` reports **8 errors** (1 × I001 import
sort, 1 × UP007 `Union` → `|`, 6 × E501 up to 185 chars). Adopting generated Python
means either teaching the generator ruff/`ruff format`-clean emission or excluding
`generated/` from linting. Full codegen is a larger commitment than the contract
count justifies.

## The true source

There is no single medium both worlds natively execute, so "one true source" is
only true relative to whatever you can regenerate. Concretely:

- For the **wire interface** the true source is **introspection XML** (Option B):
  both runtimes parse it directly and it is the only form that expresses D‑Bus type
  signatures. A bespoke `contract.json` is a *generator input*, not a runtime
  source.
- For **structural files** (`current.json`, history lines, topic payloads) the true
  source is **JSON Schema**, executable by `jsonschema` and `ajv`.
- For the **trigger enum** the true source should be a **Python code constant**;
  AD‑44 explicitly permits code constants, and it deletes the four-place
  duplication with no build step.

`contract.json` fuses all three into a fourth format. If adopted it must become the
artifact of record and the XML, JSON Schema, `.py`, and `.ts` must all be declared
generated — otherwise the repo goes from 3 copies to 5.

## Effort measured

| Artifact | Lines |
| --- | --- |
| `gen.py` | 500 (435 non-blank/non-comment) |
| `contract.json` (source) | 93 |
| `validate_py.py` + `validate_js.mjs` | 120 |
| `typecheck.ts` + `tsconfig.json` + `package.json` | 74 |
| `check.sh` | 47 |
| fixtures | 29 |
| **generated** (`history.schema.json`, `events.schema.json`, `contract.py`, `contract.ts`) | 1,269 |

`gen.py` is ~5× the source it reads. Most of it is two separate schema emitters and
two code emitters (JSON Schema, Python, TypeScript), plus a type registry — one-off
cost, but it is a real one-off cost that must be maintained as the contract evolves.

## Type coverage that is missing

The prototype maps only a slice of D‑Bus, and that slice is silent about the rest:

- **Signatures covered**: `s`, `u`, `i`, `x`, `d`, `b`, `a{sv}`, `a{ss}`, `as`, `v`.
- **Not covered**: `y`/`n`/`q`/`t` (byte/int16/uint16/uint64), `h` (fd), `o`
  (object path), `g` (signature), structs `(...)`, nested containers
  (`aa{sv}`, `a{sa{sv}}`, `a(ss)`), dicts with non-string keys, and arrays of
  structs. Any of these used by the hub would not round-trip.
- **`a{sv}` interim**: method args and signal members are validated only as
  `{"type": "object"}`. `DomainEvent.payload` and `GetTopicState.state` are opaque;
  the topic registry is typed, but a producer can still put any variant type in the
  map. This is precisely H4 and codegen does not close it.
- **`int64` (`x`) → TypeScript `number`**: JS cannot represent full int64 safely.
  `capture.state.elapsed_seconds` is `x`; fine for seconds, latent for anything
  larger.
- **`format: date-time` is annotation-only**: `ajv` warns `unknown format
  "date-time" ignored`; `jsonschema` is built without a `FormatChecker`. `ts` is
  *not* actually enforced as ISO‑8601 by either validator today.
- **`a{sv}` variants**: the source records the D‑Bus signature but not the chosen
  `v` type per payload entry, so nothing checks that `down_mbps` arrives as `d` and
  not `i` on the wire. (This prototype validates the JSON projection, not the wire.)

## What breaks on evolution

- **Additive enum growth breaks strict consumers** (demonstrated: TS2322 on
  `never`). This directly contradicts AD‑34 and review-contract H5, which require
  additive changes to be non‑breaking and drift tests to assert *subset*, not
  equality. Generated exhaustive types force lockstep releases.
- **`additionalProperties: false`** in the generated schema means a producer that
  adds an optional field is rejected by any consumer still running the old
  generated schema. Forward compatibility depends on regenerating both sides.
- **Removing/renaming a trigger or member** is a compile/lint error on both sides —
  good for safety, but it removes the independent-migration window the contract's
  `Events1`/`Events2` policy exists to provide.
- **Drift detection requires committed artifacts.** `git diff --exit-code` is
  vacuous if `generated/` is untracked or generated at provision time. This
  prototype stages `generated/` to make the mechanism real; in CI it must be
  committed, and the check must run before regeneration too (otherwise a local hand
  edit is silently overwritten and the check passes). `check.sh` now diffs both
  before and after regeneration.
- **Generated Python does not satisfy the repo's gate** (8 ruff errors: I001, UP007,
  6 × E501 — see above).
- **Source drift already exists**: `contract.json` has 7 triggers including
  `prune`, while the live `reconcile.py:68` has 6. If C were adopted today it would
  immediately flag a real bug — which is an argument for the constant, not the
  generator.

## Dependency / build / provisioning implications

- **Python (`uv`)**: the generator is stdlib-only. Validators need `jsonschema`
  (pure Python). If the hub ever enforces `Emit` structurally, `jsonschema` becomes
  a runtime dep in `src/runtime/pyproject.toml` + `uv.lock`; `cli_tools` re-pins
  `uv tool install` from source on every bootstrap and already fetches from PyPI, so
  one more dep is cheap but not offline. `spikes/codegen` uses `uv run --with
  jsonschema` (ephemeral, no lockfile change) for the spike only.
- **AGS/GJS (`ags bundle`)**: no npm, no `package.json`, no node build in
  `dotfiles/config/ags`; provisioning copies `.tsx`/`.ts` per file and AGS strips
  types at startup. Generated TypeScript therefore yields **no runtime
  enforcement**; it is editor/CI aid only. Committing generated `.ts` into the AGS
  tree would create a new skew axis unless regenerated in CI — the exact problem
  being solved. Adding node/npm to provisioning just to run `ajv`/`tsc` introduces a
  toolchain the repo deliberately does not have.
- **CI/dev**: `check.sh` requires `node` + `npm` (ajv, typescript) **and** `uv` +
  `jsonschema`. The repo currently has no JS test runner; this is a new CI
  dependency. Option A's JS leg and Option C's JS check share this cost.
- **Generated-code ownership**: 1,269 generated lines to review in diffs; must be
  excluded from `ruff`/formatting gates or emitted gate-clean.

## Recommendation

1. **Do not adopt C as a pipeline now.** The 500-line generator, committed artifacts,
   npm-in-CI, and generated-code lint exclusions are not repaid for one history
   schema and one event interface.
2. **Do adopt the executable mechanism if/when the trigger fires**: this prototype
   proves regenerate-and-diff plus dual validators is viable. Trigger it when names
   are required in >2 contracts or >3 places, per `schema-evaluation.md §6`.
3. **Immediate wins (dependency-free)**: single-source the trigger enum as
   `runtime/domain/contracts.py` (fixes `reconcile` rejecting `prune`); add the
   doc-drift test.
4. **Interface**: introspection XML as the wire source (native on both sides) + JSON
   Schema for topic payload internals; enforce payloads in the Python hub, not the
   bar.
5. If C is ever adopted, **generate from the XML**, not a new IDL — otherwise the
   "single source" is a fifth format rather than the one both worlds already parse.

## How to run

```sh
cd /home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3
bash spikes/codegen/check.sh                 # full pass; exit 1 on drift/validation failure

python3 spikes/codegen/gen.py                # regenerate only
node spikes/codegen/validate_js.mjs          # ajv only
uv run --with jsonschema spikes/codegen/validate_py.py   # jsonschema only
spikes/codegen/node_modules/.bin/tsc --noEmit -p spikes/codegen/tsconfig.json
```

Prerequisites: `python3` (stdlib) for generation; `node`+`npm` (install in
`spikes/codegen` via `npm install`) for ajv/tsc; `uv` + `jsonschema` for the Python
validator. `generated/` must be committed for the drift check to be non-vacuous.

## Files

- `spikes/codegen/contract.json` — single source
- `spikes/codegen/gen.py` — generator
- `spikes/codegen/generated/{history.schema.json,events.schema.json,contract.py,contract.ts}`
- `spikes/codegen/{validate_py.py,validate_js.mjs,typecheck.ts,tsconfig.json,package.json}`
- `spikes/codegen/fixtures/{history.good.jsonl,history.bad.jsonl,events.good.json,events.bad.json}`
- `spikes/codegen/check.sh`
- `reviews/schema-codegen.md` (this file)
