# R‑4: Schema‑Driven Structural + Wire Contracts (Hybrid)

Status: done

baseline_commit: 34721ba

Gate 1: approved (enforce on read; v1 migrate-then-validate; XML in contracts + Python conformance now/GJS later; conformance via make/tests). Gate 2: applied — Items 1–10 incl. a re-validation Update (AD-33..44 refinements, event contract with job registry/epoch/seq/lease/control/errors, capture elapsed push, watched-root recursion, trigger enum single-sourced). `ARCHITECTURE-SPINE.md` status `final`; contract JSON valid; `make contracts-check` green.

Epic: Phase 5 prerequisite remediation (AD‑44; adopts the validated hybrid).

## Story

As a maintainer,
I want the remaining cross‑boundary contracts machine‑defined and executed,
so `current.json`, `meta.json`, and the D‑Bus wire can't drift from their docs —
the way the history contract already can't (R‑1/R‑2).

## Context

R‑1 made `history.jsonl` schema‑enforced. The rest still rely on hand‑written
parsing + prose (`shared-data-contract.md`): `current.json` v2
(`JsonStateRepository._dict_to_state`, incl. a v1→v2 migration), the per‑layer
`meta.json` shapes (`CacheSeeder`), and the D‑Bus event contract
(`contracts/event-contract.json` + `.md`), whose interface is currently pinned in
JSON, not a D‑Bus‑native source.

The validated hybrid (AD‑44) says:
- **D‑Bus wire** → one **introspection XML** (`contracts/event-contract.xml`),
  parsed/enforced by GJS natively + Python via a declared signature table;
  `a{sv}` payload shapes → JSON Schema referenced from the XML.
- **Structural files** → one **JSON Schema**, enforced at runtime by the Python
  readers/tests.
- Conformance is checked by **executing** a script; contracts embedded per side +
  gated by a repo test.

## Acceptance Criteria

1. `contracts/schemas/current.schema.json` (draft‑07) defines `current.json` v2 (`schema_version: 2`, `wallpaper`, `monitors`, `palette`/`effects`/`icons` nullable, `applied_at`); the reader **migrates a v1 dict to v2 then validates**, and a malformed v2 value/job fails loud naming the field — hand‑written field checks replaced. (AC 1)
2. `contracts/schemas/meta.schema.json` (draft‑07) defines the per‑layer `meta.json` shapes; the meta readers validate against it, replacing hand‑written checks. (AC 2)
3. `contracts/event-contract.xml` is the **wire interface source** (methods/signals/member types); `contracts/event-contract.json` keeps topics/payload schemas/delivery semantics and its `methods`/`signals` blocks are pinned to the XML by an **executable conformance script**. (AC 3)
4. A repo conformance test/script verifies every embedded copy equals its canonical schema (as history does), and a `make`/CI target runs the conformance checks by execution — no prose‑reading assertions. (AC 4)
5. No behavior change for valid state: existing `current.json`/`meta.json` and the event contract round‑trip; the `shared-data-contract.md` prose is refreshed to point at the machine definitions. (AC 5)

## Tasks / Subtasks

- [ ] Author `contracts/schemas/current.schema.json` + `meta.schema.json`; embed copies under `runtime/adapters/schemas/` (byte‑identical conformance) (AC: 1, 2, 4)
- [ ] Validate `current.json` on read (migrate v1→v2 first) and `meta.json` in the readers via `fastjsonschema`; delete the hand‑written field checks (AC: 1, 2)
- [ ] Author `contracts/event-contract.xml`; add a Python conformance script that parses it and asserts the JSON `methods`/`signals` blocks match; reference the `a{sv}` payload schemas from the XML (AC: 3)
- [ ] Embed the event XML/JSON per side; conformance test (AC: 3, 4)
- [ ] Wire a `make`/CI target that runs the conformance scripts (AC: 4)
- [ ] Refresh `shared-data-contract.md` + `event-contract.md` prose (descriptive pointers) (AC: 5)
- [ ] Tests: v1 migration validates; malformed current/meta fail loud with the field; XML↔JSON conformance passes and fails when edited; run `pytest` + `ruff` + `mypy` + `test_layering.py`

## Dev Notes

- **Reuse the prototypes:** `spikes/json-schema` (current.schema prototype) and `spikes/dbus-xml` (introspection XML + Python/GJS parsers). Adapt; don't re‑invent.
- **Layering:** schemas/loader live in `adapters/` (as R‑1); domain stays pure. Validation is I/O‑adjacent → adapters.
- **Migration:** `current.json` v1 (no `monitors`) must still read; migrate the dict, then validate v2.
- **D‑Bus side:** GJS enforcement (`Gio.DBusNodeInfo`) lands with the bar work (epic 5‑2/5‑4); R‑4 authors the XML + Python conformance now.
- **AD‑44:** prose is descriptive; the definitions are authoritative.

## Gate‑1 sub‑decisions

1. **Enforce `current.json`/`meta.json` on read via schema (recommended, mirrors R‑1) vs schema+tests only?**
2. **v1 migration:** migrate dict→v2 then validate (recommended) vs a lenient schema that allows both.
3. **Event wire:** promote `event-contract.xml` to `contracts/` and keep topics/semantics in JSON (recommended) — confirm we author + Python‑conformance now, GJS later.
4. **Conformance target:** a `make contracts-check` (or extend the existing test suite) that runs the scripts — where should it live?
