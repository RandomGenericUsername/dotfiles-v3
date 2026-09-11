# Gate 2 Review — Story p4-3-1 (Diff Engine)

Status: DEV done, awaiting Gate 2 vote. NOTHING APPLIED since verification (nothing to apply — panel requires no patches).

## Verification (pre-review, all green)

- New tests: `tests/unit/test_diff.py` — 11 tests / 18 cases passed.
- Story + layering: + `tests/architecture/test_layering.py` — 89 passed.
- Full suite: 929 passed, 2 skipped (pre-existing skips).
- `ruff check` on story files: clean. `ruff format`: applied, post-format green.

## Review panel findings (3/3 reporting — unanimous APPROVE, no patches)

- **Blind Hunter:** no contract violations. All AC rules verified line-by-line against implementation. Two advisories recorded below — explicitly NOT to fix in this story without amending the contract.
- **Edge Hunter:** 11 paths walked — 7 handled, 4 correctly out-of-scope (path normalization = loader duty, `None` wallpaper = model type duty, pin element typing = model duty, frozen bypass = out of scope). No patches.
- **Acceptance Auditor:** ACCEPT — AC1/AC2/AC3 all pass with evidence, zero scope creep (`diff_states|ChangeSet` zero hits in `cli/`+`adapters/`), zero coverage gaps, layering clean.

## Advisories carried forward to p4-3-2 (planner wiring) — NOT this story

1. **`desired.keep` bool hole (inherited from 4.2):** `DesiredState` has no `__post_init__` validation, so `keep=True` converges as `1` / smuggles `True` as `keep_target`. The diff is contract-faithful (`==` as specified); hardening belongs to the planner story or a 4.2 follow-up — flagging, not patching.
2. **`pins_absent` permanently blocks `is_empty`:** any machine with an extra seed-pin reports non-converged forever, while scope forbids unpinning and defaults to no unpin. p4-3-2 must decide: `is_empty` excludes `pins_absent`, or the planner documents "converged modulo protected pins" separately.

## Amendment (owner decision, post-ballot): option 1 applied

Owner selected option 1 from the advisory: `is_empty` excludes `pins_absent`
(actionable-convergence signal; extra seed-pin = informational residue).
Applied to `ChangeSet.is_empty` + docstring, story AC 3 amended, tests updated
(`test_pins_absent_is_informational` now asserts `is_empty is True`;
truth-table pins-extra case moved to dedicated
`test_pins_absent_alone_still_converged`). Re-verified: 89 passed
(story + layering), ruff clean apart from pre-existing `models.py:35` E501.

## Ballot (vote in chat)

- Accept p4-3-1 as done WITH the option-1 amendment, commit as one proper commit and proceed to p4-3-2 draft (Gate 1)?
