# HANDOFF — provisioned session must keep its always-on AGS instances running

**Audience:** an implementing/verifying agent. This document hands over a *requirement and its
context*. The investigation of *which existing provisioning pattern to use* is yours — that is
deliberately not answered here.
**Repo:** `/home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3`
**Branch:** `master` (no `main`; `origin/HEAD -> origin/master`).
**State at handoff:** clean tree, `master` == `origin/master` at `309afd5`.

---

## 1. Requirement

**After any provisioning run, the session must still have its always-on AGS instances running —
at minimum the status bar (`ags`) and the notification daemon (`notifications`).**

Today any playbook that executes the `gui_tools` quit loop leaves them quit until the next login.
For the bar that is a missing status bar; for the notification overlay it is worse: the overlay is
the session's only notification daemon (dunst is deliberately masked), so **nothing owns
`org.freedesktop.Notifications` and every notification is silently dropped** — the user sees
notifications stop working with no error anywhere.

The fix MUST follow the pattern that already exists in this provisioning process. There is
believed to be one; finding it and conforming to it is the core investigative task. Do not invent a
new mechanism if an existing one fits.

---

## 2. Evidence (verified on the host, this session)

| Fact | Evidence |
|---|---|
| After a provision run the overlay is **not running** | `ags list` → `ags, capture, hypr-pano, icon-color-mapping-editor, wallpaper-selector` — **no `notifications`** |
| Nothing owns the notification bus | `gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.GetNameOwner org.freedesktop.Notifications` → `NameHasNoOwner` |
| dunst cannot take over (by design) | `systemctl --user is-enabled dunst.service` → `masked`; `is-active` → `inactive` |
| The overlay itself is healthy | starting it manually (`ags run -d ~/.config/ags-notifications --log-file ~/.local/state/ags/notifications.log`) works: it owns the bus (unique name returned) and `notify-send` renders a card. `~/.local/state/ags/notifications.log` is empty — **no crash**. It was simply never (re)started. |
| The emitter side is fine | `~/.local/state/capture-tool/notify.log` shows `outcome=sent` / `outcome=closed` — the capture tool emits; with no daemon the message goes nowhere |
| The quit loop is the cause | `src/provisioning/ansible/roles/gui_tools/tasks/main.yml` — "Quit running AGS instances to pick up updated sources on next launch": `ags quit -i {{ item }}` over `gui_tools_ags_instances` (`ags`, `capture`, `icon-color-mapping-editor`, `hypr-pano`, `wallpaper-selector`, `notifications`), `failed_when: false`, `changed_when: false` |
| Only login restarts them | `dotfiles/config/hypr/autostart.lua` — `ags run` (bar), a staggered `ags run -d $HOME/.config/ags-notifications --log-file …` (overlay), staggered capture |
| Same class of bug was already hit once | provisioning also quits the **bar**, so a provision run leaves the user with no status bar until re-login (reported earlier by the user, never fixed) |

---

## 3. The investigation (yours)

Determine the established pattern for "this process must be running when provisioning finishes" and
apply it to the always-on AGS instances. Pointers — **not conclusions**, verify each yourself:

- **Runtime systemd user units.** `src/provisioning/ansible/roles/runtime_daemon/templates/dotfiles-runtime-daemon.service.j2`
  and `runtime_clipboard/templates/dotfiles-runtime-clipboard.service.j2`; their roles use
  `systemctl --user` (enable / start / restart, `daemon-reload`, active-state assertions). If the
  house pattern is "long-lived process ⇒ user unit", the AGS instances may belong there — but AGS is
  currently *not* unit-managed anywhere, so weigh that against the next bullet.
- **The runtime's own AGS reload path.** `src/runtime/src/runtime/adapters/ags_reloader.py` already
  restarts running `ags run -d` instances (used after a palette swap so consumers pick up a new
  `colors.css`). That is an existing "restart AGS instances by name" capability — check whether it
  can be reused/invoked from provisioning rather than duplicated.
- **The start-if-down launcher precedent.** `src/provisioning/ansible/roles/cli_tools/templates/capture-ui.j2`
  implements toggle-if-running / start-if-down / zombie-safe semantics for the capture instance
  (`ags list | grep -qx` then `ags toggle`, else `ags quit` + fresh `ags run -d`). A sibling
  launcher or the same semantics may be the right shape for the always-on instances.
- **Where the quit loop lives** and what its contract is (it exists so the *next* launch re-bundles
  TypeScript — a restart on the spot satisfies that at least as well).

Whatever you choose must satisfy §1 without violating §5.

---

## 4. Acceptance

1. On a live session, run a playbook that executes the quit loop (e.g. `playbooks/gui-tools.yaml`)
   and then, **without logging out**:
   - `ags list` shows both `ags` and `notifications`;
   - `gdbus … GetNameOwner org.freedesktop.Notifications` returns an owner;
   - `notify-send "x" "y"` renders a card.
2. `verify` asserts the outcome, and a **negative lock** in
   `src/provisioning/tests/unit/test_verify_role.py` proves the gate fails when the overlay is down
   (mirror the dunst-mask / directory-handler gates added in `309afd5`).
3. `--check` runs mutate nothing (no process starts/quits under check mode).
4. Re-running is idempotent: no duplicate instances, no error when the instance is already running
   (AGS refuses a second instance with the same name on `/run/user/$UID/ags.js`).

---

## 5. Non-goals / do not

- Do **not** un-mask or restart **dunst**; it is masked on purpose so the overlay can own the bus
  (and both are asserted).
- Do **not** start the **on-demand** GUI tools (`capture`, `hypr-pano`, `wallpaper-selector`,
  `icon-color-mapping-editor`) — they are keybind-launched and starting them from provisioning would
  open windows nobody asked for.
- Do **not** change login-time autostart semantics; this is about the *provisioning* lifecycle.
- Do not introduce a second source of truth for "which instances are always on" — extend the
  existing vars/structure in `gui_tools/vars/main.yml`.

---

## 6. Verification commands

```sh
# state
ags list
gdbus call --session --dest org.freedesktop.DBus \
  --object-path /org/freedesktop/DBus \
  --method org.freedesktop.DBus.GetNameOwner org.freedesktop.Notifications
notify-send "test" "body"

# the provisioning slice under test (run from src/provisioning/ansible)
ANSIBLE_CONFIG=ansible.cfg ../.venv/bin/ansible-playbook -i inventory/localhost.yaml \
  -e os_family=arch -e install_dir="$HOME/.local/share/dotfiles" playbooks/gui-tools.yaml

# gates
cd src/provisioning && .venv/bin/python -m pytest tests/unit/test_verify_role.py tests/unit/test_gui_tools_role.py -q
```

---

## 7. Pitfalls

- **Detaching matters.** If the chosen mechanism backgrounds a long-lived process from an Ansible
  task, it must fully detach (redirect stdout/stderr, `&`/`disown`, or the module's async form) or
  the task hangs and/or the child dies with the connection. Prove the process SURVIVES the playbook
  exiting — that is the whole point.
- **No session, no bus.** Provisioning can run where `systemctl --user` / a Wayland session is
  unavailable; use the repo's existing discipline (`failed_when: false` on the user-session command
  + a `verify` gate that makes a real failure loud) rather than making provisioning brittle.
- **A stale pacman DB lock blocks unrelated runs.** `/var/lib/pacman/db.lck` was found stale (from
  10:16, no pacman running) and made `playbooks/packages.yaml` fail with "unable to lock database";
  it was removed. If `packages` fails that way, check for a real pacman first, then for staleness.
- AGS instance names are global per user (`/run/user/$UID/ags.js`): starting an already-running
  instance must be a no-op, not a collision error.

---

## 8. Key reference files

| What | Path |
|---|---|
| The quit loop + dunst mask (the code that causes this) | `src/provisioning/ansible/roles/gui_tools/tasks/main.yml` |
| Instance list, dirs, state dirs | `src/provisioning/ansible/roles/gui_tools/vars/main.yml` |
| Login-time starts (bar, overlay, capture) | `dotfiles/config/hypr/autostart.lua` |
| Gate patterns to mirror (masked unit, directory handler, binary scripts) | `src/provisioning/ansible/roles/verify/{vars,tasks}/main.yml` |
| Negative-lock + stub patterns | `src/provisioning/tests/unit/test_verify_role.py` |
| Restart-AGS-instances precedent | `src/runtime/src/runtime/adapters/ags_reloader.py` |
| Start-if-down launcher precedent | `src/provisioning/ansible/roles/cli_tools/templates/capture-ui.j2` |
| systemd --user unit precedent | `src/provisioning/ansible/roles/runtime_{daemon,clipboard}/templates/*.service.j2` |
| Notification overlay app | `src/gui-tools/notifications/` |

---

## 9. Related work landed in `309afd5` (context)

The same "provisioning must leave a working machine" theme produced these, already on `master` and
asserted by `verify`: the dunst stop+mask with a verify gate, the pinned `inode/directory` handler
(`Show in folder` opened a terminal), the AstalNotifd binding gate, and the capture binaries/icon
group assertions. This handoff is the missing piece of that set.
