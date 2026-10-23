# 2026-10-23 archive cleanup batch

This batch archived **34 active changes whose task lists were fully checked** (`[x]`, no `[ ]`)
to keep `openspec/changes/` focused on work that is still in flight. The 11 `wifi-*` changes
archived the same day are a separate superseded batch (see each `SUPERSEDED.md`).

Archived with `--skip-specs`: the changes are complete, and re-applying their deltas would risk
duplicate requirements in the main specs. Their artifacts remain intact under
`openspec/changes/archive/2026-10-23-<name>/` for provenance.

Batch members:

- add-btop-theme-studio
- add-csg-btop-theme-formats
- add-icon-contrast-guard
- add-icon-templates-renderer
- add-runtime-btop-theme-artifacts
- add-runtime-btop-theme-reload
- add-speedtest-notifications
- ags-apps-bar-first
- ags-consume-platform
- cli-output-cli-integration
- declare-capture-test-dependencies
- extract-capture-gui-tool
- extract-platform-in-place
- finish-audio-panel-redesign
- fix-capture-monitor-lifecycle
- fix-capture-per-monitor-state
- fix-verify-hyprland-probe-check-gate
- harden-extraction-gates
- harden-verify-probes-and-manifest
- kit-shell-four-shapes
- migrate-widgets-to-shapes
- one-event-client
- param-validation-and-explicit-output-hardening
- preferences-notifier-theme
- provision-btop-config
- reactive-domain-read-models
- relocate-dev-vm-harness
- relocate-gloview-activate
- remove-orchestrate-v5
- repair-package-manifest-drift
- repoint-runtime-to-generated-contract
- surfaces-popup-host
- swap-battery-icons-rounded
- uniform-icon-contract

Validation after the batch: `openspec validate --all` → `90 passed, 0 failed`.
