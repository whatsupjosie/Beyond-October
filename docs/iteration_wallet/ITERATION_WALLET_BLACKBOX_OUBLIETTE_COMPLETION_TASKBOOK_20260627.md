# Iteration Wallet + BlackBox + Oubliette Completion Taskbook

Date: 2026-06-27
Workspace: `C:\Users\hardc\OneDrive\Documents\Playground\Cannon Build PubCast-  Alpha Prime`

## Purpose

Finish Iteration Wallet as a standalone portable product, then integrate full BlackBox, then integrate Oubliette, and finally connect the trio cleanly back into PubCast through an adapter instead of rebuilding the wallet twice.

This taskbook is meant to stop catch-up drift. The rules below are canon unless the user explicitly changes them.

## Product Law

1. Iteration Wallet never deletes custodied user material.
2. Iteration Wallet never silently overwrites Prime, Cradle, or custodied records.
3. Iteration Wallet and Oubliette never execute custodied files or code.
4. Oubliette is an inspection, quarantine, labeling, and boundary system, not a test runner.
5. AI does not enter the yard. AI can advise from outside the gate, request review, and interpret records, but it does not touch custody, run tools, execute code, promote Prime, release custody, or import results.
6. Humans open gates and make custody decisions.
7. Engines do deterministic custody work.
8. BlackBox records custody, permission, incident, integrity, receipt, quarantine, and gate events.
9. Dangerous files may exist safely because they are never executed and never deleted. They can be quarantined, labeled, warned about, fenced off, and recorded.
10. Closed catalog surfaces show safe metadata only. They do not expose custody paths, hashes, notes, previews, raw token secrets, or protected contents.

## Work Rules And Engineering Standard

This is not practice work. This is product work.

Every pass must be treated as world-class, production-grade engineering aimed at a precedent-setting gold standard or better. That does not mean overbuilding. It means careful boundaries, clear contracts, auditable behavior, strong names, boring reliability, honest proof, and no fake completion claims.

Rules:

- Work non-destructively.
- Do not delete files.
- If a file appears obsolete, dangerous, duplicated, or no longer suitable for active use, move or copy it into a clearly named `rubish` quarantine folder for the user to review later.
- Prefer copying originals before permanent edits.
- Never silently overwrite Prime, Cradle, Vault, BlackBox, Oubliette, taskbook, handoff, or canon files.
- Keep user files, private memory, BYOK material, keys, tokens, secrets, and unrelated personal files out of scope.
- Keep experimental and transitional work inside Playground.
- Use deterministic engine behavior first; use AI as advisor only within the approved authority model.
- Write code and docs as if another serious engineer must be able to trust them without a private explanation.
- Update the handoff before stopping whenever the work changes product state, rules, or next steps.

## Source Basis

Regular app integration target:

- `modules/pubcast_vault.py`
- `modules/vault_engine_hardened.py`
- `blackbox_recorder/pubcast_event_adapter.py`
- `blackbox_event_language/schema.py`
- `blackbox_event_language/key.json`
- `tests/test_pubcast_vault_blackbox_coupling.py`
- `handoffs/CODEX_ITERATION_WALLET_REGULAR_APP_STATUS_20260627.md`

Taskbook and dependency references:

- `C:\Users\hardc\Downloads\IterationWallet_DEPENDENCY_ANALYSIS_BLACKBOX_OUBLIETTE.md`
- `C:\Users\hardc\Downloads\IterationWallet_v216_DELIVERY_AUDIT.md`
- `codex_reference_intake\iteration_wallet_lineage_ref_20260627_090807\IterationWallet_TASKBOOK_FOR_UNFAMILIAR_BOT_v216\IterationWallet_TASKBOOK_FOR_UNFAMILIAR_BOT_v216.md`

Latest loose Iteration Wallet reference intake:

- `codex_reference_intake\iteration_wallet_temp_latest_ref_20260627_092504`
- Key source files: `vault_v21.py`, `blackbox.py` if present in source lineage, `notification_manager.py`, `identity.py`, `gatekeeper.py`, `ceremony.py`, `server.py`, `cli.py`, `private_alpha_runner.py`, `private_alpha_flow_runner.py`
- Key tests: `test_blackbox_v219.py`, `test_human_intent_receipts_v221.py`, `test_ceremony_tokens_v222.py`, `test_private_alpha_flow_v223.py`, `test_private_alpha_runner_v224.py`, `test_vault_v212_no_delete_rule.py`, `test_vault_v213_no_execute_rule.py`
- Key reports: `BUILD_REPORT_v219.md` through `BUILD_REPORT_v224.md`, `README_v219.md` through `README_v224.md`, `DIFF_REPORT_v219.patch` through `DIFF_REPORT_v224.patch`

Important note: Some loose Temp filenames do not match their internal headings. Trust file contents, tests, and product rules over filename numbering.

## Chosen Build Strategy

Chosen path: finish Iteration Wallet as the standalone product, then integrate it into PubCast through an adapter.

Do not keep deepening the old PubCast vault wrapper as the final product. It is compatibility glue only.

Why:

- Iteration Wallet is its own product.
- PubCast needs it as a core custody subsystem.
- Reimplementing every wallet feature inside PubCast creates duplicate logic and drift.
- A standalone wallet plus PubCast adapter is cleaner, more portable, and easier to prove.

## Three Legitimate Completion Paths

Path A: PubCast-first patching

- Continue patching `modules/pubcast_vault.py` and `modules/vault_engine_hardened.py` until the regular app behaves correctly.
- Advantage: fastest visible PubCast progress.
- Risk: duplicates the standalone product, increases drift, and makes Iteration Wallet less portable.
- Verdict: use only as a temporary compatibility bridge.

Path B: Standalone-first rebuild

- Finish Iteration Wallet as a clean standalone package, then replace the old PubCast wrapper with an adapter.
- Advantage: clearest product boundary and best long-term architecture.
- Risk: slower before PubCast sees the whole finished feature set.
- Verdict: best core direction.

Path C: Hybrid lockstep

- Finish standalone Iteration Wallet in a clean folder while keeping the current PubCast wrapper stable and adding only bridge-safe compatibility hooks.
- Advantage: avoids breaking PubCast while preventing duplicate long-term logic.
- Risk: requires discipline not to keep growing the wrapper as the real product.
- Verdict: selected path.

## Selected Workflow Contract

Use Path C.

The current PubCast vault wrapper is treated as a temporary adapter/proving surface. The standalone Iteration Wallet package is the product. The PubCast integration must eventually call the product through an adapter instead of owning its own separate wallet rules.

Each work pass follows this loop:

1. Read the taskbook section and source files for the current phase.
2. Make backups of files that will be changed.
3. Edit only inside Playground.
4. Do not delete; quarantine/archive instead.
5. Do not execute custodied user code.
6. Prove behavior with code review and development checks only.
7. Update the taskbook checklist and handoff before stopping.
8. Leave exact next files and commands.

## Full Phase Board

Status key:

- `NOT STARTED`: no implementation work yet.
- `IN PROGRESS`: files are being adapted or created.
- `PARTIAL`: some proof exists but the phase is not complete.
- `BLOCKED`: blocked by missing file, unsafe action, or unavailable local tooling.
- `DONE`: implemented and proven against the acceptance gate.

| Phase | Name | Status | Primary Output | Exit Gate |
| --- | --- | --- | --- | --- |
| 0 | Stabilize Current PubCast Wrapper | PARTIAL | Safe closed catalog, blocked public delete, custody verify hook | Wrapper has no public delete/no-execute path and reports safe metadata by default |
| 1 | Standalone Wallet Folder | PARTIAL | Clean `iteration_wallet` product folder in Playground | Package imports; source layout normalized; product laws included |
| 2 | No-Delete / No-Execute Core | PARTIAL | Engine and CLI product paths fail closed | No product route/CLI/API deletes or executes custodied material |
| 3 | Human Intent + Gatekeeper | NOT STARTED | Central protected-action registry and receipts | Unknown actions fail closed; every protected action has receipt |
| 4 | Ceremony Tokens | NOT STARTED | Scoped token ledger with no raw-token leakage | Tokens are scoped/consumed/expired and never exposed in closed views |
| 5 | Full BlackBox | PARTIAL | Shared custody evidence layer | Custody, receipt, incident, quarantine, and integrity events chain together |
| 6 | Closed Catalog Everywhere | PARTIAL | Safe metadata views for Wallet, BlackBox, Oubliette, PubCast | Public/closed surfaces never expose protected paths/content/hash/token secrets |
| 7 | Oubliette Fence | NOT STARTED | No-execute inspection/quarantine adapter | Oubliette labels/quarantines/warns but never runs or deletes |
| 8 | Private Alpha Flow | NOT STARTED | Deterministic product flow report | Create, custody, inspect, promote, quarantine, release, verify story is complete |
| 9 | PubCast Adapter | NOT STARTED | `modules/pubcast_wallet_adapter.py` or equivalent | PubCast calls Wallet product boundary instead of duplicating it |
| 10 | Wrapper Retirement Plan | NOT STARTED | Archive/quarantine plan for old wrapper | Old wrapper is compatibility-only and not a second product |

## Autonomous Work Queue

This is the work order to follow without asking the user for another step-by-step prompt, as long as the action remains inside Playground and respects the product law.

### Phase 0: Stabilize Current PubCast Wrapper

- [x] Add BlackBox custody event coupling to the current wrapper.
- [x] Block public delete route with HTTP 403 and BlackBox denial event.
- [x] Add closed catalog default for `/api/vault/files`.
- [x] Add custody integrity verification route.
- [x] Disable or quarantine engine-level `VaultEngine.delete_file()` as a product action.
- [x] Update old direct engine tests/docs so they assert no-delete behavior, not destructive deletion.
- [ ] Add route proof for open, lock, add, remove-from-active-use, promote, custody verify, closed catalog, open catalog, and blocked delete.

### Phase 1: Create Clean Standalone Wallet

- [x] Create `iteration_wallet_product_work` or similarly named folder under the canonical app or Playground.
- [x] Copy latest loose Temp intake into that folder, preserving originals untouched.
- [x] Normalize source package under `iteration_wallet/`.
- [x] Normalize development proof files under `tests/`.
- [x] Add `PRODUCT_LAWS.md` to the standalone product folder.
- [x] Add `README.md` that says the product never deletes and never executes custodied material.
- [ ] Add `CHANGELOG.md` entry for the integrated completion pass.

### Phase 2: No-Delete / No-Execute Core

- [x] Search standalone wallet for delete, remove, unlink, rmtree, execute, subprocess, os.system, eval, exec, run, test-run language.
- [x] Separate dangerous words into:
  - product behavior to disable
  - development proof behavior to label clearly
  - wording only to rename
- [ ] Convert delete requests into no-delete denied receipts.
- [ ] Convert execute/run requests into no-execute denied receipts or static inspection records.
- [ ] Ensure release-from-custody means deliberate human copy/export/release, not deletion.
- [x] Ensure quarantine means fence and label, not removal.

### Phase 3: Human Intent + Gatekeeper

- [ ] Establish protected action registry as the single authority table.
- [ ] Require human identity session for protected actions.
- [ ] Require scoped ceremony token for highest-risk protected actions.
- [ ] Produce Human Intent Receipt for approval, denial, expiration, and blocked attempts.
- [ ] Link receipts to BlackBox event ids/hashes.
- [ ] Ensure AI cannot approve, deny, open, release, promote, quarantine, execute, delete, or enter Oubliette.

### Phase 4: Ceremony Tokens

- [ ] Implement or adapt scoped short-lived token ledger.
- [ ] Store token hashes or references, not raw token secrets in visible surfaces.
- [ ] Consume one-time tokens where required.
- [ ] Expire stale tokens.
- [ ] Write token issued/consumed/expired/denied events to BlackBox.
- [ ] Closed catalog and reports must prove raw token non-leakage.

### Phase 5: Full BlackBox Integration

- [ ] Decide exact standalone BlackBox storage shape.
- [ ] Preserve compatibility with PubCast compact `.bbx` witness through adapter.
- [ ] Make Vault, Gatekeeper, Receipts, Ceremony Tokens, and Oubliette write one coherent evidence story.
- [ ] Add chain verification.
- [ ] Add tamper-visible receipt verification.
- [ ] Add closed BlackBox summary view.
- [ ] Add incident bundle records.

### Phase 6: Closed Catalog Everywhere

- [ ] Wallet closed catalog.
- [ ] BlackBox closed summary.
- [ ] Oubliette closed inspection status.
- [ ] PubCast adapter closed catalog.
- [ ] Operational/full views gated behind human/admin/operator authority.
- [ ] No protected paths, hashes, token secrets, notes, previews, contents, or private memory in closed views.

### Phase 7: Oubliette Fence

- [ ] Inventory all Oubliette source references.
- [ ] Define Oubliette static-inspection contract.
- [ ] Implement `oubliette_adapter.py`.
- [ ] Static inspect: file type, size, metadata, risk labels, dangerous-pattern labels, provenance.
- [ ] Quarantine: label/fence and record, never delete.
- [ ] Import back: Candidate only, never Prime.
- [ ] Promotion to Prime: separate human ceremony only.
- [ ] AI advisory: read closed summaries only; no direct Oubliette operations.

### Phase 8: Private Alpha Flow

- [ ] Build deterministic flow report.
- [ ] Cover create project/section.
- [ ] Add raw/candidate.
- [ ] Show closed catalog before open.
- [ ] Issue identity session.
- [ ] Open vault through human ceremony.
- [ ] Promote candidate to Prime.
- [ ] Remove from active use without deletion.
- [ ] Restore to active use.
- [ ] Quarantine.
- [ ] Release from custody through human ceremony.
- [ ] Verify receipts.
- [ ] Verify BlackBox chain.
- [ ] Verify custody integrity.
- [ ] Lock vault.
- [ ] Confirm closed catalog still safe.

### Phase 9: PubCast Adapter

- [ ] Create `modules/pubcast_wallet_adapter.py` or equivalent.
- [ ] Translate PubCast project/session/user context to wallet product calls.
- [ ] Keep old wrapper route names only if needed for compatibility.
- [ ] Route PubCast vault operations through the standalone product boundary.
- [ ] Record PubCast-origin custody events into BlackBox.
- [ ] Keep public routes closed-catalog safe.

### Phase 10: Retire Duplicate Wrapper Logic

- [ ] Identify old wrapper logic now owned by standalone Wallet.
- [ ] Archive/quarantine duplicate code only after adapter proof.
- [ ] Keep compatibility shims small and documented.
- [ ] Do not delete the old wrapper.
- [ ] Update handoff with final replacement map.

## Definition Of Done

The trio is not done when the files exist. It is done when the product story is coherent and proven:

- Iteration Wallet is usable standalone.
- PubCast can call it through an adapter.
- Cradle protects active development material.
- Vault preserves custody.
- BlackBox records what happened.
- Oubliette fences inspection/quarantine.
- AI stays outside the yard and advises only from approved summaries.
- Humans control gate crossings.
- No product behavior deletes custodied material.
- No product behavior executes custodied material.
- Closed views are safe.
- Receipts and BlackBox make important actions reviewable.

## Section 1: Finish Standalone Iteration Wallet

Goal: A coherent standalone Iteration Wallet package that enforces no-delete, no-execute, human custody, closed catalog, ceremony tokens, receipts, and private-alpha readiness.

Tasks:

- [ ] Create a clean standalone wallet work folder inside Playground.
- [ ] Copy latest coherent wallet source from `codex_reference_intake\iteration_wallet_temp_latest_ref_20260627_092504` into that folder.
- [ ] Preserve original reference files untouched.
- [ ] Normalize package layout:
  - [ ] `iteration_wallet/__init__.py`
  - [ ] `iteration_wallet/vault_v21.py`
  - [ ] `iteration_wallet/blackbox.py`
  - [ ] `iteration_wallet/notification_manager.py`
  - [ ] `iteration_wallet/gatekeeper.py`
  - [ ] `iteration_wallet/identity.py`
  - [ ] `iteration_wallet/ceremony.py`
  - [ ] `iteration_wallet/server.py`
  - [ ] `iteration_wallet/cli.py`
  - [ ] `iteration_wallet/private_alpha_runner.py`
- [ ] Normalize test layout under `tests/`.
- [ ] Remove or disable any product-level delete action.
- [ ] Remove or disable any product-level run/execute action for custodied material.
- [ ] Rename misleading product wording:
  - [ ] `run tests` -> `evaluate test files` or `inspect test definitions`
  - [ ] `external tool run` -> `external inspection record` unless it is outside wallet custody and human-controlled
  - [ ] `lab run` -> `bounded inspection/quarantine session`
- [ ] Confirm closed catalog surfaces do not expose:
  - [ ] custody paths
  - [ ] original paths
  - [ ] vault paths
  - [ ] hashes/checksums
  - [ ] notes
  - [ ] previews
  - [ ] protected contents
  - [ ] raw ceremony token secrets
- [ ] Confirm full operational views require human/admin authority.
- [ ] Confirm protected actions are registered centrally in `gatekeeper.py`.
- [ ] Confirm protected actions fail closed if action key is missing or unknown.
- [ ] Confirm identity sessions replace caller-provided string trust.
- [ ] Confirm ceremony tokens are scoped, short-lived, one-time or consumed where required.
- [ ] Confirm raw ceremony tokens are never listed in status, reports, receipts, closed catalog, or BlackBox summaries.
- [ ] Confirm every protected action produces a Human Intent Receipt.
- [ ] Confirm receipts link to BlackBox event ids/hashes where available.
- [ ] Confirm private-alpha runner covers:
  - [ ] create project
  - [ ] create section
  - [ ] add raw/candidate
  - [ ] closed catalog before open
  - [ ] issue human identity session
  - [ ] open vault
  - [ ] issue scoped ceremony token
  - [ ] promote candidate to Prime
  - [ ] export or copy out only as inspection/candidate workflow, never execute
  - [ ] remove from active use without deletion
  - [ ] restore to active use
  - [ ] quarantine
  - [ ] release from custody by human ceremony
  - [ ] verify receipts
  - [ ] verify BlackBox chain
  - [ ] verify custody integrity
  - [ ] lock vault
  - [ ] closed catalog still safe

Acceptance gates:

- [ ] Standalone package imports.
- [ ] Existing standalone tests pass or blocked tests are documented precisely.
- [ ] No product route or CLI command executes custodied code.
- [ ] No product route or CLI command deletes custodied material.
- [ ] Private-alpha runner produces an honest report.
- [ ] All temporary/generated proof files stay inside Playground.

## Section 2: Integrate Full BlackBox

Goal: BlackBox is the shared evidence layer for wallet custody, human intent, receipts, incident reporting, quarantine, and PubCast integration.

Tasks:

- [ ] Confirm or create standalone `iteration_wallet/blackbox.py`.
- [ ] Confirm BlackBox owns:
  - [ ] event writing
  - [ ] chain verification
  - [ ] custody event writing
  - [ ] violation event writing
  - [ ] incident bundles
  - [ ] request pressure records
  - [ ] receipt records
  - [ ] closed evidence summaries
- [ ] Confirm NotificationManager uses BlackBox instead of owning BlackBox mechanics.
- [ ] Confirm VaultEngine writes custody events into the same BlackBox chain.
- [ ] Confirm Human Intent approvals/denials write into the same chain.
- [ ] Confirm receipts are hash checked and tamper visible.
- [ ] Confirm custody integrity checks write violation events for:
  - [ ] missing custody object
  - [ ] missing Prime object
  - [ ] hash mismatch
  - [ ] Prime hash mismatch
  - [ ] unauthorized quarantine access
  - [ ] forced open/closed-state mismatch if detected
- [ ] Confirm BlackBox closed summary does not expose sensitive fields.
- [ ] Confirm BlackBox status/verify routes do not expose raw records to player/public surfaces.
- [ ] Decide bridge strategy between:
  - [ ] standalone JSON BlackBox event store
  - [ ] PubCast compact `.bbx` BlackBox witness
  - [ ] or dual recording through an adapter
- [ ] Implement a PubCast BlackBox adapter only after standalone BlackBox is coherent.

Acceptance gates:

- [ ] One shared BlackBox object/adapter is used by wallet vault and human intent.
- [ ] Custody events and human intent events appear in the same evidence story.
- [ ] Tamper checks fail honestly.
- [ ] Closed summaries are safe.
- [ ] BlackBox never becomes the actor making custody decisions; it records.

## Section 3: Integrate Oubliette

Goal: Oubliette is the white picket fence around the yard: a bounded inspection/quarantine system. It does not execute files. AI does not enter it.

Tasks:

- [ ] Inventory current Oubliette files from available references.
- [ ] Create `iteration_wallet/oubliette_adapter.py` only after inventory.
- [ ] Define Oubliette product contract:
  - [ ] inspect files
  - [ ] label files
  - [ ] quarantine files
  - [ ] warn about risk
  - [ ] produce static metadata
  - [ ] record provenance
  - [ ] return candidate records for human review
  - [ ] never execute
  - [ ] never delete
  - [ ] never auto-promote Prime
- [ ] Remove or quarantine wording that implies Oubliette runs code/tests.
- [ ] Implement static evaluation only:
  - [ ] extension/type inventory
  - [ ] size and hash metadata
  - [ ] text/code preview only where safe and explicitly allowed
  - [ ] dangerous pattern labels
  - [ ] suspicious file markers
  - [ ] quarantine reasons
  - [ ] manifest generation
- [ ] Connect Oubliette to BlackBox:
  - [ ] inspection session created
  - [ ] file labeled
  - [ ] file quarantined
  - [ ] warning issued
  - [ ] human review requested
  - [ ] candidate imported from inspected material
- [ ] Connect Oubliette to Iteration Wallet:
  - [ ] export/copy to inspection area requires human ceremony
  - [ ] import back creates Candidate only
  - [ ] promotion to Prime requires separate human ceremony
  - [ ] no automatic delete/cleanup of inspected files
- [ ] Add closed Oubliette status view that exposes safe metadata only.

Acceptance gates:

- [ ] No Oubliette path executes code.
- [ ] No Oubliette path deletes files.
- [ ] AI has no direct Oubliette operation authority.
- [ ] Human-gated actions are recorded.
- [ ] BlackBox records the fence crossings and quarantine story.
- [ ] Dangerous file handling is label/quarantine/warn only.

## Section 4: PubCast Integration Adapter

Goal: PubCast uses Iteration Wallet as a subsystem, not a duplicated partial implementation.

Tasks:

- [ ] Create `modules/pubcast_wallet_adapter.py` or equivalent.
- [ ] Adapter translates PubCast identity/session/project context into wallet requests.
- [ ] Adapter exposes safe PubCast routes:
  - [ ] wallet status
  - [ ] closed catalog
  - [ ] custody verify
  - [ ] BlackBox summary
  - [ ] receipt list/detail
  - [ ] human intent request/decision surfaces
  - [ ] Oubliette inspection/quarantine status
- [ ] Keep raw operational wallet routes behind operator/mod authority.
- [ ] Block old PubCast delete route and old engine delete method from product use.
- [ ] Migrate old `modules/pubcast_vault.py` to compatibility glue only.
- [ ] Quarantine or archive old wrapper once adapter is proven, without deleting.

Acceptance gates:

- [ ] PubCast app imports.
- [ ] Wallet adapter imports.
- [ ] `/api/vault/files` or successor route returns closed catalog by default.
- [ ] No public route exposes custody paths/hashes/contents.
- [ ] No PubCast route executes custodied code.
- [ ] No PubCast route deletes custodied material.
- [ ] BlackBox receives custody events from PubCast-triggered wallet operations.

## Current Immediate Work Queue

Do these next, in order:

1. Add `CHANGELOG.md` entry for the standalone integrated completion pass.
2. Review remaining copied tests and quarantine or rewrite any development proof that deletes files during cleanup.
3. Correct remaining Oubliette/test-run language to no-execute inspection/quarantine language.
4. Build no-delete-safe development proof checks for the standalone package.
5. Add/repair Human Intent Receipts.
6. Add/repair scoped ceremony token ledger persistence or adapter.
7. Build private-alpha runner report beyond the current non-executing scaffold.
8. Integrate BlackBox fully.
9. Integrate Oubliette as no-execute inspection/quarantine fence.
10. Build PubCast adapter.
11. Retire old wrapper into archive/quarantine only after proof.

## Stop Conditions

Stop and document instead of proceeding if:

- Any task requires deleting files.
- Any task requires executing custodied user code.
- Any task requires network download/install.
- Any task risks secrets, BYOK keys, private memory, or unrelated personal files.
- The active folder is not inside Playground.

## Final Proof Required Before Calling It Done

- [ ] Standalone Iteration Wallet private-alpha runner passes or produces a precise blocked report.
- [ ] PubCast imports with wallet adapter.
- [ ] BlackBox verifies chain after sample custody flow.
- [ ] Closed catalog safe-view test passes.
- [ ] No-delete test passes at route and engine-product boundary.
- [ ] No-execute test passes at route, CLI, and Oubliette boundary.
- [ ] Human receipt tamper check passes.
- [ ] Ceremony token no-leak check passes.
- [ ] Oubliette quarantine/inspection flow records to BlackBox and does not execute/delete.
