# ALEX MEMORY REACH + BACKUP — HANDOFF (2026-10-09, supersedes the 2026-10-08 version)
Base: PubCast_Reach_OFFICIAL_CONTINUITY_HANDOFF_CERTIFIED_2026-10-02 (Security Foundation build, checksum verified).

## What was asked
"Get persistent memory working, and before that get Alex thinking and feeling as intended."
Direction given after review: **Alex's own speaking mind should receive the actual remembered content.** Jeremy and everyone else keep the minimal packet.

## Read first (design context this change respects)
handoffs/affect_model/AFFECT_MODEL_CONCLUSIONS.md, AFFECT_CONTEXT_MODEL.md, WIRING_COMPLETE_2026-08-21.md, handoffs/MEMORY_AUDIT_2026-08-21.md, SESSION_HANDOFF_2026-08-21_COMPLETE.md, handoffs/recovered_progress/Pubcast_Integration_Handoff_2026-10-02.md.
Principles kept: "Alex stays sovereign and private"; shared packet stays minimal; baseline/affect scoring untouched; no new memory system.

## Verified before changing anything (original build, 11 turns + restart)
Storage persistence already worked: 11 memories, 11 baseline observations and the state snapshot all reloaded; affect reading ("meet_them_at") survived restart.
The gap: the speaking model got only junk keyword fragments (`'pointless,'`, `"let's"`, `'good,'`); remembered content never reached it.

## Changes (4 source files, all bounded)
| File | Change |
|---|---|
| modules/alex_core.py | `_tokens()` + `_FILLER`; `_extract_keywords` now strips punctuation and conversational filler; `recall()` query uses the same tokenizer; index keys normalised both at store and at disk load (old punctuated memories still match); `_may_persist_text()` — a LIMITED turn is stored in recallable memory only if its policy has `allow_persistent_memory`; unreadable labels fail closed |
| modules/alex_jeremy_bridge.py | new `recalled_for_speaker(user_id, query, limit=3, max_chars=280)` — relevance-gated (needs keyword match), excludes the current turn's own text, never persisted to the shared packet, never used by `jeremy_whisper` |
| modules/pubpartner_core.py | in `build_turn_packet`, when `turn_audience == "private"` (same rule guidance already uses), Alex's recalled memories are added to FCP1 `memories` as `alex:<id>`, `src="alex_memory"`; wrapped so recall can never break a turn; shared rooms get nothing |
| tests/test_alex_memory_reach.py | 5 tests: clean keywords, punctuated query + old on-disk keywords, relevance/bounds/empty-on-no-match, LIMITED not stored/recalled (+fail closed), private-vs-shared spine behavior |

## Verification
- New tests: 5 passed.
- Same regression selection run on the ORIGINAL and the MODIFIED build: identical 49 fail/error lines in both (sandbox lacks python-multipart etc.; e.g. test_01_startup, test_full_host_*). Original 231 passed -> modified 236 passed (+5). **No regressions.**
- Re-ran the 11-turn restart scenario: threads are now real words; after restart, "is my sister still coming friday?" surfaces the two relevant memories; an unrelated query returns nothing.

## Behaviour change to be aware of
LIMITED turns are no longer written to Alex's long-term memory unless the label's `handling.allow_persistent_memory` is true. (Previously they were stored.) Needed because recalled content now reaches a prompt.

## Part 2 (2026-10-09): Alex memory backup — local folder AND Google Drive API
Asked: a Drive backup folder "Alex Persistent Memory AI" with an active line so Alex can back up and read her memories; local option plus Google Drive both.
Read first: modules/pubpartner_backup.py (existing, different scope: PubPartner friend zips; left untouched) and alex_core MemoryCore layout.
| File | Change |
|---|---|
| modules/alex_memory_backup.py (new) | LocalFolderBackend (Drive for Desktop folder), GoogleDriveBackend (Drive v3 via injected service), MirroredBackend (both; one failing never blocks the other), AlexMemoryBackup engine (sha256 manifest written last, append-only, throttled background notify_turn, read/search/list, hash-verified restore, restore_if_empty), env builder, auth helper, CLI |
| modules/alex_core.py | optional `after_turn_hook(user_id)` called after the turn is stored; failures logged, never raised |
| modules/alex_jeremy_bridge.py | `alex_backup` attr; `alex_for` installs the hook (lazy lookup, so attach order does not matter) and runs restore_if_empty before Alex loads |
| modules/alex_routes.py | GET /api/alex/backup/status, GET /api/alex/backup/search, POST /api/alex/backup/run (mod role) |
| main.py | builds the backup from env at startup (disabled with a console note on any error) |
| requirements.txt | optional google libs, commented |
| tests/test_alex_memory_backup.py (new) | 14 tests, mutation-checked (4 deliberate breakages, each caught by the right tests) |
| ALEX_BACKUP_SETUP.md (new) | Option A local/Drive-for-Desktop, Option B Google API (service account or OAuth), both at once |

Verification: test selection 295 passed; the only 3 failures are identical to the original build (Rust performer manager x2, static API ref check; sandbox has no Rust). Real app booted with ALEX_BACKUP_LOCAL_DIR, 2 messages over HTTP /api/alex/message -> files appeared in the backup, the status endpoint reported the upload, the search endpoint found the memory. That e2e run found a real bug (the hook first lived in process_user_turn, which the HTTP route does not use); fixed by moving it into AlexCore.
NOT verified: the real Google Drive API (this sandbox cannot reach Google); verified only against a fake Drive v3 service. First live run: `python -m modules.alex_memory_backup backup --user <id>`.
Safety: backs up only alex/<user>/ memory + state json shapes (allowlist regex); LIMITED turns are not stored so they are never backed up; restore never overwrites unless asked and rejects hostile manifest paths and hash mismatches.
Not done: Alex consulting the backup automatically when local recall is empty (search is available via module and route).

## NOT done / for decision (reported, not changed)
1. **System-Alex adjudication / orchestrator boundary** (Oct 2 handoff item) — a first attempt was discarded because it redesigned the orchestrator without reading why it exists. Do it only as the smaller change: keep the broker's evidence handling; adjudicate using the engine's own machinery (baseline-quality `capped_by`, `conclusion_withheld`, no confidence-winner picking); move Affect Dynamics after that step.
2. **Bridge `session_id` never reaches AlexCore** (`metadata["session_id"]` is unset, so the affect engine partitions under 'default'). Possibly unintended; unconfirmed.
3. `publish_emotional_signal` persists secondary signals to the packet file without checking the data label.
4. `bots.py` characters (Pete etc.) still get no Alex/affect packet (Aug 21 gap, unchanged).
5. JeremyCricket per-character routing in MemoryIngestor still dead (`register_cricket()` never called; `cricket_registry` not passed in main.py). Note PubPartner's own CricketKeeper memory is separate and live.
6. Not verified: a real model replying (Ollama/providers), PersonalPrior anomaly path on real conversations.
7. Argon2id/session credentials, Rust/Windows compile, GPU stages — untouched (see Oct 2 handoff).

## Rules for the next session
Read the docs above before changing anything. Do not restart the audit. Do not redesign working systems. Do not claim proof not produced.
