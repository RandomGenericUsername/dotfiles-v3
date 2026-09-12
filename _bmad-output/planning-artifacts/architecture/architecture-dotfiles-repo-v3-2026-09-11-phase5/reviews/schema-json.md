# Schema-as-Single-Source Spike — `history.jsonl` / `current.json`

Status: prototype complete, executed. Prototype lives in `spikes/json-schema/`.

## Verdict

One neutral, hand-written JSON Schema (draft 2020-12) **is** a viable single
source of truth across languages: the same `history.schema.json` validated the
same 17-case corpus to **identical verdicts** under `python-jsonschema` and
`ajv`, and the same held for the 6-case `current.json` sketch. The "execute to
check" property holds for that claim.

It does **not** yet hold as a claim about the Python runtime. The shipped
parser disagrees with the schema on **5/17 history cases** and **1/6 current
cases**. So today the JSON Schema is a prospective source of truth, not an
enforced one: nothing in `src/runtime` reads a schema file. Adopting it means
replacing the hand-rolled checks with a real validator; the neutral schema is
the right artifact to do that from. Pydantic is a legitimate *derived* Python
binding, not the source (see F3); TypeScript has no runtime type story here.

## Evidence (executed)

```bash
cd spikes/json-schema
npm install            # vendored ajv 8.20
./conformance.sh       # core: both validators, history + current → PASS (exit 0)
./conformance.sh --full # + pydantic-generated schema + runtime parity → FAIL (exit 1, by design)
```

- `out/core-run.log` — `CONFORMANCE: PASS`; `[history] agreement: identical
  verdicts for 17 cases`; `[current] agreement: identical verdicts for 6 cases`.
- `out/full-run.log` — `CONFORMANCE: FAIL`; the failure is entirely the
  runtime-parity and pydantic stages, which is the finding.
- Python stage ran under `uv run --python 3.14 --with jsonschema` (the repo
  requires `>=3.14` and uses PEP 758 `except A, B:` syntax). JS stage ran
  `node js_validate.mjs` against a local `ajv@8`.
- `generated/history.ajv.standalone.cjs` — `npx ajv-cli compile` output; a
  dependency-free validator (`require(...)` then call; returns `true/false`
  with `.errors`). Confirmed good→`true`, bad trigger→`false`.

Two good / bad examples from the Python run (same on the JS side):

```
[python-jsonschema] PASS good-seed-minimal
[python-jsonschema] PASS bad-unknown-top-key  <root>: Additional properties are not allowed ('apply' was unexpected)
[python-jsonschema] PASS bad-trigger   trigger: 'apply' is not one of ['seed','set',...,'prune']
[python-jsonschema] PASS bad-palette-type  palette: 5 is not of type 'string', 'null'
[python-jsonschema] PASS bad-details-removed-negative  details/removed: -1 is less than the minimum of 0
```

## Top findings

### F1 — Neutral schema is genuinely cross-language (strongest result)
`spikes/json-schema/history.schema.json` is the only artifact both sides need.
`python_validate.py` (`jsonschema.Draft202012Validator`) and
`js_validate.mjs` (`ajv/dist/2020.js`) produced identical verdict maps (the
`verdicts` objects in `out/python.history.json` and `out/js.history.json` are
equal; the files differ only in validator metadata) across required fields,
`additionalProperties:false`, the trigger enum, `string|null` unions, and
`details` (`removed/failed >= 0`, `layers: string -> int>=0`). Error *wording*
differs, error *verdicts* do not. The schema deliberately does **not** pin
`ts`/`wallpaper` to hex/ISO — matching the runtime's documented "history is
never hex-validated" policy (`inspect.py:90-109`).

### F2 — The Python runtime does not enforce the schema today (the real gap)
`InspectHistoryUseCase._parse_record` (`src/runtime/src/runtime/application/inspect.py:485`)
checks key set, trigger enum, and top-level types, but only asserts that
`details` is a `dict` with string keys — it never inspects its values. Probed
against the shipped code via `python_runtime_parity.py`:

| case | schema | runtime |
|---|---|---|
| `bad-details-removed-string`, `...negative`, `layers-value`, `unknown-key` | reject | **accept** |
| `details: null` | reject | **accept** |
| everything else (missing field, unknown key, bad trigger, wrong types) | agrees | agrees |

`current.json`: `JsonStateRepository._dict_to_state` (`json_state_repository.py:274`)
tolerates an absent `monitors` key (treats it as `{}`) while the doc/sketch
require it. Hex + ISO checks it does perform are absent from the history schema
by design, but present for `current.json` (schema uses `^[0-9a-f]{64}$`).

### F3 — Pydantic generates a *Python-flavoured* schema, not the neutral one
`pydantic_generate.py` → `generated/history.pydantic.schema.json`. Both
validators consume it fine (so Ajv-consuming-Python-generated-schema works
mechanically). But `model_json_schema()` maps `X | None = None` to
`anyOf: [X, null]`, so the generated schema **allows `details: null`,
`removed: null`, `failed: null`, `layers: null`** where the neutral schema
forbids them — this is exactly the `divergence-null-details` case, and it is
why `--full` fails only that one case for the pydantic path. The chattier
output (`anyOf`, `title`, `default`) is cosmetic; nullability is semantic.
Pydantic is fine as a **derived** binding (codegen from the schema, or a
drift test asserting `model_json_schema()` is equivalent modulo nulls), but
making it the source forces the TS side to inherit Python's optional-null
idiom. Net: neutral file > Pydantic as source.

### F4 — No JS/AGS consumer exists yet; Ajv-standalone is the bridge
Grep found no `.ts/.tsx/.js/.lua` consumer of `current.json`/`history.jsonl`
in `dotfiles/config/ags/` (only a comment in `hypr/autostart.lua`). Ajv is a
Node library and will not run as-is under AGS's GJS runtime. The realistic
runtime path is `ajv-cli compile` (or `ajv/standalone`) → a generated
dependency-free module, demonstrated in `generated/history.ajv.standalone.cjs`.
For CI/Node, plain `ajv` is sufficient.

### F5 — `additionalProperties:false` vs append-only evolution is a real tension
The log is immutable and lives forever. A new top-level field (e.g. the
planned `reactive` trigger, `shared-data-contract.md:59-60`) cannot be added
without old strict validators rejecting new lines, and adding an enum value is
equally breaking for readers. The schema's `$id`/filename version and the
`current.json` `schema_version: const 2` field are the only version handles;
`history.jsonl` currently has none (`inspect.py:98-99`). See Versioning.

## Runtime enforcement (not just tests)

- **Python, history:** load `history.schema.json` once at import; in
  `_parse_record`, replace the manual checks with
  `Draft202012Validator.iter_errors(obj)` and convert errors to the existing
  `ValueError("history.jsonl line N: ...")`. Per-line cost is tens of
  microseconds; history reads are already bounded. Requires adding
  `jsonschema` to `src/runtime/pyproject.toml` (currently only `typer`,
  `cli-output`). A Pydantic alternative reuses `pydantic>=2` (already a
  provisioning dep) but must reconcile the nullability in F3.
- **Python, current.json:** same treatment in `_validate_save` /
  `_dict_to_state`. The sketch's `if/then` cleanly expresses the cross-field
  rule "`mpv_options`/`ipc_socket` only for `mpvpaper`" (`json_state_repository.py:233`,
  `:328`) — the schema is strictly more complete than the hand-rolled checks.
- **JS/AGS:** at read time, call the vendored standalone validator; on invalid
  input, degrade to "no state" rather than crash (mirrors the read-only,
  never-crash inspect posture). Node CI uses `ajv` directly via
  `js_validate.mjs`.
- **Both:** `conformance.sh --full` is the drift gate: it must stay green, and
  today it is red exactly where runtime and schema disagree.

## Versioning / evolution

- Keep `schema_version` in `current.json` as the gate (`const: 2`);
  `history.jsonl` has no version field, so its schema is versioned by filename
  (`history.schema.json` → `history.schema.v2.json`) and the reader picks the
  validator. Without this, strict `additionalProperties:false` makes any
  additive field silently unreadable by old binaries.
- Enum growth (`reactive`) is a breaking reader change under the current
  strict schema. Options: version the schema, or relax the enum to `string`
  plus a separate known-values check with a warn-and-keep policy for forward
  compatibility. Pick one; the shared-data-contract currently says only "it's
  a shared-contract change".
- `$id` is currently `https://dotfiles.local/...` (offline namespace). Fine for
  local tooling; do not fetch it.

## Dependencies / network

- Python: `uv run --with jsonschema` pulled 6 wheels; `--with pydantic` 10.
  Runtime adoption means locking these (uv) — an additive, offline-after-lock
  dependency. No compile step (jsonschema is pure Python; `referencing`/`rpds`
  are the transitive deps). Accessing `$ref`s would need `referencing`, already
  pulled.
- JS: `npm i ajv` pulled 5 packages; `npx ajv-cli` pulled a deprecation-laden
  tree but only at codegen time. Ship the generated standalone validator so the
  AGS runtime needs **zero** network and **zero** node_modules.
- `ts` fixture values were generated with a one-off `python3` snippet; not a
  dependency.

## Does "execute to check" hold?

- Cross-validator agreement: **yes** — `./conformance.sh` exits 0 and proves
  both maintained validators agree on the shared corpus.
- Schema⇔runtime conformance: **no** — `--full` exits 1 on 5 history + 1
  current divergence. The probe imports the *actual* shipped code
  (`InspectHistoryUseCase._parse_record`, `JsonStateRepository._dict_to_state`),
  not a copy, so this is a true conformance signal.

## Recommendation

1. Make `spikes/json-schema/history.schema.json` the canonical artifact (move
   under `contracts/`), version it, and wire `conformance.sh --full` into CI as
   the gate once stage 1 is green for real.
2. Replace `_parse_record`'s manual validation with the schema validator so
   Python and Ajv share one truth (this closes F2). Do the same for current.json.
3. Keep Pydantic as a derived binding only; add a drift test that regenerates
   the schema and fails if it diverges from the canonical file (accounting for
   the `anyOf`/null mapping in F3).
4. Vendor the Ajv standalone validator for AGS and add the first real
   `current.json` reader there.
5. Decide the history-evolution policy (named schema versions vs relaxed enum)
   before `reactive` lands.

## Files

```
spikes/json-schema/
  history.schema.json            canonical neutral schema (draft 2020-12)
  current.schema.json            current.json v2 sketch
  fixtures/history.cases.json    17-case shared corpus (expected verdicts)
  fixtures/current.cases.json    6-case shared corpus
  fixtures/history.good.jsonl    valid lines (human-facing)
  fixtures/history.bad.jsonl     invalid lines (human-facing)
  python_validate.py             jsonschema validator → out/python.<tag>.json
  js_validate.mjs                ajv validator → out/js.<tag>.json
  python_runtime_parity.py       shipped-parser conformance probe (history|current)
  pydantic_generate.py           model_json_schema() → generated/history.pydantic.schema.json
  conformance.sh                 executable gate (core | --full)
  generated/                     pydantic schema + ajv standalone validator
  out/                           captured verdict maps + run logs
reviews/schema-json.md           this report
```
