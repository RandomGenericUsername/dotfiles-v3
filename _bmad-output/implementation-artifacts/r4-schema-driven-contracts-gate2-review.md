# Gate 2 Review — R‑4 (Schema‑Driven Structural + Wire Contracts)

Status: APPLIED — all items resolved and verified (1019 passed, 2 skipped; ruff/mypy no new; layering green; spine lint 0; contract JSON valid; `make contracts-check` green).

## Applied

- **Items 1–3** non-object guard (`dict` check before version); kind assertion in the three loaders; kind-dispatched meta validation (same-kind errors name the field, unknown/missing kind falls back to the generic gate).
- **Item 4** the XML carries payload-schema links (`<annotation name="org.dotfiles.PayloadSchema">` on each `a{sv}` arg, asserted); the gate parses exactly one interface, compares node name↔`object_path`, asserts unique member/arg names + signature grammar, and a true mutation test executes the gate and must fail.
- **Item 5** event `event-contract.xml`+`.json` embedded under `runtime/adapters/schemas/` with byte-identity conformance; `contracts-check` now also runs the trigger-enum drift test.
- **Item 6** `event-contract.md` names XML as the wire source; `shared-data-contract.md` current/meta sections point at the machine definitions.
- **Items 7–10** lazy validators (`RuntimeError` on corrupt schema, tested); schema↔`domain/models` enum-drift test; `current.json` truth table (`monitors:null`, wrong-type, extra-key loud-fail) + `_validate_save` enforces the schema; meta writers validate (partial → load raises); dead `applied_at` branch removed. `fastjsonschema>=2.20,<3` pinned; validators annotated.

---

## Original review (pre-apply)

## Verification

- Full suite 1012 passed, 2 skipped; ruff/mypy no new; layering test green; `make contracts-check` 8 passed; spine lint 0.
- Panel: Blind Hunter = patches required; Edge Hunter = many; Acceptance Auditor = **REWORK** (AC1/AC2 pass; **AC3 partial**, **AC4 partial**, **AC5 fail on prose**).

## Blocking

### Item 1 — non-object `current.json` escapes as `AttributeError` (Blind 1)

**Problem:** `_dict_to_state` calls `data.get(...)` before any schema gate, so a valid-JSON non-object (`[1,2]`, `"foo"`, `42`, `null`) crashes with `AttributeError`, not the promised `ValueError`. Any `except ValueError` caller (CLI, reconcile, crash-recovery) misses it. The schema would have named the problem; the code never reaches it.

**Proposed patch:**
```python
    def _dict_to_state(self, data: dict[str, Any]) -> DesktopState:
        """Deserialize dict to DesktopState with validation."""
        if not isinstance(data, dict):
            raise ValueError(
                f"current.json invalid: top-level must be an object, got {type(data).__name__}"
            )
        # Schema version check FIRST (E3 fix)
        v = data.get("schema_version")
```

### Item 2 — cross‑kind `meta.json` escapes as `KeyError` (Blind 2)

**Problem:** `_validate_meta` uses a 4-way `oneOf`, so any schema-valid kind passes; each `load_*_entry` then indexes kind-specific keys (e.g. a wallpaper meta into `load_palette_entry` → `KeyError: 'entry_hash'`). The AC says errors name the field. Any consumer expecting `ValueError` gets a surprise.

**Proposed patch** (all three loaders; example for palette at `seeder.py:442`):
```python
        meta = self.read_entry_meta(entry_dir)
        _validate_meta(meta, entry_dir)
        if meta.get("kind") != "palette":
            raise ValueError(
                f"invalid cache meta.json in {entry_dir}: "
                f"expected kind 'palette', got {meta.get('kind')!r}"
            )
```
(Repeat `"effects"` in `load_effects_entry` and `"icons"` in `load_icons_entry`.)

### Item 3 — `oneOf` total failures name no field (Blind 3 + Edge 5)

**Problem:** any `oneOf` miss (missing `kind`, unknown `kind`, partial shape) collapses to `data must be valid exactly by one definition (0 matches found)`. AC1/AC2 demand "fails loud naming the field."

**Proposed patch:** when `kind` is a known string, validate against that definition (kind-dispatched), so the error names the field; fall back to the generic `oneOf` gate otherwise:
```python
_KIND_TO_DEFINITION = {
    "wallpaper": "#/definitions/wallpaper",
    "palette": "#/definitions/palette",
    "effects": "#/definitions/effects",
    "icons": "#/definitions/icons",
}

def _validate_meta(data: dict[str, Any], entry_dir: Path) -> None:
    kind = data.get("kind") if isinstance(data, dict) else None
    if kind in _KIND_TO_DEFINITION:
        import copy
        from runtime.adapters.contract_schemas import load_meta_schema
        schema = copy.deepcopy(load_meta_schema())
        schema.pop("oneOf", None)
        schema["$ref"] = _KIND_TO_DEFINITION[kind]
        validator = fastjsonschema.compile(schema)
        try:
            validator(data)
        except fastjsonschema.JsonSchemaValueException as exc:
            raise ValueError(
                f"invalid cache meta.json in {entry_dir}: {exc.message}"
            ) from exc
        return
    try:
        _META_VALIDATOR(data)
    except fastjsonschema.JsonSchemaValueException as exc:
        raise ValueError(f"invalid cache meta.json in {entry_dir}: {exc.message}") from exc
```
(Item 2's kind assertion handles the cross-kind case; this handles the same-kind case.)

### Item 4 — AC3 gaps: payload‑schema link + gate strength

**Problem:** `contracts/event-contract.xml` contains no link to the `a{sv}` payload schemas (no `$ref`/pointer to the JSON topics), and the conformance test is weak: it parses with `xml.etree` (accepting D-Bus-illegal signatures `a{svv}`, bare `v`, duplicates, missing `direction`, empty names), takes only the first `<interface>`, never compares node name vs `object_path`, and the negative test never actually runs the gate (would pass even if deleted).

**Proposed patch:**
- Add `<annotation name="org.dotfiles.PayloadSchema" value="event-contract.json#/topics"/>` to each `a{sv}` arg in the XML; extend the test to assert the annotation's presence.
- Strengthen the test: parse with a D‑Bus-aware parser (`dbus-fast Node.parse`, fallback reject), assert exactly one `<interface>`, unique member/arg names, signature-grammar validity; compare node name to `object_path`; rewrite the negative test to execute the gate against a mutated file and expect failure.
- Extend negative coverage: two interfaces, duplicate member names, an illegal signature, a renamed signal.

### Item 5 — AC4: embedded event contract + make target

**Problem:** AC4's "embed the event XML/JSON per side; embed gate" was not built — no runtime-side embedded copy of `event-contract.xml`/`.json`, no byte-identity test. Also `make contracts-check` omits the trigger-enum drift test.

**Proposed patch:** either embed the event XML/JSON per side with a conformance test (as AC4 says), or explicitly narrow AC4 (XML↔JSON conformance only, history+current+meta byte-identity already covered). Also add the trigger-enum drift test to the `contracts-check` target.

### Item 6 — AC5 prose refresh (never shipped)

**Problem:** `contracts/event-contract.md:8-10` still calls `event-contract.json` the single machine-checkable definition (contradicts XML-as-source); `shared-data-contract.md` `current.json`/`meta.json` sections have no machine-definition pointer. Only history `:52-54` has one.

**Proposed patch:** update both docs: XML is the wire source, JSON keeps topics/payloads/delivery; add machine-definition pointers for `current.schema.json`/`meta.schema.json`.

## Strong should‑fix (in one patch each)

### Item 7 — validators compiled at import

`_CURRENT_VALIDATOR`/`_META_VALIDATOR` are compiled at module import; a corrupt schema breaks `import` for every consumer, untested.

**Proposed patch:** lazy-compile (`@lru_cache def _validators()`), wrap schema-load errors in `RuntimeError("corrupt schema …")`, and add a test that monkeypatches the resource to garbage and asserts a loud failure.

### Item 8 — enum drift between schema and `domain/models.py`

`BackendType`/`FitMode` are re-declared in the schema (`:28-36`); nothing links them to `domain/models.py:14-31`.

**Proposed patch:** add `test_schema_enums_match_domain` asserting `set(schema backend enum)=={m.value for m in BackendType}` (same for `FitMode`).

### Item 9 — `current.json` v1/extra‑key truth table + save/load asymmetry

- True v1 (no `monitors`?) gets the version guard before migration — untested interaction; explicit `"monitors":null` untested; wrong-type `monitors` message changed silently; extra top-level keys now hard-reject (probed) with no forward-compat test.
- `_validate_save` (`:209-258`) has no schema call, so save/load are asymmetrically strict.

**Proposed patch:** parametrize the migration over absent/`null`; add a loud-fail test for extra keys; either run `_CURRENT_VALIDATOR` in `_validate_save` or acknowledge the asymmetry.

### Item 10 — write‑side hole + dead code

- `write_*_meta_in` accept any `artifact_hashes` dict, so a test can persist a 1-key meta that can never load. Validate in `_write_meta_json` or add a write-partial→load-raises test.
- `json_state_repository.py:419-422` (`applied_at` KeyError) is dead post-schema; wallpaper meta has no validating loader. Remove the dead branch; either validate the wallpaper read or drop the claim.

## Nice‑to‑have

- `fastjsonschema>=2.20` unbounded (v3 could move the exception module). Pin `fastjsonschema>=2.20,<3`, import the exception explicitly, add a test.
- mypy override is narrow and respected; annotate the compiled validators (`Callable[..., None]`) for strictness.

## Ballot (Approve / Request changes PER ITEM)

- Items 1–3 (typed errors for non-object current, cross-kind meta, and field-naming meta errors)?
- Item 4 (payload-schema link + strengthened event gate)?
- Item 5 (embedded event contract, or narrow AC4 + add trigger-enum to the target)?
- Item 6 (prose refresh)?
- Items 7–10 (lazy validators, enum-drift test, v1/extra-key truth table + save/load, write-side/dead-code)?
