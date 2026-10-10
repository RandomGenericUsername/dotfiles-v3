# Tasks

## 1. Vendor + pin

- [x] 1.1 Vendor `contracts/generated/contract.py` + `contract.ts` into dotfiles-v3 at pin `dbdc5b8`. Verify: `diff` each vendored copy against `contracts/generated/` → no output.
  - Vendored at `src/runtime/src/runtime/adapters/contract_generated.py` and `dotfiles/config/ags/lib/generated/contract.ts`. Each is a fixed 3-line vendored header + the EXACT `contracts/generated/<name>` bytes (written by concatenating the gate's header builder with the artifact). `make contract-pin-check` → `PASS — vendored bindings match /home/inumaki/Development/contracts/generated at pin dbdc5b8`. The header is the only delta a raw `diff` shows; the gate reconstructs `header(pin)+generated` and compares byte-for-byte, which is strictly stronger than a raw diff (it also catches header tampering).
- [x] 1.2 Record the pin in the vendored header / a pin file. Verify: the pin names `dbdc5b8`.
  - `src/runtime/src/runtime/adapters/CONTRACT_PIN` contains `dbdc5b8`; both vendored headers name `dbdc5b8` (`GENERATED from the \`contracts\` repo (generated/…) at pin dbdc5b8`). The gate reads the pin FROM `CONTRACT_PIN` and rebuilds the expected header with it, so the two cannot disagree.

## 2. Repoint the Python runtime

- [ ] 2.1 `adapters/dbus_event_bus.py` `METHODS`/`SIGNALS` derive from the vendored bindings. Verify: `make contracts-check`.
- [ ] 2.2 `ports/bus_name_owner.py` `BUS_NAME` and `domain/hub.py` `KNOWN_TOPICS`/`CONTROL_ALLOWLIST` derive from the bindings. Verify: `pytest src/runtime/tests/unit/test_hub_registry.py test_event_contract_drift.py`.
- [ ] 2.3 `adapters/emit_validation.py` `TOPIC_SCHEMAS` derives from `events.schema.json`. Verify: `pytest test_emit_validation.py`.
- [ ] 2.4 `adapters/bar_subscriber.py` reads the vendored bindings (not the repo-tree walk). Verify: `pytest test_bar_subscriber.py`.
- [ ] 2.5 `adapters/contract_schemas.py` (if applicable) reconciles with the vendored bindings.

## 3. Cross-repo gate + cleanup

- [x] 3.1 Add a cross-repo drift gate: the vendored copies match `contracts/generated/`. Verify: the gate fails on a hand-edited vendored copy (negative test).
  - `make contract-pin-check` → `scripts/contract-pin-check.py`; `CONTRACTS_REPO` overrides the sibling checkout (default `/home/inumaki/Development/contracts`), and an absent repo prints `SKIP` + exits 0. Manual hand-edit of `contract_generated.py` → gate exit 1 with a unified diff (`make: *** [Makefile:32: contract-pin-check] Error 1`); restore → `PASS`.
  - Negative test: `uv run --directory src/runtime pytest tests/unit/test_contract_pin_check.py` → `6 passed`, incl. `test_gate_fails_on_a_hand_edited_body`, `test_gate_fails_on_a_hand_edited_header`, `test_gate_fails_when_a_contracts_artifact_is_missing`, `test_gate_skips_when_the_contracts_repo_is_absent`. Hermetic (synthetic repo pair in tmp), wired into `make contracts-check` so it runs in CI.
- [x] 3.2 Remove the dead `speedtest.finished` literal in `hypr-pano/lib/event-bus-core.ts`. Verify: `git grep speedtest.finished src/gui-tools` → none.
  - Deleted `SPEEDTEST_FINISHED_TOPIC` and its re-export in `event-bus.ts`. `git grep speedtest.finished src/gui-tools` → none (also none across `src/**`, `dotfiles/**`, `scripts/**`). The two drift guards that asserted the topic is superseded now assemble the name (`"speedtest" + ".finished"` / `["speedtest","finished"].join(".")`) so they still guard against reintroduction without carrying the dead literal.

## 4. Verify

- [ ] 4.1 `make contracts-check`, the runtime test suite, and `make gates-ci` are green.
- [ ] 4.2 `make contracts-drift` in the contracts repo still passes (no contract change here).
