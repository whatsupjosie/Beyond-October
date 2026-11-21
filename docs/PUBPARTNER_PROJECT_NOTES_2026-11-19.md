# PubPartner project notes (work log), 2026-11-19

Branch: `claude/pubpartner-work-notes-2026-11-19`, cut from `fable/integration-2026-11-13` (commit 764874a). Not merged. Merging needs the owner's okay.

## Why this exists

Shelf 2 of Fable's plan in `docs/alex_eq_2026-11-10/PUBPARTNER_MEMORY_EVALUATION_2026-11-10.txt` is a running notes page for each project. It records what was decided, what was worked on, what is still open, and what was discussed, so that any model the user talks to next already knows it. The page belongs to the user and the project, never to a character cartridge.

## What the owner decided (her words, from the task thread)

- "Build it."
- "Maybe save it as like a temporary autosave. And when the user saves it, everything's committed."
- "Just keep autosaves for a week or so. Up to a maximum of 50 autosaves."
- She left the rest to Claude: "just do what you think is best and protects the user's intent and the originality of their project and their work."

Claude then proposed the following, and she approved it:

- The chat itself is saved for real after every exchange. This was already true: the user's text goes to `VerbatimVault` and the reply goes to the turn log, which is fsynced. This build does not change that.
- Notes collect as drafts in one autosave per chat session. The autosave keeps updating while she works, and Save commits the drafts.
- Unsaved drafts are kept for one week, across at most 50 autosaves. Past either limit they are deleted. Saved notes are never deleted by the system.
- Next session, unsaved drafts from earlier chats are listed so she can save or drop them.
- A model is told only saved notes, never drafts.
- A note's words are never rewritten. A fix is a new note, and the old note stays on record marked replaced.

## How it works

- **Storage:** one SQLite file per user at `data/pubpartner/work_notes/<name>-<hash>.sqlite3`. The hash keeps users whose names clean to the same text apart. The file holds the notes, the autosaves and a hash-chained audit trail. Each change and its audit row are written in one transaction.
- **Guards inside the database:** triggers refuse any change to a note's text, kind, project, origin or source pointer. They refuse deleting anything except an unsaved draft. They refuse turning a saved note back into a draft, and any edit or delete of the audit trail.
- **Detection:** this happens after each live turn (`PubPartnerSpine.run_turn`), once the turn is already saved. Every detected note is an exact sentence copied from the chat, with the turn id, source id and character span it came from.
  - Decisions and open items come only from the user's own words, from plain phrasings such as "we decided", "let's go with", "I still need to" and "TODO:".
  - File names and version numbers ("main.py", "v12", "2.4.1") come from either side. A model's sentence is labelled as said by the model.
  - Quoted speech, quote blocks, fenced code, web addresses, pasted code and other exact-text kinds are never mined.
  - Replies from the mock, echo and offline diagnostic providers are never mined.
  - A sentence already noted in the project is not added twice.
- **What the model sees:** on private turns only, the saved notes for that project are added to the FCP1 packet as `notes`. They are newest first, up to 40 notes or 12,000 characters. A note is either shown whole or left out and counted in `not_shown`; it is never cut part-way. Shared and public rooms get no notes. The turn log records which note ids were used, not another copy of their words.
- **Failure handling:** if the notes file is damaged, the turn still completes, and the turn result reports the error under `work_notes`.
- **Source check:** `GET /api/pubpartner/work-notes/{note_id}/source` restores the exact chat text a note was quoted from and confirms that it still matches.

## Exact paths

- New: `modules/pubpartner_work_notes.py` (store and detector)
- New: `tests/test_pubpartner_work_notes.py` (23 tests)
- New: `docs/PUBPARTNER_PROJECT_NOTES_2026-11-19.md` (this file)
- Changed: `modules/pubpartner_core.py`
  - creates the store on the spine
  - adds `FCP1Packet.work_notes`, which shows only when non-empty, so packets for users with no saved notes are unchanged
  - feeds saved notes into private turns
  - records drafts after each live turn
  - adds `work_note_source`
  - keeps note words out of the turn log
- Changed: `modules/pubpartner_routes.py`, which adds these routes under `/api/pubpartner/work-notes`:
  - `GET` the list, `/drafts`, `/export` (plain text), `/verify` and `/{id}/source`
  - `POST` to add a note, `/save`, `/{id}/replace`, `/{id}/drop` and `/{id}/withdraw`
- Changed: `static/pubpartner.html`, `static/pubpartner.js` and `static/pubpartner.css`, which add a Project Notes tray:
  - this chat's drafts, earlier chats' drafts, and saved notes
  - Save, Drop, Fix, Stop using, Source, Add, Refresh and Export
  - a "Project notes" item in the memory menu

Previous versions of every changed file are the parent commit on this branch.

## Provenance

- Patterns reused from code already in Beyond-October:
  - the hash-chained audit of `VerbatimVault`
  - the quote masking and explicit-phrase approach of `RelationshipEngine.extract_explicit_lessons`
  - the user scoping (`_scoped_user_id`) and error style of the existing PubPartner routes
- Checked before writing:
  - `modules/pubpartner_knowledge.py` is an online reference desk, not a work log.
  - `handoffs/PubPartner_Automatic_Capture_Repair_Instructions.md` covers capturing replies, not a work log.
  - The vessel's `EvidenceMemory` fits character memory claims, not a draft, save and expire lifecycle owned by the user. It was not reused, to keep notes out of Alex's vessel.
- No donor repository code was overlaid.
- The Alex vessel file and its blob id `96fa66a728d07d5ff43b0d3d7fc17a466765cec1` were not touched.

## Tested

- `python -m pytest -q tests\test_pubpartner_work_notes.py` (works in PowerShell 5): 23 passed. The tests cover:
  - exact spans
  - quotes, code and links being skipped
  - decisions and open items taken only from the user
  - one autosave per session, and Save by session
  - no duplicates
  - the database refusing edits to words, deletes of saved notes and audit edits
  - fixing saved notes and drafts, drop and withdraw
  - week expiry, the 50-autosave limit, and a working session staying alive
  - no clipping inside the model budget
  - notes added by the user kept exactly as typed
  - per-user files
  - detection of a tampered audit trail
  - plain-text export
  - spine wiring: drafts are not given to the model; saved notes are, on private turns only, per project; notes follow the project saved on the session; the source check; the turn-log copy
  - diagnostic replies and pasted code not mined
  - a broken notes file not blocking a turn
  - every HTTP route end to end, including 400 and 404 errors and two users kept apart
- Related PubPartner suites (vessel, core, companion, Alex, Foresight host wiring and others, 19 files): 252 passed before the change and 252 passed after it, rerun on the final code.
- Full suite, run locally with no GitHub Actions: 2388 passed, 45 skipped, 1 xfailed, 5 failed. None of the 5 come from this change:
  - Four fail the same way on the base commit with this change removed: `test_data_checkpoint_host_recovery::test_restore_real_host_sign_in_open_work_and_play_recording` and three in `test_restart_persistence_e2e` (`test_memory_survives_process_restart`, `test_verbatim_original_is_byte_exact_on_disk`, `test_restart_tolerates_truncated_turn_log_and_corrupt_bridge_state`). Their child process stops while importing `main` and writes no result.
  - `test_alex_routes_bridge::test_alex_routes_message_and_recent_memory` passes when its file runs alone (9 passed). It fails only when run after the other PubPartner suites, and it fails the same way in that order on the base commit, so it depends on test order, not on this change.
- Five browser test files need Playwright's browser, which cannot be downloaded in the build environment, so they were not run.
- The Project Notes tray was driven in jsdom against a live local `pubpartner_app` server: refresh, drop, save, add and fix all worked through the real routes, with no page errors.

## Not tested

- The tray's look and position in a real browser. Playwright's browser download is disabled in the build environment. The tray opens to the right of the existing trays, at left 1285px. On a narrower screen, opening it from the menu or at start-up pulls it back inside the desk. That pull has only been checked as code, not on screen.
- A real model reply being mined live. This was tested with a recorded provider result, not a live Ollama or hosted model.
- Windows itself. The code uses only `pathlib` and `sqlite3` and closes every connection, but it was run on Linux.

## Still open (owner's call, not built here)

- Plain mode, Fable's decisions 2 and 6: plain mode does not exist yet, so nothing here decides those questions.
- Decision 3, which projects may be sent to an outside model: notes go only to the model on the existing PubPartner turn, and only on private turns.
- The UI uses the fixed project id `pubpartner`, as the rest of the PubPartner page already does. Per-project selection in the page is not built.
