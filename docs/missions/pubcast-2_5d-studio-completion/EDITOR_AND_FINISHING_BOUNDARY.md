# PubCast production-to-finishing boundary and release-quality gate

Owner's existing hard boundary, reaffirmed 2026-10-30:
**PubCast is not a professional finishing program. PubCast must, however,
preserve and export everything needed for the user to pursue a professional,
theater-worthy finish on a capable separate computer.**
Do not conflate "not finishing software" with "low-resolution output allowed."

## Product boundary
- PubCast: virtual sets, characters, actual shoots, replayable performances,
  authoritative camera and audio state, clacker sync, proxy viewing, camera
  coverage and rough-cut assembly, selected high-fidelity rendering and export.
- Finisher: advanced edit, color, compositing, VFX, final audio mastering,
  delivery packaging. Recommend DaVinci Resolve Free as the accessible
  starting point, but don't claim endorsement, sponsor status or guaranteed
  compatibility. Preserve alternative finishing destinations.
- UI: follow conventional NLE transport / Cut/Edit muscle memory, with original
  lightweight controls and branding. Do not mirror Resolve's visual design,
  icons or copyrighted artwork. Compact video bin, playback, trim, split, lift,
  ripple-delete, gaps, clacker timing corrections and selected-shot list only.

## Three independent media deliverables
1. **SOURCE PRODUCTION PACKAGE**: immutable/unmodified available recorded
   media bytes, actual per-track audio recordings, original virtual scene GLB
   meshes/materials/textures, asset dependencies and licenses, performers' full
   time-varying state, camera intrinsics/positions, lighting, cue timeline,
   sync marks, clocks, and an integrity manifest. Source master must be
   reconstructable without the original device's browser IndexedDB.
2. **EDITORIAL TRANSFER**: synchronized user-selected camera coverage, scene
   ranges, one-frame-rate/timecode-declared basic EDL or another validated
   interchange, and accurate sidecar preserving exact integer-microsecond
   shifts, clock drift, clacker marks and independent audio tracks. Export is
   non-destructive. A simple CMX EDL is only an approximate cut transfer;
   it is not a complete multicam / subframe / audio interchange by itself.
3. **RENDERED HIGH-QUALITY ELEMENTS**: true, configurable native render output
   of selected frames and practical handles. Independent resolution, sample
   quality, bit depth, color space, alpha and compositing pass controls. Images
   must derive from actual original scene data; never upscale a 720p proxy
   and label it a 4K render. Include verified separate audio in a conventional
   production format. Ensure selected render clips can leave PubCast entirely.

## Mandatory tests before claiming the quality promise fulfilled
- 30-minute multicam shoot: preserve every source and clacker for later angle
  decisions; save a rough cut, close the application and resume a week later.
- Select two alternative angles covering the same time range; export only
  those, not five full-time redundant camera videos.
- Include the user's example of advancing one track **+0.030 seconds**;
  verify playback and exported sidecar are consistent at 24/25/30 fps.
- Check 15-second clacker alignment of multiple recordings plus an audio blip
  and red timecode marker. **Current code has only marker/clock data structures;
  it does not yet demonstrate real synchronized sound transport/capture.**
- Render from **source-level scene state** at quality above live preview;
  measure and inspect output native dimensions, fidelity, color/alpha,
  animation determinism and sound alignment; no interpolation masquerading
  as new original detail.
- Move *all* needed media and project metadata to another device with no
  copy of the current browser's IndexedDB; import a representative cut in
  DaVinci Resolve Free or another chosen professional tool. Verify linked
  original media, cuts and timecodes; manually review subframe audio corrections
  where the selected interchange format lacks support.
- Validate full lossless source-byte export by hash and round-trip copy.
- Use actual browser + FastAPI end-to-end integration, not only mock unit tests.
  Verify against free-finisher supported resolution, codec and bit-depth limits
  separately from PubCast's lossless/high-quality source master capability.

## Verified branch-level work vs missing fundamentals — 2026-10-30
**Present in the integration branch, not yet browser/finisher validated:**
- Standalone non-destructive microsecond clacker/offset core.
- Offline IndexedDB shoot projects, proxy import and simple rough-cut control
  station (transport, trims, gap, split, lift, ripple, reordering).
- Manifest with explicit original-quality provenance warnings.
- CMX3600 non-drop 24/25/30 fps cuts export plus complete JSON sidecar.
- Browser download of selected available media bytes unchanged.
- Local 2.5D MediaRecorder output (1280×720, nominal 3Mbps), **preview-level,
  not a professional high-quality production master**.
- Authenticated low-rate JPEG Director confidence feed: **not broadcast ingest**.

**Not complete; not to be represented as complete:**
- Replayable deterministic full-resolution virtual production master with all
  GLB/scene/dependency/media state and stable timestamps.
- High-fidelity native frame renderer and professional image/alpha passes.
- Production clacker/blip on independent audio tracks and a proven sync capture
  path for all clients.
- Full cross-browser audio/media transport and Blackbox footage integration.
- Portable multi-source media package, hashes/relink, full machine-independent
  recovery.
- On-device editor smoke test, real frame rendering quality test, actual
  DaVinci Resolve EDL import/relink verification, and free-edition 4K trial.

**Next critical path:** record/render a deterministic 2.5D session off the live
timeline with all source assets and sync intact, then prove that the same
selected frame(s) can be rendered at native 4K and reopened elsewhere. Until
then the professional-quality export promise remains **an explicit release
blocker**, not a shipped capability.
