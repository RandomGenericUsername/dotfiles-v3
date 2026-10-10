# Tasks

## 1. Vendor + pin

- [ ] 1.1 Vendor `contracts/generated/contract.py` + `contract.ts` into dotfiles-v3 at pin `dbdc5b8`. Verify: `diff` each vendored copy against `contracts/generated/` → no output.
- [ ] 1.2 Record the pin in the vendored header / a pin file. Verify: the pin names `dbdc5b8`.

## 2. Repoint the Python runtime

- [ ] 2.1 `adapters/dbus_event_bus.py` `METHODS`/`SIGNALS` derive from the vendored bindings. Verify: `make contracts-check`.
- [ ] 2.2 `ports/bus_name_owner.py` `BUS_NAME` and `domain/hub.py` `KNOWN_TOPICS`/`CONTROL_ALLOWLIST` derive from the bindings. Verify: `pytest src/runtime/tests/unit/test_hub_registry.py test_event_contract_drift.py`.
- [ ] 2.3 `adapters/emit_validation.py` `TOPIC_SCHEMAS` derives from `events.schema.json`. Verify: `pytest test_emit_validation.py`.
- [ ] 2.4 `adapters/bar_subscriber.py` reads the vendored bindings (not the repo-tree walk). Verify: `pytest test_bar_subscriber.py`.
- [ ] 2.5 `adapters/contract_schemas.py` (if applicable) reconciles with the vendored bindings.

## 3. Cross-repo gate + cleanup

- [ ] 3.1 Add a cross-repo drift gate: the vendored copies match `contracts/generated/`. Verify: the gate fails on a hand-edited vendored copy (negative test).
- [ ] 3.2 Remove the dead `speedtest.finished` literal in `hypr-pano/lib/event-bus-core.ts`. Verify: `git grep speedtest.finished src/gui-tools` → none.

## 4. Verify

- [ ] 4.1 `make contracts-check`, the runtime test suite, and `make gates-ci` are green.
- [ ] 4.2 `make contracts-drift` in the contracts repo still passes (no contract change here).
