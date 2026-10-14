# Review — Web / Reality Verification

- **Spine:** `_bmad-output/planning-artifacts/architecture/architecture-ags-platform-2026-10-09/ARCHITECTURE-SPINE.md`
- **Codebase:** `/home/inumaki/Development/dotfiles-v3`
- **Reviewer lens:** verify every committed decision was web-researched or reality-checked, not asserted from training data — current library/framework versions, that each named technology still exists and fits, and the live defaults of any starter it leans on.
- **Date:** 2026-10-09
- **Host snapshot:** AGS 3.1.2.r0.gbbee2f1-2 (`ags --version` prints `3.1.0`); GNIM 1.9.1; GJS 1.90.0; Node v26.11.1; npm 12.2.0; Python 3.14.7; uv 0.9.22; gh 2.102.0; TypeScript 5.9.3 (repo `node_modules`).

## Verdict

**Mostly reality-checked, but the Stack table is stale in two rows and hides one forward risk.** The resolution mechanism the spine flags as unverified is actually confirmed working on this host (with a mechanism-naming caveat). The named technologies all exist and fit. One high-severity forward risk (Node type-stripping vs `node_modules`) is not captured anywhere in the spine, and two version claims (AGS, TypeScript) do not match reality/current.

---

## Findings

### F1 — AGS version "3.1.0" is stale; the real unit is 3.1.2

- **Severity:** medium
- **Exact claim (spine):** Stack table, line 201 — `AGS | 3.1.0 — **unpinned** (`aylurs-gtk-shell-git`); see Open Questions`. Doc 101 repeats `AGS (v3.1.0)` (line 116) and Appendix A line 637.
- **What I verified and how:**
  - `pacman -Qi aylurs-gtk-shell-git` → `Version: 3.1.2.r0.gbbee2f1-2`.
  - `/usr/share/ags/js/package.json` → `"version": "3.1.2"`.
  - `ags --version` → `ags version 3.1.0` (the CLI's own string lags the release — likely the `3.1.0` the spine was written from).
  - Web: [Aylur/ags releases](https://github.com/Aylur/ags/releases) — latest is **v3.1.2** (published 2026-04-08); no 3.2+.
  - The AUR also ships a non-git `aylurs-gtk-shell` at 3.1.2 ([AUR](https://aur.archlinux.org/packages/aylurs-gtk-shell)), which is pinnable; provisioning uses the `-git` package (`src/provisioning/ansible/roles/packages/vars/arch.yml:13`).
- **Assessment:** the "unpinned" caveat is correct and important, but the version number is wrong. A reader implementing against the spine would assume 3.1.0 behavior; the host is 3.1.2.
- **Concrete fix:** change the Stack row to `AGS | 3.1.2 (AUR git, unpinned; CLI self-reports 3.1.0)` and, in Open Questions, add the option to switch provisioning from `aylurs-gtk-shell-git` to the versioned `aylurs-gtk-shell` (or pin a git tag) so `node_modules`/esbuild behavior is reproducible.
- **Disposition:** autofix (version string) + discuss (pinning route).

### F2 — TypeScript 5.9 is two major versions behind current (6.0.3 / 7.0.2)

- **Severity:** medium
- **Exact claim (spine):** Stack table, line 202 — `TypeScript | 5.9 (pinned in the gate targets)`.
- **What I verified and how:**
  - Repo pins `typescript@5.9` at `Makefile:138`, `Makefile:228`, `Makefile:294`; installed is 5.9.3 (`node_modules/typescript/package.json`). AGS itself ships `typescript: ^5.9.3` as a devDep (`/usr/share/ags/js/package.json`).
  - Web: [Announcing TypeScript 6.0](https://devblogs.microsoft.com/typescript/announcing-typescript-6-0/) (2026-03-23) and [Announcing TypeScript 7.0](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/) (2026-07-08); npm stable today is **6.0.3**, with **7.0.2** published. 5.9 is the last pre-transition line.
  - Relevant TS 6.0 default changes: `types` now defaults to `[]`; `moduleResolution: node10` deprecated; `target` floats to the current-year ES version. The repo's configs already set `"types": []` (`tsconfig.ags.json`) and `moduleResolution: bundler`/`Bundler` (`tsconfig.ags.json`, `dotfiles/config/ags/tsconfig.bar.json`), so the repo is already aligned with TS 6 defaults.
- **Assessment:** the pin is deliberate and defensible (AGS's shipped `.ts` types were authored against 5.9), but the spine presents it as if current. It is not researched or annotated.
- **Concrete fix:** annotate the pin with why (AGS types/`@girs` compatibility) and add a follow-up to evaluate TS 6.0 (low-risk given the existing config) before/after the platform extraction. Do not silently adopt 7.0 (native port, no stable API until 7.1).
- **Disposition:** discuss.

### F3 — "Astal / GNIM (GJS) | AGS-embedded" conflates two technologies; only GNIM is embedded

- **Severity:** medium
- **Exact claim (spine):** Stack table, line 203 — `Astal / GNIM (GJS) | AGS-embedded`.
- **What I verified and how:**
  - GNIM **is** bundled with AGS: `/usr/share/ags/js/node_modules/gnim/package.json` → `"version": "1.9.1"`, and AGS declares `peerDependencies: { gnim: "^1.9.1" }`. Web: [gnim on npm](https://www.npmjs.com/package/gnim) (1.9.0), AGS v3.1.2 release notes "Update Gnim to 1.9".
  - Astal is **not** embedded. It is a separate collection of Vala/C libraries, installed as its own unpinned git AUR packages (`pacman -Q` → `libastal-git r986.cbcd9f4-1`, `libastal-4-git`, `libastal-notifd-git`, `libastal-tray-git`, `libastal-wireplumber-git`, `libastal-network-git`, `libastal-battery-git`, `libastal-hyprland-git`, `libastal-io-git`), exposed as GI typelibs (`/usr/lib/girepository-1.0/Astal*.typelib`) and imported as `gi://Astal*` (e.g. `src/gui-tools/notifications/app.tsx:4`). Web: [Aylur/astal](https://github.com/Aylur/astal) — "libraries written in Vala and C".
  - AGS depends on `libastal`/`libastal-4` (`pacman -Qi aylurs-gtk-shell-git`, `Depends On`).
- **Assessment:** the row is misleading for an implementer and, more importantly, omits that **Astal is a second unpinned git dependency** on the same critical path as AGS. The pinning Open Question only mentions AGS.
- **Concrete fix:** split the row into `GNIM | 1.9.1 (bundled with AGS)` and `Astal | libastal-* r986 (separate AUR git packages, unpinned)`, and extend the pinning Open Question to cover `libastal-*` as well.
- **Disposition:** autofix.

### F4 — Node's type-stripping refuses `.ts` under `node_modules`; the AD-17 bare-specifier platform will break `node --test` if tests import it

- **Severity:** high (forward risk; blocks the stated test strategy once the platform moves under the node_modules shortcut)
- **Exact claim(s):**
  - Stack table, line 205 — `Test runner (AGS) | Node built-in `node --test` (no vitest/jest)`.
  - AD-17 (lines 157–161): the framework is found **by a bare specifier via a `node_modules` shortcut**.
  - AD-19 (lines 169–173): per-app drift/symbol suites run in the root gate; "Every migration step leaves the tree green."
- **What I verified and how:**
  - Reproduced on this host with Node v26.11.1: a `.ts` entry importing `ags-platform` from `node_modules/ags-platform/index.ts` → `Error [ERR_UNSUPPORTED_NODE_MODULES_TYPE_STRIPPING]: Stripping types is currently unsupported for files under node_modules`. This is Node's documented behavior for the built-in type stripping the repo relies on.
  - The existing workaround, `dotfiles/config/ags/tests/ts/resolve-hooks.mjs`, only rewrites **relative** extensionless specifiers (`specifier.startsWith("./") || "../"`); it does nothing for a bare specifier resolving into `node_modules`. `src/gui-tools/capture-tool/tests/ts/resolve-hooks.mjs` has the same shape.
  - Today's tests import sibling source with explicit `.ts` (e.g. `dotfiles/config/ags/tests/ts/network-icon.test.ts`), so the limitation is not yet hit — but AD-17 moves the shared platform behind a `node_modules` bare specifier, at which point any test that imports the platform through that specifier fails.
  - Node docs confirm the runner is stable ([node:test](https://nodejs.org/api/test.html)); the failure is specific to *source `.ts` inside `node_modules`*, not the runner.
- **Assessment:** the spine freezes a distribution shape (bare specifier → node_modules) and a test runner (native type stripping) whose combination is not viable for source `.ts`. Neither AD-17 nor AD-19 acknowledges it.
- **Concrete fix (pick one, and write it into AD-17/AD-19):**
  1. Ship `ags-platform` compiled (`index.js` + `index.d.ts`) so `node_modules` contains only JS — tests can import it; **or**
  2. Tests import the platform via a relative path / a test-only alias that points at source outside `node_modules`; **or**
  3. Keep the platform as bundled output for tests (mirrors how `ags bundle` already resolves).
  Do **not** assume the existing `resolve-hooks.mjs` covers this — it does not handle bare specifiers.
- **Disposition:** discuss (architecture decision; needs to be settled before extraction).

### F5 — The resolution mechanism is confirmed working on this host, but it is AGS's embedded esbuild, not "Node"

- **Severity:** low (precision); the underlying capability is **confirmed**
- **Exact claim(s):**
  - AD-17 (line 161): "it is found by a **bare specifier** via a `node_modules` shortcut … distinct from the dev-time `ags`/`gnim` built-in aliases."
  - Open Question, line 278: "Node resolution through config symlinks — the shared-ancestor shortcut (AD-17) assumes Node resolves `node_modules` relative to the real install path; verify before relying on it."
- **What I verified and how (reality-check, reproducible):**
  - Built `/tmp/opencode/noderes`: `install/config/node_modules/ags-platform/` (the shared ancestor) + `install/config/ags/app.ts`, with `~/.config/ags -> install/config/ags` symlinked. `ags bundle app.ts out.js -g 4` from the symlinked path inlined the platform (bundle payload decodes to `hello from ags-platform`). Repeating with an app-local `ags/…/node_modules/ags-platform` also inlined (`hello from app-local`). **Both the shared-ancestor and app-local shortcuts resolve through the symlinked entry path.**
  - Built-in aliases confirmed: `ags bundle` of `import { createState } from "ags"` with **no** `node_modules` produced a 92 KB bundle (exit 0).
  - Corroborated by doc 101 §3.2 lines 118–126 and Appendix A line 638 (host-verified: bare specifier for `bundle` **and** `run`, plus `--alias` bundle-only).
  - Caveat: the resolver doing this is AGS's **embedded esbuild** (`github.com/evanw/esbuild` in `/usr/bin/ags`), plus AGS's own `run` transpile — not Node's runtime resolver. `gjs` runs the already-bundled output.
- **Assessment:** the Open Question can be downgraded from "verify before relying on it" to "confirmed on host 2026-10-09; mechanism is esbuild, not Node". The memlog notes there is still **no committed regression test**, so it is host-verified only.
- **Concrete fix:** reword AD-17 and the Open Question to attribute resolution to AGS's embedded esbuild (bundle) / AGS run; add a tiny committed regression test (a fixture app + `ags bundle` + assert the payload) so the behavior is gated, not folklore.
- **Disposition:** autofix (wording) + discuss (add the regression test).

### F6 — AGS's embedded esbuild (0.25.10) lags current (0.28.2) and sits in a published vulnerable range

- **Severity:** low
- **Exact claim (spine):** not stated in the Stack table; implicit in AD-17 (the shortcut relies on esbuild resolution).
- **What I verified and how:** `strings /usr/bin/ags` → `github.com/evanw/esbuild v0.25.10`; web — esbuild latest is **0.28.2** ([npm](https://www.npmjs.com/package/esbuild)), and a 2026 advisory lists a code-injection range covering 0.17.0–0.28.0. This version is determined by the AGS package, not by this repo.
- **Assessment:** not actionable in this repo directly; worth recording because the whole distribution mechanism depends on AGS's bundler behavior and because the unpinned AGS package is what controls it.
- **Concrete fix:** fold into the AGS-pinning Open Question ("resolution/esbuild behavior is a property of the unpinned AGS package; pinning also fixes the bundler version").
- **Disposition:** defer (tied to F1 pinning).

### F7 — "GitHub (private repos) via gh, HTTPS credential helper" is a target decision, not reality-checked in-repo

- **Severity:** low
- **Exact claim (spine):** Stack table, line 206 — `Distribution | GitHub (private repos) via `gh`, HTTPS credential helper`.
- **What I verified and how:**
  - Host prerequisites exist: `gh` 2.102.0 installed; `git config --get-all credential.https://github.com.helper` → `!/home/inumaki/.local/bin/gh auth git-credential` (an HTTPS credential helper backed by gh). So the *mechanism* is real on this machine.
  - No code in the repo implements it: provisioning distributes via Ansible `git clone` of public GitHub repos (`src/provisioning/ansible/group_vars/all.yml:39-41`, `src/provisioning/ansible/playbooks/zsh-tools.yaml:8`); a repo-wide search for `gh auth|gh repo|gh release|private repo` found nothing outside vendored Ansible and the BMad skills.
- **Assessment:** the row reads as current fact but is an unbuilt target. Nothing verifies private-repo access, release creation, or per-app fetching.
- **Concrete fix:** mark the row as decided-not-implemented (like the Deferred/Open-Question sections do elsewhere) and add a provisioning smoke check (e.g. `gh auth status` + a private-repo fetch) before AD-17 ships.
- **Disposition:** discuss/defer.

### F8 — Python 3.14 (uv-managed) is accurate

- **Severity:** none (confirmed)
- **Exact claim:** Stack table, line 204 — `Python runtime | 3.14 (uv-managed)`.
- **What I verified and how:** `.python-version` files = `3.14`; `src/runtime/pyproject.toml:5` and `src/cli-tools/color-scheme-generator/pyproject.toml:5` require `>=3.14` (some shared libs still `>=3.12`); installed `Python 3.14.7`; `uv 0.9.22`. Web: 3.14 is the current bugfix line (3.14.8, 2026-09-30); 3.15.0 released 2026-10-09 ([Python downloads](https://www.python.org/downloads/), [status of versions](https://devguide.python.org/versions/)).
- **Concrete fix:** none. Optionally note 3.15.0 landed the same day (do not chase it).
- **Disposition:** ignore.

### F9 — Node built-in `node --test` is accurate and current

- **Severity:** none (confirmed)
- **Exact claim:** Stack table, line 205.
- **What I verified and how:** repo uses `node --test` (`Makefile:236`, `Makefile:310`); Node v26.11.1 installed; `node:test` is documented **Stable** ([node:test docs](https://nodejs.org/api/test.html)); no vitest/jest anywhere. Node 26 is the Current line, entering LTS Oct 2026.
- **Assessment:** correct — with the F4 caveat about `.ts` under `node_modules`.
- **Disposition:** ignore (see F4).

---

## Confirmed / cleared claims

| Claim (spine) | Verdict | Evidence |
| --- | --- | --- |
| AGS exists, is the right scaffolding tool | ✅ exists & fits | `aylurs-gtk-shell-git 3.1.2`; `ags --help`; web Aylur/AGS |
| AGS embeds esbuild | ✅ confirmed | `strings /usr/bin/ags` → `github.com/evanw/esbuild v0.25.10` |
| `ags`/`gnim` are built-in aliases | ✅ confirmed | `ags bundle` of `import ... from "ags"` with no `node_modules` → 92 KB bundle |
| Bare specifier resolves via `node_modules` shortcut (shared ancestor **and** app-local, through symlinks) | ✅ confirmed on host | `/tmp/opencode/noderes` fixture; doc 101 §3.2 |
| Node built-in test runner, no vitest/jest | ✅ confirmed | `Makefile`; `node:test` Stable |
| Python 3.14 via uv | ✅ confirmed | `.python-version`; pyproject; Python 3.14.7; uv 0.9.22 |
| gh + HTTPS credential helper available | ✅ host prerequisites | `gh 2.102.0`; `credential.https://github.com.helper = !gh auth git-credential` |

## Verification log

- **Files:** `ARCHITECTURE-SPINE.md` (Stack lines 197–206; AD-17 157–161; AD-19 169–173; Open Questions 274–278); `docs/101-ags-platform-architecture.md:114–137,637–639`; `Makefile:58,91,138,228,236,255–257,294,310,535`; `dotfiles/config/ags/tsconfig.bar.json`; `dotfiles/config/ags/tests/ts/resolve-hooks.mjs`; `tsconfig.ags.json`; `src/provisioning/ansible/roles/packages/vars/arch.yml:13`; `src/provisioning/ansible/group_vars/all.yml:39–41`.
- **Commands:** `ags --version`; `pacman -Qi aylurs-gtk-shell-git`; `pacman -Q libastal-*`; `strings /usr/bin/ags`; `node --test`/`node app.ts` fixture; `ags bundle` fixtures; `git config --get-all credential.https://github.com.helper`.
- **Web:** Aylur/ags releases (v3.1.2, 2026-04-08); TypeScript 6.0 (2026-03-23) / 7.0 (2026-07-08) / npm 6.0.3, 7.0.2; Python 3.14.8 (2026-09-30) & 3.15.0 (2026-10-09); esbuild 0.28.2; gnim 1.9; Aylur/astal; node:test Stable; Node 26 LTS Oct 2026.
