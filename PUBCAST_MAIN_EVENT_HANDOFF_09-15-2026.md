# PubCast Main-Event Engineering Handoff — 09-15-2026

## Preservation rule
All source repositories and source archives remain untouched/read-only. Current implementation exists only in the isolated working copy extracted from `Reach_Writers_Room_001.zip` under `/mnt/data/pubcast_main_event_work/working/Reach_Writers_Room_001`.

## Immediate assignment
Conversation Ownership subsystem first. Do not begin whole-program consolidation. 2i remains manuscript authority; generic conversation archive must not own manuscript state.

## Evidence read this turn
- `00_READ_ME_FIRST.md`
- `04_LOCKED_PRODUCT_DECISIONS.md`
- `07_TASK_TO_FILE_INDEX.md`
- existing `static/pub_partner_chat.html`
- existing `modules/pub_partner_chat.py`
- existing `modules/tts_engine.py`
- existing `modules/save_metadata.py`
- host routes around `/pub-partner-chat` in `main.py`
- focused existing tests `tests/test_pub_partner_chat.py` and `tests/test_reach_writers_room.py`

## VERIFIED baseline
Command actually run before feature edits:
`python -m pytest -q tests/test_pub_partner_chat.py tests/test_reach_writers_room.py`
Result: **14 passed in 3.38s**.

This is a focused baseline only. It is NOT evidence that the complete Reach test suite is green.

## Files created this turn
1. `modules/conversation_archive.py`
   - SQLite canonical conversation store.
   - Exact message text is stored without `.strip()` or normalization.
   - FTS5 local search.
   - conversation/message IDs and provenance-adjacent fields.
   - TXT, Markdown, JSON, JSONL and offline HTML exports.
   - SHA-256 helper.

2. `modules/package_service.py`
   - Save Conversation Raw with structured folder.
   - manifest + SHA-256 checksums.
   - Save Conversation ZIP under separate Archives directory.
   - collision-safe filenames.
   - ZIP post-write `testzip()` integrity verification.

3. `tests/conversation_ownership/test_archive_package.py`
   - exact whitespace/Unicode/newline round-trip.
   - FTS retrieval maps to original exact text.
   - parsed JSON/JSONL exact-text preservation.
   - raw manifest/checksum output.
   - ZIP integrity and required members.

No pre-existing source file was modified this turn.

## VERIFIED after feature seam
Command actually run:
`python -m pytest -q tests/conversation_ownership/test_archive_package.py tests/test_pub_partner_chat.py tests/test_reach_writers_room.py`
Result: **17 passed in 3.16s**.

This proves the new three tests plus the 14 focused existing tests pass together. It does NOT prove full-host, browser selection, autosave/restart, STT/TTS, or complete Reach regressions.

## Important existing behavior discovered
`modules/pub_partner_chat.py` currently calls `.strip()` on incoming message and generated reply. Its historical JSONL is therefore not suitable as the new verbatim archive authority. Do not silently repurpose that file as canonical Conversation Ownership storage. Integrate the new archive at a seam where the exact incoming text is still available, while preserving existing model-input behavior if desired.

`static/pub_partner_chat.html` uses ordinary DOM divs and `textContent` for message bodies, which is promising for native selection, but actual Ctrl+A cross-message behavior has NOT been browser-tested.

## Next actions
1. Add a General Chat API/router backed by `ConversationArchive`; keep it distinct from 2i and PubPartner-specific identity/model logic.
2. Integrate exact archival at request/response boundaries without changing the existing PubPartner behavior accidentally.
3. Build reusable General Chat UI with continuous selectable transcript + Plain Document Mode.
4. Add Save / Save As / autosave/export status and Save All Raw/ZIP API/UI.
5. Add safe package import only after export is stable.
6. Inspect/reconcile existing `tts.js`, `tts_engine.py`, `pubpartner_voice.py`; establish a functioning free/local TTS path and then STT.
7. Run focused tests after each seam, then broader Reach regressions.
8. Before promotion, reconcile against canonical Reach snapshot and later Reach handoff/runtime changes. Historical consolidation winners are floor, not ceiling.

## Status labels
VERIFIED: isolated extraction, named files present, 14-test baseline, three new archive/package tests, combined 17-test pass.
INFERRED: ordinary DOM structure should permit good native selection with deliberate focus handling.
UNTESTED: full suite, full host, physical browser/mobile behavior, crash/restart autosave, STT, live TTS, final ZIP of program, later Reach reconciliation.
