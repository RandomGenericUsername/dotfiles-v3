---
description: Execute TDD cycles from a plan document with decision gates and plan verification
---

Execute TDD cycles from a plan document with decision gates and plan verification.

**Input**: Path to the plan document (required). No default.

Usage: `/opsx:tdd docs/00-container-manager.md`

Load the `plan-driven-tdd` skill and execute with the provided plan path.
The skill reads the plan, determines the next incomplete cycle,
surfaces ambiguities before writing code, and verifies against the plan after.
