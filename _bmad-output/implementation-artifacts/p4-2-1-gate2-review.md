# Gate 2 Review — Story p4-2-1 (Desired-State File + Schema + Loader)

Status: DEV done, awaiting patch decisions. NOTHING APPLIED — no code changed since verification.

## Verification (pre-review, all green)

- New tests: `tests/unit/test_desired_state.py` — 19 passed.
- Story + layering: `pytest tests/unit/test_desired_state.py tests/architecture/test_layering.py` — 88 passed.
- Full suite: 890 passed, 2 skipped (pre-existing skips).
- `ruff check src` — 3 errors, identical to stashed baseline (pre-existing: `models.py:35` E501 + 2 elsewhere). My files clean.
- `mypy src` — 5 errors, all pre-existing (`models.py:30` FitMode, 3× cli_output stubs, `main.py:1410` redef). No new issues.
- `ruff format` — applied to new reader only (whitespace); post-format tests re-run green.

## Review panel findings (3/3 reporting)

### Item 1 — `version: true` / `version: 1.0` bypass strict check (Blind Hunter + Edge Hunter agree: BUG)

**Problem (full):** `adapters/desired_state_reader.py:64-65` compares `version != DESIRED_VERSION`. In Python `True == 1` and `1.0 == 1`, so `{"version": true}` and `{"version": 1.0}` are ACCEPTED as valid v1. Edge Hunter verified live: the reader returns `DesiredState` instead of raising. The story contract requires schema `{version: 1}` (int); `keep` already guards `isinstance(keep, bool)` at line 73 — `version` was missed. Tests also miss it (no `True`/`1.0`/`"1"`/`None` version cases).

**Proposed patch:**
```python
# adapters/desired_state_reader.py:64-65
-    version = data.get("version", "<absent>")
-    if version != DESIRED_VERSION:
+    version = data.get("version", "<absent>")
+    if type(version) is not int or version != DESIRED_VERSION:
         raise ValueError(
             f"desired state version must be {DESIRED_VERSION}, got {version!r}: {desired_path}"
         )
```
plus regression cases in the malformation parametrize: `{**VALID_DOC, "version": True}`, `{**VALID_DOC, "version": 1.0}`, `{**VALID_DOC, "version": "1"}`, `{**VALID_DOC, "version": None}`.

### Item 2 — Symlink check-then-read TOCTOU defeats the refusal claim (Blind Hunter + Edge Hunter agree: BUG)

**Problem (full):** Line 47 `is_symlink()` then line 50 `read_text()` — an attacker swapping regular-file → symlink between the two calls gets the symlink followed, defeating the control the module docstring justifies as "refuse to follow: spoofing vector". Mirrors nothing else in the repo (history/meta have the same check-then-act shape, but this story explicitly sells the refusal as a security property, so it should actually hold).

**Proposed patch** (open with `O_NOFOLLOW` so the kernel refuses, instead of check-then-read):
```python
 import json
+import errno
+import os
 from pathlib import Path
```
```python
     desired_path = state_root / DESIRED_FILENAME
     if desired_path.is_symlink():
         raise ValueError(f"desired state is a symlink (refusing to follow): {desired_path}")
     try:
-        raw = desired_path.read_text(encoding="utf-8")
+        fd = os.open(desired_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
     except FileNotFoundError:
         return None
+    except OSError as exc:
+        if exc.errno == errno.ELOOP or desired_path.is_symlink():
+            raise ValueError(
+                f"desired state is a symlink (refusing to follow): {desired_path}"
+            ) from exc
+        raise ValueError(f"cannot read desired state {desired_path}: {exc}") from exc
+    try:
+        with os.fdopen(fd, "r", encoding="utf-8") as f:
+            raw = f.read()
     except (OSError, UnicodeDecodeError) as exc:
         raise ValueError(f"cannot read desired state {desired_path}: {exc}") from exc
```
plus a dangling-symlink test (`desired.json -> nonexistent` must raise symlink `ValueError`, not `None`).

### Item 3 — Test gaps, no implementation change (Acceptance Auditor + Blind Hunter agree)

**Problem (full):** Implementation handles all of these correctly, but no test locks the behavior: (a) missing `wallpaper`/`keep`/`pinned` keys individually (only missing-`version` tested; story says "all four keys required"); (b) the malformation regex `match=r"desired\.json|desired state"` proves a `ValueError` but not that the message names the offending field — the story's "ValueError naming file+field" contract is unpinned; (c) top-level scalars (`null`, `123`, `"str"`, `{}`) and whitespace-only file untested (only `["not","an","object"]` and `"{not json"`).

**Proposed patch** (tests only):
- Add 3 parametrize entries: dict minus `wallpaper`, minus `keep`, minus `pinned`.
- Add top-level scalar entries: `"null"`, `"123"`, `'""'`, `"{}"`, `"   "`.
- Optionally tighten to per-case `match=` on the field name (`version`, `wallpaper`, `keep`, `pinned`, `unknown keys`) — recommended but minimal form is (a)+(b-list) additions.

## Process note (not a patch item)

Auditor flags ~158 uncommitted `cli/main.py` lines (`reconcile --plan`) belonging to p4-1-1's surface, still in the working tree. p4-2-1's changeset is exactly: `domain/models.py` (+15-line `DesiredState`), new `adapters/desired_state_reader.py`, new `tests/unit/test_desired_state.py`. Commit p4-2-1 separately; do not sweep p4-1-1's CLI surface into it. No scope creep in p4-2-1 files — nothing consumes the loader yet, dead code by design per story.

## Ballot (vote Approve / Request changes PER ITEM in chat)

- Item 1 (strict version type + 4 regression tests)?
- Item 2 (O_NOFOLLOW open + dangling-symlink test)?
- Item 3 (missing-key + scalar test additions)?
