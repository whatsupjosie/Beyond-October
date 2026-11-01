# Three-Solutions Test — PubCast 2.5D Video Media Plane
**Date:** October 30, 2026  
**Owner requirement:** The 2.5D and explorable studios use the SAME audio and video switchers. Preserve natural 3D performer animation, offline-first operation and owner-replaceable scenery.

## The pivotal question
Who creates authoritative program pixels, and how do real rendered video and audio reach the shared Control Room and recording machinery?

The previous shortcut registered virtual 2.5D cameras in `CameraManager` but supplied no media. Camera names moved between Program/Preview while the Director had **no real frames**. That is not working remote video.

## Solution A — Fully independent browser canvases
Each interface renders its own copy of the stage from replicated JSON state. Controls share camera IDs; no media is moved.
- **Works for:** zero-network/offline local playback, simple preview and individually captured local video.
- **Strengths:** extremely low server bandwidth; offline; no transcoding.
- **Weaknesses:** remote Control Room is not guaranteed to see the same pixels, avatar pose or recording as the originating performer browser. Multiple engines may diverge. Failed acceptance: one authoritative production.
- **Decision:** retain as the offline fallback ONLY. Not sufficient as the canonical video solution.

## Solution B — Server-side authoritative rerender
Have a headless browser, WebGL renderer or separate 3D graphics worker rebuild each camera server-side and capture from that.
- **Works for:** an always-on centralized multi-camera broadcast with server-controlled recording; no originating performer browser required once the world state is replicated.
- **Strengths:** excellent central output authority and centralized persistence.
- **Weaknesses:** duplicates the existing Three.js/GLB stage renderer and animation state; considerable GPU/CPU and deployment weight; hard to keep live characters, poses and EQ/prosody in lockstep. Especially poor for modest hardware/offline-first owner use.
- **Decision:** reject as the first release path; consider only as a later dedicated-render-farm option.

## Solution C — Browser-originated authoritative video, existing server switcher
The performing 2.5D browser renders genuine Program and Preview canvases, sends viewable media to the server, and keeps full-resolution audio/video capture connected to the canonical recording/Blackbox pathway. The existing `CameraManager` remains the selection/control authority.
- **Works for:** one visual truth at the source, shared Program/Preview controls, genuine remote confidence monitoring and a progressive path to full-rate media ingest without rebuilding the stage.
- **Strengths:** reuses existing avatar/animation code; avoids a second render engine; keeps local production possible offline; scalable by replacing the transport, not production geometry.
- **Weaknesses:** requires an actual encoded video transport, access control, frame timing, failure recovery, and ingest/recording bridge. Browser-origin JPEG confidence is NOT full broadcast video. Media transport needs testing and eventual higher-rate WebRTC/NDI/RTMP path.

### Selected combination: C + local fallback from A
**Implemented as an initial, testable slice:** The stage publishes real downscaled 640×360 JPEG confidence frames (approximately 4 Hz per camera, capped by bandwidth/time) to a bounded, authenticated FastAPI media endpoint. The existing Director Switcher reads/decodes those frames and displays them as actual remote images; stale/missing frames show an explicit failure. Program/Preview selection stays on the SAME canonical switcher. The local browser keeps full 1280×720 MediaRecorder capture and established program-audio bus routing.

### Why this is a legitimate selection
It is the least invasive implementation that immediately replaces *camera IDs without media* with actual transmitted frames. It preserves genuine 3D performers and avoids introducing another production renderer. It establishes a source ownership, permissions, lifecycle, and media transport seam suitable for a later transport upgrade.

### Critical limits — do NOT call complete
- A JPEG confidence feed is deliberately lower rate/quality than production video and not synchronized broadcast video transport.
- Actual full-framerate server ingest/recording and remotely playable Blackbox video still require implementation and runtime proof.
- Server-side recording of the browser's full-resolution program media remains a release acceptance gate.
- Audio from other browser clients is NOT currently combined into the originating browser's recorder; that is not a solved media mix.
- Performance on modest phones and full browser operation have not been measured.
- Current source registry may retain stale genre cameras after stop; flags and later cleanup must not remove other operators' active sources.
- Existing Control Room final imagery, decorative knobs and creative effect mappings remain owner-dependent.

## Upgrade path / next engineering decision
Keep the camera registry and event contract. Upgrade confidence JPEG transport to a WebRTC track publisher + server media ingress (or compatible ingest gateway), with server-side recording and synchronized audio. Use separate selectable per-camera media tracks when actually produced by the originating browser; do not infer streams from registry IDs. Retain local MediaRecorder as an offline fallback and recovery export. Measure latency and device load before selecting codecs.

## Acceptance tests for the chosen architecture
1. Authenticate as a moderator and register a real 2.5D camera pair.
2. Stage genuinely renders a moving GLB performer from multiple perspectives.
3. Stage uploads decodable JPEG frames; remote Director monitors display them, not fake previews.
4. Camera selection, CUT and dissolve are reflected consistently in server state and stage output.
5. Competing publisher, stale, oversized, unauthenticated or malformed frames are rejected.
6. Stop cleans camera media; late uploads cannot revive a stopped session.
7. Local full-res recording captures the actual Program plus routed program audio and optional mic, saves a retrievable manifest, plays back after reload.
8. Full-rate server ingest, multi-client audio, Blackbox artifacts, latency and long-running stress testing remain explicitly separate, unpassed gates.

## Engineering quality rule
When an implementation meets only a subsection, document that subsection as verified and keep the remaining gates open. Never promote a confidence monitor to a commercial broadcast pipeline by renaming it.
