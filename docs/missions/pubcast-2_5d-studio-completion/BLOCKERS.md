# Blockers and deferred work

- Browser runtime verification: no browser execution has yet been performed against this branch. **Not a claim that browser execution is impossible**; next action is to attempt it with available runtime or have owner verify. Do not mark passed.
- Full legacy Control Room integration: mapping and connections remain unverified. Next action: inspect existing station interfaces and backend routes, identify common command contract.
- Owner photographs and final set artwork: intentionally deferred; placeholder layers and configuration must remain replaceable.

Two-minute stall rule: record actual attempts/errors here; avoid repeated unchanged retries. Resolve entries when evidence changes.

## Current known limitations of shared switching
- Shared switcher controls 2.5D source selection through backend, but the browser renderer's pixels are not transported back into the server switcher's network video output. Must design and verify media ingest before calling remote multi-client broadcast complete.
- Registration of per-genre sources currently persists in CameraManager after a 2.5D production ends; cleanup must be safe for other active operators. Do not blindly reset global Program/Preview when stopping.
- Audio master and bus state now share the backend; media output from a DIFFERENT BROWSER PAGE is not automatically captured by the 2.5D local recorder. Cross-client audio ingest remains to be engineered and tested.
- Live browser and FastAPI verification remain unperformed. Local clone attempt blocked by DNS earlier; no executed pytest or Node test suite yet. Isolated source/module mock checks are documented separately.

## Three-round continuation blockers and facts
1. **No local clone:** Container DNS could not resolve github.com/raw.githubusercontent.com. Connected GitHub connector can fetch/edit source, but cannot provide a mounted complete checkout. Node and Python suites have NOT been run as true repository commands.
2. **CI jobs opaque:** Workflow run returned failure with no step details; logs returned BlobNotFound. Stop repeated unproductive retries unless new runner evidence appears.
3. **Broadcast ingest:** Real JPEG confidence snapshots now reach authenticated server and remote Director surface *by implementation*, but this is low-rate preview only. No complete synchronized high-rate multi-camera recording/Blackbox video. Domain recording guard explicitly refuses 2.5D virtual confidence sources.
4. **Cross-browser audio:** Existing program audio bus state shared; actual media from a different browser is not mixed into the originating browser's video recorder. Needs separate transport/test.
5. **Runtime/performance:** No full browser/phone trial yet, no actual MediaRecorder persisted WebM playback, no GLB offscreen renderer stress measurements.
6. **Camera registration lifetime:** Genre sources may remain registered after studio closes; do not unregister other operators' active cameras without ownership arbitration.
7. **Owner artwork:** Pending, *nonblocking*. Keep placeholders and final switcher layout replaceable.


## Post-production / professional-quality export release blockers — 2026-10-30
- **HARD:** The 2.5D production source is not yet a deterministic, machine-portable, fully asset-backed replay master. A browser preview WebM and event JSON are insufficient for reconstructing arbitrary camera coverage at higher fidelity.
- **HARD:** No verified native 4K/high-fidelity selected-frame renderer with independent audio and source-level material/animation fidelity. Exporting original existing WebM bytes honestly is useful but is NOT the promised high-quality cinema-master path.
- **HARD:** A CMX3600 EDL and .pubcast-handoff.json are implemented but have not been imported/relinked in actual Resolve Free on an independent computer. Current interchange is intentionally lossy for multitrack audio and subframe sync.
- **HARD:** Clacker reference/offset core exists, but actual camera/audio/blip recording and automatic sync marks from all clients are not yet verified. The 15-second red dash/independent blip path is still absent from full production capture.
- **ENGINEERING:** Browser editor controls, local-file persistence, relink, download and timing playback need real runtime acceptance. 12/12 isolated script checks are not a substitute.
- **ENGINEERING:** The existing local browser/proxy storage does not yet provide a single portable all-source export bundle, independent hashes/asset licensing, or cross-machine restoration.
- Acceptance contract: `EDITOR_AND_FINISHING_BOUNDARY.md`. None of these blockers are cleared merely by adding UI labels or metadata.
