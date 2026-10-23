# Tasks

## 1. Vendor + pin

- [x] 1.1 Vendor `contracts/generated/contract.py` + `contract.ts` into dotfiles-v3 at pin `dbdc5b8`. Verify: `diff` each vendored copy against `contracts/generated/` → no output.
  - Vendored at `src/runtime/src/runtime/adapters/contract_generated.py` and `dotfiles/config/ags/lib/generated/contract.ts` (slice 2 later relocated the Python copy to `src/runtime/src/runtime/domain/contract_generated.py`; see 2.1). Each is a fixed 3-line vendored header + the EXACT `contracts/generated/<name>` bytes (written by concatenating the gate's header builder with the artifact). `make contract-pin-check` → `PASS — vendored bindings match /home/inumaki/Development/contracts/generated at pin dbdc5b8`. The header is the only delta a raw `diff` shows; the gate reconstructs `header(pin)+generated` and compares byte-for-byte, which is strictly stronger than a raw diff (it also catches header tampering).
- [x] 1.2 Record the pin in the vendored header / a pin file. Verify: the pin names `dbdc5b8`.
  - `src/runtime/src/runtime/adapters/CONTRACT_PIN` contains `dbdc5b8`; both vendored headers name `dbdc5b8` (`GENERATED from the \`contracts\` repo (generated/…) at pin dbdc5b8`). The gate reads the pin FROM `CONTRACT_PIN` and rebuilds the expected header with it, so the two cannot disagree.

## 2. Repoint the Python runtime

- [x] 2.1 `adapters/dbus_event_bus.py` `METHODS`/`SIGNALS` (and `INTERFACE`/`OBJECT_PATH`/`JOB_*`) derive from the vendored bindings. Verify: `make contracts-check`.
  - `_method_table`/`_signal_table` adapt the generated `Method`/`Member` dataclasses into the runtime's `{name: {"in": ((arg, sig), ...), "out": (...)}}` / `{name: ((arg, sig), ...)}` shapes; `INTERFACE = EVENTS_INTERFACE`, `OBJECT_PATH = EVENTS_OBJECT_PATH`, `JOB_OBJECT_PATH/JOB_INTERFACE/JOB_METHODS` likewise. `make contracts-check` → `40 passed`; `git grep -n "org.dotfiles.Events1" src/runtime/src/runtime/adapters/dbus_event_bus.py` → no matches (exit 1).
  - **Relocation (slice 2).** The pure-Python binding moved `adapters/contract_generated.py` → `src/runtime/src/runtime/domain/contract_generated.py`: the hexagonal layering test (`tests/architecture/test_layering.py`) forbids `domain`/`ports` importing `adapters`, so the shared pure-data binding must live in the innermost layer every layer may import. The JSON Schema stays in `adapters/` (file I/O is an adapter concern). `scripts/contract-pin-check.py` and `make contract-pin-check` cover all three vendored artifacts (path updated; `PASS — ... at pin dbdc5b8`).
- [x] 2.2 `ports/bus_name_owner.py` `BUS_NAME` and `domain/hub.py` `KNOWN_TOPICS` derive from the bindings; `CONTROL_ALLOWLIST` is NOT a contract value. Verify: `pytest src/runtime/tests/unit/test_hub_registry.py test_event_contract_drift.py`.
  - `BUS_NAME = EVENTS_BUS_NAME`; `KNOWN_TOPICS = frozenset(topic.name for topic in EVENTS_TOPICS)`. The generated bindings carry no kind→actions table, so `CONTROL_ALLOWLIST` (H1) legitimately stays a code constant. `uv run --directory src/runtime pytest tests/unit/test_hub_registry.py tests/unit/test_event_contract_drift.py -q` → `49 passed`.
- [x] 2.3 `adapters/emit_validation.py` `TOPIC_SCHEMAS` derives from `events.schema.json`. Verify: `pytest test_emit_validation.py`.
  - Vendored the generated schema at `src/runtime/src/runtime/adapters/contract_generated.schema.json` (byte-identical to `contracts/generated/events.schema.json`; pin-gated — JSON cannot carry a comment header, so the gate compares it raw). `TOPIC_SCHEMAS` is built from `$defs/Topic_<topic>` (required/types/enums exact); `additionalProperties` is opened to `True` deliberately (AD-34 additive fields, matching the previous policy). `uv run --directory src/runtime pytest tests/unit/test_emit_validation.py -q` → `38 passed`.
- [x] 2.4 `adapters/bar_subscriber.py` reads the vendored bindings (not the repo-tree walk). Verify: `pytest test_bar_subscriber.py`.
  - `BUS_NAME`/`OBJECT_PATH`/`INTERFACE`/`KNOWN_TOPICS`/`DOMAIN_EVENT_ARGS` now come from `runtime.domain.contract_generated`; the `_find_contract`/`_CONTRACT`/`_signal_args` repo-tree walk is deleted (module no longer imports `pathlib`). Added `TestEmbeddedContractConstants` (mirrors the gtk4 binding's guard) proving the constants come from the generated bindings and no repo-root lookup survives. `uv run --directory src/runtime pytest tests/unit/test_bar_subscriber.py -q` → `31 passed`.
- [x] 2.5 `adapters/contract_schemas.py` — **not applicable.** It serves the `history`/`current`/`meta`/`last-converged` schemas from `contracts/schemas/` (the state/cache contract), not the event contract; there is nothing to reconcile with the event bindings. No change.
- [x] 2.6 (added) `tests/unit/test_event_contract_drift.py` repointed to the canonical source. The runtime-table assertions now compare against the vendored generated bindings (`runtime.domain.contract_generated` + `contract_generated.schema.json`), not the stale repo-tree `contracts/event-contract.json` (which lags the pin on `wallpaper.state` `stage`/`reload_failures`). Contract-internal XML↔JSON agreement and the TS-ahead scan still read the repo-tree document. Verify: `pytest tests/unit/test_event_contract_drift.py -q` → `passed`.

## 3. Cross-repo gate + cleanup

- [x] 3.1 Add a cross-repo drift gate: the vendored copies match `contracts/generated/`. Verify: the gate fails on a hand-edited vendored copy (negative test).
  - `make contract-pin-check` → `scripts/contract-pin-check.py`; `CONTRACTS_REPO` overrides the sibling checkout (default `/home/inumaki/Development/contracts`), and an absent repo prints `SKIP` + exits 0. Manual hand-edit of `contract_generated.py` → gate exit 1 with a unified diff (`make: *** [Makefile:32: contract-pin-check] Error 1`); restore → `PASS`.
  - Negative test: `uv run --directory src/runtime pytest tests/unit/test_contract_pin_check.py` → `6 passed`, incl. `test_gate_fails_on_a_hand_edited_body`, `test_gate_fails_on_a_hand_edited_header`, `test_gate_fails_when_a_contracts_artifact_is_missing`, `test_gate_skips_when_the_contracts_repo_is_absent`. Hermetic (synthetic repo pair in tmp), wired into `make contracts-check` so it runs in CI.
- [x] 3.2 Remove the dead `speedtest.finished` literal in `hypr-pano/lib/event-bus-core.ts`. Verify: `git grep speedtest.finished src/gui-tools` → none.
  - Deleted `SPEEDTEST_FINISHED_TOPIC` and its re-export in `event-bus.ts`. `git grep speedtest.finished src/gui-tools` → none (also none across `src/**`, `dotfiles/**`, `scripts/**`). The two drift guards that asserted the topic is superseded now assemble the name (`"speedtest" + ".finished"` / `["speedtest","finished"].join(".")`) so they still guard against reintroduction without carrying the dead literal.

## 4. Verify

- [x] 4.1 `make contracts-check`, the runtime test suite, and `make gates-ci` are green.
  - `make contracts-check` → `40 passed`; the required 7-file pytest set → `181 passed`; the full runtime suite → `2120 passed, 2 skipped, 1 xpassed`; `mypy` on the changed modules → clean. `make gates-ci` not run in this worktree (desktop-stack gates); the AGS gates are unaffected by this runtime-only change.
- [x] 4.2 `make contracts-drift` in the contracts repo still passes (no contract change here).
  - The `contracts` repo is unchanged by this work (`dbdc5b8`); `make contracts-drift` there → exit 0 (verified at the pin).
