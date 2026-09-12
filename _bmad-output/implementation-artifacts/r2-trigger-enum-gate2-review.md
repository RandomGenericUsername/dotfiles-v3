# Gate 2 Review — R‑2 (Trigger Enum Single‑Source)

Status: APPLIED — all items resolved and verified (993 passed, 2 skipped; ruff/mypy no new; layering green).

## Applied

- **Item 1** stale prose lists replaced with a pointer to `runtime.domain.history.HISTORY_TRIGGERS` (`reconcile.py:26,:139`, `seeder.py:819`).
- **Item 2** `test_reconcile.py` reverted to `eac14b7` and re-applied with only the intended parametrize change (diff noise gone).
- **Item 3** drift gate strengthened: asserts the enum from the **embedded** copy (`load_history_schema()`) and a symbol‑identity regression test (`inspect.HistoryTrigger is HistoryTrigger`, `reconcile.HISTORY_TRIGGERS is HISTORY_TRIGGERS`).
- **Item 4** exact error‑message test (lists every value from the constant); a session `repo_root` fixture replaces the hardcoded `parents[4]` in both conformance tests; `reactive` comment reworded.

---

## Original review (pre-apply)

## Verification

- Full suite 990 passed, 2 skipped; targeted suites 155 passed. ruff/mypy no new issues; layering green (77).
- Panel: Blind Hunter = patches required; Edge Hunter = 3 fixes; Acceptance Auditor = **ACCEPT** (all 4 ACs) with a noise/stale-prose note.

## Findings

### Item 1 — stale prose copies of the enum (Blind V2/V3 + Edge #2 + Auditor)

**Problem:** the story's whole point is "no other copy," but three docstrings still enumerate an old set:
- `reconcile.py:26` and `:139` list `seed|set|reconcile|force|regenerate|doctor` (missing `prune` and `reactive`) — in the very file R‑2 edited.
- `seeder.py:819` lists 7 (missing `reactive`).

**Proposed patch:** replace each value list with a pointer to the source — `runtime.domain.history.HISTORY_TRIGGERS` — so the prose can't drift again. (The `shared-data-contract.md` enum line is descriptive; optional to refresh.)

### Item 2 — unrelated `ruff format` noise in `test_reconcile.py` (Auditor)

**Problem:** my `ruff format` pass reformatted ~45 pre-existing lines in `test_reconcile.py` (parenthesized asserts, line joins), adding diff noise unrelated to R‑2.

**Proposed patch:** revert `test_reconcile.py` to `eac14b7` and re-apply only the one intended change (extend the parametrize list with `prune`/`reactive`), so the changeset is minimal.

### Item 3 — strengthen the drift gate so it can't pass while behavior diverges (Edge #2, #4)

**Problem:** the drift test reads only the canonical schema file; the runtime actually validates against the **embedded** copy, and nothing pins `inspect`/`reconcile` to the shared symbol. A future local re-definition with matching values would pass silently.

**Proposed patch (tests):** (a) assert the enum from `load_history_schema()` (the embedded copy the reader uses) equals the constant; (b) a regression test asserting `inspect.HistoryTrigger is domain.history.HistoryTrigger` and that `reconcile` uses `HISTORY_TRIGGERS` (symbol identity, not value coincidence).

### Item 4 — minor (optional, Edge #6/#8 + #7)

- Pin the `reconcile` error message's value list with an exact-match test.
- Replace the hardcoded `parents[4]` repo-root in the two conformance/drift tests with a small walk-up helper (shared `conftest`).
- Reword the `domain/history.py` `reactive` comment (reconcile can now write it; "no caller writes it yet" is accurate).

### Process note (not a code change)

Blind Hunter flagged that `domain/history.py` and `test_history_trigger_enum.py` are **untracked**, so a pathspec diff omits them. They'll be `git add`-ed at commit; no code change.

## Ballot (Approve / Request changes PER ITEM)

- Item 1 (docstrings point to the source)?
- Item 2 (revert test_reconcile.py reformat noise)?
- Item 3 (drift gate: embedded copy + symbol identity)?
- Item 4 (optional minors)?
