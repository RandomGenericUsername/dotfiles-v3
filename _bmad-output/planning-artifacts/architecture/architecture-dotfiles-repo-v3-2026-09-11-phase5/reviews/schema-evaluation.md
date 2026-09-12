# Schema / Contract Enforcement Evaluation — dotfiles-repo-v3

- **Role:** integration / adversarial evaluator (does not edit spines or prototypes)
- **Decision:** which schema strategy (A JSON Schema+ajv, B D-Bus introspection XML, C compact source+generator) fits the *actual* repo
- **Evidence base:** `src/runtime/`, `src/provisioning/ansible/roles/{cli_tools,compositor_configs,gui_tools,verify}/`, `dotfiles/config/ags/`, `src/gui-tools/`, `contracts/`, `shared-data-contract.md`, `ARCHITECTURE-SPINE.md` (AD-33..AD-44), phase-5 `.memlog.md`, `reviews/review-contract.md`, live host probes (`gjs 1.88.1`, `ags 3.1.0`)

---

## Verdict

**Hybrid — B for the D-Bus wire contract, A/JSON-Schema for structural files and `a{sv}` payloads. Use C's regenerate-and-diff idea only as an in-repo drift test; do not adopt a runtime codegen pipeline.**

There is no single source format that both worlds can *natively* execute. GJS has built-in D-Bus introspection (`Gio.DBusNodeInfo.new_for_xml` — verified present as a function under gjs 1.88.1) and built-in `JSON`, but **no JSON Schema validator and no npm/node at build or runtime**. Python has no D-Bus introspection validator and no built-in JSON Schema. The honest split is therefore by *medium*, not by tool preference.

---

## 1. Repo constraints that decide this

| Constraint | Evidence | Consequence |
| --- | --- | --- |
| AGS/GJS has **no npm, no package.json, no node build** | only `package.json` in repo is `.opencode/package.json`; `compositor_configs`/`gui_tools` copy `.tsx`/`.ts` per-file to the spine; `ags run` bundles TS at startup; `ags bundle` used only in a dev Makefile (`src/gui-tools/icon-color-mapping-editor/Makefile:9`) | `ajv`/`jsonschema` in JS is **not reachable** without introducing a package manager + build step the provisioning chain does not have. Option A's JS leg is dead on arrival for the bar. |
| GJS **does** have built-in D-Bus validation | `Gio.DBusNodeInfo.new_for_xml` is a function (live probe); bar already uses `Gio.DBusProxy.new_for_bus` (`dotfiles/config/ags/bar/widgets/battery.tsx:42`) and Astal GObject bindings (`network.tsx:1-6`) | Option B gives real, dependency-free enforcement on the GJS side. This is the strongest single fact in the decision. |
| GJS has built-in `JSON` but no schema validator | `typeof JSON === "object"`, `typeof JSON.parse === "function"` (live probe) | Bar can parse payloads but cannot validate them; enforcement must live in the Python hub. |
| Runtime is Python 3.14, `uv tool install` from the repo path | `cli_tools/tasks/main.yml:65-89` installs `dotfiles-runtime` from `src/runtime` via `uv tool install`, then `--force` re-pins **every bootstrap**; `pyproject.toml` deps = `typer`, `cli-output` (local path) | Python-side runtime deps are cheap to change (add to `pyproject.toml` + `uv.lock`) but **each new dep is a new PyPI download**; the repo has no wheelhouse/vendor dir. |
| No `jsonschema`, `pydantic`, or D-Bus client installed | `.venv/lib/python3.14/site-packages/` contains none | A requires adding a dep; the current runtime style is stdlib dataclasses + `TypedDict` + `StrEnum` + hand-written strict validation (`domain/models.py`, `adapters/desired_state_reader.py`). |
| Two worlds deploy by **different mechanisms** | bar = ansible per-file `template`/`copy` + `ags quit && ags run`; runtime = `uv tool install`; `contracts/` is copied by **neither** (grep: no role references `contracts/` or `event-contract`) | A shared contract *file* is a version-skew vector. The contract should be **embedded** in each side, with a repo test as the gate — not copied at provision time. |
| Runtime is re-pinned from current source every bootstrap; bar copied per file | `cli_tools/tasks/main.yml:84-89`; `gui_tools/vars/main.yml:60-97` | Skew is normal, not exceptional. Interface-name versioning (`Events1`/`Events2`) is the only existing mitigation and it only covers the D-Bus contract. |
| AD-44 already requires one machine-checkable definition | `ARCHITECTURE-SPINE.md:106-110` | The strategy must satisfy this, including for `current.json`, `meta.json`, the backstop record, the intent document, and the trigger enum. |
| The current "rung 2" is already insufficient | `event-contract.json` encodes `a{sv}` payloads as bare letter types, with no required/enum/range fields — `review-contract.md` H4 finds the hub's "reject non-conforming Emit" **unimplementable** from it; H5 finds equality drift tests contradict additive evolution | A names-only JSON is not a machine-checkable definition under AD-44. |
| Trigger enum is already triplicated **and inconsistent** | `reconcile.py:68` = `{seed,set,reconcile,force,regenerate,doctor}` (**missing `prune`**); `inspect.py:71` = same **plus `prune`**; `seeder.py:818` docstring = seven values; `shared-data-contract.md:45` = four | The AD-44 defect is live. `reconcile` would reject the `prune` value the spine now requires. This is the migration's first, dependency-free win. |

---

## 2. Approach-by-approach fit

### A — JSON Schema + Pydantic, consumed by `jsonschema` and `ajv`

- **Structural files (Python only): good.** JSON Schema is the correct executable description of `current.json`, `meta.json`, the backstop record, and `desired.json`. `jsonschema` is pure Python; one dep; enforces on read *and* write. This part should be adopted.
- **Cross-world event contract (JS leg): fails the repo.** `ajv` cannot be imported by AGS: no npm dependency, no build step that runs npm, and GJS resolves `gi://`, not `node_modules`. Vendoring `ajv` into the bundled source is possible in principle but adds an unowned JS dependency tree to a codebase that deliberately has none.
- **Pydantic: unnecessary.** The domain already uses frozen dataclasses; pydantic would add a second model system and a heavy dep without changing enforcement. Generated pydantic models also couple the contract to the runtime's model layer, which AD-34 explicitly forbids (core depends on the port, not the transport/contract library).
- **Net:** adopt the JSON Schema *format* for structural files; drop the ajv/Pydantic framing.

### B — D-Bus introspection XML, `Gio.DBusNodeInfo` / Python

- **GJS leg: best possible fit.** Zero deps, native, already the codebase's idiom. `Gio.DBusNodeInfo.new_for_xml` parses the interface; the same `Gio.DBusInterfaceInfo` drives `Gio.DBusConnection.register_object` (hub side) and proxy construction (consumer side). It validates method/signal **names and D-Bus type signatures** exactly as the wire enforces them — something `event-contract.json` cannot do.
- **Python leg: adequate.** `xml.etree.ElementTree` parses introspection XML; the hub can drive dispatch/registration from it. It is client-library-agnostic, which dissolves the memlog's reason for rejecting codegen ("a generator would couple the contract to an unchosen client library" — `memlog:44`): standard XML does not.
- **Gap:** introspection XML **cannot express `a{sv}` payload internals**, enums, ranges, or required keys (`a{sv}` is opaque by design). This is exactly `review-contract.md` H4. B alone does **not** satisfy AD-44 for topic payloads.
- **Net:** adopt as the wire source; pair it with JSON Schema for payload internals.

### C — compact single source + tiny generator → JSON Schema + Python + TS, regenerate-and-diff

- **The only true "single source."** It removes the real duplication: the interface/member names currently live in `event-contract.json`, the MD tables, the future XML, Python constants, and TS types.
- **But the TS output is types only.** The AGS bundler strips types at startup; generated TS gives **no runtime validation** on the bar. GJS-side runtime enforcement still requires `Gio.DBusNodeInfo` (i.e. you still need the XML). So C does not eliminate B; it wraps it.
- **No JS test runner exists.** `regenerate-and-diff` and "a drift test per language" (AD-44, `event-contract.md:9-10`) cannot run *in GJS*. Any JS-side drift check must be a Python test that reads/parses the TS source (textual subset assertion). C's promise of a symmetric per-language drift gate is not achievable here.
- **Owns bespoke tooling + a build hook.** The repo has no build phase for the bar; generated TS would have to be committed (regenerate-and-diff in CI) or generated by a provisioning task. The prior architecture decision explicitly rejected owning a generator for cost reasons (`memlog:41`, `:44`), and that cost calculus is still right for one contract.
- **Net:** do not adopt as a pipeline now. Hold it as a contingency with a stated trigger (§6).

### Decision matrix

| Contract class | A (JSON Schema) | B (introspection XML) | C (generator) |
| --- | --- | --- | --- |
| D-Bus methods/signals/signatures | weak (no JS executor) | **native on GJS, parseable in Python** | wraps B; adds build hook |
| D-Bus topic payload `a{sv}` / enums / ranges | **right tool (hub-side Python)** | cannot express | can emit both |
| Structural files (`current.json`, `meta.json`, …) | **right tool** | not applicable | overkill |
| Trigger enum / code constants | JSON Schema `$ref` or code constants | not applicable | can emit |
| Drift gate across worlds | Python `jsonschema` + doc/table test | Python XML parse + GJS source scan | regenerate-and-diff (but no JS runner) |

---

## 3. Single executable source per contract type

| Contract | Single executable source | Enforcer (runtime) | Notes |
| --- | --- | --- | --- |
| D-Bus interface: bus/object/interface, methods, signals, type signatures, versioning, errors | **`contracts/event-contract.xml`** (D-Bus introspection XML) | GJS `Gio.DBusNodeInfo`; Python `xml.etree` + hub dispatch | The wire truth. The hub can also serve it via `org.freedesktop.DBus.Introspectable`, which lets consumers detect `Events1`/`Events2` **live** instead of trusting a copied file. |
| D-Bus topic payload internals (`a{sv}` required keys, variant signatures, enums, ranges, units) | **`contracts/event-payloads.schema.json`** (JSON Schema), referenced from the XML by an `org.dotfiles.PayloadSchema` annotation | Python hub (`jsonschema`) on every `Emit` | This is the missing half of the current `event-contract.json` (H4). GJS never validates it; the bar is a thin consumer and the hub is the sole structural validator (AD-38). |
| `current.json`, `meta.json`, backstop record, `desired.json` | **`contracts/schemas/*.schema.json`** (JSON Schema) | Python `jsonschema` on read **and** write, fail-loud | Bar does not read these; no JS leg needed. Keeps `schema_version` migration-on-read. |
| History trigger enum + `history.jsonl` line shape | **one Python module** (`runtime/domain/contracts.py`) as code constants; the JSON Schema `$ref`s the enum | Runtime writers/validator + drift test | AD-44 explicitly allows code constants. This deletes the triplication at `reconcile.py:68` / `inspect.py:71` / `seeder.py:818`. |
| Prose (`shared-data-contract.md`, `event-contract.md`) | descriptive only; tables generated from, or value-asserted against, the definitions | repo test | Satisfies AD-44's "prose is descriptive". |

Rationale for two files (XML + payload schema) rather than one: the D-Bus wire and JSON payload are different type systems. Options A/B each cover only one; C would fuse them but at the cost ruled out in §2. The XML→schema annotation keeps a single reference root without a generator.

---

## 4. How an artifact reaches both worlds, and version skew

**Do not copy the contract file at provision time.** `cli_tools` (`uv tool install`) and `compositor_configs`/`gui_tools` (per-file copy) are independent deployment paths; a shared copied file would add a third skew axis and violate "neither world depends on the other's code." Instead:

- **Python world:** the schema + XML are **embedded in the `dotfiles-runtime` package** and re-pinned from repo source on every bootstrap (`cli_tools/tasks/main.yml:84-89`). The hub validates `Emit` against them.
- **GJS world:** the bar embeds only what it needs — the interface name and member metadata (hand-written or generated-and-committed) used to construct proxies/variants. It can additionally call `Introspect` on the live hub to confirm the interface version. This is GJS's native path and needs no npm.
- **Repo test is the gate**, run in CI/dev, asserting: XML ↔ Python constants ↔ GJS source names ↔ prose tables. Because there is no JS test runner, the GJS assertion is a Python test that parses the `.tsx`/`.ts` sources (textual subset check), not a run in GJS.
- **Skew handling.** Additive method/signal/topic/optional field stays on `Events1`; removed/retyped/newly-required → `Events2`, and the hub may serve both interfaces (already pinned in AD-34). Structural files carry `schema_version` and migrate on read (pattern already in `current.json` v1→v2 and `desired.json` `version:1`). The drift test asserts **subset**, not equality, on the consumer side, so an old bar is not broken by an additive hub change (`review-contract.md` H5).

---

## 5. Migration path from the hand-written contracts

Ordered so each step ships independently and the first is dependency-free.

1. **Single-source the trigger enum (no new dep).**
   Create `runtime/domain/contracts.py` with the `seed|set|reconcile|regenerate|doctor|prune|reactive` enum (per `AD-42`) as the only definition. Point `reconcile.py`, `inspect.py`, and `seeder.py` at it. Add a test that parses `shared-data-contract.md` and `event-contract.md` tables and asserts they equal the constant. **This fixes the live bug where `reconcile` rejects `prune`.**

2. **JSON Schema for structural files (one new Python dep).**
   Add `jsonschema` to `src/runtime/pyproject.toml` + `uv.lock`. Author `contracts/schemas/{current,meta-wallpaper,meta-palette,meta-effects,meta-icons,backstop,intent}.schema.json`. Enforce on **read and write**; keep the symlink/spoof policy in code (`desired_state_reader.py`). Retire the hand-rolled field checks that the schema now covers. Validate `meta.json` variants by `kind`.

3. **Introspection XML for the wire contract.**
   Author `contracts/event-contract.xml` from the current `event-contract.json` (methods, signals, type signatures, errors, versioning). Wire the Python hub/adapter to register from it; expose `Introspect`. On the GJS side, switch the bar's consumer to construct `Gio.DBusInterfaceInfo` via `Gio.DBusNodeInfo.new_for_xml` (or a committed metadata module) and validate variant construction. Delete `event-contract.json` once the XML + payload schema supersede it (the JSON is currently the only definition and is the one H4/H5 find uncheckable).

4. **JSON Schema for topic payloads.**
   Move each topic's `a{sv}` shape into `contracts/event-payloads.schema.json` `$defs` with `required`/`enum`/`range`/unit annotations; reference from the XML. The hub rejects non-conforming `Emit` with a typed error (`review-contract.md` C1/H4 decisions the spine already adopted). Consumers ignore unknown topics/keys (subset semantics).

5. **Drift gate + rebuild.**
   One repo-level test suite: XML parses; schemas are valid; Python constants match; **GJS source scan** matches member names; prose tables match. Add to CI and to provisioning `verify`. Because contracts are embedded per side, provisioning needs no new copy task.

6. **Contingency — C.**
   If contract count or name-duplication grows past a threshold (e.g. >2 contracts, or a name required in >3 places), introduce a generator that emits XML + JSON Schema + Python constants + committed TS types, and replace step-3/4 hand-maintenance with regenerate-and-diff in the same test. Trigger condition, not a default.

---

## 6. Trade-offs and where this recommendation is wrong

- **Two sources for the event contract (XML + payload schema).** This is the honest cost of the two-type-system reality. It is contained by one XML→schema annotation reference and one drift suite. A single source is only achievable by C, which then owns a generator and still gets no GJS runtime validation.
- **`jsonschema` is a new runtime dep.** The repo has no vendoring/wheelhouse, so bootstrap must be online (it already is: it downloads `uv` and resolves from PyPI via `uv.lock`). If the project ever needs fully offline provisioning, `jsonschema` must be vendored or replaced by a tiny generated validator — this is the main condition that would force C (self-contained emitted validators).
- **GJS validation is construction/parse, not payload enforcement.** The bar never runtime-validates payloads; it trusts the hub. That is consistent with AD-38 (hub is the sole structural validator) but means a compromised/misbehaving hub can send a shape the bar mis-renders. Acceptable under the trusted same-user model; if the trust model changes (unix socket + `SO_PEERCRED` per AD-38), rego/JSON-Schema-in-GJS would need vendoring.
- **The prior "rung 2, no codegen" decision is partially overridden.** It is overridden only for the *format* of the D-Bus source (JSON → introspection XML, because JSON cannot express the wire) and only for structural files (prose → JSON Schema). The rejection of owning a custom generator stands.

`R-1` below is the minimum change that fixes an existing defect; if only one thing ships, ship it.

**R-1:** single-source the history trigger enum and make `reconcile`/`inspect` agree; add the doc-drift test.
