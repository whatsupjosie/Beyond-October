# PubCast communications marathon — findings and proposed plan for Claude
Prepared October 20, 2026 · America/Los_Angeles
Owner: Josie Curtsey Cobbley (Curtsey)

## Request to Claude

Review this plan against the existing architecture. Identify omissions, contradictions, stronger existing implementations, and unnecessary scope. In particular, challenge whether the proposed integration can meet the acceptance criteria. Preserve Curtsey’s decisions and working source. This is a planning/review handoff, not a claim that the work below has been implemented.

The goal is to finish a reliable communications system across PubCast, PubPartner Base, PubPartner Horizon, and 2i, including collaboration, voice, background AI exchanges, and Blackbox. “100%” means the agreed workflows genuinely work together, with evidence. No completion-time guarantee has been made.

## 1. Owner requirements established in this conversation

### Conversation and authority
- Receive messages from senders, deliver them to the intended recipient, and provide a working response path.
- Support the established world/room/private boundaries, identities, permissions, and persistent conversation history.
- AIs can talk in the background, with relevant initiative settings and turn coordination.
- Jeremy Cricket can contact a particular PubPartner and trigger consideration of a speaking turn without forcing participation.
- The host can require a partner to speak. This must be distinct from an invitation and distinct from posting a supplied line of text.
- Preserve established role separation: Jeremy protocol/context; per-user Cricket; personal PubPartner; System Alex emotional adjudication; Pete operations; Pub Manager; Security; Blackbox.
- The established personal AI owns final wording and voice. Route changes must preserve the intended Jeremy → appropriate Cricket → personal AI responsibility chain.
- Chat must work for Base and Horizon, within 2i, and in collaboration.
- “Collaboration” needs a precise mapping to the existing product behavior. AI co-writing exists; shared-human live document editing is a separate capability and must not be silently added as an assumed requirement.

### Microphones, speech, and rooms
- Microphones are set up and usable.
- Speech-to-text and text-to-speech work.
- Control-room audio can be recorded.
- Audio can play in every room except the dressing room.
- The dressing room permits direct director announcements only.
- The room rule must govern all audible paths, including partner speech, media, background speech, and announcement routing. Recording privacy and playback permissions are different rules.

### Blackbox
- Starts automatically with the program and closes with the program.
- Keeps an accurate log and records the required media.
- PubCast cannot browse recordings, edit stored evidence, or upload arbitrary content into Blackbox through its UI/control connection.
- PubCast has a narrow status/action connection.
- Two separate visible indicators inside PubCast:
  1. Connection/health: Blackbox is connected and functioning.
  2. Recording: Blackbox is actually recording.
- Status language: steady green = on/running; steady red = inactive/fault; blinking red = crashed; blinking green = restarting.
- A healthy connection cannot make the recording light green unless actual capture is working.
- Limited commands include save and preserve a specified time range.
- Example: preserve footage from 6:36 p.m. to 8:49 p.m. as a separate file. Copy that section; do not remove it from the main recording.
- The program must receive a truthful success/failure result for save operations.
- The final permitted action-command list must follow the existing design; do not infer a broad management API.

### Scope boundary
Personal avatars accompanying users in external worlds, including Meta sign-in/live representation, were discussed. The proposed marathon excludes that platform integration. Preserve the identity/conversation seams it will need. Avatar rebuilding, decorative UI redesign, and advanced tray physics are also outside this communications target.

## 2. Sources actually inspected

Latest identified full source checkpoint:
- PubCast_Foresight_Real_HTTP_and_Browser_CI_Checkpoint_2026-10-14.zip
- 32,422,746 bytes; ZIP integrity check passed; 1,329 entries.
- Extracted complete october/ tree; original archive preserved.

Supporting current handoffs read:
- README_FIRST_PubCast_Recovery_2026-10-18.md
- PubCast_Avatar_Menu_Recovery_Index_and_Claude_Handoff_2026-10-18.md
- PubCast_Foresight_WORK_MODE_MASTER_HANDOFF_2026-10-14.md
- PubCast_Foresight_THREE_PATH_REVIEW_AND_REVISED_WORK_HANDOFF_2026-10-14.md
- Embedded WORK_SESSION_HANDOFF_2026-10-14_NEXT.md and AGENT_RUN_HANDOFF_2026-10-14_CONTINUED.md
- PUBPARTNER_FORWARD_INTEGRATION_HANDOFF_2026-10-06.md
- PUBPARTNER_CHAT_STARTUP_BINDER_10-17-2026_11-32_PM.md

Recovered donors inspected:
- Pub-Partner-Base-Horizon-main.zip — 54,400 bytes; integrity passed.
- pubpartner-manuscript-intelligence.zip — 54,602 bytes; integrity passed. This previously missing package is now available.

October 18 recovery/menu/avatar bundles were located. They are collections of donor work, not proof of a newer integrated application.

The parts audit used three parallel read-only source reviews: messaging, audio, and Blackbox. No application source was changed. No microphone recording, live provider call, or new runtime certification was performed. No AGENTS.md was found in the inspected source.

## 3. Findings

| Area | Present in source | Gap |
|---|---|---|
| Canonical PubPartner | main.py configures modules/pubpartner_core.py:PubPartnerSpine with Alex/Jeremy bridge, CricketKeeper, vessel and scoped memory. run_turn assembles context, invokes provider, restores partner voice and records outcomes. | Genuine provider/browser acceptance remains open; parallel paths bypass it. |
| Legacy messaging | /api/pub-partner-chat/message calls modules/pub_partner_chat.py; direct character chat has durable transcripts and generation locks. | Legacy path calls provider directly; blackbox_witness argument is unused. Direct character chat also bypasses parts of enrichment/canonical spine. |
| Rooms/private delivery | chat_rooms.py includes role-gated rooms, consented DMs, durable permissions, WebSocket identity checks and receipts. | Consistent end-to-end delivery, recording coverage, ownership and restart recovery need proof across surfaces. |
| Base/Horizon | All nine donor pubpartner/*.py files match the integrated pubpartner/ package byte-for-byte. | PortableRuntime/SequenceController use was not found in active main/modules chat. Determine intended architectural relationship before adding adapters; presence alone proves neither integration nor incompatibility. |
| Background AI | BotManager handles mentions/autoreplies, presence, busy state and bot-to-bot limits; RoomConductor exists. | RoomConductor is constructed with an empty adapter registry; no watch_room activation found. Another watch_room call belongs to thinking_context. |
| Cricket invitations | Nudge and Cricket memory mechanisms exist. | Nudge directly schedules generation; no explicit invitation/defer/decline lifecycle or exact requested-partner targeting found. |
| Host turn | Privileged /api/bots/{id}/speak exists. | Posts supplied text verbatim; does not request a generated partner turn. |
| 2i | AI co-writing controls, canonical turns/live chat, manuscript context, saved partner conversations, recovery copies and SQLite revision checks. | Browser workflow remains unverified. No shared-document grants/live human edit broadcast found; federation is a separate unmounted peer-sync service. |
| Manuscript intelligence | Authenticated modules/manuscript_intelligence.py is mounted. | Shorter alternative to recovered donor. Stores chapters/signals, basic entities and context-only generation; stored voice signals/intelligence are not applied to generation. Donor adds continuity, authority/corrections/merges, indexing and voice learning. Endpoints overlap: do not mount both blindly. |
| Microphones | Enumeration, selected-device preferences/tests; browser picker; EQ/compression/pitch/gain/meters. | Picker/processor scripts were not found included by HTML. Processing opens default mic and lacks a connected recording/network sink. |
| STT | faster-whisper local engine; browser SpeechRecognition in 2i. | Lifespan assigns local stt_engine while routes read the module global initialized None. No frontend caller to local transcription endpoint found. |
| TTS | XTTS with pyttsx3 fallback; browser speechSynthesis; 2i reader. | Same lifecycle/global defect. Server-TTS browser client expects audio bytes but alias returns JSON. Bundled voice reference clips not found. |
| Playback | Web Audio buses, spatial attenuation, music ducking and stop-all; server audio-state routes. | Server command-to-player consumer not found. Raw Audio/speechSynthesis bypass mixer. No central dressing-room/director-announcement routing rule. |
| Blackbox log | Sequence/time/session/hash-chained JSONL; flush/fsync; verification; Hub committed-chat witness; production/audio metadata events. | Concurrent appends need validation/hardening; whole-program ingress coverage and recovery after witness failure are not established. |
| Blackbox lifecycle/status | In-process witness constructed at startup; operator status/verify routes. | No explicit final stop/session marker; enabled is configuration, not health. Two actual health/recording indicators and restart/crash states absent. |
| Recording/media | Recording session/artifact/profile machinery; stage canvas video capture. | Recording pipeline stores JSON events/chat/camera metadata, not actual control-room audio. Stage video lacks audio tracks. Save/time-range preservation commands absent. |

Critical distinction: an “active recording” metadata session does not establish that audio samples or video frames are reaching durable storage.

## 4. Proposed execution plan

### Phase A — protected baseline and contracts
1. Work on a versioned copy of the October 14 checkpoint; preserve originals and user data.
2. Reuse the existing audit and valid historical tests; investigate only unresolved paths or changed behavior.
3. Map every UI ingress to its current routing, identity, authority, persistence and recording path.
4. Agree internal message/turn/audio/recording contracts and failure semantics using existing types where possible.
5. Resolve architectural questions through source comparison first. Do not build a second conversation authority or replace working systems wholesale.
6. Establish isolated test data and inspect dependency/model/voice availability without exposing credentials.

### Phase B — parallel implementation with coordinated ownership
| Workstream | Deliverable |
|---|---|
| Messaging | Consistent scoped ingress, replies, durable commit/receipts and reconnection across required surfaces; close legacy bypasses while preserving clients. |
| PubPartners | Base/Horizon compatibility; personal identity/memory; functioning background scheduling; voluntary targeted Cricket invitations; authorized host-required generated turns. |
| Audio | Selected microphone reaches STT/transport/capture; repaired STT/TTS lifecycle and response contracts; routed playback and cancellation; enforce dressing-room announcement exception. |
| Blackbox | Durable capture/logging lifecycle, concurrent append correctness, truthful independent status, restricted action commands and non-destructive preserved segments. |
| Integration | Test real interfaces, concurrency, failure/restart behavior, permissions and packaged launch; coordinate repairs across workstreams. |

One integration owner coordinates shared files such as main.py and shared schemas. Agents should not independently rewrite these files or introduce competing queues/runtimes.

### Phase C — integrate in dependency order
1. Prove basic launch and consistent durable messaging.
2. Complete partner routing, scoped memory and Base/Horizon compatibility.
3. Connect AI background activity, invitations and required turns with bounded queues, cancellation and loop prevention.
4. Connect selected microphones, transcription and speech output through the room policy.
5. Connect actual control-room audio capture and required media to durable recording.
6. Derive health and recording indicators from actual liveness/capture progress, including stale-state detection.
7. Implement save and preserve-range requests with receipt/completion/failure reporting.
8. Exercise 2i collaboration using the established meaning of that feature.
9. Compare the richer manuscript donor. Integrate capabilities required by the agreed 2i workflow while retaining current owner/auth isolation. Broader manuscript enrichment should not delay reliable chat merely because a donor was recovered.

The exact Blackbox process boundary is an architectural implementation decision to inspect, not a new user requirement. The requirement is accurate recording, lifecycle and restricted access.

### Phase D — acceptance and delivery
Run the acceptance matrix below against one assembled build. Fix failures before labeling the relevant requirement complete. Deliver a complete runnable ZIP, concise launch instructions, source-change record, exact test evidence and explicit unresolved external gates.

## 5. Acceptance matrix

| Scenario | Required evidence |
|---|---|
| Normal startup/shutdown | Program opens required surfaces; Blackbox starts; final events/media flush and clean shutdown occur. |
| Incoming/reply | Two real clients exchange messages with correct identity, order, receipts and persistence. |
| Scope/privacy | Intended participants receive/retrieve messages; unauthorized clients cannot; background/private context does not leak into other scopes. |
| Base and Horizon | Each required surface exercises real intended partner runtime, identity/memory and genuine provider replies. |
| Background AI | Actual AI-to-AI exchange occurs without user prompting; initiative settings, silence and limits work. |
| Cricket invitation | Targeted partner receives invitation and can respond/defer/decline; no forced generation hidden as consent. |
| Host-required turn | Authorized host requests a generated speaking turn; unauthorized request fails; source and outcome are logged. Requiring speech does not script agreement. |
| Microphone and STT | Selected input produces understandable transcription; raw transcript remains distinguishable from corrections; permission/device failures are visible. |
| TTS and interruption | Intended voice produces audible speech; stop/mute/interruption prevent duplicate or continuing unwanted playback; actual delivery is distinguished from generated text. |
| Room audio | Allowed rooms receive audio; dressing room receives only authorized direct director announcements, including when playback originates from alternative players. |
| Control-room capture | Known microphone/program sources are audibly present in a finalized recording; elapsed duration and ordering are checked. |
| Blackbox indicators | Independently simulate disconnected, connected-but-not-recording, running, crash and restart conditions. Lights reflect each condition truthfully. |
| Preservation | A time-range request produces a playable separate copy with verified bounds; original remains intact. Resolve date/timezone/session ambiguity rather than guessing a recording. |
| 2i | Write/save/reopen manuscript, converse with partner, exercise co-writing, retain authorship and correct document context after restart. |
| Recovery | Disconnect, interrupted turn, provider failure, disk/write failure and restart produce visible states and safe recovery without lost committed text or duplicate speech. |
| Log accuracy | Independently inspect chronological/correlated events against actual client actions and media, including concurrent activity, commands and failures. |

An independent inspection path for recordings/logs is a verification need; it must not introduce browsing access inside PubCast.

## 6. External gates and honest reporting

- Local STT: faster-whisper and model weights.
- Character-cloned TTS: runtime/model and reference clips; fallback needs an available working system voice.
- Server audio devices: sounddevice/native PortAudio where used.
- Media export/segment operations: working media toolchain such as ffmpeg.
- Browser audio: supported secure context, microphone permission and actual device.
- Genuine model conversation: configured reachable provider.
- Browser integration and Windows launch require appropriate execution environments.

Previous handoffs report targeted tests and a real HTTP manuscript restart test. They explicitly leave live browser workflow, genuine provider replies and fresh Windows launch unverified. This audit did not rerun those suites or certify those gates.

Use PASS / FAIL / UNVERIFIED per requirement. Unit tests, mocks, source-string assertions, HTTP 200 responses and an event recorder cannot substitute for a real conversation, audible output or actual captured media.

## 7. Specific questions for Claude’s review

1. Which existing modules already satisfy gaps identified here, particularly Blackbox media capture, room audio policy and background orchestration? Cite concrete implementation paths.
2. What is the intended integration boundary between Base/Horizon PortableRuntime and the active PubPartnerSpine? Can compatibility be completed without duplicate ownership?
3. Which chat paths should delegate to the canonical pipeline, and which have justified distinct behavior?
4. Does the invitation/required-turn contract preserve partner initiative and host authority without uncontrolled background loops?
5. Is the proposed capture/status architecture sufficient to avoid false “recording” indicators and to preserve ranges accurately?
6. What does the current product mean by collaboration, and what additional behavior is actually required for completion?
7. Which dependencies or platform limits make a claimed complete tonight deliverable impossible to verify here?
8. What essential acceptance case is missing, and what proposed work can safely be deferred without weakening reliable communications?

Please return concrete corrections and a prioritized implementation order. Do not describe source availability as successful runtime integration.

