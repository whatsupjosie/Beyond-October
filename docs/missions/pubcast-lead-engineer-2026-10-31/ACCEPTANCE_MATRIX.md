# Acceptance matrix — Control Room + 2.5D Television Studio
**Date:** 2026-10-31 · **Revision:** 1 · **State:** UNSEALED

This is not a list of aspirations. A row is complete only with:
- executable command and observed exit status;
- dated log/test artifact or screenshot/recording and where it can be read;
- source commit SHA;
- negative-path checks for a consequential control;
- explicit owner verification if a gate depends on owner aesthetics or hardware.

Use: `NOT STARTED`, `CODE PRESENT / RUNTIME UNVERIFIED`,
`FAIL WITH REPRO`, `VERIFIED IN EXECUTED ENVIRONMENT`,
`OWNER APPROVED`. Never use “green” for source inspection alone.

| ID | Acceptance gate / exact observation | Starting status 10/31 | Next proof |
|---|---|---|---|
| G00 | Environment: bootstrap pinned requirements, launch main.py, no hidden dependency downloads, explicit startup log | NOT STARTED | real install and health |
| G01 | Authentication and operator roles: director/mod/guest enforced on camera/audio/recording and media | CODE PRESENT / RUNTIME UNVERIFIED | real HTTP positive/negative permissions |
| G02 | 2.5D page opens on phone and laptop without script errors | CODE PRESENT / RUNTIME UNVERIFIED | browser console/network inspection |
| G03 | Eight unique stage genre packages load with distinct usable sets and real camera angles | CODE PRESENT / RUNTIME UNVERIFIED | screenshots/video of each real scene |
| G04 | GLB avatar actual walk/gesture/animation, reliable repeated teardown, depth/occlusion, 2.5D blocking | CODE PRESENT / RUNTIME UNVERIFIED | multi-genre browser run |
| G05 | Shared one Program/Preview CameraManager used by TV and walkable studio, true atomic CUT and dissolve | CODE PRESENT / RUNTIME UNVERIFIED | two simultaneous real clients + server state |
| G06 | Director displays actual remote camera frames with freshness/staleness and no invented LIVE imagery | CODE PRESENT / RUNTIME UNVERIFIED | real frame transport acceptance |
| G07 | Production-grade broadcast-rate video ingest and multiple independent camera feeds beyond JPEG confidence | NOT STARTED | media stream transport + replay/record |
| G08 | Shared authoritative program-audio mixer plus real cross-client media and solo/mute/gain | CODE PRESENT / RUNTIME UNVERIFIED | synchronized recorded audio |
| G09 | Audio/video switching keyboard controls do not operate live stage while editor is focused | CODE PRESENT / RUNTIME UNVERIFIED | browser keyboard regression |
| G10 | Director stations: teleprompter, VTR, camera rig, graphic/chyron, recording, joystick and stable operator actions | PARTLY CODE PRESENT / RUNTIME UNVERIFIED | station-by-station accepted test |
| G11 | Real recording button starts capture and indicates success only upon file writing | PARTLY CODE PRESENT / RUNTIME UNVERIFIED | inspect created media |
| G12 | PANIC stops active captures, silences actual audio, cues black output, logs partial failure | CODE PRESENT / RUNTIME UNVERIFIED | trigger during active session |
| G13 | Production persists after stop/restart and media is playable, accessible in project browser | CODE PRESENT / RUNTIME UNVERIFIED | reopen after process/browser restart |
| G14 | Blackbox receives actual audio/video/performance/telemetry/manifest, not just markers | NOT STARTED | recorded manifest with checksums |
| G15 | Separate 15-second clacker reference: video red dash, dedicated blip audio, same timeline across sources | PARTLY CORE CODE / RECORDING UNVERIFIED | timestamp measurement and playback |
| G16 | Per-track +0.030s offset persists across reload; 24/25/30 fps EDL and exact sidecar map correctly | ISOLATED V8 TESTS ONLY | actual editor and Resolve import |
| G17 | Basic shoot editor: media bin, viewer, rough selects, split, lift, ripple, close gaps, save/reopen | CODE PRESENT / RUNTIME UNVERIFIED | real browser smoke |
| G18 | Proxy footage and authoritative replayable master separate, camera coverage preserved for later editorial decision | NOT STARTED | full independent source bundle |
| G19 | Deterministic source-level scene replay: performer, camera, lights, graphics, media and dependencies | NOT STARTED | re-render same frame twice after restart |
| G20 | Render only chosen camera/time ranges at genuine native 4K high fidelity (not upscaled proxy) | NOT STARTED | inspect frames and native resolution |
| G21 | Professional media package: separate audio, usable image/video masters, manifests/hashes, nonproprietary relinking on different computer | NOT STARTED | round trip to independent machine |
| G22 | DaVinci Resolve Free takes a supported cut/footage path; source masters unmodified and editor metadata portable | CODE PRESENT / IMPORT UNVERIFIED | actual Resolve cut/relink |
| G23 | All significant shortcut audits/repros corrected, three debug rounds and performance profile on modest device | NOT STARTED | dated performance/test artifacts |
| G24 | Walkable Bella Faux Pas experience not regressed by 2.5D/Control Room work | USER SAW HISTORICAL DEMO; CURRENT BRANCH UNVERIFIED | smoke test old and new |
| G25 | No owner input except specific visuals, artistic decisions, credentials and live hardware genuinely needed | ACCEPTANCE POLICY | record owner-only issues |
| G26 | Final owner acceptance and explicit seal approval | NOT REQUESTED | owner review after G00–G25 |

## Practical test commands to attempt, not to claim already run
```sh
python -m pip install -r requirements.txt
python -m pytest -q tests/test_shared_studio_switchers.py tests/test_studio25d_media_routes.py tests/test_studio25d_recording_guard.py
node --test tests/test_production25d_core.cjs tests/test_production25d_wiring.cjs tests/test_production25d_switcher_bridge.cjs tests/test_studio25d_confidence.cjs tests/test_editor_sync_interchange.cjs
python main.py
```
Adjust only after inspecting the actual repo's commands/dependencies and
security setup; never run destructive install or network access silently.

## Previous evidence (scoped)
The October 30 branch reported isolated V8 module/DOM checks, 12/12
isolated mocked studio behavior checks, 12/12 isolated editor logic tests,
and a synthetic editor UI run. The Python pytest, actual browser camera
transmission, cross-client audio, full recording and Resolve import were
**not** verified. CI failed before showing usable job steps/logs; no
executed CI result is available. Those scoped observations are historical,
not pass marks for this matrix.

## Defect priority
P0: data loss/security/media falsely marked saved; source-master corruption.
P1: unusable camera/audio control, incorrect routing, authentication failure,
    capture/stop/panic failure, cross-client desync, startup failure.
P2: broken genre shot/animations/UI or editor handoff.
P3: final surface/art and minor cosmetics.
Fix highest-priority reproducible issues first while preserving all work.

## October 31 executed update — source `73ca8bba3acad765c5388ce5b8e56fe37d093a82`

The starting column above is historical. This update is scoped to Linux Chromium
141/SwiftShader and the exact source tree recorded in `RUNTIME_REPORT.md`. Final
whole-suite results are under `evidence/2026-10-31/README.md`.

| Gate | Observed execution | Remaining boundary |
|---|---|---|
| G00 | VERIFIED IN EXECUTED ENVIRONMENT: dependency installation, real server startup/health and dependency consistency | Other operating systems/hardware |
| G01 | Real owner setup, authenticated two-page camera control and denied anonymous CUT/media; lease/role negative tests | Every station/role and external media boundary still needs full acceptance |
| G02 | VERIFIED IN EXECUTED ENVIRONMENT: all genres, no page errors, 1440×1000 and 390×844 layouts | Physical phone/browser diversity and performance |
| G03 | Eight actual rendered packages with loaded GLB actors and distinct Program/Preview pixels; screenshots retained | Final set art and detailed creative/shot-quality review |
| G04 | Actual Wave rig pixels, bundled walking bodies, repeated genre loading and walker teardown regressions pass | Full staging/occlusion/motion coverage on target devices |
| G05 | Actual CUT across studio and Director pages plus canonical atomic-switch tests | Real-browser dissolve and all world/source combinations |
| G06 | VERIFIED IN EXECUTED ENVIRONMENT: actual decoded remote frames and loss after source stop | Confidence transport remains deliberately low-rate |
| G07 | NOT STARTED / OPEN: no production-rate encoded ingest implemented by this pass | Genuine transport and independent camera coverage |
| G08 | Shared mixer state tested; PANIC silences a real measured signal through the browser mixer | Cross-client audio media and separate track recording |
| G09 | Executed Node keyboard/editor invariants pass | Complete browser editor/live-focus interaction |
| G10 | Storage station now reports measured space and honest cloud/backup state | Remaining stations require individual runtime acceptance |
| G11 | Actual local MediaRecorder/IndexedDB, multiple takes, quota recovery and partial-error preservation | Server ingest/Blackbox capture and durable in-progress recording recovery |
| G12 | VERIFIED IN EXECUTED ENVIRONMENT for browser Program: remote PANIC stops real recording, blacks pixels, zeros measured program output, preserves take and status | Physical devices, network partitions and other capture transports |
| G13 | Local recording plays after reload; server metadata restores in a fresh service; interrupted captures identified | Full shoot master recovery across devices/processes |
| G14 | OPEN: full Blackbox shoot media/performance integration absent | Marker/witness events alone do not pass |
| G15 | OPEN: real synchronized blip/video path not implemented | Cross-source recording measurements |
| G16 | Actual Node clacker/offset/EDL tests pass | Real editor playback and Resolve/import round trip |
| G17 | Source remains present; no new claim of full browser editor acceptance | Full rough-cut workflow |
| G18–G20 | OPEN: no asset-complete deterministic replay master or native selected 4K renderer | Source package and replay/render implementation |
| G21 | Actual existing-recording source-byte export, hashes, collision-safe packaging, separate conversions and fresh-tree relink pass | Full multi-source shoot, independent audio, high-quality render elements and second physical machine |
| G22 | Original media preservation improved; no actual Resolve run | Independent finishing import/relink |
| G23 | Reproduced defects, adversarial failure injection and broad regression executed | Modest physical device profile and complete release audit |
| G24 | Actual walker GLB/host tests and Counter integration regressions pass | Physical multi-client/device soak |
| G25 | No owner input was needed to execute these repairs | Owner-only final assets/hardware/release decisions remain |
| G26 | NOT REQUESTED / UNSEALED | Explicit owner acceptance after release gates |

No partial row is promoted to complete merely because its tested subsection passed.

Final isolated editor correction: source `4f6c5d3f48eb0b4d157f8947eaea1a51d7a8f610`.
The whole run on the preceding implementation had 2,166 passes and one diagnostic
UI race. After repairing it, all 14 affected browser tests and three file Node
cases pass. The whole suite was not repeated once more; its saved failure remains
in the evidence log. This does not change the open production release gates.
