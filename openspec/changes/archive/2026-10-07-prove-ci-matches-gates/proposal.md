## Why

`.github/workflows/gates.yml` opens by claiming exactly the guarantee it does not
provide:

> The repo's executable gates. "Reuse the existing architecture" and "the mock
> matches the code" are only real if something runs them, **so this workflow is
> the place a future change cannot quietly drop one.**

`bluetooth-mock-parity` has been quietly dropped. It is in the `Makefile`'s
`GATES` and therefore in `gates-ci`, the set the workflow's own header names as
**authoritative** — and there is no job for it:

```
$ comm -23 <(gates-ci targets) <(ci job names)
bluetooth-mock-parity
```

So the Bluetooth mock/code parity gate has run on every developer's machine and
**never in CI**, since the `add-bluetooth-bar-popup` change landed. The comment
described an enforcement mechanism that was never written; the omission is
invisible because nothing compares the two lists.

This is the same failure shape the mock-parity harnesses already guard against
for their own vocabularies (the orphan-cell check in `bluetooth-mock-parity.py`,
added after `popup-scanning-devices` was drawn in the mock and the gate said
nothing). The lesson was learned for mock tokens and not applied to the gate
list itself.

## What Changes

- **Add the missing `bluetooth-mock-parity` job.** It is stdlib-only
  (`python3 scripts/bluetooth-mock-parity.py`), like `wifi-mock-parity` and
  `battery-mock-parity`, so it runs on a stock runner.
- **Add the enforcement the header claims.** A check that proves the workflow's
  job set and `gates-ci` are the same set, so the next drop fails loudly instead
  of silently. Renames are allowed but must be declared, the way
  `bluetooth-mock-parity.py`'s `CLASS_MAP` declares a token's shipped equivalent
  rather than trusting the reader to see the correspondence.
- **Correct the header** to describe the mechanism that exists rather than the
  one that was intended.

## Capabilities

### New Capabilities

- `ci-gates-parity`: every gate in `make gates-ci` has a CI job, every CI job is
  a gate in `make gates-ci`, and a check keeps that true.

### Modified Capabilities

- `gates` (CI workflow): one job per runner-capable gate, with
  `bluetooth-mock-parity` restored and renames declared rather than implied.
