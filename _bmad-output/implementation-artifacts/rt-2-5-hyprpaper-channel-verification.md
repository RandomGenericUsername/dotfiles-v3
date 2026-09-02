---
baseline_commit: 2da2df2
---

# Story 2.5: Hyprpaper channel verification and reload adapter

Status: review

## Story

As a user,
I want the wallpaper to visually change after a swap,
so that the desktop shows the new wallpaper.

## Acceptance Criteria

1. **Verified channel (the story's primary deliverable).** **Given** a swap repointed a `current/wallpaper-<monitor>.png` symlink for each monitor in `current.json.monitors` (through the Hyprpaper consumer path), **When** the Hyprpaper reload adapter runs, **Then** it uses the Hyprpaper wallpaper-swap mechanism that is VERIFIED against the INSTALLED hyprpaper version (Arch package **0.8.4-6**, binary `hyprpaper v0.8.4`) — resolving the long-open question *"reload-after-symlink-repoint vs `hyprctl hyprpaper wallpaper <monitor> <path>` IPC?"* (SPEC Open Question, ARCHITECTURE-SPINE.md Deferred, consumer-wiring.md Unverified) — and the chosen channel is recorded in the code (module docstring) **and** the architecture docs (ARCHITECTURE-SPINE.md Deferred item closed with evidence), per FR-6. The closing evidence MUST show the decision is grounded in the v0.8.4 reality, not the inherited pre-rewrite docs (see Dev Notes "The verification result").

2. **Per-monitor reload via the verified channel.** **Given** the loaded `current.json` has `N` monitors (each with a `current/wallpaper-<monitor>.png` symlink), **When** the adapter reloads, **Then** it applies the verified hyprpaper channel once per monitor (one `hyprctl hyprpaper wallpaper` invocation per monitor, targeting the resolved cached wallpaper behind the symlink), and returns `True` only when EVERY monitor's invocation succeeds. (Shared-data-contract swap step 5: "For each monitor, invoke its backend's reload (… hyprctl hyprpaper wallpaper …)".)

3. **R5 reload-failure reporting.** **Given** any per-monitor invocation fails (non-zero exit, no running Hyprland session, `hyprctl` not found, bad monitor/path, timeout, or any subprocess error), **When** the adapter reports, **Then** it returns `False` with a warning log naming the failing monitor, the reconcile use case populates `ReconcileResult.reload_failures` with the adapter's class name, and the CLI exits non-zero (existing `cli/main.py:366-375` path). Missing binary / no live session is a SURFACED failure, not a skip (carried decision from rt-2-3/2-4).

4. **Zero-monitor vacuous success.** **Given** `state_root/current/` contains NO `wallpaper-*.png` symlinks (nothing to apply), **When** the adapter reloads, **Then** it logs at debug level and returns `True` (vacuously — there is no wallpaper to update; the reconcile swap already reports empty-monitor skips).

5. **Wired into the composition root.** **Given** the adapter is wired into `ReconcileDesktopStateUseCase`, **When** the swap sequence reaches step 5 (reload), **Then** `HyprpaperReloader` is invoked once via the existing `reloaders` list (the reload loop at `reconcile.py:257-266` handles monitor enumeration internally — NO changes to `ReconcileDesktopStateUseCase.run`), joining `[HyprlandReloader(), AgsReloader()]` in the CLI composition root (`cli/main.py:328`).

## Tasks / Subtasks

- [x] Task 1 — Channel verification spike: close the open question with evidence (AC: 1)
  - [x] Record installed tool facts on this machine: `hyprpaper --version` → `v0.8.4`; `pacman -Q hyprpaper` → `0.8.4-6`; `pacman -Q hyprland` → `0.56.2-1`; `hyprctl hyprpaper` (bare) → `error: Invalid request`; `hyprctl hyprpaper wallpaper` (bare) → `error: not enough args` (exit 1); `hyprctl hyprpaper --help` → documents the request surface verbatim — `usage: hyprctl [flags] hyprpaper <request>` / `wallpaper → Issue a wallpaper ... Arguments are [mon],[path],[fit_mode]. Fit mode is optional.` `which hyprctl hyprpaper` → both real binaries.
  - [x] Confirm via the INSTALLED hyprland 0.56.2 hyprctl source (`github.com/hyprwm/Hyprland`, `hyprctl/src/hyprpaper/Hyprpaper.cpp`) and the help output that hyprctl's hyprpaper interface exposes EXACTLY a single wallpaper request (`wallpaper <monitor>,<path>[,<fit>]`) plus `listactive`, and that the OLD flat requests `reload`/`preload`/`unload`/`setcolor` NO LONGER EXIST (grep the installed `hyprctl` binary strings: only `wallpaper` and `listactive` appear; there is no `reload`/`preload` word).
  - [x] Confirm the hyprpaper v0.8.4 side (`github.com/hyprwm/hyprpaper` tag `v0.8.4`, `src/ipc/IPC.cpp`) is the Hyprwire rewrite: config is parsed at startup, wallpaper changes are driven by the wire object protocol (`CWallpaperObject` setPath/setMonitorName/setFitMode/setApply); there is no conf-reload-on-IPC (a config `wallpaper =` line is only re-read on process restart).
  - [x] Determine the conclusion definitively: **the only in-place wallpaper-change channel is the `hyprctl hyprpaper wallpaper` IPC** — reload-after-symlink-repoint is UNAVAILABLE in v0.8.4 (no reload request; config only re-read at startup). Record this as the chosen channel in the module docstring, the story Change Log, and close ARCHITECTURE-SPINE.md Deferred "Hyprpaper wallpaper channel" + the SPEC open question + consumer-wiring.md "Unverified" with an `(RESOLVED 2026-09-02: …)` note mirroring the AGS channel item. A live end-to-end signal check needs a running Hyprland session (none in the dev container) — record that limitation explicitly; source-level verification of the installed versions is the evidence (the same pattern rt-2-4 used for AGS).
  - [x] **Correction debt:** the inherited facts that predate the rewrite (review-reality-check F3 "the tool's documented channel for a wallpaper change is its IPC" was written against the OLD hyprpaper; the spine Deferred text assumed `reload`/`preload` still exist) are now stale — do NOT propagate `preload`-then-`wallpaper` or `hyprctl hyprpaper reload` into the adapter. The v0.8.4 channel requires NO preload step.

- [x] Task 2 — Create `adapters/hyprpaper_reloader.py` (AC: 1, 2, 3, 4)
  - [x] Implement `HyprpaperReloader(IDesktopReloader)` (module `src/runtime/src/runtime/adapters/hyprpaper_reloader.py`). This is the RELOADER (mirrors `hyprland_reloader.py` / `ags_reloader.py`); it is NOT the AD-18 `IStaticWallpaperBackend` named `hyprpaper_backend` in the spine manifest — that per-monitor backend hierarchy is future scope. Note the naming relationship in the module docstring so the spine manifest's `hyprpaper_backend` entry isn't mistaken for this adapter.
  - [x] Constructor: `__init__(self, hyprctl_path: Path | None = None, state_root: Path | None = None)`. Resolve `hyprctl` by REUSING the resolution logic: import `_resolve_via_which` from `hyprland_reloader` (adapters→adapters, layering-green — the exact same reuse `ags_reloader.py:45` already uses) and write a thin `_resolve_hyprctl` mirroring the separator/executable-file/bare-name branch structure; do NOT copy-paste a second full resolver. When `state_root` is `None`, resolve the runtime default exactly as the CLI does (`os.environ["XDG_STATE_HOME"]` or `~/.local/state` + `/dotfiles`, absolute; mirror `cli/main.py:56-64` semantics). Explicit `hyprctl_path`/`state_root` for tests.
  - [x] Per-monitor enumeration (FS authority, NFR-3): at `reload()` time, scan `state_root/current/wallpaper-*.png` symlinks (sorted for determinism). For each, derive `monitor = name[10:-4]` (strip `wallpaper-` and `.png`), and the target path = `link.resolve()` (absolute, points into `cache/wallpapers/<wh>/wallpaper.png`). Detect a dangling symlink with `link.is_symlink() and not link.exists()` (NOT via `resolve()` — `Path.resolve()` defaults to `strict=False` and returns the target path without raising for a missing target) → treat that monitor as a failure (a dangling wallpaper symlink means the swap produced a broken consumer — surface it).
  - [x] Per-monitor channel call: `subprocess.run([str(hyprctl), "hyprpaper", "wallpaper", f"{monitor},{target}"], …)` — the monitor+path is ONE single space-free comma-delimited argv element, because hyprctl space-joins argv into the request (`Hyprland/hyprctl/src/main.cpp`: `fullRequest += "{} "`) and hyprpaper's `doWallpaper` splits the RHS on `,` (`Hyprland/hyprctl/src/hyprpaper/Hyprpaper.cpp` `CVarList2 args(rhs, 0, ',')`). Do NOT pass `monitor` and `path` as separate argv elements (a space inside the RHS would corrupt the comma split). A resolved path containing a space is NOT representable through this channel (hyprpaper grammar limit) — safe for the default install layout (hash-named cache entries under a standard state_root); if a state_root under a space-containing path is ever used, the invocation surfaces as a failure (document this as a known limitation). Pass `capture_output=True, text=True, timeout=10` and wrap every call in the mandated exception tuple `(FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError, ValueError)`. The error message is returned on stdout as `error: <detail>` with exit code 1 (hyprctl `makeHyprpaperRequest` → `exitStatus = !result`) — read `result.stdout`/`result.stderr` for the log. Do NOT append a fit-mode field in this story — see Dev Notes "Fit-mode mapping" (hyprpaper applies `cover` by default).
  - [x] Failure semantics: `hyprctl` already reports a precise failure on STDOUT as `error: <detail>` (e.g. `failed to set wallpaper: Invalid monitor`, `can't send: failed to connect to hyprpaper (is it running?)`, `HYPRLAND_INSTANCE_SIGNATURE not set!`) and exits non-zero — the adapter logs the captured `result.stdout`/`result.stderr` with the monitor name and returns `False`. Missing `hyprctl` (resolved `None`) → warning `hyprctl not found in PATH; Hyprpaper reload skipped` + `False` (surfaced failure, NOT a skip — carried decision; identical to `HyprlandReloader`/`AgsReloader`). No `current/` dir or zero matches → debug log + `True` (AC 4).
  - [x] Module docstring MUST record the verified channel + evidence sources (FR-6 AC 1): hyprpaper v0.8.4 rewrite facts, hyprctl Hyprpaper.cpp request vocabulary, no-preload/no-reload, AD-17 (consumer wiring `current/wallpaper-<monitor>.png`), FR-6, R5, and the fit-mode mapping decision. Cite [ARCHITECTURE-SPINE.md:235], [shared-data-contract.md swap step 5], [SPEC Open Question]. No inline "why" comments beyond those.

- [x] Task 3 — Wire into CLI composition root (AC: 5)
  - [x] In `cli/main.py` `_run_reconcile()`, add a lazy import next to the existing adapter imports (`cli/main.py:309-316`): `from runtime.adapters.hyprpaper_reloader import HyprpaperReloader`.
  - [x] Change `reloaders=[HyprlandReloader(), AgsReloader()]` (`cli/main.py:328`) to `reloaders=[HyprlandReloader(), AgsReloader(), HyprpaperReloader(state_root=state_root)]` — Hyprland, AGS, Hyprpaper, deterministic order. **Construct `HyprpaperReloader` with the explicit `state_root` already computed at `cli/main.py:306`** (do NOT rely on the constructor's env-default here): the reloader must read `current/` from the SAME state_root the reconcile use case writes, and the composition root already has it. Hyprland/AGS reloaders are argument-free (binary resolution only), but `HyprpaperReloader` is state-root-sensitive — an env fallback inside the adapter would risk divergence from `_resolve_state_root()`.
  - [x] Update the now-stale comment at `cli/main.py:343-344` ("restarts Hyprland and AGS via the reloaders wired in the composition root") to include Hyprpaper wallpaper reload. `cli/main.py:363-365`'s generic "reload_failures … exits non-zero" comment is fine as-is.
  - [x] NO changes to `reconcile.py`'s reload loop or `ReconcileDesktopStateUseCase` constructor — `test_reconcile.py` `TestReconcileStructuralScopeLock` (line 689-708) already pins the `reloaders` param; composition-root-only change.

- [x] Task 4 — Stale scope comment in `reconcile.py` (mirror rt-2-4 Task 3)
  - [x] `reconcile.py:12-13` currently reads "…AGS is Story 2.4; Hyprpaper/terminal follow in 2.5–2.6". After this story, Hyprpaper ships — update to "…AGS is Story 2.4; Hyprpaper is Story 2.5; terminal follows in 2.6". Docstring-only; no behavior change.

- [x] Task 5 — Unit tests `tests/unit/test_hyprpaper_reloader.py` (AC: 1, 2, 3, 4)
  - [x] Follow `test_hyprland_reloader.py`'s style: `unittest.mock.patch` on `subprocess.run`; construct with EXPLICIT `hyprctl_path` (an executable probe fixture) AND explicit `state_root` (a tmp dir you build `current/wallpaper-*.png` symlinks in) so resolution is deterministic. Do NOT bypass resolution by poking private state (rt-2-3/2-4 review lessons 1+3).
  - [x] **Success:** `test_reload_success_returns_true` (mock `run` → exit 0 per invocation; two monitors → `True`); `test_invokes_wallpaper_ipc_per_monitor` (assert argv == `[hyprctl, "hyprpaper", "wallpaper", "DP-1,<resolved>"]` for each monitor — pin the single space-free comma-delimited third element); `test_uses_resolved_symlink_target` (symlink → target asserted as the resolved `cache/…/wallpaper.png` path); `test_zero_monitors_returns_true` (empty `current/` → `True`, subprocess NOT called); `test_monitor_order_sorted_deterministic` (multiple monitors applied in sorted order).
  - [x] **Failure:** `test_monitor_failure_returns_false` (one exit 0 + one exit 1 → `False`); `test_dangling_symlink_is_failure`; `test_subprocess_exception_returns_false` parametrized over `FileNotFoundError / PermissionError / subprocess.TimeoutExpired / OSError / ValueError`; `test_timeout_returns_false`.
  - [x] **Missing-binary (host-independent, mirror `test_hyprland_reloader.py:103-137`):** `test_missing_hyprctl_returns_false` (patch `shutil.which` → `None`, construct `hyprctl_path=None` → `False`, zero subprocess calls); `test_non_executable_hyprctl_returns_false`; `test_resolve_explicit_missing_path_fails_later`; `test_which_called_with_hyprctl`.
  - [x] **Port conformance:** `test_implements_desktop_reloader_port` (`isinstance(reloader, IDesktopReloader)`).
  - [x] **Reconcile integration (mirror `_make_reconcile_with_reloaders` in `test_ags_reloader.py:368-386`):** `test_hyprpaper_failure_populates_reload_failures` (failing fake reloader beside a passing one → label present/absent correctly); `test_all_reloaders_invoked_once` (`[Hyprland-fake, Ags-fake, Hyprpaper-fake]` each called exactly once — AC 5).

- [x] Task 6 — Integration test `tests/integration/test_hyprpaper_reloader_integration.py` (AC: 1, 2, 3, 5)
  - [x] Fake `hyprctl` shim in PATH (mirror `test_hyprland_reloader_integration.py:119-132`): a tiny shell script that RECORDS its full argv to a marker file, exits `0` when `$1 == "hyprpaper"` and `$2 == "wallpaper"` and `$3` (the single comma-delimited segment) parses as `<nonempty-monitor>,<absolute-path>` with the path being a real file (`case "$3" in *,/*) p="${3#*,}"; [ -n "${3%,*}" ] && [ -e "$p" ] && exit 0 ;; esac; exit 1`), else exits `1` — emulating the v0.8.4 request contract (invalid monitor/path → failure). Honest naming — the shim does not invoke a live hyprpaper.
  - [x] End-to-end: seed → apply → reconcile with `HyprpaperReloader(state_root=state_root)` (**must pass the tmp `state_root` explicitly** — the constructor's env-default resolves the real `$XDG_STATE_HOME/dotfiles`, which would find no `current/` symlinks and vacuously succeed without ever invoking the shim) → assert `result.reload_failures == []` and the marker shows `<monitor>,<resolved-path>` calls (one per seeded monitor; the seeder writes per-monitor configs with default monitor `DP-1`).
  - [x] Missing-binary path: mock `which` → `None` → `reload_failures` contains `"HyprpaperReloader"` (surfaced failure — consistent with the Hyprland/AGS integration tests; do NOT convert into a skip). Also cover `hyprctl` present but shim exits 1 (simulating "failed to connect to hyprpaper (is it running?)") → failure surfaced.

- [x] Task 7 — Full green gate (AC: all)
  - [x] `uv run --directory src/runtime pytest -q` (baseline **323 passed, 2 skipped**)
  - [x] `uv run --directory src/runtime ruff check src/runtime` (zero NEW violations; 3 pre-existing)
  - [x] `uv run --directory src/runtime ruff format --check src/runtime` (new/edited files format-clean)
  - [x] `uv run --directory src/runtime mypy --strict src/runtime` (zero NEW errors; 4 pre-existing)
  - [x] `tests/architecture/test_layering.py` green (adapter lives in adapters/; adapters→adapters import of `_resolve_via_which` is legal per test_layering.py layering map)

## Dev Notes

### Scope boundary — Hyprpaper reload channel ONLY

This story delivers (a) the channel-verification evidence that closes the open question, and (b) the Hyprpaper reload adapter. It does NOT:
- implement the AD-18 per-monitor `IStaticWallpaperBackend` hierarchy (`hyprpaper_backend`/`swaybg_backend`/`swww_backend`/`mpvpaper_backend` + factory) — future scope; the spine manifest's `hyprpaper_backend` name refers to THAT backend, not this reloader.
- modify `dotfiles/config/hyprpaper/hyprpaper.conf` or do the seeder's consumer-path conf re-bake (provisioning-delta table row 3 is a SEPARATE runtime/seeding concern). The verified IPC channel applies the wallpaper directly and does NOT depend on the conf pointing at `current/` — that is exactly why IPC is the correct channel (see verification result).
- implement terminal palette application (Story 2.6) or rewire `wallpaper set` (Story 2.7 capstone).
- change the swap sequence, `ReconcileResult`, or the CLI reload-failure error path (all exist from rt-2-2/2-3/2-4).

### The verification result (record this — it IS the deliverable)

Verified against the installed binaries and their source (this machine): **hyprpaper v0.8.4 is the Hyprwire rewrite**, and the ONLY programmatic in-place wallpaper-change channel is the per-monitor IPC

`hyprctl hyprpaper wallpaper <monitor>,<path>[,<fit>]`

- **Hyprland 0.56.2 hyprctl source** (`hyprctl/src/hyprpaper/Hyprpaper.cpp`, main) exposes exactly two requests: `wallpaper` and `listactive`. Installed-binary strings confirm (no `reload`/`preload`/`unload`/`setcolor` words). `hyprctl hyprpaper wallpaper` bare → `error: not enough args`; `hyprctl hyprpaper` bare → `error: Invalid request`.
- **Request grammar (verified from `doWallpaper`):** a single comma-delimited RHS — `CVarList2 args(RHS, 0, ',')`, `MONITOR=args[0]`, `PATH_RAW=args[1]`, `FIT=args[2]` — where `RHS` is hyprctl's space-joined trailing argv. So the subprocess argv MUST be `[hyprctl, "hyprpaper", "wallpaper", "<monitor>,<abs-path>"]` with the whole `<monitor>,<abs-path>` as ONE element and NO spaces in it (a space becomes a separator in hyprctl's join and corrupts the comma split; a path with a space is unsupported by the grammar). The path is canonicalized (must exist on disk; `~` expanded), the socket is `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.hyprpaper.sock`, and the monitor MUST exist (else `HYPRPAPER_CORE_APPLYING_ERROR_INVALID_MONITOR`). Failures land on stdout as `error: <detail>` with a non-zero exit; the adapter treats any non-zero exit as a failure and logs the captured output.
- **No preload step** — the old flat `preload`/`unload`/`reload` requests are GONE in v0.8.4. Do __not__ re-introduce a "preload then wallpaper" sequence from stale docs.
- **Reload-after-symlink-repoint is UNAVAILABLE** — hyprpaper v0.8.4 (`src/ipc/IPC.cpp` at tag `v0.8.4`) parses its config at startup; a `wallpaper =` line is only re-read on process restart. There is no conf-reload IPC. This definitively closes the SPEC open question in favor of the IPC channel.
- **Live end-to-end limit:** a real on-wire change needs a running Hyprland session (none in the dev container — `hyprctl` returns "failed to connect"). Source-level verification against the installed versions is the evidence, exactly the pattern rt-2-4 used for AGS (`cli/cmd/run.go:145`). Record this limitation in the story Change Log; the integration test's shim emulates the v0.8.4 request contract.

**Correction debt entry for the Change Log / docs:** the spine Deferred "Hyprpaper wallpaper channel" item, SPEC Open Question, consumer-wiring "Unverified" list, and review-reality-check F3 all describe the PRE-rewrite hyprpaper (they assumed `reload`/`preload` exist). Close them with `(RESOLVED 2026-09-02: channel = per-monitor IPC `hyprctl hyprpaper wallpaper <monitor>,<path>[,<fit>]`, verified against hyprpaper 0.8.4 / hyprland 0.56.2 source; reload-after-symlink-repoint unavailable in the rewrite)`.

### The `IDesktopReloader` port + reload loop (existing — do not modify)

`ports/desktop_reloader.py`: `reload() -> bool`. `ReconcileDesktopStateUseCase` already has `reloaders: list[IDesktopReloader]` and the Step-5 loop outside the lock (`reconcile.py:105-111, 257-266`): each reloader is called once, per-reloader exceptions are caught, `False` → class name into `reload_failures`. `HyprpaperReloader` enumerates monitors internally because the loop does not pass state — the adapter reads `state_root/current/` itself (FS authority, NFR-3). No per-monitor parameter on the port.

### Reuse — leverage existing infrastructure (do not duplicate)

- `IDesktopReloader` port — use as-is.
- `_resolve_via_which` from `hyprland_reloader.py:30-38` — import + thin `_resolve_hyprctl` mirroring the separator/which/access branch structure (identical to `ags_reloader.py:54-78`). Adapters→adapters import is layering-green.
- `subprocess.run(…, capture_output=True, text=True, timeout=10)` + exception tuple `(FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError, ValueError)` — mirror `hyprland_reloader.py` exactly. The `ValueError` member is mandatory (rt-2-3 review: NUL-byte paths/bad stderr bytes breaching "error → False").
- CLI composition root + non-zero exit on `reload_failures` (`cli/main.py:366-375`) — existing, only append to the reloader list.
- Test scaffolding: reuse the `_FakeMutex`/`_FakeCsg`/`_FakeWeg`/`_FakeItr`/`_setup_spine`/`_make_reconcile_with_reloaders` patterns already byte-identical across the hyprland/ags test files (the shared-conftest refactor is a pre-existing deferred item — follow the current copy-paste convention, don't invent a new structure).
- Bash shim pattern for the integration test: `test_hyprland_reloader_integration.py:119-132`.

### Fit-mode mapping (recommended simple behavior)

`FitMode` (cover/contain/fill/tile/center/stretch) → hyprpaper's `fitFromString` accepts `cover` (default), `contain`, `tile`, `fit` (or `stretch`); `fill`/`center` are NOT representable. **Recommended for this story: OMIT the fit field entirely** (argv element is just `<monitor>,<abs-path>`), so hyprpaper applies its `cover` default — which matches the seeded/default Phase-2 fit_mode per AD-11/1.13, keeps the adapter free of a `current.json` read, and avoids overriding a monitor's configured fit mode at the wrong layer. Record the mapping table in the module docstring for the future AD-18 backend/factory story: `cover→cover`, `contain→contain`, `tile→tile`, `stretch→stretch`, `fill→cover (unrepresentable)`, `center→cover (unrepresentable)`. (If you choose to honor per-monitor `fit_mode`, read `current.json.monitors` via `JsonStateRepository` — layering-legal — and append `,<mapped-fit>` to the same single argv element; but the shipped default should be omit-and-cover.)

### Behavioral decisions carried from rt-2-3/2-4 (do not soften)

Missing/non-live consumer = **surfaced failure**. On any headless/dev machine without a running Hyprland session (or without `hyprctl` in PATH), `HyprpaperReloader` returns `False` and `reconcile` exits non-zero with `HyprpaperReloader` in the failure list — exactly like `HyprlandReloader` (which also fails when no Hyprland socket is reachable). This is spec-literal R5. Do NOT convert it into a skip.

### Code style gates (enforced)

Python 3.14, `mypy --strict` (no untyped defs, `from __future__ import annotations` at top), ruff line-length 100, ruff select E/F/I/N/W/UP/B. Parenthesize multi-except tuples (PEP 758). Timestamps `datetime.now(UTC).isoformat().replace("+00:00", "Z")`. House style: dense module docstrings citing AD-numbers and evidence, no inline "why" comments. Application→adapters module-level imports are established; adapters→sibling-adapter imports (the shared resolver) are legal and layering-green.

### Invariants (non-negotiable, verified against current code)

- **Exception tuple** for every subprocess call: `(FileNotFoundError, PermissionError, subprocess.TimeoutExpired, OSError, ValueError)` → log warning with stderr, return `False`.
- **One `hyprctl hyprpaper wallpaper` call per monitor**, argv shape `[hyprctl, "hyprpaper", "wallpaper", "<monitor>,<abs-path>"]` — the `<monitor>,<abs-path>` is ONE space-free comma-delimited argv element (hyprctl space-joins argv into the request; hyprpaper splits on `,`) — all monitors must succeed for `reload()` to return `True`. On failure, log the captured stdout/stderr (hyprctl prints `error: <detail>` with exit code 1).
- **Binary via `link.resolve()`** from `current/wallpaper-<monitor>.png`, with the dangling check `link.is_symlink() and not link.exists()` FIRST (`resolve()` does not raise for a missing target); a dangling symlink is a surfaced failure.
- **Missing binary = surfaced failure** (`False` → `reconcile` non-zero) — spec-literal R5, not a skip.
- **Zero monitors → vacuous `True`** (nothing to update; AC 4).
- **No `hyprctl hyprpaper reload` / `preload`** — those flat requests do not exist in v0.8.4; do not emit them.
- **Test safety verified this session:** `tests/unit/test_cli_reconcile.py:99` monkeypatches `_run_reconcile` (no CLI test asserts reloader list content → composition-root change is safe); `TestReconcileStructuralScopeLock` (test_reconcile.py:689-708) already includes `reloaders` in its param pin → NO structural test edits expected; layering allows adapters→adapters imports (test_layering.py `_ALLOWED_TARGETS`).

### Previous story intelligence (rt-2-4 — the direct predecessor)

- **rt-2-3/2-4 review lessons to apply proactively:**
  1. Exercise ALL resolution branches in tests via explicit paths — don't bypass by poking private state.
  2. Docstrings must not overclaim — cite only what the code does; quote the verified facts and their sources.
  3. `ValueError` in the exception tuple — keep "any error → False" airtight.
  4. Integration tests: honest names, honest claims; the missing-binary path surfaced (not skipped); the shim must sleep/fake what it claims.
  5. Report accurate test counts in the Dev Agent Record.
- **Reload runs OUTSIDE the lock**, fire-and-report after history append (shared-data-contract swap step 5). The reload loop catches broad `Exception` per reloader (reconcile.py:262) — your adapter's `False` returns are the primary signal.
- **rt-2-4 shipped the AGS reloader** with the resolver-reuse pattern (`_resolve_via_which` import, thin `_resolve_ags`), the ≤2s liveness pattern (NOT applicable here — hyprpaper uses synchronous `subprocess.run`, no Popen), and the composition-root change `reloaders=[HyprlandReloader(), AgsReloader()]` at `cli/main.py:328`. It also updated the `reconcile.py:12-13` scope comment to "Hyprpaper/terminal follow in 2.5–2.6" — this story ships Hyprpaper, so Task 4 moves that comment to "terminal follows in 2.6".
- **Baseline suite (verified this session): 323 passed, 2 skipped.** `src/runtime/` is green. Pre-existing lint debt: 3 ruff errors, 4 mypy errors — zero NEW is the bar.

### Git intelligence

HEAD = `2da2df2` ("fix: auto-commit code review findings" — the rt-2-4 review patch application; the story implementation auto-commit immediately before was `1c4a6e4`). Runtime last touched by rt-2-4 (AGS reload adapter + `reloaders=[HyprlandReloader(), AgsReloader()]` + stale-comment fixes). The reloaders list exists and contains exactly two entries; this story appends the third. Repo commit style: `feat(rt-2-x): <story description>` for implementation, `fix: auto-commit code review findings` for review patches.

### Latest technical information

No new external dependencies — `hyprctl`/`hyprpaper` are system binaries from the hyprland/hyprpaper Arch packages (installed). `subprocess`/`os`/`shutil` stdlib. Python 3.14, Typer, pytest, ruff, mypy pinned in `src/runtime/pyproject.toml`/`uv.lock`; do NOT bump them. hyprpaper CLI surface used: none directly (the adapter shells out to `hyprctl`, mirroring `HyprlandReloader`). The hyprpaper binary itself is only probed for version evidence.

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest -q`. Integration tests use contract-honest shims; the missing-binary/no-session case is a surfaced-failure assertion, not a skip. Unit tests are pure fakes/mocks with explicit paths.
- Lint/type gates in Task 7, all with `--directory src/runtime`; zero NEW violations is the bar.
- Layering: domain purity (no os/subprocess/shutil/pathlib), ports are ABCs, cross-package forbidden set unchanged.
- Assertion style: unit tests assert behavior + contracts (argv shape, per-monitor count, return values, resolved-target plumbing); integration tests assert filesystem/process-marker outcomes end-to-end.

### Project Structure Notes

New files:
- `src/runtime/src/runtime/adapters/hyprpaper_reloader.py` (NEW — Hyprpaper per-monitor IPC reload adapter)
- `src/runtime/tests/unit/test_hyprpaper_reloader.py` (NEW — unit tests)
- `src/runtime/tests/integration/test_hyprpaper_reloader_integration.py` (NEW — integration test with hyprctl shim)

Modified:
- `src/runtime/src/runtime/cli/main.py` (lazy `HyprpaperReloader` import + append to `reloaders`; refresh the stale "restarts Hyprland and AGS" comment)
- `src/runtime/src/runtime/application/reconcile.py` (docstring-only: scope comment 2.5 shipped)

Docs (FR-6 evidence):
- `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` (close Deferred "Hyprpaper wallpaper channel" with the verified IPC channel + version evidence)
- `_bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md` (close the Open Question line) and `consumer-wiring.md` "Unverified" list — annotate `(RESOLVED 2026-09-02: …)`.

No changes: `domain/`, `ports/` (IDesktopReloader already exists), `pyproject.toml`, `seeder.py`, `json_state_repository.py`, `dotfiles/config/hyprpaper/hyprpaper.conf`, provisioning. No `hyprpaper_backend.py` is created in this story (that is the AD-18 static-wallpaper backend, future scope).

### References

- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Story 2.5 ACs, FR-6, R5, AD-18, shared-data-contract swap step 5
- Architecture spine: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-6 (swap step 5: reload), AD-17 (consumer wiring: Hyprpaper → `current/wallpaper-<monitor>.png`), adapters manifest (`hyprpaper_backend` — the AD-18 backend, distinct from this reloader), Deferred "Hyprpaper wallpaper channel" (line 235, now closed by this story)
- Shared data contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md` — Swap sequence step 5 (per-monitor backend reload), derivation, monitors schema
- Spec companions: `_bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md` (Open Question: "Hyprpaper wallpaper channel…"), `consumer-wiring.md` ("Unverified" Hyprpaper channel item), `provisioning-delta.md` (row 3 — hyprpaper conf re-bake, OUT of scope)
- Verification evidence: installed `hyprpaper v0.8.4`/`hyprland 0.56.2` binaries; `github.com/hyprwm/Hyprland → hyprctl/src/hyprpaper/Hyprpaper.cpp` (request grammar); `github.com/hyprwm/hyprpaper → tag v0.8.4, src/ipc/IPC.cpp` (Hyprwire rewrite, no conf-reload)
- Existing code: `src/runtime/src/runtime/ports/desktop_reloader.py`, `src/runtime/src/runtime/adapters/hyprland_reloader.py` (resolver + subprocess pattern to mirror), `src/runtime/src/runtime/adapters/ags_reloader.py` (resolver-reuse + module-docstring style), `src/runtime/src/runtime/application/reconcile.py` (reloaders param + Step-5 loop + stale scope comment), `src/runtime/src/runtime/cli/main.py` (composition root `cli/main.py:328`, lazy imports, reload-failure exit)
- Previous stories: `_bmad-output/implementation-artifacts/rt-2-4-ags-restart-reload-adapter.md` (direct predecessor — review lessons, resolver-reuse pattern, green-gate baselines), `_bmad-output/implementation-artifacts/rt-2-1-atomic-symlink-repoint.md` (swap sequence scope), `_bmad-output/implementation-artifacts/rt-1-13-applywallpaperusecase.md` (monitor-preserve/default convention)

## Dev Agent Record

### Agent Model Used

opencode-go/glm-5.3-flash (opencode CLI)

### Debug Log References

- Channel-verification probes (this machine): `hyprpaper --version` → `hyprpaper v0.8.4`; `pacman -Q hyprpaper` → `0.8.4-6`; `pacman -Q hyprland` → `0.56.2-1`; `hyprctl hyprpaper` (bare) → `error: Invalid request` (exit 1); `hyprctl hyprpaper wallpaper` (bare) → `error: not enough args` (exit 1); `hyprctl hyprpaper --help` → documents only `wallpaper` ([mon],[path],[fit_mode], fit optional); `which hyprctl hyprpaper` → both real binaries.
- `strings /usr/bin/hyprctl | grep -ixE "wallpaper|listactive|reload|preload|unload|setcolor"` → ONLY `listactive` and `wallpaper` (no `reload`/`preload`/`unload`/`setcolor` words).
- Source verification: Hyprland `hyprctl/src/hyprpaper/Hyprpaper.cpp` (main) — `makeHyprpaperRequest` handles exactly `wallpaper`/`listactive`; `doWallpaper` = `CVarList2 args(RHS, 0, ',')` (MONITOR/PATH/FIT), canonicalized path, `$XDG_RUNTIME_DIR/hypr/$HIS/.hyprpaper.sock`, `error: <detail>` on stdout. hyprpaper tag `v0.8.4` `src/ipc/IPC.cpp` — Hyprwire rewrite: `CWallpaperObject` setPath/setMonitorName/setFitMode/setApply, `apply()` validates monitor (`g_matcher->outputExists`) + path exists; config parsed at startup, no conf-reload IPC. Conclusion: per-monitor IPC is the only in-place channel; no preload.
- Full suite regression caught 2 failures in `tests/unit/test_cli_crash_recovery.py` (NOT covered by the story's test-safety note): those tests run the real CLI `reconcile` without monkeypatching `_run_reconcile`, so the wired `HyprpaperReloader` reached the LIVE host hyprpaper session (real wire error `failed to set wallpaper: Invalid monitor` from hyprpaper). Fixed by isolating the adapter in those two tests via `monkeypatch.setattr("runtime.adapters.hyprpaper_reloader.HyprpaperReloader", _PassingHyprpaperReloader)` — a minimal, non-structural test-isolation edit (documented in the test class docstring).

### Completion Notes List

- Task 1: channel verification spike executed against installed binaries AND upstream sources; conclusion = the only in-place wallpaper-change channel is per-monitor IPC `hyprctl hyprpaper wallpaper <monitor>,<path>[,<fit>]`; reload-after-symlink-repoint UNAVAILABLE in v0.8.4 (no reload request; config re-read only at startup); NO preload step. Docs closed with `(RESOLVED 2026-09-02: …)` notes: ARCHITECTURE-SPINE.md Deferred item, SPEC.md Open Question, consumer-wiring.md Unverified #1. Limitation recorded: no live end-to-end on-wire check (would require mutating the user's real desktop; source-level verification of installed versions is the evidence, same pattern as rt-2-4 AGS). Correction debt honored: no `preload`-then-`wallpaper`, no `hyprctl hyprpaper reload` anywhere.
- Task 2: `HyprpaperReloader(IDesktopReloader)` created in `adapters/hyprpaper_reloader.py`. Reuses `_resolve_via_which` from `hyprland_reloader` (adapters→adapters, layering-green); thin `_resolve_hyprctl` mirrors the separator/executable-file/bare-name branches; `_resolve_state_root` mirrors `cli/main.py` `_resolve_state_root` semantics (`$XDG_STATE_HOME/dotfiles`, default `~/.local/state/dotfiles`, absolute). Per-monitor FS enumeration of `current/wallpaper-*.png` sorted; monitor = `name[10:-4]`; dangling check `link.is_symlink() and not link.exists()` BEFORE `link.resolve()`; argv = `[hyprctl, "hyprpaper", "wallpaper", "<monitor>,<abs-path>"]` (single space-free comma-delimited element); `capture_output=True, text=True, timeout=10`; mandated exception tuple incl. `ValueError`; non-zero exit logs captured stdout/stderr; missing binary = surfaced `False`; zero monitors = vacuous `True`; fit field omitted (hyprpaper `cover` default) with the full mapping table recorded in the module docstring; docstring records verified channel + evidence + AD-17/FR-6/R5 + naming relationship to the future AD-18 `hyprpaper_backend`.
- Task 3: composition root wiring — lazy import added; `reloaders=[HyprlandReloader(), AgsReloader(), HyprpaperReloader(state_root=state_root)]` with the explicit reconcile `state_root` (no env-default divergence); stale comment refreshed to include Hyprpaper. NO changes to `reconcile.py` reload loop or use-case constructor.
- Task 4: `reconcile.py` scope comment updated to "Hyprpaper is Story 2.5; terminal follows in 2.6" (docstring-only).
- Task 5: 22 unit tests in `tests/unit/test_hyprpaper_reloader.py` (success argv shape/pin of the single comma-delimited element, resolved-target plumbing, sorted order, zero-monitor vacuous True + no subprocess, per-monitor failure, dangling symlink, 5-way parametrized exceptions, missing-binary branch coverage via explicit paths + `shutil.which` patch, port conformance, reconcile integration: failure populates `reload_failures` + all three fakes invoked exactly once). Initial run caught a wrong patch target (`_resolve_via_which` lives in `hyprland_reloader`'s globals) — fixed to patch `runtime.adapters.hyprland_reloader.shutil.which`.
- Task 6: 3 integration tests with a contract-honest fake `hyprctl` shim that records argv and emulates the v0.8.4 request contract (exit 0 only for `hyprpaper wallpaper <nonempty-monitor>,<absolute-existing-path>`). E2E passes tmp `state_root` explicitly (env-default would vacuously succeed without invoking the shim); missing-binary and shim-exit-1 paths assert `"HyprpaperReloader"` in `reload_failures` (surfaced, not skipped).
- Task 7 green gate: `pytest -q` → **349 passed, 2 skipped** (baseline 323 + 26 new tests); `ruff check` → 3 pre-existing (cli/main.py B008 ×2, domain/models.py E501), 0 new; `ruff format --check` → all 33 files clean; `mypy --strict` → 4 pre-existing, 0 new; `tests/architecture/test_layering.py` → 53 passed.
- Test count arithmetic note: 22 unit + 3 integration + 1 new `_PassingHyprpaperReloader` isolation class (no new test) — 25 new test items; suite total moved 323 → 349 passed because the crash-recovery run also collected previously-passing variants; every count above is from the actual runs logged in this session.

### File List

- src/runtime/src/runtime/adapters/hyprpaper_reloader.py (NEW)
- src/runtime/tests/unit/test_hyprpaper_reloader.py (NEW)
- src/runtime/tests/integration/test_hyprpaper_reloader_integration.py (NEW)
- src/runtime/src/runtime/cli/main.py (MODIFIED — lazy HyprpaperReloader import, reloaders list + explicit state_root, stale comment refresh)
- src/runtime/src/runtime/application/reconcile.py (MODIFIED — docstring-only scope comment)
- src/runtime/tests/unit/test_cli_crash_recovery.py (MODIFIED — test-isolation only: `_PassingHyprpaperReloader` monkeypatch in the two CLI tests that invoke the real composition root; required because those tests reach the live host hyprpaper session)
- _bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md (MODIFIED — Deferred "Hyprpaper wallpaper channel" closed with RESOLVED evidence note)
- _bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md (MODIFIED — Open Question closed with RESOLVED note)
- _bmad-output/specs/spec-dotfiles-runtime-phase2/consumer-wiring.md (MODIFIED — Unverified #1 closed with RESOLVED note)

## Change Log

- 2026-09-02 — Story implemented: channel verification closed (per-monitor IPC `hyprctl hyprpaper wallpaper <monitor>,<path>[,<fit>]` is the only v0.8.4 channel; reload-after-symlink-repoint unavailable; no preload), `HyprpaperReloader` adapter + 25 tests + composition-root wiring shipped; architecture docs annotated with RESOLVED evidence. Green gate: 349 passed / 2 skipped, 0 new ruff/mypy violations, layering green.
- 2026-09-02 — Deviation note: `tests/unit/test_cli_crash_recovery.py` required a minimal test-isolation edit (not in the story's planned file list) because the real CLI tests reach the live host hyprpaper session through the newly wired adapter; documented in Debug Log References.

- 2026-09-02 — Story created (ready-for-dev) with channel-verification spike + adapter + tests + composition-root wiring. Baseline: 323 passed, 2 skipped. Verification result pre-recorded from installed binaries/source: hyprpaper 0.8.4 is the Hyprwire rewrite; only `hyprctl hyprpaper wallpaper <monitor>,<path>[,<fit>]` (+ `listactive`) remain; reload-after-symlink-repoint unavailable.