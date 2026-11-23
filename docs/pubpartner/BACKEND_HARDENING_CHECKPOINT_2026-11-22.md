# PubPartner backend hardening checkpoint

Date: 2026-11-22 (America/Los_Angeles)
Working branch: gpt/pubpartner-backend-hardening-2026-11-22
PR: https://github.com/whatsupjosie/Beyond-October/pull/20
Base: main at 7fd1fea88aea102067c58136daf407412b3ec188

## Scope and custody

This is unmerged, unqualified source work, NOT an end-to-end working-product certificate. Leave 2i, the UI design, and model integration untouched. In particular, do NOT replace 2i with an older copy missing the new chat, offline dictionary, thesaurus or independent offline spelling tools.

## Code changes staged

1. Blackbox Light now reuses modules/conversation_archive.py, recording original user text and partner reply on successful private PubPartner turns. Owner-and-partner scoped list/read/full-text search routes exist, with original VerbatimVault custody unchanged. Full export bypasses interactive pagination caps.
2. Friend working-data backup selection no longer enumerates all user/partner files with fuzzy matches. Selects owner+partner sessions, attributable original source records, confirmed relationship files, relevant calibration and audio, filtered owner guidance, authored cartridge data, and a transaction-consistent SQLite memory snapshot. Mixed-partner sessions are excluded rather than exported into a friend backup. Export is staged, manifest-hashed, verified, then atomically published.
3. Legacy backups without scope=owner_and_partner are rejected by the upgraded verification gate; old backup selection could include foreign records. No data or old ZIP is deleted.
4. Backup download/verification routes check authenticated owner against the manifest. Guidance retrieval checks embedded exact user ID even if normalized filenames collide. Backup and calibration slugs cannot be dot segments.
5. Calibration answers can become active behavior guidance only by an explicit approve=true request referencing an answered question or open-continuation event. Existing RelationshipEngine owns the confirmed, versioned, reversible lesson. Nothing automatically diagnoses a user, changes a persona, or alters original evidence.
6. Focused no-model regression tests and a CI workflow have been added.

## Verification and known limitations

Source paths, imports and connections were reviewed. No Python unit, HTTP route, or browser test executed in this environment. GitHub Actions run 45121524934 and calibration run 45121524856 ended in failure BEFORE any job steps (zero steps; no runner assigned). These do not establish a passing or failing application test.

Run at least:

    python -m py_compile modules/pubpartner_backup.py modules/pubpartner_blackbox_light.py modules/pubpartner_calibration.py modules/pubpartner_routes.py modules/pubpartner_core.py
    python -m pytest -q tests/test_pubpartner_blackbox_light.py tests/test_pubpartner_backup_isolation.py tests/test_pubpartner_calibration_approval.py tests/horizon_ref_pubpartner_backup.py tests/test_pubpartner_calibration.py tests/test_pubpartner_cartridge_memory_wiring.py tests/test_pubpartner_existing_wiring.py

Then run a real private mock/offline turn and confirm both exact archived messages, authenticated search, backup restore roundtrip to an isolated directory, mixed-session exclusion and an owner-isolation HTTP probe. Never merge based only on static inspection.

Further open issues:
- Sealed Iteration Wallet birth, last-good, quarantine and identity pairing are NOT integrated. Working-data ZIP is not Wallet custody.
- Base/Portable remote authenticated docking, conflict reconciliation, and roundtrip movement remain incomplete. Never silently overwrite either side.
- Archived voice/audio, live/retrospective EQ, and provider-backed companion behavior are incomplete.
- Canonical newest 2i with independent new Chat and local dictionary, thesaurus and spellcheck has NOT been verified as a complete source set. Do not replace current 2i until identified and qualified.
- Backup can omit malformed or cross-partner legacy sessions. This is safer than copying unprovable private data, but requires explicit review in a future recovery flow.
- Other existing stores, notably relationship/receipt slug-collision behavior, need a separate collision-resistance and owner audit. Do not claim full tenant isolation until they pass.
- Backup ZIP verification proves byte integrity, not original authenticity, safe restoration, or Wallet authorization.
- No acceptance test with an actual local or remote LLM was performed.

## Do not call complete

Committed = branch has files.
Connected = call sites and storage API link.
Statically checked = source reviewed.
Tested = executable checks ran and passed.
Merged = on main.
Accepted = representative end-to-end real-device behavior verified.

Current PR #20 is connected at source level only. It is not tested, merged, accepted, or feature-complete.
