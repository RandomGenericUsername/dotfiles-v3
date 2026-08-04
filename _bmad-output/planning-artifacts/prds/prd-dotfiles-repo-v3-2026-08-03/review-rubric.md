# PRD Quality Review — Dotfiles System Phase 1 — Provisioning

## Overall verdict

A strong chain-top capability spec: every FR carries a testable consequence, scope is de-scoped honestly (Non-Goals, Out-of-Scope-for-MVP, Non-Users all present), trade-offs are surfaced via counter-metrics, and the FR/NFR numbering matches the epics decomposition exactly so downstream extraction is clean. The at-risk spots concentrate in FR-25 (§4.7), whose "verify after a dry-run bootstrap" acceptance is physically infeasible and contradicts the decomposition's own correction (apply+verify on a disposable target), plus two "everything is locked" overclaims in §9/§10 that hide a real residual (the run-as-user privilege decision) and silently inherit the SPEC's seven assumptions. Fix the FR-25 language and the PRD is essentially build-ready.

## Decision-readiness — strong

The decisions that matter are stated as decisions, not hedged: the `plan`/`apply` diff-then-execute loop via Ansible's native `--check` (FR-1), Ansible as the state authority with no `provisioning-state.json` (FR-2, NFR-2), `overwrite=true` scoped to the single default-palette task via `environment: COLORSCHEME__OUTPUT__OVERWRITE: "true"` (FR-18), and the §11 boundary enforced mechanically (FR-24). Trade-offs are named with what is given up, not just what was chosen: SM-C1 ("a slow, verifiable `bootstrap` is strictly preferred to a fast one that can leave the machine partially provisioned") and SM-C2 (size/simplicity vs. the §11 boundary). Non-Goals (§6) and Out-of-Scope for MVP (§7.2) make the cut line explicit. The one blemish is a blanket "None" in §9.

### Findings
- **[medium]** [Open Questions: None overstates the lock] (§9, cf. §0) — §9 asserts "None" because the SPEC declares none, but the decomposition this PRD cites as a locked input (epics story 2.3) contemplates a genuinely unresolved decision: whether a single run context can satisfy both privileged steps (`makepkg -si`, `pacman`/`apt`) and user-scoped steps (`uv tool install`, `~/.config` symlinks), "recorded as an open question for the run-as-user decision." A chain-top reader of this PRD would assume full lock and miss a real implementation risk in the packages role. *Fix:* either note the residual run-as-user decision in §9 with a pointer to story 2.3, or confirm it was resolved in the provisioning plan and say so.

## Substance over theater — strong

No furniture. Single persona (Diego) with persona + context inline in UJ-1; Non-Users (§2.2) do real scoping work — they remove Phase 2 runtime reconcilers, root-`dotfiles`-CLI users, and receipt/content-hash users from v1. The Vision (§1) is product-specific: it names the three compute providers, the capability boundary ("it does not reconcile the desktop"), and the trust loop (plan before mutation, verify as a hard gate). NFRs are substantive, each with a mechanism and validating FRs — NFR-1 (Ansible as state authority), NFR-4 (§11 via `test_layering.py`), NFR-6 (parse via each tool's `--config` gate) — and there is no boilerplate scalability/security NFR. §4.8 is an honest stub ("None unique to any single feature...") rather than invented content.

## Strategic coherence — strong

The thesis is stated and held: Phase 1 makes the machine *capable* so the Phase 2 runtime's §12 preconditions hold. The features serve one arc — capability (CLI + hexagon, §4.1–4.3), content (manifests + roles, §4.4–4.5), proof (bootstrap + integration, §4.6–4.7) — which maps cleanly to Epics 1→2→3. Success metrics validate the thesis rather than measuring activity: SM-1 (fresh-machine bootstrap green), SM-2 (plan diffs, mutates nothing), SM-3 (verify green after re-apply — idempotency), SM-4 (spine data flow), SM-5 (boundary test). Counter-metrics SM-C1/C2 guard the thesis against the natural pull toward speed and convenience. MVP scope kind (platform/enabling layer feeding a later runtime) matches the scope logic.

## Done-ness clarity — adequate

This is where the PRD is densest and best: nearly every FR ends with "Consequences (testable)" that are concrete and checkable — exit codes, "no drift" on a second consecutive run, the seam extra-var keys pinned by a test (FR-10), "a deliberately-violating import fails the test" (FR-24), "existing `dotfiles/config/{nvim,starship,wlogout,zsh}/` dirs are unchanged" (FR-23). I found no "handles gracefully," "reasonable performance," or "user-friendly" language in the FRs; NFRs carry mechanisms, not adjectives. One FR breaks the pattern and drags the dimension down.

### Findings
- **[high]** [FR-25 verify-after-dry-run is infeasible as written] (§4.7 FR-25) — "a verify test asserting all ten done-criteria hold after a dry-run bootstrap" asserts a physical impossibility: `--check` leaves no state behind, so the ten done-criteria cannot hold after it. This contradicts the decomposition this PRD claims to mirror (epics story 3.2), which explicitly requires a *real* `apply` followed by `verify` "on a disposable/container target — not after `--check`, which cannot leave state behind" — and the PRD also silently drops the disposable/container-target mechanism. Downstream story creation pulling FR-25 as written would bake in an impossible acceptance criterion. *Fix:* rephrase to "a verify test asserting the ten done-criteria hold after a real `apply` on a disposable/container target; a separate dry-run test proves every playbook `--check`s cleanly with no mutation."

## Scope honesty — adequate

De-scoping is exemplary and explicit: Non-Goals (§6, nine items), Out-of-Scope for MVP with deferral annotations (§7.2), Non-Users (§2.2), and per-FR Out-of-Scope (FR-1 excludes any non-Ansible diff engine). No silent cuts. The gap is the claim that nothing is assumed.

### Findings
- **[medium]** [Assumptions Index overclaims; the SPEC's seven assumptions are inherited, not indexed] (§10) — §10 says "No `[ASSUMPTION]` tags were required: every requirement in this PRD is distilled from locked sources," yet the SPEC it distills carries a formal seven-item Assumptions section that the PRD silently leans on — e.g. `default.png` verified present in `wallpapers.tar.gz` (underpins FR-17/FR-18), CSG ships the `conf` (Hyprland) output format (underpins FR-18/FR-19), `$XDG_DATA_HOME` defaults to `~/.local/share` when unset (underpins the install-dir resolution). Inheriting these without a tag or index note breaks the roundtrip a downstream reader relies on to distinguish load-bearing facts from inferences. *Fix:* add an Assumptions Index entry stating "SPEC §Assumptions (7 items) inherited as locked; no new assumptions added," making the inheritance explicit.

## Downstream usability — adequate

Extractability is generally excellent: the Glossary (§3) defines every load-bearing noun with one consistent definition (install spine/install dir, §11 boundary, §12 preconditions, done-criteria, default palette); FR-1…25 and NFR-1…9 are unique and match the epics document exactly (the §0 structure note promises this, and it holds); SM/NFR cross-references all resolve ("Validates FR-2, FR-3, NFR-1, CAP-2, CAP-3"); CAP references resolve to the SPEC via §0. The exception is FR-25's content drift from the canonical decomposition, which is a downstream-consistency failure as much as a done-ness one.

### Findings
- **[low]** [FR-25 drops the Phase 2 `--templates-dir` invocation-contract test] (§4.7 FR-25 vs. epics story 3.3) — epics story 3.3's final acceptance criterion ("CSG invoked with `--templates-dir <install>/csg-templates/` renders from the spine templates") is absent from FR-25, even though §3/FR-21 note the templates dir is not a settings field. Without it the spine-chain guarantee is only half-locked. *Fix:* add a CSG `--templates-dir <install>/csg-templates/` assertion to FR-25's spine-chain consequence.
- Cross-ref: the FR-25 verify-after-dry-run issue (see Done-ness clarity, high) is a content divergence from the decomposition this PRD promises to match, so it belongs on the downstream-consistency ledger too.

## Shape fit — strong

Correct shape for the stakes. Internal tool, single-operator role → capability-spec form, and the PRD says so explicitly (§2.3: "journeys are kept light — one per command surface"). Three UJs with one named protagonist (Diego) carry real decision weight (they map to FR-1/2/3/4 and the UJ-1 edge case maps to distro handling), Non-Users stand in for a persona gallery, SMs are operational rather than user-facing, and traceability to the SPEC (CAP-1…5) is maintained. Neither over-formalized (a single-operator tool with only three light UJs) nor under-formalized (consequences carry the acceptance load).

## Mechanical notes

- ID continuity: FR-1…25 and NFR-1…9 are unique, contiguous, and match the epics document; SM-1…5 plus SM-C1/C2 all resolve. Minor: §4.3 lists FR-10 before FR-9 (numeric order broken within one grouping); §4.1 places FR-11 before FR-6 (intentional grouping, covered by the §0 structure note).
- CAP-1…5 are referenced (SM-1…4, FR-25) without local definitions; intentional — §0 declares the SPEC canonical and not duplicated — and it resolves for readers holding both docs.
- Assumptions Index roundtrip: no inline `[ASSUMPTION]` tags, so trivially consistent — but see the scope-honesty finding on the SPEC-inheritance claim.
- UJ protagonists: Diego carries persona + context inline in UJ-1; UJ-2/UJ-3 are command-surface only, which is calibrated-acceptable for a single-operator tool.
- Glossary consistency: "install spine" / "install dir" / "install-dir subtree" variants are covered by the single "Install dir / install spine" entry and used consistently (hyphenated "install-dir subtree" in FRs).
- Required sections present for the stakes: Vision, Target User, Glossary, Features, NFRs, Non-Goals, MVP Scope, Success Metrics, Open Questions, Assumptions Index.
