# PubPartner automatic conversation capture: repair handoff

Prepared for the chat currently consolidating and merging PubCast/PubPartner.
Date: 2026-10-21

## Goal

Preserve user messages and completed assistant replies automatically, verbatim, with durable receipts. Reuse the existing recorder and memory architecture. Keep this repair small and compatible with the consolidation already underway.

Do not describe automatic ChatGPT capture as working until an actual ChatGPT-origin message and reply have reached persistent storage automatically and survived readback after restart.

## What the investigation established

- `PUBPARTNER_LIVE_CHAT_CAPTURE_2026-10-06.txt` explicitly describes manual per-turn appending. It is a transcript artifact, not an automatic integration or proof of later completion.
- October `main` was inspected at `b44db358455d1d5e2467e4802afd91b3f3051dba`.
- `October-Foresight-Doc-Integration` was inspected at `d5fc7ecb51ac74526a208cf94e88ea9d4e3760f4`. Its `modules/pubpartner_core.py`, `modules/pubpartner_routes.py`, and `pubpartner_app.py` matched the inspected main versions.
- These are inspection baselines, not instructions to reset the current merge branch. Recheck the current files before editing.
- No live capture or repository tests were run during this investigation.

## Existing implementation to preserve

| File or component | Existing behavior |
| --- | --- |
| `static/pubpartner.js` | PubPartner's own UI sends messages to `/api/pubpartner/turns/live`. This is not a ChatGPT-surface connection. |
| `modules/pubpartner_routes.py` | Validates text and scopes the user to authenticated identity. |
| `PubPartnerSpine.build_turn_packet()` in `modules/pubpartner_core.py` | Calls `self.vault.store(text=message)` before prompt compaction; passes source references into vessel/Jeremy continuity. |
| `VerbatimVault` in the same file | Stores exact UTF-8 sidecars, JSON metadata, SHA-256 hashes and audit-chain rows; supports verified restoration. This is the strongest reuse point. |
| `PubPartnerSpine.run_turn()` | Persists raw provider output and displayed friend response in session turn logs and records response hashes in receipts. Those responses do not go through the same user-source vault call. |
| `blackbox_recorder/pubcast_event_adapter.py` | Maps received PubCast events to BlackBox records. It does not itself intercept ChatGPT turns. Its normal compact projection is not a universal lossless transcript store. |

Related repositories do not establish the missing connection: Horizon's `PortableRuntime` requires the host to submit input, and its episodic memory is not a two-role verbatim transcript. The older `NowCurtsey-Build/vault_store.py` is a separate versioned document vault, not a ChatGPT capture adapter. Avoid replacing the current spine with either.

## Exact missing boundary

ChatGPT conversation events -> an authenticated, capture-only receiver -> VerbatimVault -> durable receipt and later memory retrieval.

The missing evidence is an automatic producer/delivery path from the actual ChatGPT surface. A working downstream vault, an OpenAI API provider, an imported transcript, or manual assistant tool calls do not establish that path.

## Repair steps

1. **Fit the current merge.** Inspect the branch and pending changes. Reuse equivalent work if another merged component already supplies it. Preserve existing APIs, authentication, source records, memory scopes and provider behavior. Add a focused commit on the consolidation branch; do not create another repository.

2. **Add a capture-only ingestion service and authenticated route.** Reuse `VerbatimVault.store()` and the existing identity-scoping helpers. A suggested route is `POST /api/pubpartner/capture/messages`; this is a proposed new route, not an existing one. Do not route recorded assistant replies through `run_turn()` or treat them as new user prompts. Capture must not call a model, spend provider credentials, restore a different voice, or infer new personal facts merely to save an event.

3. **Define a small event contract.** Include source surface, external conversation ID, stable external message ID, role (`user` or `assistant` initially), exact text, source timestamp when available, and revision/parent/order identifiers when available. Bind ownership to authentication. Preserve whitespace, newlines and Unicode without trimming or normalization. Distinguish source time from receiver time. Preserve provenance as metadata; do not invent missing IDs, dates or ordering certainty.

4. **Make delivery safe to retry.** Persist a unique event mapping scoped by owner, source, conversation, message and revision. Identical retries return the original source ID and receipt without another vault append. Conflicting content under the same identity must be rejected or recorded as an explicit revision, never silently overwritten. Serialize writes as needed: a read-last-hash/append chain alone does not establish concurrency safety. Handle a crash between vault writing and mapping/receipt persistence so retry can recover without falsely acknowledging success or duplicating the event.

5. **Return evidence after persistence.** Return the source ID, text SHA-256, byte length, event identity and durable receipt/reference only after the record is committed. Reuse existing receipt machinery where appropriate. Report storage failures explicitly. Do not equate an HTTP connection or healthy recorder process with a successfully saved message.

6. **Connect a real source adapter only where supported.** Determine what actual host event hook, supported integration, or user-installed client adapter is available. Subscribe to user messages and completed assistant replies; preserve edits/regenerations as distinct revisions or branches. Use a durable pending queue and acknowledge/remove entries only after matching receiver confirmation. Clearly distinguish pending, saved, and failed events. Do not claim access to ChatGPT internals, silently use private endpoints, or label periodic/manual exports as live automatic capture. If no source hook is available, complete and verify the receiver, then report that the ChatGPT producer remains blocked.

7. **Keep derived memory downstream.** Save exact source first. Where appropriate, send a source pointer through existing vessel/Jeremy paths. Maintain role and authorship so an assistant statement does not become a user fact. Memory filtering, summaries and token budgets must never determine whether the original transcript survives. Avoid duplicating existing PubPartner-native capture if both old and new paths see the same event.

## Required verification

- Save one user message and one completed assistant reply; restore both exactly, including leading/trailing spaces, blank lines, multilingual text and emoji. Compare UTF-8 bytes and hashes.
- Retry each event and submit concurrent duplicates: one source record and one stable acknowledgement per event identity.
- Submit changed content under the same identity: explicit conflict or revision; original unchanged.
- Restart the receiver and retry/read back: identities, text and receipts remain recoverable.
- Inject storage failure and interruption between write stages: no false saved status; recovery has no duplicate or lost acknowledged event.
- Verify owner isolation for submission and readback. Client-supplied user IDs must not bypass authentication.
- Confirm capture-only ingestion never invokes a provider or generates another response.
- Run relevant existing vault, source restoration, receipt, route/authentication and live-loop tests. Confirm existing PubPartner UI/provider behavior still works. Inspect the `horizon_ref_pubpartner_*` tests explicitly; do not assume their filenames are collected by the default test command.
- For a real source adapter, disconnect/reconnect and replay pending events; test a completed reply and an edited/regenerated reply. Define treatment of interrupted streaming output explicitly.

## Completion labels and delivery

Report these separately:

1. **Recorder components:** existing code and which checks were actually rerun.
2. **Capture receiver:** implemented and tested, or still incomplete.
3. **Source adapter:** synthetic sender, import, PubPartner-native client, or actual ChatGPT surface; identify which.
4. **ChatGPT end-to-end:** verified only after real automatic delivery and restart/readback succeed.

Deliver the focused diff/commit, actual test commands and results, and remaining blockers with the consolidation handoff. A passing synthetic sender test narrows the gap; it does not close the ChatGPT-surface boundary.

## Source references

- Capture document: `PUBPARTNER_LIVE_CHAT_CAPTURE_2026-10-06.txt`, Library version 4 read during investigation (modified 2026-10-18).
- Current spine: https://github.com/whatsupjosie/October/blob/b44db358455d1d5e2467e4802afd91b3f3051dba/modules/pubpartner_core.py
- Routes: https://github.com/whatsupjosie/October/blob/b44db358455d1d5e2467e4802afd91b3f3051dba/modules/pubpartner_routes.py
- App wiring: https://github.com/whatsupjosie/October/blob/b44db358455d1d5e2467e4802afd91b3f3051dba/pubpartner_app.py
- Native client: https://github.com/whatsupjosie/October/blob/b44db358455d1d5e2467e4802afd91b3f3051dba/static/pubpartner.js
