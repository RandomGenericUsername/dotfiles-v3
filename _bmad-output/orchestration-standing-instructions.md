# Orchestration Standing Instructions — Phase 3 dev loop

Recorded 2026-09-10 per operator request. These apply to every story iteration
until the operator revokes them. The orchestrated full cycle per story is:

```
CREATE → GATE 1 (story approval) → DEV → REVIEW → GATE 2 (patch decisions) → NEXT
```

## Standing instructions

1. **Gate 1 always opens the story doc in Google Chrome.** When a story file is
   created under `_bmad-output/implementation-artifacts/` and presented for
   approval, open it with `google-chrome-stable --new-window "file://<abs path>"`
   (detached via `nohup ... &`) so the operator can review it in the browser.
   Do this on every iteration without being asked.
2. **Gate 1 prompt is approval-only.** After opening, ask Approve / Request
   changes via the question tool. On approval, proceed to DEV autonomously.
3. **Gate 2 presents review findings as patch decisions.** After the 3-agent
   code review (Blind Hunter / Edge Case Hunter / Acceptance Auditor), present
   findings as structured approve/dismiss choices; apply approved patches,
   re-verify, mark done in `sprint-status.yaml`.
4. **Gate 2 walkthrough format (standing):** present decisions + patches ONE BY
   ONE — each item states the issue, the proposed solution with concrete patch,
   and explicit alignment with the established clean architecture
   (hexagon layering, domain purity, ports-as-ABCs, adapters own I/O,
   `test_layering.py` green), plus scalability/maintainability rationale.
   Dismissals carry the reason (gate conflict, scope, convention). Never batch
   Gate 2 into an unexplained list.
5. **Gate 2 iron rule (incident 2026-09-10): NEVER apply review patches before
   explicit approval.** Show every finding with its full patch first; change
   zero files until the operator approves per-item or batch. Applying first
   and asking after is a contract violation — if it ever happens again, revert
   to the pre-review state immediately and re-present.
6. **Gate 2 presentation format (confirmed 2026-09-10):** for EACH item, in
   plain chat text (never hidden behind a question-tool summary): the problem
   stated concretely, then the suggested fix with its complete before/after
   patch (file:line, full code). Dismissals get the same treatment: the claim
   plus the full rebuttal. No approval prompt until every item is shown in
   full. This format holds for all remaining iterations.
7. **Gate 2 review document (added 2026-09-10):** the per-item walkthrough
   MUST additionally be written as a markdown document
   (`_bmad-output/implementation-artifacts/<story>-gate2-review.md`), one
   section per item explaining in detail the issue/situation that arose the
   patch/decision plus the proposal (with file:line + full before/after code
   for applies, claim + full rebuttal for dismissals). Open it in Chrome
   alongside the ballot. The story file's Review Record keeps only the
   itemized outcome list (applied/dismissed one-liners); the -gate2-review.md
   is the detailed record.

## Log

- 2026-09-10: file created; instruction 1 requested at Gate 1 of p3-1-1.
