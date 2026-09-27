# Tasks: Wi-Fi Settings footer opens nm-connection-editor

- [x] 1. Wire the footer click → `execAsync(["nm-connection-editor"])` + error log + missing-binary fallback message.
- [ ] 2. Provision + restart AGS; click footer → editor opens; hover affordance confirmed.
- [ ] 3. Negative: hide binary from PATH → guidance message, no crash.
- [ ] 4. Parity gate green (handler-only: expect zero new classes); screenshot footer rows vs mock anchors.

Verification: `packages.yaml` + both group_vars mappings present (landed);
`test_packages_role.py` green.
