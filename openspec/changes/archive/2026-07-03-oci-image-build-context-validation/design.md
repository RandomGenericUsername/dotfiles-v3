## Context

`BuildContext.__post_init__` (`types.py:91-111`) already rejects `context_path + files` (lines 104-110) but doesn't reject `build_file_path + files`. The `image.py:39-41` branch silently drops `files` when `build_file_path` is set. Separately, `image.py:45,48` use `assert` stripped under `-O`.

## Goals / Non-Goals

**Goals:** Reject `build_file_path + files` at construction. Replace bare asserts with typed errors.
**Non-Goals:** Changing the `build_file_path` parent-directory behavior (correct when `files` is empty).

## Decisions

Symmetric validation: after the existing `context_path + files` check, add `build_file_path + files` check. For the asserts, replace with `if x is None: raise ImageRuntimeError(message=...)`. The `else` branch's guard is defensive (post_init already rejects both-None) but catches callers using `dataclasses.replace` which bypasses `__post_init__`.

## Risks / Trade-offs

- Breaking callers silently setting both — they were already broken (files silently dropped). Making the bug loud is the improvement.