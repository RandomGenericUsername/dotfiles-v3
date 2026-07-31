# CSG Test Characterization & Hardening

Overhaul the color-scheme-generator (csg) test suite: characterize real CLI behavior via CliRunner with fakes at port boundaries, add config resolution-chain and ENV-override coverage, harden container mount-plan assertions, remove the inert `min`/`max` catalog range fields, replace `test_user_journey.sh` with per-command CliRunner tests, and flag known behavioral inconsistencies as xfail tests.
