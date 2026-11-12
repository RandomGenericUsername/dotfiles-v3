---
id: REQ-115
title: "Provision Evolution and gnome-keyring from the dotfiles composition"
kind: requirement
status: proposed
lane: direct
links:
  openspec: none
  bmad: none
worktree: .worktrees/REQ-115/
branch: ticket/REQ-115-evolution-secret-service
---

# Provision Evolution + gnome-keyring

## Requirement

The dotfiles composition must install everything needed to run Evolution and
store its OAuth credentials, so a fresh provisioned machine can launch
Evolution and complete Google sign-in without a manual `pacman -S` step.

This ticket is the composition half of the cross-repo requirement. The engine
half is `dotfiles-provision` **REQ-046**
(`tickets/REQ-046-evolution-secret-service/ticket.md`).

## Triage

Current composition state:

- `dotfiles/provisioning/packages.yaml` lists `thunderbird` under the mail
  client entry but has no `evolution` or `gnome-keyring`.
- The current installer pin predates any secret-service support.
- `gnome-keyring` provides `org.freedesktop.secrets`; `evolution` depends on
  `libsecret` and `evolution-data-server` transitively.
- The previous manual Evolution failure was `The name is not activatable`
  because no secret service was present. This ticket removes that manual gap.

## Decisions

- Add `evolution` and `gnome-keyring` as first-class composition package
  entries; keep `thunderbird`.
- Rely on D-Bus activation for `gnome-keyring`; no Hyprland autostart entry and
  no PAM edits.
- Do not add `evolution-data-server` or `libsecret` separately; package
  dependencies own them.
- The browser OAuth consent step remains manual by design; provisioning only
  guarantees the client and secret service are installed and activatable.

## Work

1. Add to `dotfiles/provisioning/packages.yaml` under the mail/client area:
   - `evolution` — email client
   - `gnome-keyring` — `org.freedesktop.secrets` provider for libsecret
2. Bump `dotfiles/provisioning/installer.pin` to the engine release produced by
   REQ-046. Do not guess the tag: read it from the engine release.
3. Run `make deploy-coverage` and `make gates-ci`.
4. Commit the package list and pin separately from any engine work.
5. Tag/push the next free composition release; apply/verify from this checkout.
6. Record live evidence:
   - `command -v evolution`, `command -v gnome-keyring-daemon`
   - `pacman -Q evolution gnome-keyring`
   - `secret-tool` store/lookup round-trip, then clear
   - fresh Evolution Google OAuth flow with no `not activatable`
   - `dotfiles-provision verify` and `dotfiles-runtime doctor` clean

## Non-goals

- No AGS/bar/assets/platform/runtime changes.
- No replacing or removing Thunderbird.
- No automatic OAuth, secret migration, or token storage in the repo.
- No PAM/autostart/keyring-unlock changes.
- No manual package install presented as the fix.

## Dependencies and sequencing

1. Engine REQ-046 must release first with the package mappings, tests, verify
   probes, and installer tag.
2. This ticket pins that released tag.
3. Only then apply and validate. The engine worktree must not edit this
   composition, and this ticket must not guess an unreleased pin.

## Acceptance

- [ ] `packages.yaml` declares `evolution` and `gnome-keyring`; `thunderbird`
  remains.
- [ ] `installer.pin` points at the engine release containing REQ-046.
- [ ] `make deploy-coverage` and `make gates-ci` pass.
- [ ] A fresh `apply` installs both packages without a manual install command.
- [ ] `verify` gates the Evolution binary and the secret-service D-Bus service.
- [ ] `secret-tool` round-trip works, and Evolution completes a fresh Google
  OAuth flow without `The name is not activatable`.
- [ ] Re-running `apply` is idempotent and does not remove the user's existing
  mail packages.
- [ ] Composition tag is immutable, pushed, and recorded here.

## Start gate

Do not implement until the user explicitly says go. When approved, the
orchestrator dispatches the engine and composition agents; this ticket remains
the composition source of truth.
