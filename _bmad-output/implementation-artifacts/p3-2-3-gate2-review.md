# Gate 2 Review — p3-2-3 Torn-History-Tail Tolerance

Date: 2026-09-10. Reviewers: Blind Hunter / Edge Case Hunter / Acceptance Auditor (parallel).
~18 findings (overlapping). Zero files changed — all items below are proposals.

Files: `seeder.py` = `src/runtime/src/runtime/adapters/seeder.py`;
`doctor.py` = `src/runtime/src/runtime/application/doctor.py`;
`main.py` = `src/runtime/src/runtime/cli/main.py`;
tests = `src/runtime/tests/unit/test_history_tail_repair.py`.

**A is a blocker (reproduced live).**

---

## APPLY A — terminate a complete-but-unterminated record (Blind #1, Edge #1, BLOCKER)

**Situation.** A tail that is valid JSON but lost only its `\n` returns
`None` ("not torn"). The next append concatenates two records into one physical
line; the reader sees a newline-terminated invalid-JSON line → treats it as
middle corruption → raises. Reproduced: `Extra data: line 1 column 204`.

**Proposal.** If the tail parses as a JSON **object**, restore the newline (a
complete record was merely unterminated — do not lose it). If it parses as a
non-object scalar, treat as torn.
```python
# BEFORE (seeder.py heal)
        try:
            json.loads(tail.decode("utf-8"))
        except UnicodeDecodeError, ValueError:
            pass
        else:
            return None  # complete JSON line, merely unterminated — not torn
# AFTER
        try:
            parsed = json.loads(tail.decode("utf-8"))
        except UnicodeDecodeError, ValueError:
            pass
        else:
            if isinstance(parsed, dict):
                # complete record, only the newline was lost — restore it so
                # the next append cannot concatenate onto this record.
                with open(history_path, "ab") as handle:
                    handle.write(b"\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                return None
            # valid JSON scalar is not a history record → treat as torn
```

## APPLY B — refuse a symlinked history in heal (Blind #2, Edge #3, Auditor #4)

**Situation.** Heal follows a symlinked `history.jsonl` and `os.replace`s the
link itself — bypassing the `O_NOFOLLOW` hardening the writer uses and the
reader's explicit refusal.

**Proposal.** Early guard mirroring the reader/writer:
```python
# AFTER (seeder.py heal, first lines)
        history_path = self._state_root / "history.jsonl"
        if history_path.is_symlink():
            return None  # mirror writer O_NOFOLLOW / reader refusal; never follow
```

## APPLY C — serialize heal+append with a history lock (Blind #3, Edge #2, Auditor #6)

**Situation.** Heal is a lock-free read-modify-write; a concurrent
`append_history` (reconcile appends outside the seed mutex) can be silently
dropped by the `os.replace`, or lost when its fd points at the unlinked inode —
violating AD-4 must-not-lose.

**Proposal.** A dedicated `flock` held across heal+open+write+fsync; heal from
inside append uses a private `_heal_locked` helper (flock is not reentrant on a
second fd).
```python
# seeder.py: _HISTORY_LOCK = ".history.lock"
    def heal_torn_history_tail(self) -> Path | None:
        lock_fd = os.open(str(self._state_root / _HISTORY_LOCK), os.O_WRONLY | os.O_CREAT, 0o644)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            return self._heal_torn_history_tail_locked()
        finally:
            os.close(lock_fd)

    # append_history: hold the same lock across _heal_locked + open + write + fsync
```

## APPLY D — single-read quarantine, mode preservation, safe unlink (Blind #5/#6, Auditor #6)

**Situation.** `shutil.copy2` re-reads the file (a concurrent append in the
window survives in quarantine but is dropped from the live file); the tmp file
loses the original mode; `tmp.unlink` in `finally` can mask the real error.

**Proposal.** Write the quarantine from the same `raw` bytes; `os.chmod` the
tmp to the original mode before replace; guard the unlink.
```python
# BEFORE
        shutil.copy2(history_path, target)
        ...
        finally:
            tmp.unlink(missing_ok=True)
# AFTER
        with open(target, "wb") as qh:
            qh.write(raw)
            qh.flush()
            os.fsync(qh.fileno())
        ...
            os.chmod(tmp, stat.S_IMODE(history_path.stat().st_mode))
            os.replace(tmp, history_path)
        finally:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
```

## APPLY E — typed heal failure in repair (Edge #5)

**Situation.** A heal `OSError` (ENOSPC/permission) escapes `repair()` as a raw
platform error before unrelated drift is handled.

**Proposal.** Wrap into a typed error:
```python
        try:
            tail = self._heal_tail() if self._heal_tail is not None else None
        except OSError as exc:
            raise RuntimeError(f"history tail heal failed: {exc}") from exc
```

## APPLY F — tests (Blind #6, Auditor #2, #3, #8)

- Replace `test_complete_but_unterminated_json_not_torn` with
  `test_append_over_complete_but_unterminated` asserting both records parse.
- Plain `DoctorUseCase.check()` over a torn `history.jsonl` → file byte-identical,
  no quarantine dir (AC3 doctor half).
- Drift+tail: fake reconcile appends via a real `CacheSeeder` on the healed log;
  assert line count == complete+1, every line parses.
- CLI: `RepairResult(..., history_tail_quarantined=Path(...))` renders
  "healed torn history tail" / ", history tail healed".

## APPLY G — docs + story hygiene (Auditor #1, #7)

- Amend AD-23 (`ARCHITECTURE-SPINE.md`) and AR-4 (`epics-...phase3.md`) to record
  the ratified interpretation: read commands never mutate; the writer self-heals
  before append and `doctor --repair` heals explicitly. Reference this story.
- Tick story boxes; append the Gate 2 record.

---

## DISMISS X1 — make `heal_history_tail` required (Auditor #5)

**Claim:** the optional `| None = None` lets a caller silently skip healing.
**Rebuttal:** required would break the DONE 2.2 tests' ctor call; the production
CLI always wires it, and the default preserves the 2.2 contract. Recorded as a
deliberate default; a future refactor may require it.

## DISMISS X2 — stream large torn tails (Edge #7)

**Claim:** multi-MB torn tail buffered ~3x. **Rebuttal:** a torn tail is the
incomplete fragment of a single JSON record (bounded by one line, ~hundreds of
bytes); the whole-file read is only reached on the rare torn path. Premature.

---

## Item-to-finding index

| Item | Findings |
|------|----------|
| A | Blind #1, Edge #1 (blocker) |
| B | Blind #2, Edge #3, Auditor #4 |
| C | Blind #3, Edge #2, Auditor #6 |
| D | Blind #5, Blind #6, Auditor #6 |
| E | Edge #5 |
| F | Blind #6, Auditor #2/#3/#8 |
| G | Auditor #1, Auditor #7 |
| Dismiss X1 | Auditor #5 |
| Dismiss X2 | Edge #7 |
