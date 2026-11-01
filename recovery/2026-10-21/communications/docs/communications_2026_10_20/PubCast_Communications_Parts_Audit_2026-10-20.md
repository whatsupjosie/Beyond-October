# PubCast communications parts audit — October 20, 2026

Scope: availability and source wiring for the communications marathon discussed with Curtsey. Read-only source inspection, not runtime certification. Original archives preserved; no implementation changes.

## Authoritative starting point
Inspected PubCast_Foresight_Real_HTTP_and_Browser_CI_Checkpoint_2026-10-14.zip, identified by the October 18 recovery handoff as the latest identified full source checkpoint. Archive integrity passed; 1,329 entries extracted. October 18 complete-recovery/menu/avatar collections are donor collections, not newer integrated program builds.

## Located additional parts
- Pub-Partner-Base-Horizon-main.zip: downloaded and integrity checked. All nine pubpartner Python files match integrated pubpartner/ byte for byte. Availability is confirmed; use of that portable runtime by the live PubCast chat path is not.
- pubpartner-manuscript-intelligence.zip: previously reported missing, now located, downloaded and integrity checked. Richer manuscript intelligence package, separate from current modules/manuscript_intelligence.py. Requires comparison and selective integration, not blind overlay.
- October 18 menu/settings and avatar recovery bundles located. Avatar work remains outside tonight's communications scope.

## Inventory

| Requirement | Existing parts | Gap / work required |
|---|---|---|
| Messaging | Hub, scoped rooms, chat commit store, permissions, PubPartner routes and provider adapters | Actual cross-surface send/reply, restart and privacy acceptance remain unverified |
| Base/Horizon | Portable runtime, cartridges, memory store, prompt assembler and sequence controller are present | Main live chat uses modules/pubpartner_core.py PubPartnerSpine; portable runtime integration not found |
| Background AI activity | BotManager mention/autoreply logic; RoomConductor class and construction | Conductor constructed with empty adapter registry; no watch_room activation found. Complete background conversation not established |
| Cricket invitations | Jeremy Cricket module; bot nudge/generation mechanisms | Explicit invite/accept/defer/decline protocol not found; nudge directly schedules generation |
| Host-required speaking turn | Privileged /api/bots/{id}/speak endpoint | Posts supplied text; does not establish a required model-generated speaking turn |
| 2i | Real manuscript store, revision conflicts, PubPartner turn calls, saved conversation state, AI co-writing controls | Browser acceptance remains open. Shared-human document membership/live editing not found; separate federation sync is not mounted in main |
| Manuscript intelligence | Current authenticated intelligence router is mounted | Recovered richer donor has additional capability; compare before integration |
| Microphones | Device enumeration/preferences/test, browser picker and processing/EQ/compression | Picker/processor scripts not included by HTML found; processor uses default input; no processed-output capture/transport sink found |
| Speech-to-text | Local faster-whisper engine; browser SpeechRecognition in 2i | Lifespan creates local stt_engine while routes read uninitialized module global; no frontend caller to local STT endpoint found |
| Text-to-speech | XTTS/pyttsx3 engine; browser speechSynthesis; 2i reader | Same local/global lifecycle wiring defect. Browser server-TTS client expects audio but alias returns JSON. Bundled voice reference clips not found |
| Room playback | Web Audio mixer/buses, spatial attenuation, ducking, stop-all; audio state routes | End-to-end server command consumer not found; raw Audio/speechSynthesis bypass mixer |
| Dressing room | Separate recording privacy default exists | Playback prohibition except direct director announcements is not implemented in inspected playback path |
| Blackbox event log | Append-only sequence/time/session/hash-chain JSONL; fsync; verification; Hub committed-chat witness | Concurrent appends need validation/hardening; full ingress coverage not established; explicit final shutdown marker absent |
| Blackbox lifecycle | Constructed and attached at startup in main lifespan | In-process event witness, not independent media recorder; no explicit stop/final capture confirmation |
| Blackbox indicators | Operator status reports enabled/sequence/hash | No independent health heartbeat and actual media recording progress; requested two lights/crash/restart states absent |
| Blackbox commands | Operator status and verification routes | Save and preserve-time-range-copy commands plus confirmed completion absent |
| Control-room recording | Recording service session/artifact/profile machinery | Recording pipeline stores metadata; durable actual control-room audio capture sink missing in inspected paths |
| Footage | Canvas video capture exists for stage | No audio tracks added; not proof of complete media recording or time-range preservation |

## Important source references
- main.py: lifespan, Blackbox construction, STT/TTS setup and endpoints, room conductor construction, manuscript intelligence router.
- blackbox_recorder.py; modules/blackbox_runtime.py; modules/blackbox_routes.py; modules/hub.py.
- modules/recording.py; modules/recording_pipeline.py.
- modules/program_audio.py; modules/program_audio_routes.py; static/program_audio_runtime.js.
- modules/audio_devices.py; modules/mic_routes.py; static/mic_device_picker.js; static/mic_processor.js.
- modules/stt_engine.py; modules/tts_engine.py; static/tts.js.
- modules/jeremy_cricket.py; modules/room_conductor.py; BotManager message/nudge logic.
- modules/pubpartner_core.py; pubpartner/portable_runtime.py; pubpartner/sequence_controller.py.
- modules/writers_room.py; modules/manuscript_intelligence.py; 2i/2i-assets/reach.js.
- pubpartner/pubpartner_federation/: separate synchronization service.

## Dependencies and acceptance gates
Local STT needs faster-whisper and model weights. Cloned TTS needs its runtime/model and character reference clips; system-voice fallback needs an available working voice. Server microphone enumeration requires sounddevice/PortAudio; media conversion requires ffmpeg. Browser capture needs permissions and a supported secure context. Live LLM replies need a configured reachable provider. None of these external/device gates were certified in this parts audit.

Historical handoffs report targeted tests and real HTTP manuscript restart persistence. The checkpoint explicitly does not certify actual browser operation, real provider replies, or fresh Windows launch. No new runtime test pass is claimed here.

## Assessment
A substantial communications foundation exists, with recovered Base/Horizon and manuscript donor code available. We do not yet have every required component integrated. Blackbox media capture and preservation, independent truthful indicators, central room playback policy, and the precise invitation/host authority behavior require implementation or recovery from a demonstrated stronger donor. Speech and microphone paths require concrete wiring repairs. Use this inventory to assign bounded implementation tasks, followed by full integrated acceptance.

