---
name: plan-driven-tdd
description: Execute TDD cycles from a plan document with decision gates and plan verification. Use when the user says "run tdd", "execute plan", "next cycle", or loads this skill explicitly.
license: MIT
metadata:
  version: "1.0"
---

# Plan-Driven TDD

## Overview

Execute TDD cycles strictly against a plan document.
Each cycle requires a decision gate before code and plan verification after.
Designed to prevent AI drift from the specification.

## Required Input

The user MUST provide a path to a plan document.
No default — the plan path is always required.

Example: `/opsx:tdd docs/00-container-manager.md`

## Role

Act as a disciplined TDD engineer. Follow the plan document exactly.
Surface ambiguities before acting. Verify every implementation against the plan.
Never skip steps, never assume.

## Workflow

### 1. Setup

1a. Read the plan document from the provided path.
1b. Derive tracking file path: `<plan-path>.tdd-status.md`
     Examples:
       docs/00-container-manager.md  →  docs/00-container-manager.md.tdd-status.md
       plan.md                       →  plan.md.tdd-status.md
1c. If tracking file exists, read it to determine state.
     If not, read the plan document and ask the user which cycle to start with.
     Then create the tracking file.
1d. Display current status:
     - Last completed cycle
     - Next cycle to implement
     - Overall progress (e.g., "3/14 cycles complete")

### 2. Intent Gate

2a. Read the relevant section of the plan for this cycle.
2b. Present to the user:

     ```
     ┌─────────────────────────────────────────────────────────┐
     │  Cycle N: [cycle name from plan]                        │
     │                                                         │
     │  Plan says:                                             │
     │    [exact excerpt from plan]                            │
     │                                                         │
     │  Files to create:                                       │
     │    • [file 1]                                           │
     │    • [file 2]                                           │
     │                                                         │
     │  Ambiguities I need you to decide:                      │
     │    • [thing 1 — plan doesn't specify]                   │
     │    • [thing 2 — could go either way]                    │
     │                                                         │
     │  Proceed? (y/n)                                         │
     └─────────────────────────────────────────────────────────┘
     ```

2c. Wait for explicit confirmation from the user.
2d. If user raises concerns, discuss and adjust. Continue only when user says go.

### 3. TDD Implementation

Execute strict RED → GREEN → REFACTOR:

3a. **RED**: Write the failing test first.
     - Reference which part of the plan the test covers.
     - Optionally show the test to the user before proceeding.

3b. **GREEN**: Write the minimal implementation to pass the test.
     - Stay scoped to what the test requires.
     - Do NOT add features the plan doesn't specify for this cycle.

3c. **VERIFY**: Run the test. Confirm it passes.
     - `cd <project-root> && python -m pytest <test-path> -v`
     - Show the result.

3d. **REFACTOR**: Clean up if needed.
     - Run tests again after refactor.

### 4. Verification Gate

4a. Build a checklist from the plan's spec for this cycle:

     ```
     Verification checklist — Cycle N:
     ┌────────────────────────────────────────────────────────┐
     │  Plan says:                │ Actual:                   │
     ├────────────────────────────────────────────────────────┤
     │  File: domain/types.py     │ ✓ exists                  │
     │  Class: RunConfig          │ ✓ exists, dataclass       │
     │  Field: command: list[str] │ ✓ correct                 │
     │  ...                       │ ...                       │
     │  Test: test_types.py       │ ✓ exists, passes          │
     │  No extra files created    │ ✓ (only what plan says)   │
     └────────────────────────────────────────────────────────┘
     ```

4b. For each item: check and report.
4c. If deviations found → PAUSE. Report to user. Ask how to resolve.
4d. If clean → report "Verification passed."

### 5. Status Update

5a. Update the tracking file. Content format:

     ```markdown
     # TDD Status
     Plan: <plan-path>

     ## Done
     - [x] Cycle N: <name> (<date>)

     ## Next
     - [ ] Cycle N+1: <name>

     ## Decisions Made This Session
     - <decision>

     ## Deviations
     - <deviation or "None">
     ```

5b. Show summary to user:

     ```
     Cycle N complete. X/Y cycles done.
     Phase Z: A/B ✓

     Proceed to Cycle N+1: <name>? (y/n)
     ```

5c. If yes → loop to Step 2.
     If no → save tracking file, report where we stopped.

## Guardrails

- **Mandatory tracking file**: Always create and update. Failure to write the tracking file is a blocker.
- **Never skip Intent Gate**: Even for trivial cycles. Surface ambiguities before code.
- **Never skip Verification Gate**: Every cycle must be checked against the plan before marking done.
- **Scope discipline**: Implement only what the current cycle specifies. If you notice something outside scope, log it in the tracking file's notes and move on.
- **Plan takes priority**: If there's a conflict between the plan and what "makes sense," surface it in the Intent Gate. Do not silently override the plan.
- **Block on user**: If a decision is needed, don't guess. Ask, wait, continue.
- **No BMad dependency**: This skill is standalone. It does not use BMad or OpenSpec frameworks.
