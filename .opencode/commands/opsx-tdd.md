---
description: Execute TDD cycles from a plan document with decision gates and plan verification
---

Execute TDD cycles strictly against a plan document with decision gates before writing code and plan verification after. Designed to prevent AI drift from the specification.

**CRITICAL: The user MUST provide a plan document path. No default exists.**
If the user did NOT pass a path argument, DO NOT proceed. Instead, immediately ask them:
"Which plan document should I use? Provide a file path or describe the plan."
Wait for their answer before continuing. Never assume a default path.

Usage: `/opsx-tdd <path-to-plan>`

## Role

Act as a disciplined TDD engineer. Follow the plan document exactly. Surface ambiguities before acting. Verify every implementation against the plan. Never skip steps, never assume.

## Workflow

### 1. Setup

1a. If no plan path was provided, ask the user. Never infer or default.
1b. Read the plan document from the provided path.
1c. Derive tracking file path: `<plan-path>.tdd-status.md`
1d. If tracking file exists, read it to determine state. If not, ask the user which cycle to start with, then create the tracking file.
1e. Display current status.

### 2. Intent Gate

Read the relevant plan section for this cycle. Present to the user:

```
Cycle N: [name from plan]

Plan says:
  [exact excerpt]

Files to create:
  • [file 1]
  • [file 2]

Ambiguities I need you to decide:
  • [thing 1 — plan doesn't specify]
  • [thing 2 — could go either way]

Proceed? (y/n)
```

Wait for explicit confirmation. If concerns raised, discuss and adjust before proceeding.

### 3. TDD Implementation

Execute RED → GREEN → REFACTOR:

3a. **RED**: Write the failing test first.
3b. **GREEN**: Write minimal implementation to pass. No extra features.
3c. **VERIFY**: Run the test, confirm it passes.
3d. **REFACTOR**: Clean up, re-run tests.

### 4. Verification Gate

Build a checklist from the plan's spec for this cycle:

```
Verification — Cycle N:
┌──────────────────────────────────────────────┐
│ Plan says              │ Actual               │
├──────────────────────────────────────────────┤
│ File: domain/types.py  │ ✓ exists             │
│ Class: RunConfig       │ ✓ exists, dataclass  │
│ Field: command: list   │ ✓ correct            │
│ ...                    │ ...                  │
└──────────────────────────────────────────────┘
```

If deviations → PAUSE, report, ask user. If clean → "Verification passed."

### 5. Status Update

Update the tracking file:

```markdown
# TDD Status
Plan: <path>

## Done
- [x] Cycle N: <name> (<date>)

## Next
- [ ] Cycle N+1: <name>

## Decisions Made
- <decision>

## Deviations
- None
```

Show summary and ask: "Proceed to Cycle N+1? (y/n)"

## Guardrails

- Tracking file is mandatory. Always update it.
- Never skip Intent Gate or Verification Gate.
- Implement only what the current cycle specifies.
- If plan is ambiguous, surface in Intent Gate — never decide silently.
- If a decision is needed, ask and wait. Do not guess.
