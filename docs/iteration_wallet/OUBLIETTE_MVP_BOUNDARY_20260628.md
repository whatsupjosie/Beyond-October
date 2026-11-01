# Oubliette MVP Boundary

Date: 2026-06-28

## Decision

For the approved MVP, Oubliette is represented by the existing quarantine/no-execute boundary in the Vault.

No separate active Oubliette adapter is introduced in this pass.

## Why This Exists

Product Law requires dangerous or uncertain files to be labeled, fenced, warned about, and preserved without deletion or execution.

## Existing Capability Used

The existing custody engine already has:

- `FileState.QUARANTINE`
- `Section.quarantine`
- `VaultEngine.quarantine_file(...)`
- BlackBox event `FILE_QUARANTINED`
- Human Intent receipt wiring for quarantine
- Closed catalog scrubbing

## What Oubliette Means In MVP

MVP Oubliette is:

- quarantine state
- no-execute rule
- no-delete rule
- BlackBox evidence
- Human Intent receipt for quarantine
- closed catalog visibility only

MVP Oubliette is not:

- a test runner
- a code execution sandbox
- a second vault
- a second quarantine implementation
- a place AI can operate

## Completion Gate

Oubliette MVP is considered PARTIAL but integrated when:

- quarantine state exists in Vault
- quarantine action records a BlackBox event
- quarantine action returns a Human Intent receipt when BlackBox is available
- active package has no execution markers
- closed catalog does not expose protected internals

This keeps Iteration Wallet from blocking PubCast while preserving the future path for a richer Oubliette static inspection adapter.
