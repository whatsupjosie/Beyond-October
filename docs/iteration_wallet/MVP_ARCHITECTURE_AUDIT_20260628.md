# Iteration Wallet MVP Architecture Audit

Date: 2026-06-28
Workspace: `C:\Users\hardc\OneDrive\Documents\Playground\Iteration_Wallet_Standalone_20260627_1420`

## Scope

This audit follows the approved MVP taskbook. It does not introduce a new plan.

MVP systems:

- BlackBox
- Vault
- Ceremony
- Gatekeeper
- Oubliette/quarantine
- Identity
- Cradle/Prime
- Archive
- Removed staging

## Product Law Trace

Every active module must exist because of at least one product law:

- No delete: `vault_v21.py`, `vault.py`, `server.py`, `cli.py`
- No execute: `server.py`, `vault_v21.py`, quarantine/Oubliette boundary
- Humans open gates: `ceremony.py`, `gatekeeper.py`, `identity.py`, `notification_manager.py`
- BlackBox records everything important: `blackbox.py`
- Closed catalog is safe: `vault_v21.py`

## Active Module Ownership

| Module | Owner Role | Status | Notes |
| --- | --- | --- | --- |
| `blackbox.py` | BlackBox evidence chain and Human Intent receipt storage | ACTIVE | One authoritative BlackBox implementation. |
| `vault_v21.py` | Vault, Cradle/Prime, Archive, Removed staging, quarantine records | ACTIVE | One authoritative custody engine. |
| `vault.py` | Compatibility import wrapper for `vault_v21.py` | ACTIVE THIN WRAPPER | Must not grow separate vault logic. |
| `ceremony.py` | Ceremony token issue/verify/consume primitives | ACTIVE | In-memory ledger only; persistence remains future work. |
| `gatekeeper.py` | Protected action policy table and enforcement helpers | ACTIVE | One authoritative protected-action registry. |
| `guard.py` | Compatibility wrapper for `gatekeeper.py` | ACTIVE THIN WRAPPER | Retired old duplicate ceremony-token ownership. |
| `identity.py` | Local actor/session identity records | ACTIVE | Provider-neutral local identity shape. |
| `notification_manager.py` | Human-intent access decision log | ACTIVE | Supports gate decisions; not a second policy owner. |
| `server.py` | Existing local FastAPI route surface | ACTIVE | Route surface only; no delete routes and no execution paths. |
| `app.py` | Compatibility wrapper for `server.app` | ACTIVE THIN WRAPPER | Retired Markdown-in-Python mismatch. |
| `cli.py` | Local-only CLI helper | ACTIVE | Loopback-only; no real delete command. |
| `__init__.py` | Package export list | ACTIVE | Exports normalized MVP modules only. |

## Import Graph

```text
app.py -> server.app
server.py -> blackbox.py, ceremony.py, gatekeeper.py, notification_manager.py, vault_v21.py
vault.py -> vault_v21.py
guard.py -> gatekeeper.py
gatekeeper.py -> identity.py, notification_manager.py
notification_manager.py -> optional blackbox instance at runtime
vault_v21.py -> optional blackbox instance and optional ceremony ledger at runtime
blackbox.py -> stdlib only
ceremony.py -> stdlib only
identity.py -> stdlib only
cli.py -> requests, local loopback only
```

## Subsystem Dependency Graph

```text
Human/Session Identity
  -> Gatekeeper
  -> Ceremony
  -> Vault protected action
  -> BlackBox custody event
  -> BlackBox Human Intent receipt

Vault
  -> Cradle/Prime
  -> Archive
  -> Removed staging
  -> Quarantine/Oubliette boundary
  -> Closed catalog
  -> BlackBox event chain

Server/CLI
  -> thin control surfaces over the modules above
```

## Duplicate / Retired Active Implementations

The following were preserved before active repair:

- `rubish\module_mismatch_backup_20260628_101557`
- `rubish\pre_receipts_oubliette_backup_20260628_102612`
- `rubish\structural_normalization_20260628_103501`
- `rubish\pre_mvp_stabilization_backup_20260628_103631`

Retired from active package:

- Markdown content in `app.py`; replaced with thin `server.app` wrapper.
- Duplicate ceremony-token ownership in `guard.py`; replaced with thin `gatekeeper.py` wrapper.
- Temporary `private_alpha_runner.py`; moved out of active package pending approved MVP fit.
- `key_derivation.py`; moved out of active package because secure key derivation is not required to complete the approved MVP section and would broaden scope.

## Known Incomplete Areas

- Ceremony ledger is in-memory only.
- Human Intent receipts exist in BlackBox, but protected vault moves still need final receipt wiring proof.
- Oubliette is represented by quarantine/no-execute boundary, but a distinct static inspection adapter is not active yet.
- Broad historical tests are not trusted because copied reference tests include mismatches and some old cleanup assumptions.
- Normal sandbox proof command was denied by Windows ACL behavior; escalated scoped proof was not run after user rejected the prompt. Treat compile/proof as BLOCKED after the latest stabilization edits until a project-local proof command is allowed or a non-escalated path works.

## Current MVP Completion Gate

Before returning to PubCast avatar work, finish only these conservative items:

1. Verify active package compiles.
2. Verify no active delete/execute markers exist.
3. Wire existing BlackBox receipt method into existing protected vault actions with the fewest line changes.
4. Add static proof that active modules match their filenames.
5. Update taskbook, blockers, changelog, and handoff.

No feature expansion should occur before those are complete.
