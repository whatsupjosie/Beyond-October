# PubPartner Calibration Integration Checkpoint
Date: 2026-11-22
Branch: `gpt/pubpartner-calibration-2026-11-22`
Status: **Integrated source implementation, not qualified production release**

## Implemented in this branch
- Shared calibration endpoints on the canonical `modules.pubpartner_routes.router`, used by `pubpartner_app.py` and PubCast `main.py`.
- File-persisted, user-scoped interviews: User Calibration and System Calibration.
- Formal interview target three main questions; hard stop after five. Each main question permits one optional follow-up; user can continue afterward. Clarification events after formal close do not increase formal question count.
- Actual Calibration entry in the PubPartner Memory menu, responsive modal, restart/resume support, typed responses, optional browser speech dictation.
- Optional 60-second MediaRecorder voice samples and authenticated upload/retrieval, constrained size and per-interview count. Browser dictates only when explicitly activated. No background microphone recording.
- Source-grounded retrospective review for recent completed conversation turns, restoring real original user text from Verbatim Vault.
- User-approved corrections routed into the existing Relationship Engine as confirmed `identity` (System Calibration) or `workflow` (User Calibration) guidance; no silent direct overwrite of the character profile.
- Tests added for the calibration store, isolation, formal limits, persisted audio references, and static integration contracts.

## Explicit limits
- No automated affect/EQ interpretation of the recorded audio, no confidence calibration, and no acoustic baseline comparison yet. Audio is preserved as evidence; no emotion is guessed by this feature.
- The question selector is a small evidence-aware question set, not an LLM-based adaptive selector or the full 30-question research bank.
- Voice transcription uses optional browser SpeechRecognition where available; this may be serviced outside the device. Actual voice samples are recorded separately.
- No Iteration Wallet archival adapter or cryptographic pairing is part of this branch.
- This is not yet a complete searchable Blackbox Light archive across every chat surface; the recent-moments adapter is scoped to existing PubPartner completed turns and selected session.
- There is no retention/expiration UI for audio; currently recordings persist on the configured PubPartner host until a separately implemented retention workflow manages them.
- Mobile browser, HTTP-route, EQ, provider behavioral, and full Python runtime tests are NOT RUN in this checkpoint. GitHub Actions usage was not consumed.

## Verification completed
- Compared actual canonical application registration paths for embedded and standalone use.
- Confirmed new routes, source references, and Relationship Engine's existing confirmed-lesson `compact()` connection.
- Parsed the new browser JavaScript with V8 `new Function` without executing it.
- Checked DOM id/handler bindings, audio endpoint markers, and key constraints by reading source.
- Corrected a mistaken static test assertion referring to `this.relationship` instead of Python `self.relationship`.

## Acceptance before merging
1. Run `pytest -q tests/test_pubpartner_calibration.py tests/test_pubpartner_calibration_integration_static.py`.
2. Run standalone FastAPI HTTP tests using a fresh temporary user data directory; verify auth separation, storage, and archive behavior.
3. Open `/pubpartner` in Chromium at 360px viewport and test Start, Answer, Follow-up, Question 3, Question 5 hard stop, Finish, Continuation, Resume, and explicit application of a correction.
4. Exercise actual MediaRecorder capture, upload, replay, and microphone-stop behavior on mobile; verify 60-second ceiling.
5. Hold a new conversation and inspect FCP1 guidance to confirm an approved calibration lesson appears under the expected partner and user, without leakage to other users.
6. Once validated, implement an EQ-facing annotation reader and Wallet archival adapter against the existing authoritative services rather than duplicating them.

Do not mark this feature production-complete until the above proof is recorded.
