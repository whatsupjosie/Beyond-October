# Engineering decisions

- Prioritize fixed/constrained camera 2.5D television production; preserve separate walkable world.
- Eight independent declarative show packages share one renderer and console.
- Use original procedural scenery as replaceable artwork; do not copy trademarked television sets.
- Reuse existing `world_walk_glb.js` GLB bridge; do not substitute flat character sprites.
- Browser-local MediaRecorder + IndexedDB is a standalone production slice; do not misrepresent as completed Blackbox/server integration.
- Keep work isolated in integration branch; do not merge without owner authorization.

## Shared switcher decision (owner, October 30)
- Both studio environments use the same canonical video switcher and program-audio mixer: do not make competing station implementations.
- 2.5D genre cameras register with the canonical CameraManager under `p25d_<genre>_<shot>` IDs. Existing Control Room switcher can then select them. The browser publishes real low-rate JPEG confidence frames to an authenticated server media plane; it is not full-rate broadcast video ingest.
- If canonical backend/auth is unavailable, show explicitly LOCAL ONLY, not fake synchronized state. Do not override the backend state after a failed switch.
- Shared audio uses existing ProgramAudioState, including one new master_volume scalar, existing dialogue/music/SFX/etc buses, and a program capture output; local mic can join recorder without creating duplicate playback buses.
- Owner supplies video switcher artwork/reference later; it is not a blocker to wiring.

## Three-solutions decision — accepted implementation direction
- A: each browser rerenders scene: valid offline fallback, but not canonical remote media truth.
- B: server reconstructs entire GLB/WebGL stage: viable with dedicated hardware but duplicates renderer, expensive/unnecessary for first beta.
- C: browser originating genuine rendered video, sharing CameraManager/Control Room and a media transport: selected. The now-added bounded authenticated JPEG confidence endpoint, publisher and remote monitor are a **first slice only**, not a broadcast media transport/Blackbox replacement.
- Camera controls must use canonical CameraManager.take() for atomic CUT everywhere; stage opens via checked pair selection. Audio uses same ProgramAudioState and program runtime, not another mixer.
- Final switcher image and set art remain owner-dependent, not core engineering blockers. Three-solution comparison in THREE_SOLUTIONS_PIVOT.md.
