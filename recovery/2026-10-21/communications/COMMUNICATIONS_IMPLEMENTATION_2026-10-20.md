# PubCast communications — implementation checkpoint

October 20, 2026 · Owner: Josie Curtsey Cobbley (Curtsey)

This ZIP contains the full source tree, core communications repairs, recovered donors, original audit/plan, and test evidence. It is an implementation checkpoint, **not full communications-marathon acceptance or production commissioning**.

## Start

Extract the ZIP and open `october/`. Use the existing `OPEN_REACH_WINDOWS.bat`, or install `requirements.txt` and run `python run_reach.py`. The launcher remains unchanged. Preserve your existing user-data directory when updating; use a separate extracted copy for evaluation. Configure your existing provider, microphone permissions, and voice/model dependencies. No new model weights or character voice recordings are bundled.

Read this file before the older embedded handoffs: those describe their own earlier source checkpoints.

## Changes

- **Speech:** STT and TTS constructed in the lifespan now populate the globals used by their HTTP endpoints. Browser server-TTS calls `/api/tts/synthesize`, checks for audio content, and sends playback through the program mixer. Cancellation invalidates pending output and releases object URLs.
- **Microphones:** the control room now loads the existing device picker, profiles and processor. Activation uses the selected device, exposes processed audio to capture and utterance transcription, and connects cough gates to the processed gain. An unavailable selected device fails visibly rather than silently substituting another. The raw transcript is displayed separately; it is not silently edited or posted as chat.
- **Playback:** authenticated players consume a bounded sequence of audio commands. Recovery commands reach players; duplicate command IDs are suppressed; a command gap stops stale playback. The feed filters room-specific commands by the existing room-role policy. The shared runtime blocks ordinary playback in the dressing room, stops it on entry, and permits authorized direct director announcements. Raw media-element playback and browser speech pass through guards on the pages that load this runtime. Playback rejection cleans up active handles. Dispatch is not reported as proof of audible delivery.
- **Partner turns:** targeted voluntary invitations now have distinct consideration, acceptance, deferral, decline, failure and completion outcomes. Host-required turns request generated speech and preserve the partner's own wording and ability to disagree. The existing exact-text `/speak` endpoint retains its original contract. New turn endpoints require an authenticated host/moderator, even in relaxed compatibility mode. Receipts survive restart, and interrupted requests are marked interrupted. Busy-state reservation, room scheduling locks, timeouts and a six-turn background-burst ceiling bound generation.
- **Conversation activation:** configured rooms are watched by the existing RoomConductor; committed chat updates scene state. Initiative remains configurable and owner presence is checked. The conductor no longer aggregates unscoped private character banks into room hints.
- **Personal chat:** the mounted legacy personal-partner endpoint now binds the authenticated caller and delegates to PubPartnerSpine using trusted runtime profiles. Existing local-provider configuration and fallback selection remain available through that dispatcher. Echo profiles are not counted as live conversation. Canonical partner turns emit Blackbox receipts. Fictional-cast direct conversations retain their separate private transcript/service contract and receive a private thread-scoped Cricket; room Crickets use owner/partner/room scopes.
- **Blackbox events:** the active `blackbox_recorder/` package now serializes concurrent appends and verification and flushes/fsyncs acknowledged event writes. The same-named standalone module is unchanged. Session identifiers are unique; shutdown records a final marker and closes media sinks. Nested application clients cannot shut down another active lifespan's tasks.
- **Blackbox audio:** a dedicated authenticated live PCM WebSocket accepts control-room capture, writes acknowledged samples into durable WAV files, and reports capture progress separately from event-witness health. It rejects invalid format, conflicting capture sources, cross-origin browser connections, stale streams and streams outside the live sample clock. Stalls/failures cannot leave a green recording state indefinitely.
- **Blackbox controls:** save and preserve commands return completion/failure receipts. Preservation copies exact sample frames into a separate WAV and retains the original. Choose an explicit capture ID and either relative seconds or complete timezone-qualified datetimes; ambiguous/incomplete clock requests are rejected. Completed capture files can be preserved after process restart. There is no recording-content browser, media download endpoint, evidence editor, or arbitrary-file upload control.
- **Indicators:** Foresight and the control room show separate connection and recording lights. Green means running, red inactive, blinking red failure/stall, and blinking green a capture reconnect in progress. Health requests time out so a dead connection cannot keep a stale green light. Foresight's lights inspect status; the control-room client owns browser audio capture.
- **Stage footage:** the older DOM stage recorder produced a painted title card. It now requests actual tab capture, verifies an opted-in same-origin PubCast stage tab through the capture-handle API, and labels video-only versus video-with-tab-audio honestly. Unsupported browsers fail visibly. This local video export remains separate from Blackbox audio.
- **Missing optional character data:** missing intent JSON now falls through to already-authored character-module replies rather than crashing the intent lookup. No character personality or replacement dialogue was invented.

## Evidence

| Check | Result | What it proves |
|---|---|---|
| Consolidated Python suite | **182 passed**, one upstream deprecation warning | New capture/host/turn contracts plus existing portable partner, canonical spine/live-loop, 2i, durable chat, authorization and lifecycle regressions |
| Real HTTP/WebSocket capture test | **PASS**, included above | A separate Uvicorn process receives generated PCM, acknowledges frames, saves, restarts, and preserves the exact requested waveform samples |
| Concurrent event-chain test | **PASS**, included above | Eight threads append to one active recorder without broken sequence/hash chains |
| WAV copy/recovery tests | **PASS**, included above | Sample-accurate separate copies, original-file hash unchanged, capture discovery after restart, invalid bounds rejected |
| JavaScript runtime/room tests | **PASS** | Mixer failure cleanup, interruption, room blocking, announcement exception and routing behavior using API doubles |
| Capture browser-contract tests | **PASS** | PCM packet/tail output, selected-tab verification, media labels and track cleanup using native-interface doubles |
| JavaScript parsing | **PASS** | Eight changed external scripts and eight inline script blocks across changed pages parse |
| Workbench preflight | **PASS** | Packaged routes/assets and first-run workbench wiring respond in process |
| Actual Chromium run | **UNVERIFIED / BLOCKED** | Browser download repeatedly returned invalid archives; no real browser session ran |
| Physical mic, local STT/TTS, audible speech, live LLM, Windows | **UNVERIFIED** | No device, voice-model, genuine-provider or fresh Windows acceptance is claimed |

The final combined result is in `agent_evidence/communications_2026_10_20/pytest.log` and `pytest.xml`. Node and preflight logs are adjacent. The initial combined failure log is retained as historical evidence: it exposed the nested-lifespan task ownership defect, which was repaired before the final 182-pass run. Provider and speech doubles are labeled in their test files; they are not evidence of real model replies or audible speech.

## What is still incomplete

1. **Automatic all-program capture is not complete.** The server starts the event witness automatically; actual browser audio begins when an authenticated control-room page opens and browser permission/autoplay permits it. Closing that page ends its source. Foresight indicators alone do not start media capture. A supervisor-owned capture source and automatic reconnect across page/process failures remain work.
2. **Recording coverage is limited.** The new WAV contains the chosen microphone/processed mic outputs and audio routed into the same control-room Web Audio graph. Browser `speechSynthesis`, raw media players, audio in other iframe contexts, external applications and video are not thereby proven captured. A green recording indicator proves recent durable PCM progress, not complete source coverage or intelligible microphone content. Full source-coverage acceptance remains essential.
3. **Blackbox video and footage-range preservation remain incomplete.** The stage's real tab-video export is local and browser-unverified; it is not a Blackbox video sink. Preserve currently produces audio WAV copies, not synchronized audio/video footage. Datetime mapping uses the server's capture-acceptance timestamp plus the source sample clock; network/browser startup offset has not been measured. Exact sample offsets are verified; absolute wall-clock accuracy is not certified.
4. **Browser and cross-frame audio behavior need actual acceptance.** Check room transitions, all alternate players, browser autoplay, same-origin tab capture, microphone switching, cancellation, closed tabs and embedded tray routing. The server playback-state counters describe commands, not independent evidence of sound reaching listeners.
5. **Live AI and personal continuity need acceptance.** Test actual configured providers and background exchanges. Existing legacy histories and unscoped Cricket records are retained, but are not automatically imported into new scopes because their ownership can be ambiguous. Review/migrate only records with demonstrated owner/room provenance; do not erase old memory or silently expose it across users. The canonical legacy adapter needs real-provider and prior-history continuity checks.
6. **Base/Horizon architectural acceptance remains open.** All nine portable `pubpartner/*.py` donor files are byte-identical to the checkpoint; their tests pass. That proves preservation and the tested portable API, not that a live Base/Horizon UI exercises every intended portable-runtime/cartridge behavior. The active application still uses PubPartnerSpine as its conversation owner. No second live conversation authority was added.
7. **Manuscript intelligence enrichment is deferred deliberately.** The richer recovered donor is included unchanged in `recovery_donors/`. Its README and module inventory were reviewed. Its overlapping unaudited routes were not mounted over the current authenticated manuscript service. Existing 2i save/reopen/co-writing wiring and revision checks remain. Shared-human document editing was not silently added.
8. **Single-process assumptions remain.** Capture ownership, event locking, bot room locks and turn-request restart recovery assume one application process. Cross-worker capture ownership and recorder locking are not implemented. A WAV approaching RIFF's size limit fails visibly and requires a new capture; seamless rollover is not implemented. Power-loss durability and exhausted-disk finalization require additional fault injection.
9. **Final user-machine commissioning remains.** Test fresh Windows launch, credentials, actual provider calls, microphones, installed transcription/voice dependencies and real recordings before using this build for a marathon.

## Next implementation order

1. Establish a browser-capable environment and reproduce the control-room microphone, output and indicator flows.
2. Finish source coverage and a supervisor-owned capture lifecycle; reconnect and roll over without silently losing intervals.
3. Integrate durable video plus audio/video range copying into the restricted Blackbox boundary.
4. Exercise live providers and scoped-memory continuity across personal partner, cast, Base/Horizon and 2i surfaces.
5. Execute the original acceptance matrix against one assembled build, then fix every failed case before commissioning it.

## Preservation

The original October 14 archive was not modified. This package includes every original source file, the intended code changes and new tests. Test-generated user data, accounts, temporary captures and caches are excluded; original archived data files are preserved. `COMMUNICATIONS_SOURCE_CHANGES_2026-10-20.json` records source differences by filename/hash. The original audit and proposed plan are retained under `docs/communications_2026_10_20/`; recovered donor ZIPs remain unchanged under `recovery_donors/`.
