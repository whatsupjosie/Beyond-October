# Iteration Wallet Standalone Blockers

## Active Blockers

No hard blocker currently prevents continued safe work inside this standalone folder.

## Known Limitations

### Runtime Development Tests Not Yet Run

Status: NOT RUN

Reason:

- The reference test files were copied from loose historical artifacts and may expect older module names or destructive cleanup patterns.
- The product rule forbids executing custodied user code. Development checks are allowed only after reviewing that they do not exercise unsafe product behavior.

Next safe step:

- Use static scans first.
- Review test imports and cleanup behavior before running any test command.

### Copied Tests Need No-Delete Review

Status: PARTIAL

Reason:

- One copied receipt test used `Path(...).unlink()` to simulate tamper and was moved to `rubish\unsafe_reference_tests`.
- Remaining copied tests no longer match the direct destructive-pattern scan, but they have not been fully reviewed for fixture cleanup behavior or historical import assumptions.

Next safe step:

- Build or rewrite no-delete-safe proof tests before running broad pytest.

### BlackBox Source Was Not In Latest Temp Intake

Status: PARTIAL

Reason:

- `blackbox.py` was not present in `iteration_wallet_temp_latest_ref_20260627_092504`.
- A standalone `blackbox.py` was copied from the v2.1.9 BlackBox/Vault coupling reference.

Next safe step:

- Review `iteration_wallet\blackbox.py` against `notification_manager.py`, `gatekeeper.py`, and receipt tests before treating BlackBox as fully integrated.

### Misclassified Reference Files

Status: PARTIAL

Reason:

- `ceremony.py` in the latest Temp intake was actually an HTML ceremony surface, not Python.
- `private_alpha_flow_runner.py` in the latest Temp intake was a pytest-style test suite, not a product runner module.
- `private_alpha_runner.py` in the latest Temp intake was a commit-guard style file using subprocess/git, not the intended private-alpha custody report runner.

Actions taken:

- HTML ceremony surface preserved at `docs\ceremony_surface_reference.html`.
- Misplaced flow-runner test preserved in `rubish\misplaced_package_tests`.
- Misnamed commit-guard file preserved in `rubish\misnamed_commit_guard`.
- Active Python modules were replaced with safe, importable product scaffolds where appropriate.

## 2026-06-28 MVP Normalization Blocker Update

Resolved:

- Cross-labeled active modules were repaired or reduced to thin wrappers.
- Temporary/non-MVP active modules were moved out of the active package and preserved in `rubish`.
- Active package compile/static marker proof passed after normalization.

Still open:

- Protected vault actions need final Human Intent receipt wiring proof.
- Oubliette is currently represented by quarantine/no-execute boundary; no distinct active static-inspection adapter is proven yet.
- Broad historical tests remain untrusted until each copied test is reviewed for no-delete/no-execute fixture behavior.

## 2026-06-28 Remaining MVP Blockers After Receipt/Oubliette Checkpoint

Open:

- Focused pytest proof NOT RUN; elevated project-local proof prompt was rejected.
- Route-level FastAPI proof NOT RUN.
- Ceremony ledger is still in-memory; persistence decision remains open.
- Broad historical copied tests remain untrusted until reviewed.

Closed/Reduced:

- Active package cross-labeling reduced to normalized modules plus thin wrappers.
- Oubliette MVP boundary is documented and uses existing quarantine/no-execute path.
- Protected promote/remove/quarantine actions now return BlackBox Human Intent receipts when BlackBox is available.

## 2026-06-28 PubCast Return Boundary

Iteration Wallet no longer needs feature expansion before returning to PubCast avatars.

Do not claim Iteration Wallet is product-complete. Treat it as MVP-infrastructure-stable with these blockers:

- Pytest proof NOT RUN.
- FastAPI route proof NOT RUN.
- Ceremony persistence open.
- PubCast adapter not yet wired.

PubCast may proceed against normalized boundaries only.
