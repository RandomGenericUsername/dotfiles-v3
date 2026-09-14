# HANDOFF — hypr-pano clipboard manager → main

Coordination note for the agent working on `main`. Read this before merging
`feat/hypr-pano-clipboard`.

## TL;DR

The bulk of this work is **already merged into `main`** via `7a2a7e6`
(`a1de8bf` clipboard manager + `fdb4090` shared icon pack). Only **one commit
is unmerged**:

- `58932e5` — `fix(hypr-pano): stop rebuilding the list on arrow navigation`
  (touches only `src/gui-tools/hypr-pano/ui/ItemCard.tsx` +
  `ui/PanoWindow.tsx`)

The merge is **conflict-free** (see verification). After merging, run a normal
bootstrap/apply so the overlay + icons + runtime topics are provisioned, and
restart the daemon (step 1 below).

## Verified merge status

At the time of writing (feature `58932e5`, `main` `49781d5`, main worktree
clean):

```bash
git merge-tree --write-tree --name-only main feat/hypr-pano-clipboard   # exit 0
git -C <main> merge-base --is-ancestor a1de8bf main                     # in main
git -C <main> merge-base --is-ancestor fdb4090 main                     # in main
git -C <main> merge-base --is-ancestor 58932e5 main                     # NOT yet
```

## How to merge

```bash
git checkout main
git merge --no-ff feat/hypr-pano-clipboard -m "Merge branch 'feat/hypr-pano-clipboard'"
```

Clean, no conflicts. To take only the fix instead:
`git cherry-pick 58932e5`.

## What the change is

A Hyprland clipboard history manager built on the Phase 5 hub:

- **Runtime**: `dotfiles-runtime clipboard` resident job — `wl-paste`
  `wlr-data-control` watch (declared polling fallback), JSON history store
  (atomic, hash dedupe, per-kind eviction, orphan cleanup), file-only per-kind
  retention config, emits `clipboard.update`/`clipboard.state`, serves hub
  `Control` for incognito. New files under
  `src/runtime/src/runtime/{domain,ports,adapters,application}/*clipboard*`
  plus `tests/**`; CLI command in `cli/main.py`; additive topics in
  `contracts/event-contract.{json,md}` + hub `KNOWN_TOPICS`/`CONTROL_ALLOWLIST`
  + `emit_validation.TOPIC_SCHEMAS` (all additive on `org.dotfiles.Events1`).
- **AGS overlay**: `src/gui-tools/hypr-pano/` — bottom layer-shell overlay,
  search, keyboard nav (arrows/`Enter`/`Ctrl+1..9`/`Delete`/`Ctrl+F`),
  per-type previews, position badges, incognito toggle; themed from the
  generated palette; shares the `ui` icon pack via `lib/icon-registry.ts`.
- **Shared icon pack**: `dotfiles/assets/icon-templates/ui/`
  (`search/text/image/link/code/color/emoji`), group `ui` in
  `icon-mappings/icons.yaml`, rendered by ITR and advertised in the shared AGS
  `icons.json`.
- **Provisioning**: new `runtime_clipboard` role (systemd user unit,
  restart-on-template-change) + `playbooks/runtime-clipboard.yaml` + bootstrap
  import; `gui_tools` places `ags-hypr-pano/`; `config_links` symlinks
  `~/.config/ags-hypr-pano`; `cli_tools` installs the `hypr-pano-ui` launcher;
  `SUPER+V` keybind; autostart. **Replaces the dormant `cliphist` stopgap**
  (autostart lines removed, `cliphist` dropped from `packages.yaml`).
- **OpenSpec**: change `add-hypr-pano-clipboard-manager`.

## Post-merge operational steps

1. **Restart the daemon after the runtime is (re)installed.** The new topics
   are additive, but a *code-only* runtime change does not restart the daemon
   via the unit-template handler. After `cli_tools` force-installs the runtime:
   ```bash
   systemctl --user restart dotfiles-runtime-daemon.service
   ```
   Otherwise the hub answers `UnknownTopic: clipboard.update/state` and the
   overlay loses live updates (history still loads from disk).

2. **Provision to deploy the overlay + icons + manifest:**
   - `assets` playbook → places `icon-templates/ui/` + `icon-mappings/icons.yaml`
   - `compositor-configs` playbook → regenerates `config/ags/icons.json`
     (now includes the `ui` group)
   - runtime derive (`uv run --directory src/runtime dotfiles-runtime wallpaper
     set <wallpaper>` **from the repo**, or `reconcile`) → renders
     `current/icons/ui-*.svg`
   - `gui_tools` → deploys `ags-hypr-pano/` (incl. `lib/icon-registry.ts`)
   - `config-links` + `cli_tools` → `~/.config/ags-hypr-pano` symlink +
     `hypr-pano-ui` launcher

3. Provisioning's `gui_tools` quits the running `hypr-pano` AGS instance so the
   next launch re-bundles; the `SUPER+V` launcher (or autostart at next login)
   brings it back. `SUPER+V` also needs `hyprctl reload` in the current session
   after the keybind is (re)placed.

## Verification commands

```bash
# runtime unit + architecture (fast):
(cd src/runtime && uv run --frozen pytest tests/unit tests/architecture -q)  # ~1618 passed
# AGS overlay contract + bundle:
(cd src/gui-tools/hypr-pano && node tests/event-contract-drift.mjs && \
  ags bundle app.tsx /tmp/hp.js -r "$PWD" --gtk 4)
# provisioning slices touched by this branch:
(cd src/provisioning && .venv/bin/pytest -q tests/unit/test_gui_tools_role.py \
  tests/unit/test_runtime_clipboard_role.py tests/unit/test_verify_role.py)
```

Manual smoke: rapid held `←/→` must stay smooth (the `58932e5` fix);
`Enter`/`Ctrl+1..9` copy, `Delete`, `Ctrl+F`, `Esc`, incognito toggle.

## Known non-blockers / pitfalls

- **`csg` integration test**: `tests/integration/test_csg_adapter_integration_real_binary`
  fails until `cli_tools` upgrades `csg` (its installed bundle lacks
  `colors.kitty.j2`; `csg dump-templates` omits it). Environmental, unrelated
  to this branch.
- **Palette eviction pitfall** (flag; may be partly fixed by `75c5c9b`):
  `reconcile` can evict a "pre-growth" palette cache entry and leave
  `~/.local/state/dotfiles/current/colors.*` dangling, while `wallpaper set`
  then skips regeneration because `current.json` still records the hash —
  breaking GTK/rofi/terminal colors. Recovery: back up + remove `current.json`
  and re-run `wallpaper set` from the repo.
- **`cliphist`**: the two `wl-paste --watch cliphist store` autostart lines are
  removed and `cliphist` is dropped from `packages.yaml`. If another branch
  re-added either, resolve in favor of the single `dotfiles-runtime clipboard`
  watcher.
- **Icon fallback is cosmetic**: without the `compositor-configs` manifest
  regen + runtime icon render, cards use stock symbolic icons; the `ui-*.svg`
  glyphs appear once rendered.
- **Do not commit `src/gui-tools/hypr_pano/`** (underscore) — an untracked
  reference prototype only.
- **Do not reinstall the runtime from a tree lacking these commits** — they are
  on `main` after the merge.
- **OpenSpec task `7.2` (VM end-to-end smoke)** was intentionally left
  unchecked; complete it, then archive `add-hypr-pano-clipboard-manager`.

## Remove after merge

Once merged and provisioned:

```bash
git worktree remove /home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3-clipboard
git branch -d feat/hypr-pano-clipboard
```
